Section:      public-interface-inventory
Version:      1.0.0
Last updated: 2026-05-26

## HTTP APIs (cross-container)

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `POST /query` | `nlp/main.py` | endpoint | Accepts `{question: str}`; returns `PipelineResult` dict or `{error: str}` with HTTP 200 | `ui/main.py` | stable |
| `GET /health` | `nlp/main.py` | endpoint | Returns `{status, ollama_url}` | Docker (implicit) | stable |
| `POST /execute` | `db/main.py` | endpoint | Accepts `{sql: str}`; returns `{columns, rows, row_count}` or `{error, sql}` | `nlp/pipeline/sql_executor.py` | stable |
| `GET /schema` | `db/main.py` | endpoint | Returns `{ddl: str}` (hardcoded SCHEMA_DDL) | External callers (not used by nlp pipeline) | stable |
| `GET /health` | `db/main.py` | endpoint | Returns `{status, row_count}` or 500 error envelope | `docker-compose.yml` healthcheck | stable |
| `GET /`, `POST /` | `ui/main.py` | endpoint | HTML form; POST forwards question to NLP `/query` | Browser | stable |

## Pipeline orchestration

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `Pipeline` | `nlp/pipeline/pipeline.py` | class | `run(question: str) -> PipelineResult`; orchestrates all stages + JSONL logging | `nlp/main.py`, `nlp/eval/harness.py` | stable |
| `PipelineResult` | `nlp/pipeline/pipeline.py` | dataclass | question, resolved_question, interpretations, query_class, sql, execution, narrative, run_id, total_latency_ms | `nlp/main.py`, UI template, eval harness | stable |

## Pipeline stages (intra-nlp, exported via `pipeline/__init__.py` where noted)

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `LLMClient` | `nlp/pipeline/llm_client.py` | class | `generate(prompt, model?, **kwargs) -> str`; backends: ollama, groq, together | classifier, sql_generator, sql_executor, result_synthesizer, eval harness | stable |
| `detect_and_resolve` | `nlp/pipeline/ambiguity_detector.py` | function | `(question, domain_descriptor) -> ResolvedQuestion` | `pipeline.py` | stable |
| `ResolvedQuestion` | `nlp/pipeline/ambiguity_detector.py` | dataclass | original, resolved, interpretations_applied | sql_generator, pipeline, result_synthesizer | stable |
| `SemanticLayer` | `nlp/pipeline/semantic_layer.py` | class | Loads YAML; `get_kpis() -> list[dict]`; `render_ddl() -> str` | `SchemaLinker`, `pipeline.py` | stable |
| `SchemaLinker` | `nlp/pipeline/schema_linker.py` | class | `link(question) -> str` (returns full DDL; question ignored) | `pipeline.py` | stable |
| `QueryClass` | `nlp/pipeline/query_classifier.py` | enum | time_filter, window, aggregation, simple | sql_generator, eval harness | stable |
| `classify` | `nlp/pipeline/query_classifier.py` | function | `(question, llm_client) -> (QueryClass, method)` | `pipeline.py` | stable |
| `generate_sql` | `nlp/pipeline/sql_generator.py` | function | `(ResolvedQuestion, schema, QueryClass, kpis, llm_client) -> str` | `pipeline.py` | stable |
| `extract_sql` | `nlp/pipeline/sql_generator.py` | function | Strips markdown fences; extracts SELECT/WITH statement | sql_generator, sql_executor | stable |
| `build_sql_prompt` | `nlp/pipeline/sql_generator.py` | function | Builds prompt from schema, KPIs, few-shot example | sql_generator, tests | stable |
| `FEW_SHOT_EXAMPLES` | `nlp/pipeline/sql_generator.py` | constant | Dict keyed by QueryClass → SQL example string | sql_generator, tests | stable |
| `SQLExecutor` | `nlp/pipeline/sql_executor.py` | class | `execute_react(sql, question, schema, max_steps=4) -> ExecutionResult` | `pipeline.py` | stable |
| `ExecutionResult` | `nlp/pipeline/sql_executor.py` | dataclass | success, data, columns, sql, steps_taken, failure_reason | pipeline, result_synthesizer, eval harness | stable |
| `Action`, `ObservationResult` | `nlp/pipeline/sql_executor.py` | enum / dataclass | ReAct observation action (accept/refine) + message | sql_executor (internal) | stable |
| `build_refinement_prompt` | `nlp/pipeline/sql_executor.py` | function | Builds SQL correction prompt from observation | sql_executor | stable |
| `ResultSynthesizer` | `nlp/pipeline/result_synthesizer.py` | class | `synthesize(question, ExecutionResult, interpretations) -> str \| None` | `pipeline.py` | stable |

## Data layer

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `load_csv_to_db` | `db/ingest.py` | function | `(csv_path, db_path) -> None`; normalizes M/D/YYYY dates to ISO, derives ticket_prefix | `db/main.py` lifespan | stable |

## Evaluation

| Symbol | Module | Kind | Signature summary | Consumed by | Stability |
|--------|--------|------|-------------------|-------------|-----------|
| `EvalHarness` | `nlp/eval/harness.py` | class | `run_eval(test_cases, skip_judge) -> EvalReport`; structural SQL + optional judge | CLI `python -m eval.harness` | active |
| `TestCase` | `nlp/eval/harness.py` | dataclass | question, expected_class, expected/forbidden SQL clauses, optional known_answer | eval harness | active |
| `check_sql_structure` | `nlp/eval/harness.py` | function | Clause presence/absence check on generated SQL | eval harness | active |
