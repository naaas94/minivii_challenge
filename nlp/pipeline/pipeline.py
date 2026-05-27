import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pipeline import ambiguity_detector, sql_generator
from pipeline.llm_client import LLMClient
from pipeline.query_classifier import classify
from pipeline.result_synthesizer import ResultSynthesizer
from pipeline.schema_linker import SchemaLinker
from pipeline.semantic_layer import SemanticLayer
from pipeline.sql_executor import ExecutionResult, SQLExecutor


@dataclass
class PipelineResult:
    question: str
    resolved_question: str
    interpretations: list[str]
    query_class: str
    sql: str
    execution: ExecutionResult
    narrative: str | None
    run_id: str
    total_latency_ms: int


class Pipeline:
    def __init__(
        self,
        db_url: str,
        llm_client: LLMClient,
        sql_model: str,
        synthesis_model: str,
        semantic_layer: SemanticLayer | None = None,
        log_dir: str | Path = "logs/runs",
    ):
        self.semantic_layer = semantic_layer or SemanticLayer()
        self.domain = self.semantic_layer.descriptor
        self.kpis = self.semantic_layer.get_kpis()
        self.schema_linker = SchemaLinker(self.semantic_layer)
        self.llm_client = llm_client
        self.db_url = db_url
        self.sql_model = sql_model
        self.synthesis_model = synthesis_model
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self._run_context: dict = {}
        self.sql_executor = SQLExecutor(
            db_url=db_url,
            llm_client=llm_client,
            sql_model=sql_model,
            log_fn=self._log_executor_step,
            run_context=self._run_context,
            dataset_date_bounds=self.semantic_layer.get_date_anchor(),
        )
        self.result_synthesizer = ResultSynthesizer(llm_client, synthesis_model)

    def run(self, question: str) -> PipelineResult:
        run_id = datetime.now(timezone.utc).isoformat()
        t0 = time.time()
        self._run_context.update(
            {
                "run_id": run_id,
                "question": question,
                "resolved_question": question,
            }
        )

        t_stage = time.time()
        resolved = ambiguity_detector.detect_and_resolve(
            question, self.domain, semantic_layer=self.semantic_layer
        )
        self._run_context["resolved_question"] = resolved.resolved
        self._log(
            run_id,
            "ambiguity",
            question=question,
            resolved_question=resolved.resolved,
            latency_ms=int((time.time() - t_stage) * 1000),
        )

        t_stage = time.time()
        linked_schema = self.schema_linker.link(resolved.resolved)
        self._log(
            run_id,
            "schema_linker",
            question=question,
            resolved_question=resolved.resolved,
            latency_ms=int((time.time() - t_stage) * 1000),
        )

        t_stage = time.time()
        query_class, cls_method = classify(resolved.resolved, self.llm_client)
        # query_class and cls_method omitted from JSONL per §2 Logging (11-field schema only).
        self._log(
            run_id,
            "classifier",
            question=question,
            resolved_question=resolved.resolved,
            model=self.sql_model if cls_method == "llm" else None,
            latency_ms=int((time.time() - t_stage) * 1000),
        )

        t_stage = time.time()
        sql = sql_generator.generate_sql(
            resolved,
            linked_schema,
            query_class,
            self.kpis,
            self.llm_client,
        )
        self._log(
            run_id,
            "sql_generator",
            question=question,
            resolved_question=resolved.resolved,
            model=self.sql_model,
            sql_attempted=sql,
            latency_ms=int((time.time() - t_stage) * 1000),
        )

        t_stage = time.time()
        execution = self.sql_executor.execute_react(
            sql,
            resolved.resolved,
            linked_schema,
        )
        # execution.success and steps_taken omitted from JSONL per §2 Logging (11-field schema only).
        self._log(
            run_id,
            "sql_executor_complete",
            question=question,
            resolved_question=resolved.resolved,
            model=self.sql_model,
            sql_attempted=execution.sql,
            latency_ms=int((time.time() - t_stage) * 1000),
        )

        narrative = None
        if execution.success and execution.data:
            t_stage = time.time()
            narrative = self.result_synthesizer.synthesize(
                question=question,
                result=execution,
                interpretations=resolved.interpretations_applied,
            )
            self._log(
                run_id,
                "result_synthesizer",
                question=question,
                resolved_question=resolved.resolved,
                model=self.synthesis_model,
                latency_ms=int((time.time() - t_stage) * 1000),
            )

        return PipelineResult(
            question=question,
            resolved_question=resolved.resolved,
            interpretations=resolved.interpretations_applied,
            query_class=query_class.value,
            sql=execution.sql,
            execution=execution,
            narrative=narrative,
            run_id=run_id,
            total_latency_ms=int((time.time() - t0) * 1000),
        )

    def _log_executor_step(self, **fields) -> None:
        ctx = self._run_context
        self._log(
            ctx["run_id"],
            fields.pop("stage", "sql_executor"),
            question=ctx["question"],
            resolved_question=ctx["resolved_question"],
            **fields,
        )

    def _log(
        self,
        run_id: str,
        stage: str,
        *,
        question: str,
        resolved_question: str,
        model: str | None = None,
        step: int | None = None,
        sql_attempted: str | None = None,
        observation_action: str | None = None,
        observation_message: str | None = None,
        latency_ms: int = 0,
    ) -> None:
        record = {
            "run_id": run_id,
            "stage": stage,
            "question": question,
            "resolved_question": resolved_question,
            "model": model,
            "step": step,
            "sql_attempted": sql_attempted,
            "observation_action": observation_action,
            "observation_message": observation_message,
            "latency_ms": latency_ms,
        }
        log_path = self.log_dir / f"{run_id}.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
