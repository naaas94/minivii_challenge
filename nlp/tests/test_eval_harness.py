"""TA2 eval assertions: class_pass, ambiguity_pass, cases 2/8 expected_class."""

from unittest.mock import MagicMock

from eval.harness import (
    TEST_CASES,
    EvalHarness,
    TestCase,
    check_ambiguity,
    check_class_match,
)
from pipeline.llm_client import LLMClient
from pipeline.pipeline import Pipeline
from pipeline.sql_executor import ExecutionResult


def test_cases_2_and_8_expected_class_matches_keyword_heuristic():
    assert TEST_CASES[1].expected_class == "time_filter"
    assert TEST_CASES[7].expected_class == "aggregation"


def test_check_class_match():
    case = TestCase("q", "aggregation", [], [])
    assert check_class_match("aggregation", case) is True
    assert check_class_match("simple", case) is False


def test_check_ambiguity_case_10_and_11():
    result_10 = MagicMock(
        question="Show me the most popular product",
        resolved_question="Show me the most popular product — x",
        interpretations=["axis: rule"],
    )
    result_11 = MagicMock(
        question="What were the recent sales?",
        resolved_question="What were the recent sales? — y",
        interpretations=["recent: window"],
    )
    assert check_ambiguity(10, result_10) is True
    assert check_ambiguity(11, result_11) is True
    assert check_ambiguity(10, MagicMock(interpretations=[])) is False


def test_run_eval_case_pass_requires_class_and_sql(tmp_path):
    pipeline = MagicMock(spec=Pipeline)
    pipeline.run.return_value = MagicMock(
        sql="SELECT count(*) FROM sales",
        query_class="wrong_class",
        question="q",
        resolved_question="q",
        interpretations=[],
        total_latency_ms=1,
        narrative=None,
        execution=ExecutionResult(success=True, data=[], steps_taken=1),
    )
    llm = MagicMock(spec=LLMClient)
    harness = EvalHarness(pipeline, llm, "qwen3:32b", log_dir=tmp_path)
    case = TestCase("q", "aggregation", ["select"], [])

    report = harness.run_eval([case], skip_judge=True)

    row = report.results[0]
    assert row["sql_pass"] is True
    assert row["class_pass"] is False
    assert row["execution_pass"] is True
    assert row["case_pass"] is False


def test_execution_pass_false_when_execution_fails(tmp_path):
    pipeline = MagicMock(spec=Pipeline)
    pipeline.run.return_value = MagicMock(
        sql="SELECT date FROM sales WHERE date >= '2024-10-01'",
        query_class="time_filter",
        question="What were the recent sales?",
        resolved_question="What were the recent sales? — recent window",
        interpretations=["recent: window"],
        total_latency_ms=1,
        narrative=None,
        execution=ExecutionResult(
            success=False,
            data=[],
            steps_taken=4,
            failure_reason="max steps reached without successful result",
        ),
    )
    llm = MagicMock(spec=LLMClient)
    harness = EvalHarness(pipeline, llm, "qwen3:32b", log_dir=tmp_path)
    case = TestCase(
        "What were the recent sales?",
        "time_filter",
        ["where", "date"],
        [],
    )

    report = harness.run_eval([case], skip_judge=True)

    row = report.results[0]
    assert row["sql_pass"] is True
    assert row["class_pass"] is True
    assert row["ambiguity_pass"] is True
    assert row["execution_pass"] is False
    assert row["case_pass"] is False


def test_run_eval_case_11_mock_case_pass_false(tmp_path):
    """Case 11 (recent sales): structural gates pass but execution fails."""
    pipeline = MagicMock(spec=Pipeline)
    pipeline.run.return_value = MagicMock(
        sql="SELECT * FROM sales WHERE date >= '2024-10-01'",
        query_class="time_filter",
        question=TEST_CASES[10].question,
        resolved_question=f"{TEST_CASES[10].question} — anchored",
        interpretations=["recent: window"],
        total_latency_ms=1,
        narrative=None,
        execution=ExecutionResult(
            success=False,
            data=[],
            steps_taken=4,
            failure_reason="max steps reached without successful result",
        ),
    )
    llm = MagicMock(spec=LLMClient)
    harness = EvalHarness(pipeline, llm, "qwen3:32b", log_dir=tmp_path)

    report = harness.run_eval([TEST_CASES[10]], skip_judge=True)

    row = report.results[0]
    assert row["sql_pass"] is True
    assert row["class_pass"] is True
    assert row["ambiguity_pass"] is True
    assert row["execution_pass"] is False
    assert row["case_pass"] is False
