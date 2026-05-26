from unittest.mock import MagicMock

from eval.harness import (
    TEST_CASES,
    EvalHarness,
    JudgeScore,
    TestCase,
    check_sql_structure,
    parse_json,
)
from pipeline.llm_client import LLMClient
from pipeline.pipeline import Pipeline
from pipeline.sql_executor import ExecutionResult


def test_check_sql_structure_substring_match():
    case = TestCase(
        question="q",
        expected_class="simple",
        expected_clauses=["week_day", "friday"],
        forbidden_clauses=["sum(total)"],
    )
    sql = "SELECT product_name FROM sales WHERE week_day = 'Friday' GROUP BY product_name"
    result = check_sql_structure(sql, case)
    assert result["pass"] is True


def test_check_sql_structure_fails_on_forbidden_clause():
    case = TestCase(
        question="q",
        expected_class="aggregation",
        expected_clauses=["sum(quantity)"],
        forbidden_clauses=["sum(total)"],
    )
    sql = "SELECT product_name, SUM(total) FROM sales GROUP BY product_name"
    result = check_sql_structure(sql, case)
    assert result["pass"] is False


def test_test_case_kill_criteria_clauses():
    case1 = TEST_CASES[0]
    assert "week_day" in case1.expected_clauses
    assert "friday" in case1.expected_clauses

    case4 = TEST_CASES[3]
    assert "2024-10" in case4.expected_clauses

    case6 = TEST_CASES[5]
    assert "strftime" in case6.expected_clauses
    assert "substr(" in case6.forbidden_clauses

    case10 = TEST_CASES[9]
    assert "sum(quantity)" in case10.expected_clauses
    assert "sum(total)" in case10.forbidden_clauses

    case11 = TEST_CASES[10]
    assert "where" in case11.expected_clauses
    assert "date" in case11.expected_clauses


def test_parse_json_extracts_object_from_fenced_response():
    payload = parse_json(
        'Here is the score:\n```json\n{"factual_accuracy": 4, "interpretation_fidelity": 5, "issues": null}\n```'
    )
    assert payload["factual_accuracy"] == 4
    assert payload["interpretation_fidelity"] == 5


def test_judge_synthesis_returns_none_when_narrative_missing():
    llm = MagicMock(spec=LLMClient)
    harness = EvalHarness(MagicMock(spec=Pipeline), llm, "qwen3:32b")
    assert harness.judge_synthesis("q", [{"a": 1}], None) is None
    llm.generate.assert_not_called()


def test_judge_synthesis_parse_fallback():
    llm = MagicMock(spec=LLMClient)
    llm.generate.return_value = "not valid json at all"
    harness = EvalHarness(MagicMock(spec=Pipeline), llm, "qwen3:32b")
    score = harness.judge_synthesis("q", [{"total": 1}], "Revenue was high.")
    assert score == JudgeScore(
        factual_accuracy=0,
        interpretation_fidelity=0,
        issues="parse_error",
    )


def test_run_eval_isolates_pipeline_failures(tmp_path):
    pipeline = MagicMock(spec=Pipeline)
    pipeline.run.side_effect = RuntimeError("pipeline exploded")
    llm = MagicMock(spec=LLMClient)
    harness = EvalHarness(pipeline, llm, "qwen3:32b", log_dir=tmp_path)
    cases = [
        TestCase("one", "simple", ["select"], []),
        TestCase("two", "simple", ["select"], []),
    ]

    report = harness.run_eval(cases, skip_judge=True)

    assert len(report.results) == 2
    assert all(r["sql_pass"] is False for r in report.results)
    assert all("error" in r for r in report.results)
    llm.generate.assert_not_called()
    assert list(tmp_path.glob("eval_*.json"))


def test_judge_synthesis_truncates_to_ten_rows():
    llm = MagicMock(spec=LLMClient)
    llm.generate.return_value = (
        '{"factual_accuracy": 5, "interpretation_fidelity": 5, "issues": null}'
    )
    harness = EvalHarness(MagicMock(spec=Pipeline), llm, "qwen3:32b")
    data = [{"id": i} for i in range(15)]
    harness.judge_synthesis("q", data, "Summary.")
    prompt = llm.generate.call_args.args[0]
    assert "'id': 9" in prompt
    assert "'id': 14" not in prompt


def test_run_eval_skips_judge_when_requested(tmp_path):
    pipeline = MagicMock(spec=Pipeline)
    pipeline.run.return_value = MagicMock(
        sql="SELECT 1",
        query_class="simple",
        total_latency_ms=10,
        narrative="A narrative.",
        execution=ExecutionResult(success=True, data=[{"x": 1}], steps_taken=1),
    )
    llm = MagicMock(spec=LLMClient)
    harness = EvalHarness(pipeline, llm, "qwen3:32b", log_dir=tmp_path)
    case = TestCase("q", "simple", ["select"], [])

    report = harness.run_eval([case], skip_judge=True)

    assert report.results[0]["judge"] is None
    llm.generate.assert_not_called()
