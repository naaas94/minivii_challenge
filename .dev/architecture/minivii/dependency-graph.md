Section:      dependency-graph
Version:      1.0.1
Last updated: 2026-05-26

## Internal dependencies

| Dependent | Depends on | Nature of coupling | Risk if changed independently |
|-----------|-----------|--------------------|------------------------------|
| `nlp/pipeline/ambiguity_detector.py` | `nlp/schema/domain.yaml` (via `disambiguation_rules.when`) | `AMBIGUITY_TRIGGERS` values must match YAML `when` axis strings exactly | Rules silently stop firing; ambiguous questions pass through unresolved |
| `nlp/pipeline/semantic_layer.py` | `nlp/schema/domain.yaml` | Column names, types, KPI definitions, date_range metadata drive rendered DDL | SQL generator prompts diverge from actual SQLite schema |
| `db/main.py` | `db/ingest.py` + hardcoded `SCHEMA_DDL` | DDL comment block duplicated separately from SemanticLayer output (accepted submission debt) | `/schema` endpoint and LLM prompts disagree on column semantics |
| `nlp/pipeline/sql_executor.py` | `db/main.py` `POST /execute` | HTTP JSON shape `{columns, rows}` or `{error, sql}`; `DB_URL` env default `http://db:8001` | Executor cannot run queries; ReAct loop fails all steps |
| `nlp/pipeline/pipeline.py` | `nlp/pipeline/sql_executor.py` via shared `_run_context` dict | Mutable run_context passed into SQLExecutor for logging callback | Log records lose question/run_id correlation |
| `nlp/pipeline/sql_generator.py` | `nlp/pipeline/query_classifier.py` | `FEW_SHOT_EXAMPLES` keyed by all `QueryClass` members | Missing enum member causes KeyError at generation time |
| `nlp/eval/harness.py` | `nlp/pipeline/pipeline.py` + `TEST_CASES.expected_class` | expected_class strings must match `QueryClass.value` | Eval misreports classification without failing loudly |
| `ui/main.py` | `nlp/main.py` | Assumes `PipelineResult` field names and top-level `error` key; checks JSON body not HTTP status | UI renders broken/empty sections |
| `ollama/entrypoint.sh` | `docker-compose.yml` env + README CPU fallback docs | Hardcoded model pulls (`qwen2.5-coder:14b`, `qwen3:32b`) vs env overrides on CPU path | Wrong models loaded or env/entrypoint mismatch |
| `nlp/pipeline/llm_client.py` | Ollama Python SDK (`OLLAMA_HOST` env) | Compose/README document `OLLAMA_URL`; SDK reads `OLLAMA_HOST` (default `http://127.0.0.1:11434`). `LLMClient` passes no host. | **Confirmed defect in Compose:** NLP container LLM calls hit localhost, not `ollama` service, unless `OLLAMA_HOST` set externally |

## External dependencies

| Dependency | Version pinned | Role in project | Sensitivity |
|------------|---------------|-----------------|-------------|
| Python | 3.11 (Dockerfile `python:3.11-slim`) | Runtime for all services | medium |
| FastAPI | unpinned in requirements.txt | HTTP APIs (db, nlp, ui) | low |
| Uvicorn | unpinned (`uvicorn[standard]`) | ASGI server | low |
| Pydantic | unpinned | Request models (nlp, db) | low |
| httpx | unpinned | ui→nlp and nlp→db HTTP | low |
| ollama (Python) | unpinned | Local LLM inference client; host via `OLLAMA_HOST` | high |
| litellm | unpinned | Groq/Together fallback backends | medium |
| PyYAML | unpinned | domain.yaml loading | low |
| Jinja2 | unpinned (ui) | HTML templating | low |
| pytest | unpinned (nlp dev) | Unit tests | low |
| SQLite3 | stdlib | Embedded database in db service | low |
| ollama/ollama (container image) | unpinned (`ollama/ollama`) | Model serving; pulls ~29 GB on first run | high |
| qwen2.5-coder:14b | tag pin via entrypoint + env | SQL generation and refinement | high |
| qwen3:32b | tag pin via entrypoint + env | Narrative synthesis | high |
