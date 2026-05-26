# TA1 — Infra Integration Fixes (Ollama Host + db Healthcheck)

**Plan:** minivii-build · **Subtask:** TA1 · **Date:** 2026-05-26  
**Audit findings:** F1 (Ollama host wiring), F2 (db healthcheck curl missing)

## Chosen approach

### F1 — Ollama host wiring

- Added `_ollama_client()` cached factory in `nlp/pipeline/llm_client.py` that constructs `ollama.Client(host=os.environ["OLLAMA_URL"])`.
- `_ollama_generate` calls `_ollama_client().generate(...)` instead of module-level `ollama.generate()`.
- Missing `OLLAMA_URL` raises `KeyError` on the first Ollama inference call (when `_ollama_client()` resolves the env var). No fallback to `http://127.0.0.1:11434`.
- `nlp/main.py` health display continues to read `OLLAMA_URL` unchanged.

### F2 — db healthcheck

- **Option A:** Added `wget` to `db/Dockerfile` via `apt-get install --no-install-recommends wget`.
- Updated `docker-compose.yml` db healthcheck from `curl -sf` to `wget -q -O- http://localhost:8001/health`.

## Alternatives rejected

### F1

- **`os.environ["OLLAMA_HOST"] = os.environ["OLLAMA_URL"]` at module load:** Rejected because it mutates process-global env and may affect other threads or SDK callers; instance-scoped `Client(host=)` is cleaner.
- **Module-level `os.environ["OLLAMA_URL"]` read at import time:** Rejected because existing unit tests (`test_sql_executor.py`) construct `LLMClient()` without setting `OLLAMA_URL`; import-time failure would break those tests, and the executor contract prohibits modifying existing tests to pass. First-call `KeyError` still fails loudly for misconfigured deployments.

### F2

- **Option B (Python `urllib.request` probe in compose healthcheck):** Rejected in favor of Option A. `wget` adds ~300 KB but provides a standard HTTP probe without Python startup overhead on each healthcheck interval.

## Assumptions made

- The Ollama Python SDK `Client(host=...)` constructor accepts the full URL form set in compose (`http://ollama:11434`), matching docker-compose service DNS.
- `wget -q -O-` exits non-zero on HTTP errors, satisfying Docker healthcheck semantics for `GET /health`.

## Items deferred

- **T4 decision log supersession (F13):** TA3 owns adding the supersession banner to `.dev/decision-logs/T4-react-loop-pipeline.md` pointing here.
- **Import-time `OLLAMA_URL` validation:** Deferred to first inference call to preserve existing unit tests; see Alternatives rejected above.

## Landed (TA1) — §2 Naming `OLLAMA_URL`

> `OLLAMA_URL` is now consumed on the inference path. `LLMClient` initializes `ollama.Client(host=os.environ["OLLAMA_URL"])` via cached `_ollama_client()`. Health display continues to read `OLLAMA_URL` unchanged. If `OLLAMA_URL` is unset, `KeyError` is raised loudly on the first Ollama generate call (no silent fallback to localhost).
