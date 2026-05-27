from dataclasses import dataclass
from enum import Enum
from typing import Callable

import httpx

from pipeline.llm_client import LLMClient
from pipeline.sql_generator import extract_sql


class Action(Enum):
    ACCEPT = "accept"
    REFINE = "refine"


@dataclass
class ObservationResult:
    action: Action
    message: str


@dataclass
class ExecutionResult:
    success: bool
    data: list[dict] | None = None
    columns: list[str] | None = None
    sql: str = ""
    steps_taken: int = 0
    failure_reason: str | None = None


def build_refinement_prompt(
    original_sql: str,
    observation: str,
    schema: str,
    question: str,
) -> str:
    return f"""You are correcting a SQL query that failed or produced a bad result.

Schema:
{schema}

Original question: {question}

Attempted SQL:
{original_sql}

Problem observed:
{observation}

Instructions:
- Fix only the specific problem described above.
- Keep all correct parts of the original query unchanged.
- Do not add columns, tables, or logic not needed to fix the stated problem.
- Common fixes for '0 rows': check WHERE clause values match actual data
  (week_day values: Monday/Tuesday/Wednesday/Thursday/Friday/Saturday/Sunday;
   product names are case-sensitive exact strings).
- Common fixes for 'too many rows': add GROUP BY, ORDER BY + LIMIT, or a WHERE filter.
- Common fixes for SQL errors: check column names against the schema above.

Return only the corrected SQL query. No explanation. No markdown fences."""


class SQLExecutor:
    def __init__(
        self,
        db_url: str,
        llm_client: LLMClient,
        sql_model: str,
        log_fn: Callable[..., None] | None = None,
        run_context: dict | None = None,
        dataset_date_bounds: tuple[str, str] | None = None,
    ):
        self.db_url = db_url.rstrip("/")
        self.llm_client = llm_client
        self.sql_model = sql_model
        self.log_fn = log_fn
        self.run_context = run_context or {}
        self.dataset_date_bounds = dataset_date_bounds

    def execute_react(
        self,
        sql: str,
        question: str,
        linked_schema: str,
        max_steps: int = 4,
    ) -> ExecutionResult:
        for step in range(max_steps):
            result = self._try_execute(sql)

            if not result.success:
                obs = ObservationResult(
                    action=Action.REFINE,
                    message=f"SQL error: {result.failure_reason}",
                )
            else:
                obs = self._observe_result(question, sql, result)

            self._log_step(step, sql, obs)

            if obs.action == Action.ACCEPT:
                return ExecutionResult(
                    success=True,
                    data=result.data,
                    columns=result.columns,
                    sql=sql,
                    steps_taken=step + 1,
                )

            sql = self._refine_sql(sql, obs.message, linked_schema, question)

        return ExecutionResult(
            success=False,
            sql=sql,
            steps_taken=max_steps,
            failure_reason="max steps reached without successful result",
        )

    def _observe_result(
        self,
        question: str,
        sql: str,
        result: ExecutionResult,
    ) -> ObservationResult:
        del sql
        row_count = len(result.data or [])

        if row_count == 0:
            bounds_hint = ""
            if self.dataset_date_bounds:
                start, end = self.dataset_date_bounds
                bounds_hint = (
                    f" Dataset date_range: {start} to {end}."
                )
            return ObservationResult(
                action=Action.REFINE,
                message=(
                    "Query returned 0 rows. Possible causes: "
                    "filter value mismatch (check product_name or week_day spelling), "
                    "overly restrictive date range, or incorrect column reference."
                    f"{bounds_hint}"
                ),
            )

        if row_count > 10_000:
            return ObservationResult(
                action=Action.REFINE,
                message=(
                    f"Query returned {row_count} rows. Likely missing WHERE clause "
                    "or GROUP BY for an aggregation query."
                ),
            )

        scalar_indicators = ["total", "average", "how many", "count", "sum", "most", "top"]
        expects_scalar = any(w in question.lower() for w in scalar_indicators)
        if expects_scalar and row_count > 50:
            return ObservationResult(
                action=Action.REFINE,
                message=(
                    f"Question implies aggregated result but got {row_count} rows. "
                    "May be missing GROUP BY, ORDER BY + LIMIT, or aggregation function."
                ),
            )

        return ObservationResult(
            action=Action.ACCEPT,
            message="Result shape matches question intent.",
        )

    def _try_execute(self, sql: str) -> ExecutionResult:
        try:
            response = httpx.post(
                f"{self.db_url}/execute",
                json={"sql": sql},
                timeout=30.0,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, httpx.ConnectError) as exc:
            return ExecutionResult(
                success=False,
                sql=sql,
                failure_reason=f"db unreachable: {exc}",
            )

        if payload.get("error"):
            return ExecutionResult(
                success=False,
                sql=sql,
                failure_reason=payload["error"],
            )

        columns = payload.get("columns", [])
        rows = payload.get("rows", [])
        data = [dict(zip(columns, row)) for row in rows]
        return ExecutionResult(
            success=True,
            data=data,
            columns=columns,
            sql=sql,
        )

    def _refine_sql(
        self,
        sql: str,
        observation: str,
        schema: str,
        question: str,
    ) -> str:
        prompt = build_refinement_prompt(sql, observation, schema, question)
        response = self.llm_client.generate(
            prompt,
            model=self.sql_model,
            temperature=0.0,
        )
        return extract_sql(response)

    def _log_step(self, step: int, sql: str, obs: ObservationResult) -> None:
        if self.log_fn is None:
            return
        self.log_fn(
            stage="sql_executor",
            model=self.sql_model,
            step=step,
            sql_attempted=sql,
            observation_action=obs.action.value,
            observation_message=obs.message,
        )
