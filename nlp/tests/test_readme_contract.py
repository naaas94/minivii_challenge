"""README contract checks for T7 kill criteria (documentation-only slice)."""

from pathlib import Path

README = Path(__file__).resolve().parents[2] / "README.md"


def test_readme_exists():
    assert README.is_file(), "README.md must exist at repo root"


def test_first_run_download_size():
    text = README.read_text(encoding="utf-8")
    assert "~29 GB" in text
    assert "qwen2.5-coder:14b" in text
    assert "qwen3:32b" in text


def test_cpu_fallback_configuration():
    text = README.read_text(encoding="utf-8")
    assert "SQL_MODEL=qwen2.5-coder:7b" in text
    assert "SYNTHESIS_MODEL=qwen3:8b" in text


def test_data_range_not_one_year():
    text = README.read_text(encoding="utf-8").lower()
    assert "~1 year" not in text
    assert "60 days" in text
    assert "sep 21" in text
    assert "nov 20, 2024" in text


def test_eval_harness_final_pass_gate():
    text = README.read_text(encoding="utf-8")
    assert "final-pass gate, not a CI regression suite" in text
    assert "90–120 minutes on GPU" in text or "90-120 minutes on GPU" in text


def test_architecture_decision_table_covers_all_ten():
    text = README.read_text(encoding="utf-8")
    decisions = [
        "DIN-SQL stage decomposition",
        "CREATE TABLE over natural language schema",
        "Date normalization at ingestion",
        "ReAct over fixed retry",
        "Rule-based AmbiguityDetector",
        "Keyword heuristic QueryClassifier",
        "SQLite over Postgres",
        "Four containers over monolith",
        "Two-model strategy",
        "Structural few-shot examples",
    ]
    for decision in decisions:
        assert decision in text, f"Missing architecture decision: {decision}"


def test_eval_harness_run_command():
    text = README.read_text(encoding="utf-8")
    assert "docker compose exec nlp python -m eval.harness" in text
    assert "python -m nlp.eval.harness" in text


def test_first_run_not_documented_as_nine_gb_total():
    """Falsifier: total first-run download misstated as ~9 GB (spec C6)."""
    text = README.read_text(encoding="utf-8")
    assert "~29 GB" in text
    lower = text.lower()
    assert "first-run" in lower
    # Must not describe total first-run as ~9 GB without the ~29 GB correction
    assert lower.count("~9 gb") == 0 or "~29 gb" in lower
