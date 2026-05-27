import re

from pipeline.ambiguity_detector import ResolvedQuestion
from pipeline.llm_client import LLMClient
from pipeline.query_classifier import QueryClass

RETURNS_TRIGGERS: tuple[str, ...] = ("return", "refund", "negative")

RETURNS_CONSTRAINT = (
    "-- REQUIRED: filter return rows with WHERE total < 0"
)

FEW_SHOT_EXAMPLES: dict[QueryClass, str] = {
    QueryClass.SIMPLE: """
-- Q: How many transactions happened on Saturdays?
SELECT COUNT(DISTINCT ticket_number) AS transaction_count
FROM sales
WHERE week_day = 'Saturday';
""",
    QueryClass.AGGREGATION: """
-- Q: What is the most bought product on Fridays?
SELECT product_name,
       SUM(quantity) AS total_qty
FROM sales
WHERE week_day = 'Friday'
  AND total > 0
GROUP BY product_name
ORDER BY total_qty DESC
LIMIT 10;

-- Q: Which product has the most returns?
SELECT product_name,
       SUM(quantity) AS return_qty
FROM sales
WHERE total < 0
GROUP BY product_name
ORDER BY return_qty ASC
LIMIT 10;
""",
    QueryClass.TIME_FILTER: """
-- Q: What are the busiest hours on weekdays?
SELECT CAST(substr(hour, 1, 2) AS INTEGER) AS hour_of_day,
       COUNT(DISTINCT ticket_number) AS transactions
FROM sales
WHERE week_day NOT IN ('Saturday', 'Sunday')
GROUP BY hour_of_day
ORDER BY transactions DESC
LIMIT 10;
""",
    QueryClass.WINDOW: """
-- Q: What is the week-over-week revenue trend?
-- date column is ISO YYYY-MM-DD (normalized at ingestion). Use strftime() directly.
WITH weekly AS (
    SELECT strftime('%Y-W%W', date) AS week,
           SUM(total) AS weekly_revenue
    FROM sales
    WHERE total > 0
    GROUP BY week
)
SELECT week,
       weekly_revenue,
       weekly_revenue - LAG(weekly_revenue) OVER (ORDER BY week) AS wow_change
FROM weekly
ORDER BY week;
""",
}


def build_sql_prompt(
    question: str,
    schema: str,
    query_class: QueryClass,
    kpi_definitions: list[dict],
    few_shot_example: str,
) -> str:
    kpi_lines = []
    for kpi in kpi_definitions:
        line = f"-- {kpi['name']}: {kpi['definition']}"
        if kpi.get("note"):
            line += f"  ({kpi['note']})"
        kpi_lines.append(line)
    kpi_block = "\n".join(kpi_lines)

    question_lower = question.lower()
    returns_block = ""
    if any(trigger in question_lower for trigger in RETURNS_TRIGGERS):
        returns_block = f"\n{RETURNS_CONSTRAINT}\n"

    return f"""{schema}

{kpi_block}

{few_shot_example}
{returns_block}
Question: {question}

Return only the SQL query. No explanation. No markdown fences."""


def extract_sql(response: str) -> str:
    response = re.sub(r"```sql|```", "", response).strip()
    match = re.search(r"\b(SELECT|WITH)\b", response, re.IGNORECASE)
    if match:
        sql = response[match.start() :]
        if ";" in sql:
            sql = sql[: sql.index(";") + 1]
        return sql.strip()
    return response


def generate_sql(
    resolved_question: ResolvedQuestion,
    linked_schema: str,
    query_class: QueryClass,
    kpi_definitions: list[dict],
    llm_client: LLMClient,
) -> str:
    prompt = build_sql_prompt(
        question=resolved_question.resolved,
        schema=linked_schema,
        query_class=query_class,
        kpi_definitions=kpi_definitions,
        few_shot_example=FEW_SHOT_EXAMPLES[query_class],
    )
    response = llm_client.generate(prompt, temperature=0.0)
    return extract_sql(response)
