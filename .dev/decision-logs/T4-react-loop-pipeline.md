# T4 — ReAct Loop, Synthesis, Pipeline Orchestration + FastAPI

**Plan:** minivii-build · **Subtask:** T4 · **Date:** 2026-05-26

## Chosen approach

- Implemented `SQLExecutor` with structured `ObservationResult` / `Action` enum (no string sentinel), `execute_react(max_steps=4)`, rule-based `_observe_result`, HTTP `_try_execute` via `httpx` against db `POST /execute`, and spec-verbatim `build_refinement_prompt`.
- SQL refinement runs inside `SQLExecutor._refine_sql` using `build_refinement_prompt` + `LLMClient.generate(temperature=0.0)` + T3 `extract_sql`. T3 did not ship `sql_generator.refine()`; behavior matches spec §5.6 intent without modifying T3 files.
- `ResultSynthesizer.synthesize` guards on `success` and non-empty `data`; synthesis uses `temperature=0.3` and `_build_synthesis_prompt` truncates with `data[:10]`.
- `Pipeline.run()` orchestrates T3 stages, JSONL logging to `logs/runs/{run_id}.jsonl`, and calls synthesis only inside `if execution.success and execution.data`.
- `nlp/main.py` exposes `POST /query` on port 8002, reads `DB_URL`, `OLLAMA_URL`, `SQL_MODEL`, `SYNTHESIS_MODEL`, returns `dataclasses.asdict(result)` on success and HTTP 200 `{"error": "..."}` on handled failures.

## Alternatives rejected

- **Adding `refine()` to `sql_generator.py` (T3 file):** Rejected — T4 packet forbids modifying T3 outputs; refinement is colocated with `build_refinement_prompt` on `SQLExecutor`.
- **Raising on db HTTP errors:** Rejected per packet risk mitigation — `_try_execute` returns `ExecutionResult(success=False, failure_reason="db unreachable: ...")`.
- **Synthesis at `temperature=0.0`:** Rejected — spec §5.7 requires 0.3 for narrative quality; kill criterion enforces this.

## Assumptions made

- `datetime.now(timezone.utc).isoformat()` satisfies the `run_id` ISO-timestamp contract (replaces deprecated `datetime.utcnow()` while preserving wire shape).
- `OLLAMA_URL` is read in `main.py` for health visibility; `LLMClient` continues to use the Ollama Python client default host (T3 behavior).
- Per-stage `latency_ms` in JSONL is measured per logged stage, not cumulative pipeline time (`total_latency_ms` on `PipelineResult` is end-to-end).

## Items deferred

- **End-to-end ReAct refinement with live LLM + db:** Validated in T6 eval harness; unit tests mock HTTP/LLM only.
- **Full multi-stage log field parity for every sub-step of `generate_sql`:** Generator logs one record after completion; ReAct steps log via `sql_executor` callback.
