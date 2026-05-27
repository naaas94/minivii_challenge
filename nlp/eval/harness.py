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
    tier_summary: dict[str, str]


TEST_CASES = [
    TestCase(
        question="What is the most bought product on Fridays?",
        expected_class="aggregation",
        expected_clauses=["week_day", "friday", "sum(quantity)", "group by"],
        forbidden_clauses=["sum(total)"],
        known_answer="Alfajor Sin Azucar Suelto (850 units)",
    ),
    # F8: "how many" → AGGREGATION, but "on saturday" matches TIME_FILTER first in KEYWORD_CLASS_MAP iteration.
    TestCase(
        question="How many transactions happened on Saturdays?",
        expected_class="time_filter",
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
    # F8: keyword heuristic maps "how many" to AGGREGATION (no day-of-week keyword in question).
    TestCase(
        question="How many transactions were there in November?",
        expected_class="aggregation",
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


def check_class_match(pipeline_query_class: str, case: TestCase) -> bool:
    if not case.expected_class:
        return True
    return pipeline_query_class == case.expected_class


def check_ambiguity(case_num: int, pipeline_result) -> bool:
    """Cases 10–11 (1-based): ResolvedQuestion / interpretations gate (TA2 F6)."""
    if case_num == 10:
        return bool(pipeline_result.interpretations)
    if case_num == 11:
        return pipeline_result.resolved_question != pipeline_result.question
    return True


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
            case_num = i + 1
            try:
                pipeline_result = self.pipeline.run(case.question)
                sql_score = self.check_sql_structure(pipeline_result.sql, case)
                class_pass = check_class_match(pipeline_result.query_class, case)
                ambiguity_pass = check_ambiguity(case_num, pipeline_result)
                execution_pass = pipeline_result.execution.success
                case_pass = (
                    sql_score["pass"]
                    and class_pass
                    and ambiguity_pass
                    and execution_pass
                )
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
                    "expected_class": case.expected_class,
                    "sql_pass": sql_score["pass"],
                    "class_pass": class_pass,
                    "ambiguity_pass": ambiguity_pass,
                    "execution_pass": execution_pass,
                    "case_pass": case_pass,
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
                    "class_pass": False,
                    "ambiguity_pass": False,
                    "execution_pass": False,
                    "case_pass": False,
                }
            results.append(result_entry)
            print(
                f"[{i + 1}/{total}] "
                f"{'PASS' if result_entry.get('case_pass') else 'FAIL'} "
                f"(sql={result_entry.get('sql_pass')}, class={result_entry.get('class_pass')}, "
                f"amb={result_entry.get('ambiguity_pass')}, "
                f"exec={result_entry.get('execution_pass')}): "
                f"{case.question[:60]}"
            )
        sql_passes = sum(1 for r in results if r.get("sql_pass"))
        class_passes = sum(1 for r in results if r.get("class_pass"))
        structural_passes = sum(
            1
            for r in results
            if r.get("sql_pass") and r.get("class_pass") and r.get("ambiguity_pass")
        )
        execution_passes = sum(1 for r in results if r.get("execution_pass"))
        case_passes = sum(1 for r in results if r.get("case_pass"))
        tier_summary = {
            "structural": f"{structural_passes}/{total}",
            "execution": f"{execution_passes}/{total}",
            "composite": f"{case_passes}/{total}",
        }
        print(
            f"Summary: composite {case_passes}/{total} | "
            f"structural {structural_passes}/{total} | execution {execution_passes}/{total} | "
            f"SQL {sql_passes}/{total} | class {class_passes}/{total}"
        )
        report = EvalReport(results=results, tier_summary=tier_summary)
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
