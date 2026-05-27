from unittest.mock import MagicMock, patch

import httpx

from pipeline.llm_client import LLMClient
from pipeline.sql_executor import (
    Action,
    ExecutionResult,
    ObservationResult,
    SQLExecutor,
    build_refinement_prompt,
)


def test_observe_result_zero_rows_refines():
    executor = SQLExecutor(
        "http://db:8001",
        LLMClient(),
        "test-model",
        dataset_date_bounds=("2024-09-21", "2024-11-20"),
    )
    result = ExecutionResult(success=True, data=[])
    obs = executor._observe_result("How many sales?", "SELECT 1", result)
    assert obs.action == Action.REFINE
    assert "0 rows" in obs.message
    assert "date_range" in obs.message
    assert "2024-09-21" in obs.message
    assert "2024-11-20" in obs.message


def test_observe_result_accepts_small_scalar_result():
    executor = SQLExecutor("http://db:8001", LLMClient(), "test-model")
    result = ExecutionResult(success=True, data=[{"count": 5}])
    obs = executor._observe_result("How many tickets?", "SELECT COUNT(*) AS count FROM sales", result)
    assert obs.action == Action.ACCEPT


def test_observe_result_scalar_question_many_rows_refines():
    executor = SQLExecutor("http://db:8001", LLMClient(), "test-model")
    data = [{"id": i} for i in range(51)]
    result = ExecutionResult(success=True, data=data)
    obs = executor._observe_result("What is the total revenue?", "SELECT * FROM sales", result)
    assert obs.action == Action.REFINE


def test_build_refinement_prompt_is_full_spec_text():
    prompt = build_refinement_prompt(
        "SELECT 1",
        "Query returned 0 rows.",
        "CREATE TABLE sales (id INTEGER);",
        "How many tickets?",
    )
    assert "You are correcting a SQL query" in prompt
    assert "CREATE TABLE sales" in prompt
    assert "week_day values: Monday" in prompt
    assert len(prompt) > 200


@patch("pipeline.sql_executor.httpx.post")
def test_try_execute_parses_db_success(mock_post):
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "columns": ["product_name", "total_qty"],
            "rows": [["Alfajor", 10]],
            "row_count": 1,
        },
    )
    mock_post.return_value.raise_for_status = MagicMock()

    executor = SQLExecutor("http://db:8001", LLMClient(), "test-model")
    result = executor._try_execute("SELECT 1")

    assert result.success is True
    assert result.data == [{"product_name": "Alfajor", "total_qty": 10}]
    assert result.columns == ["product_name", "total_qty"]


@patch("pipeline.sql_executor.httpx.post")
def test_try_execute_parses_db_error(mock_post):
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"error": "no such column: foo", "sql": "SELECT foo"},
    )
    mock_post.return_value.raise_for_status = MagicMock()

    executor = SQLExecutor("http://db:8001", LLMClient(), "test-model")
    result = executor._try_execute("SELECT foo")

    assert result.success is False
    assert result.failure_reason == "no such column: foo"


@patch("pipeline.sql_executor.httpx.post", side_effect=httpx.ConnectError("connection refused"))
def test_try_execute_db_unreachable_returns_failure(_mock_post):
    executor = SQLExecutor("http://db:8001", LLMClient(), "test-model")
    result = executor._try_execute("SELECT 1")

    assert result.success is False
    assert "db unreachable" in (result.failure_reason or "")


def test_execute_react_default_max_steps_is_four():
    import inspect

    sig = inspect.signature(SQLExecutor.execute_react)
    assert sig.parameters["max_steps"].default == 4
