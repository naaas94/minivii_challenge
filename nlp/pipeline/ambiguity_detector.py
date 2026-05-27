from dataclasses import dataclass, field
from datetime import date, timedelta

from pipeline.semantic_layer import SemanticLayer

RECENT_AXIS = "recent without explicit time window"

AMBIGUITY_TRIGGERS: dict[str, str] = {
    "most": "most bought / most popular product",
    "popular": "most bought / most popular product",
    "top": "top N without explicit metric",
    "best": "top N without explicit metric",
    "recent": "recent without explicit time window",
    "latest": "recent without explicit time window",
    "busiest": "busiest / most active",
    "active": "busiest / most active",
    "last month": "last month / this month",
    "this month": "last month / this month",
}


@dataclass
class ResolvedQuestion:
    original: str
    resolved: str
    interpretations_applied: list[str] = field(default_factory=list)


def lookup_disambiguation_rule(axis: str, domain_descriptor: dict) -> dict | None:
    for rule in domain_descriptor.get("disambiguation_rules", []):
        if rule.get("when") == axis:
            return rule
    return None


def _anchored_recent_qualifier(semantic_layer: SemanticLayer) -> str:
    _start, end = semantic_layer.get_date_anchor()
    end_date = date.fromisoformat(end)
    window_start = (end_date - timedelta(days=30)).isoformat()
    return f"date >= '{window_start}' AND date <= '{end}'"


def detect_and_resolve(
    question: str,
    domain_descriptor: dict,
    semantic_layer: SemanticLayer | None = None,
) -> ResolvedQuestion:
    fired_axes: dict[str, dict] = {}

    for trigger, axis in AMBIGUITY_TRIGGERS.items():
        if trigger in question.lower() and axis not in fired_axes:
            rule = lookup_disambiguation_rule(axis, domain_descriptor)
            if rule:
                fired_axes[axis] = rule

    if not fired_axes:
        return ResolvedQuestion(original=question, resolved=question)

    qualifiers = []
    interpretations = []
    date_anchor_note: str | None = None
    for axis, rule in fired_axes.items():
        if axis == RECENT_AXIS and semantic_layer is not None:
            qualifier = _anchored_recent_qualifier(semantic_layer)
            if date_anchor_note is None:
                start, end = semantic_layer.get_date_anchor()
                date_anchor_note = f"date_anchor:{start}..{end}"
        else:
            qualifier = rule.get("apply", "")
        if qualifier:
            qualifiers.append(qualifier)
        interpretations.append(f"{axis}: {qualifier}")

    base = question.rstrip("?.!")
    resolved = base + " — " + "; ".join(qualifiers) if qualifiers else question

    if date_anchor_note is not None:
        interpretations.append(date_anchor_note)

    return ResolvedQuestion(
        original=question,
        resolved=resolved,
        interpretations_applied=interpretations,
    )
