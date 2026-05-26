Section:      module-map
Version:      1.0.1
Last updated: 2026-05-26

| Module path | Role | Key files | Stability |
|-------------|------|-----------|-----------|
| `nlp/pipeline/` | Multi-stage NL→SQL→narrative pipeline (ambiguity, schema link, classify, generate, ReAct execute, synthesize) | `pipeline.py`, `ambiguity_detector.py`, `semantic_layer.py`, `schema_linker.py`, `query_classifier.py`, `sql_generator.py`, `sql_executor.py`, `result_synthesizer.py`, `llm_client.py` | active — end-to-end wired and tested; SchemaLinker.question seam and LLMClient backend switch may evolve post-submission |
| `nlp/schema/` | Authoritative domain semantic descriptor consumed by pipeline | `domain.yaml` | stable — T1 kill criterion locks content to spec §5.2 |
| `nlp/` (service) | FastAPI HTTP entry exposing `POST /query` and orchestrating `Pipeline` | `main.py` | stable — PipelineResult wire shape and HTTP 200 envelope frozen for submission |
| `nlp/eval/` | Offline eval harness: structural SQL checks + optional LLM judge for narratives | `harness.py` | active — TEST_CASES and gate semantics may expand |
| `nlp/tests/` | Unit tests for pipeline modules, harness, and README contract | `test_*.py` | active |
| `db/` | CSV ingest, SQLite persistence, SQL execution and schema HTTP API | `main.py`, `ingest.py` | stable — ingest and /execute contract frozen; dual DDL is accepted debt |
| `ui/` | Server-rendered web UI; proxies user questions to NLP service | `main.py`, `templates/index.html` | stable |
| `ollama/` | Container bootstrap: start Ollama, pull models, signal readiness | `entrypoint.sh` | stable — frozen for submission; model tag changes require coordinated entrypoint + compose + README edits |
| repo root | Orchestration, dataset mount, build spec | `docker-compose.yml`, `data.csv`, `mini-nivii-final-spec.md` | stable |
