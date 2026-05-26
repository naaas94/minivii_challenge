from pipeline.query_classifier import QueryClass
from pipeline.sql_generator import FEW_SHOT_EXAMPLES, build_sql_prompt, extract_sql


def test_extract_sql_strips_fences():
    response = "```sql\nSELECT 1;\n```"
    assert extract_sql(response) == "SELECT 1;"


def test_extract_sql_finds_select():
    response = "Here is the query:\nSELECT product_name FROM sales;"
    assert extract_sql(response) == "SELECT product_name FROM sales;"


def test_extract_sql_truncates_at_semicolon():
    response = "SELECT 1; This is not SQL."
    assert extract_sql(response) == "SELECT 1;"


def test_extract_sql_returns_raw_on_no_match():
    response = "No valid SQL here."
    assert extract_sql(response) == "No valid SQL here."


def test_window_few_shot_uses_strftime_not_substr_on_date():
    example = FEW_SHOT_EXAMPLES[QueryClass.WINDOW]
    assert "strftime('%Y-W%W', date)" in example
    assert "substr(" not in example.lower() or "substr(hour" in example.lower()


def test_build_sql_prompt_order():
    schema = "CREATE TABLE sales (id INTEGER);"
    kpis = [{"name": "total_revenue", "definition": "SUM(total)"}]
    few_shot = "-- Q: example\nSELECT 1;"
    prompt = build_sql_prompt(
        question="How many tickets?",
        schema=schema,
        query_class=QueryClass.SIMPLE,
        kpi_definitions=kpis,
        few_shot_example=few_shot,
    )
    schema_pos = prompt.index(schema)
    kpi_pos = prompt.index("total_revenue")
    few_shot_pos = prompt.index(few_shot)
    question_pos = prompt.index("Question: How many tickets?")
    instruction_pos = prompt.index("Return only the SQL query")
    assert schema_pos < kpi_pos < few_shot_pos < question_pos < instruction_pos
