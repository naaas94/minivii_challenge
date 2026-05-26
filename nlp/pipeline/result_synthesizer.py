from pipeline.llm_client import LLMClient
from pipeline.sql_executor import ExecutionResult


class ResultSynthesizer:
    def __init__(self, llm_client: LLMClient, synthesis_model: str):
        self.llm_client = llm_client
        self.synthesis_model = synthesis_model

    def synthesize(
        self,
        question: str,
        result: ExecutionResult,
        interpretations: list[str],
    ) -> str | None:
        if not result.success or not result.data:
            return None

        prompt = self._build_synthesis_prompt(
            question=question,
            data=result.data,
            sql=result.sql,
            interpretations_applied=interpretations,
            steps_taken=result.steps_taken,
        )
        return self.llm_client.generate(
            prompt,
            model=self.synthesis_model,
            temperature=0.3,
        )

    def _build_synthesis_prompt(
        self,
        question: str,
        data: list[dict],
        sql: str,
        interpretations_applied: list[str],
        steps_taken: int,
    ) -> str:
        del sql, steps_taken
        sample = data[:10]
        summary = {
            "total_rows": len(data),
            "columns": list(data[0].keys()) if data else [],
            "showing": f"first {len(sample)} of {len(data)} rows",
        }
        interp_text = (
            "\n".join(f"- {i}" for i in interpretations_applied)
            if interpretations_applied
            else "None"
        )

        return f"""You are a business analyst generating a concise insight from a query result.

Question asked: {question}

Interpretations applied (business rules used): 
{interp_text}

Result summary: {summary}
Result sample: {sample}

Write a 2–3 sentence analytical narrative that includes:
1. The concrete finding (specific numbers from the result)
2. One business implication or actionable observation
3. Any interpretation assumptions, stated explicitly

Be factual. Do not invent numbers not present in the result sample.
Write in plain language, as if briefing a store manager."""
