from unittest.mock import MagicMock

from pipeline.llm_client import LLMClient
from pipeline.result_synthesizer import ResultSynthesizer
from pipeline.sql_executor import ExecutionResult


def test_synthesize_guard_skips_llm_on_failed_execution():
    llm = MagicMock(spec=LLMClient)
    synthesizer = ResultSynthesizer(llm, "qwen3:32b")

    result = synthesizer.synthesize(
        "How many tickets?",
        ExecutionResult(success=False, failure_reason="db unreachable"),
        [],
    )

    assert result is None
    llm.generate.assert_not_called()


def test_synthesize_guard_skips_llm_on_empty_data():
    llm = MagicMock(spec=LLMClient)
    synthesizer = ResultSynthesizer(llm, "qwen3:32b")

    result = synthesizer.synthesize(
        "How many tickets?",
        ExecutionResult(success=True, data=[]),
        [],
    )

    assert result is None
    llm.generate.assert_not_called()


def test_build_synthesis_prompt_truncates_to_ten_rows():
    llm = MagicMock(spec=LLMClient)
    synthesizer = ResultSynthesizer(llm, "qwen3:32b")
    data = [{"id": i, "value": i * 10} for i in range(15)]

    prompt = synthesizer._build_synthesis_prompt(
        question="Show all rows",
        data=data,
        sql="SELECT id, value FROM sales",
        interpretations_applied=[],
        steps_taken=1,
    )

    assert "first 10 of 15 rows" in prompt
    assert '"id": 14' not in prompt


def test_synthesize_uses_temperature_point_three():
    llm = MagicMock(spec=LLMClient)
    llm.generate.return_value = "Revenue increased."
    synthesizer = ResultSynthesizer(llm, "qwen3:32b")

    synthesizer.synthesize(
        "What is total revenue?",
        ExecutionResult(
            success=True,
            data=[{"total": 100}],
            sql="SELECT SUM(total) AS total FROM sales",
            steps_taken=1,
        ),
        ["rule applied"],
    )

    llm.generate.assert_called_once()
    assert llm.generate.call_args.kwargs["temperature"] == 0.3
