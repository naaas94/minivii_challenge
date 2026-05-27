import re
from pathlib import Path

import yaml

from pipeline.ambiguity_detector import detect_and_resolve
from pipeline.semantic_layer import SemanticLayer


def _load_domain_descriptor() -> dict:
    yaml_path = Path(__file__).resolve().parent.parent / "schema" / "domain.yaml"
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_resolve_no_ambiguity():
    descriptor = _load_domain_descriptor()
    result = detect_and_resolve("How many sales on Monday?", descriptor)
    assert result.resolved == result.original
    assert result.interpretations_applied == []


def test_resolve_single_trigger():
    descriptor = _load_domain_descriptor()
    result = detect_and_resolve("What is the most popular product?", descriptor)
    assert "default to SUM(quantity) DESC" in result.resolved
    assert result.resolved.count("default to SUM(quantity) DESC") == 1
    assert "most bought / most popular product" in result.interpretations_applied[0]


def test_resolve_multi_trigger_composition():
    descriptor = _load_domain_descriptor()
    result = detect_and_resolve("top recent products", descriptor)
    assert "default to SUM(total) DESC" in result.resolved
    assert "default to last 30 days using date column" in result.resolved
    assert result.resolved.count(" — ") == 1
    assert len(result.interpretations_applied) == 2


def test_resolve_ambiguity():
    descriptor = _load_domain_descriptor()
    question = "top recent products"
    result = detect_and_resolve(question, descriptor)
    assert question in result.resolved
    assert "top recent products — " in result.resolved
    assert "recently" not in result.resolved.lower()


def test_get_date_anchor_returns_iso_strings():
    layer = SemanticLayer()
    start, end = layer.get_date_anchor()
    assert start == "2024-09-21"
    assert end == "2024-11-20"


def test_resolve_recent_uses_dataset_anchored_window():
    descriptor = _load_domain_descriptor()
    layer = SemanticLayer()
    result = detect_and_resolve("recent sales", descriptor, semantic_layer=layer)
    assert re.search(r"\d{4}-\d{2}-\d{2}", result.resolved)
    assert "date >= '2024-10-21' AND date <= '2024-11-20'" in result.resolved
    assert "default to last 30 days using date column" not in result.resolved
    assert any("date_anchor:" in entry for entry in result.interpretations_applied)
