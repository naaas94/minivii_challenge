from enum import Enum

from pipeline.llm_client import LLMClient

class QueryClass(Enum):
    TIME_FILTER = "time_filter"
    WINDOW = "window"
    AGGREGATION = "aggregation"
    SIMPLE = "simple"


KEYWORD_CLASS_MAP: dict[QueryClass, list[str]] = {
    QueryClass.TIME_FILTER: [
        "on monday",
        "on tuesday",
        "on wednesday",
        "on thursday",
        "on friday",
        "on saturday",
        "on sunday",
        "on weekends",
        "on weekdays",
        "in the morning",
        "in the afternoon",
        "peak hour",
        "busiest hour",
        "what hour",
        "what time",
        "what day",
    ],
    QueryClass.WINDOW: [
        "trend",
        "week-over-week",
        "month-over-month",
        "over time",
        "growth",
        "change over",
        "evolution",
        "compared to last",
    ],
    QueryClass.AGGREGATION: [
        "most",
        "top",
        "best",
        "total",
        "average",
        "how many",
        "sum",
        "by product",
        "by waiter",
        "per product",
        "per waiter",
        "breakdown",
        "ranking",
    ],
}

# Ranking/product terms that beat TIME_FILTER when both co-occur (Option C override).
# Excludes bare "most" and "how many" so case 2 and "what day has the most …" stay TIME_FILTER.
AGGREGATION_OVERRIDES: tuple[str, ...] = (
    "most bought",
    "most popular",
    "top",
    "best",
    "by product",
    "by waiter",
    "per product",
    "per waiter",
    "breakdown",
    "ranking",
)


def classify(question: str, llm_client: LLMClient) -> tuple[QueryClass, str]:
    q = question.lower()
    for cls, keywords in KEYWORD_CLASS_MAP.items():
        if any(kw in q for kw in keywords):
            if cls == QueryClass.TIME_FILTER and any(term in q for term in AGGREGATION_OVERRIDES):
                return QueryClass.AGGREGATION, "heuristic_override"
            return cls, "heuristic"
    return _llm_classify(question, llm_client), "llm"


def _llm_classify(question: str, llm_client: LLMClient) -> QueryClass:
    prompt = f"""Classify this SQL query question into exactly one category.

Categories:
- time_filter: filtering by day of week, hour of day, or time period
- window: trends over time, week-over-week or month-over-month comparisons
- aggregation: GROUP BY queries, totals, counts, rankings by product/waiter
- simple: single-condition filter with no grouping

Question: {question}

Respond with exactly one word: time_filter, window, aggregation, or simple"""

    response = llm_client.generate(prompt, temperature=0.0)
    label = response.strip().lower()
    try:
        return QueryClass(label)
    except ValueError:
        return QueryClass.SIMPLE
