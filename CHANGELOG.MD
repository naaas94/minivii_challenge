# Changelog

## minivii-build — 2026-05-26

- T1 (Project scaffold and Docker infrastructure): Added directory tree, Dockerfiles, docker-compose.yml, ollama entrypoint, requirements stubs, domain.yaml semantic layer, and .gitignore. Establishes the four-container Compose layout and frozen naming contracts for downstream subtasks. Test coverage deferred: T1 contract explicitly waives tests; automated compose/port/env validation deferred to T2 smoke test and T7 full stack bring-up.
- T2 (db FastAPI service): Added `db/ingest.py` with spec-verbatim CSV→SQLite ingestion (ISO date normalization via `strptime`, `ticket_prefix` extraction, `quantity REAL`) and `db/main.py` with lifespan startup load plus `/execute`, `/schema`, and `/health` endpoints honoring the §2 error envelope. Smoke test confirmed `GET /health` returns `row_count: 24212` with authoritative dataset. Adversarial gap deferred: no automated test for malformed date strings in CSV (T2 contract waives unit tests; eval harness is the gate in T6).
- T3 (NLP pipeline core — upstream components): Implemented LLMClient, SemanticLayer, AmbiguityDetector, SchemaLinker, QueryClassifier, and SQLGenerator with live LLM wiring for classifier fallback and SQL generation. Non-cascading ambiguity resolution and WINDOW few-shot using strftime on ISO dates per spec correction C1. See `.dev/decision-logs/T3-nlp-pipeline-core.md`.
