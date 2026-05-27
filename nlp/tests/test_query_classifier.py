from unittest.mock import MagicMock

from pipeline.llm_client import LLMClient
from pipeline.query_classifier import QueryClass, classify


def _mock_llm() -> MagicMock:
    return MagicMock(spec=LLMClient)


def test_aggregation_override_beats_time_filter():
    """TEST_CASES[0]: day-of-week wins map order unless ranking override fires."""
    llm = _mock_llm()
    query_class, method = classify("What is the most bought product on Fridays?", llm)
    assert query_class == QueryClass.AGGREGATION
    assert method == "heuristic_override"
    llm.generate.assert_not_called()


def test_case2_time_filter_not_overridden():
    """TEST_CASES[1]: 'how many' + Saturday must stay TIME_FILTER (not in AGGREGATION_OVERRIDES)."""
    llm = _mock_llm()
    query_class, method = classify("How many transactions happened on Saturdays?", llm)
    assert query_class == QueryClass.TIME_FILTER
    assert method == "heuristic"
    llm.generate.assert_not_called()


def test_most_bought_on_fridays_aggregation():
    llm = _mock_llm()
    query_class, method = classify("most bought on Fridays", llm)
    assert query_class == QueryClass.AGGREGATION
    assert method == "heuristic_override"
    llm.generate.assert_not_called()


def test_bare_most_with_what_day_stays_time_filter():
    """Risk matrix: 'what day' + bare 'most' is legitimately TIME_FILTER, not AGGREGATION."""
    llm = _mock_llm()
    query_class, method = classify("What day has the most transactions?", llm)
    assert query_class == QueryClass.TIME_FILTER
    assert method == "heuristic"
    llm.generate.assert_not_called()
