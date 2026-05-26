import argparse
import dataclasses
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_NLP_ROOT = Path(__file__).resolve().parent.parent
if str(_NLP_ROOT) not in sys.path:
    sys.path.insert(0, str(_NLP_ROOT))

from pipeline.llm_client import LLMClient
from pipeline.pipeline import Pipeline

LOG_DIR = _NLP_ROOT / "logs"


@dataclass
class TestCase:
    question: str
    expected_class: str
    expected_clauses: list[str]
    forbidden_clauses: list[str]
    known_answer: str | None = None


@dataclass
class JudgeScore:
    factual_accuracy: int
    interpretation_fidelity: int
    issues: str | None = None


@dataclass
class EvalReport:
    results: list[dict]


TEST_CASES = [
    TestCase(
        question="What is the most bought product on Fridays?",
        expected_class="aggregation",
        expected_clauses=["week_day", "friday", "sum(quantity)", "group by"],
        forbidden_clauses=["sum(total)"],
        known_answer="Alfajor Sin Azucar Suelto (850 units)",
    ),
    TestCase(
        question="How many transactions happened on Saturdays?",
        expected_class="simple",
        expected_clauses=["count(distinct ticket_number)", "saturday"],
        forbidden_clauses=[],
    ),
    TestCase(
        question="What are the busiest hours on weekdays?",
        expected_class="time_filter",
        expected_clauses=["hour", "count(distinct ticket_number)", "saturday", "sunday"],
        forbidden_clauses=[],
    ),
    TestCase(
        question="What is the total revenue for October 2024?",
        expected_class="aggregation",
        expected_clauses=["sum(total)", "2024-10"],
        forbidden_clauses=[],
        known_answer="~110,614,650 ARS",
    ),
    TestCase(
        question="Which waiter generated the most revenue?",
        expected_class="aggregation",
        expected_clauses=["waiter", "sum(total)", "group by"],
        forbidden_clauses=[],
    ),
    TestCase(
        question="What is the week-over-week revenue trend?",
        expected_class="window",
        expected_clauses=["strftime", "lag(", "group by"],
        forbidden_clauses=["substr("],
    ),
    TestCase(
        question="What are the top 5 products by revenue?",
        expected_class="aggregation",
        expected_clauses=["product_name", "sum(total)", "limit 5"],
        forbidden_clauses=[],
    ),
    TestCase(
        question="How many transactions were there in November?",
        expected_class="simple",
        expected_clauses=["count(distinct ticket_number)", "2024-11"],
        forbidden_clauses=[],
    ),
    TestCase(
        question="What is the average ticket value per waiter?",
        expected_class="aggregation",
        expected_clauses=["waiter", "count(distinct ticket_number)", "group by"],
        forbidden_clauses=[],
    ),
    TestCase(
        question="Show me the most popular product",
        expected_class="aggregation",
        expected_clauses=["sum(quantity)", "product_name", "group by", "order by", "desc"],
        forbidden_clauses=["sum(total)"],
        known_answer="Alfajor Sin Azucar Suelto",
    ),
    TestCase(
        question="What were the recent sales?",
        expected_class="time_filter",
        expected_clauses=["where", "date"],
        forbidden_clauses=[],
    ),
    TestCase(
        question="Which products have the most returns?",
        expected_class="aggregation",
        expected_clauses=["total < 0", "product_name", "group by"],
        forbidden_clauses=[],
    ),
]


def check_sql_structure(generated_sql: str, case: TestCase) -> dict:
    sql_lower = generated_sql.lower()
    passes = [c.lower() in sql_lower for c in case.expected_clauses]
    fails = [c.lower() in sql_lower for c in case.forbidden_clauses]
    return {
        "pass": all(passes) and not any(fails),
        "expected_present": list(zip(case.expected_clauses, passes)),
        "forbidden_present": list(zip(case.forbidden_clauses, fails)),
    }


def parse_json(response: str) -> dict:
    text = response.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise


class EvalHarness:
    def __init__(
        self,
        pipeline: Pipeline,
        llm_client: LLMClient,
        synthesis_model: str,
        log_dir: str | Path = LOG_DIR,
    ):
        self.pipeline = pipeline
        self.llm_client = llm_client
        self.synthesis_model = synthesis_model
        self.log_dir = Path(log_dir)

    def check_sql_structure(self, generated_sql: str, case: TestCase) -> dict:
        return check_sql_structure(generated_sql, case)

    def judge_synthesis(
        self,
        question: str,
        result_data: list[dict] | None,
        narrative: str | None,
    ) -> JudgeScore | None:
        if narrative is None:
            return None
        data = result_data or []
        sample = data[:10]
        summary = {
            "total_rows": len(data),
            "columns": list(data[0].keys()) if data else [],
        }
        prompt = f"""Evaluate whether this narrative faithfully represents the query result.

Question: {question}
Result summary: {summary}
Result sample (first {len(sample)} rows): {sample}
Narrative: {narrative}

Score on two dimensions (1–5 each):
1. Factual accuracy: do all numbers in the narrative appear correctly in the result data?
2. Interpretation fidelity: does the framing match the direction and magnitude of the data?

Respond with JSON only:
{{"factual_accuracy": <int>, "interpretation_fidelity": <int>, "issues": "<str or null>"}}"""
        response = self.llm_client.generate(prompt, model=self.synthesis_model)
        try:
            return JudgeScore(**parse_json(response))
        except Exception:
            return JudgeScore(
                factual_accuracy=0,
                interpretation_fidelity=0,
                issues="parse_error",
            )

    def run_eval(
        self,
        test_cases: list[TestCase],
        skip_judge: bool = False,
    ) -> EvalReport:
        results = []
        total = len(test_cases)
        for i, case in enumerate(test_cases):
            try:
                pipeline_result = self.pipeline.run(case.question)
                sql_score = self.check_sql_structure(pipeline_result.sql, case)
                judge_score = None
                if not skip_judge and pipeline_result.narrative:
                    judge_score = self.judge_synthesis(
                        case.question,
                        pipeline_result.execution.data,
                        pipeline_result.narrative,
                    )
                result_entry = {
                    "question": case.question,
                    "class": pipeline_result.query_class,
                    "sql_pass": sql_score["pass"],
                    "sql_detail": sql_score,
                    "judge": dataclasses.asdict(judge_score) if judge_score else None,
                    "latency_ms": pipeline_result.total_latency_ms,
                    "steps_taken": pipeline_result.execution.steps_taken,
                    "failure_reason": pipeline_result.execution.failure_reason,
                }
            except Exception as exc:
                result_entry = {
                    "question": case.question,
                    "error": str(exc),
                    "sql_pass": False,
                }
            results.append(result_entry)
            print(
                f"[{i + 1}/{total}] "
                f"{'PASS' if result_entry.get('sql_pass') else 'FAIL'}: "
                f"{case.question[:60]}"
            )
        report = EvalReport(results=results)
        self._write_report(report)
        return report

    def _write_report(self, report: EvalReport) -> Path:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        report_path = self.log_dir / f"eval_{timestamp}.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(dataclasses.asdict(report), f, indent=2)
        print(f"Report written to {report_path}")
        return report_path


def _build_pipeline() -> tuple[Pipeline, LLMClient, str]:
    db_url = os.environ.get("DB_URL", "http://db:8001")
    sql_model = os.environ.get("SQL_MODEL", "qwen2.5-coder:14b")
    synthesis_model = os.environ.get("SYNTHESIS_MODEL", "qwen3:32b")
    backend = os.environ.get("LLM_BACKEND", "ollama")
    llm_client = LLMClient(backend=backend, model=sql_model)
    pipeline = Pipeline(
        db_url=db_url,
        llm_client=llm_client,
        sql_model=sql_model,
        synthesis_model=synthesis_model,
    )
    return pipeline, llm_client, synthesis_model


def main() -> None:
    parser = argparse.ArgumentParser(description="Mini Nivii evaluation harness (final-pass gate)")
    parser.add_argument(
        "--skip-judge",
        action="store_true",
        help="Run structural SQL checks only (Phase 2 / Together.ai)",
    )
    args = parser.parse_args()
    pipeline, llm_client, synthesis_model = _build_pipeline()
    harness = EvalHarness(pipeline, llm_client, synthesis_model)
    harness.run_eval(TEST_CASES, skip_judge=args.skip_judge)


if __name__ == "__main__":
    main()
