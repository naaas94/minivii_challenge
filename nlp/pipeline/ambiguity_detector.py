from dataclasses import dataclass, field

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


def detect_and_resolve(question: str, domain_descriptor: dict) -> ResolvedQuestion:
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
    for axis, rule in fired_axes.items():
        qualifier = rule.get("apply", "")
        if qualifier:
            qualifiers.append(qualifier)
        interpretations.append(f"{axis}: {qualifier}")

    base = question.rstrip("?.!")
    resolved = base + " — " + "; ".join(qualifiers) if qualifiers else question

    return ResolvedQuestion(
        original=question,
        resolved=resolved,
        interpretations_applied=interpretations,
    )
