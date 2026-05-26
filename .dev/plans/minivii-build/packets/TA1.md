# Executor Packet — TA1: Infra Integration Fixes

**Plan:** minivii-build · **Subtask:** TA1 · **Log tier:** architectural  
**Executor skill:** executor-subtask-execution  
**Spec source (binding):** `mini-nivii-final-spec.md` at repo root  
**Amendment cycle:** v1.2 — post-audit remediation  
**Audit source:** `.dev/audits/2026-05-26-minivii-build.md` findings F1, F2  
**Decision log path (required — architectural tier):** `.dev/decision-logs/TA1-ollama-host-wiring.md`

---

## §1. Task Statement

Fix two stack-breaking integration failures that prevent the Docker Compose application from functioning at all.

**F1 — Ollama host wiring:** `docker-compose.yml` sets `OLLAMA_URL=http://ollama:11434` in the `nlp` environment, but `LLMClient._ollama_generate` calls the module-level `ollama.generate()` function, which uses the `ollama.Client()` default of `OLLAMA_HOST=http://127.0.0.1:11434`. Inside the `nlp` container, `127.0.0.1` is loopback — there is no Ollama process there. Every LLM call (SQL generation, classification fallback, synthesis, eval judge) silently fails with a connection error.

**F2 — db healthcheck curl missing:** `docker-compose.yml` specifies the db healthcheck as `curl -sf http://localhost:8001/health`, but `db/Dockerfile` is based on `python:3.11-slim` which has no `curl` binary. The healthcheck never succeeds, so the `nlp` service (which has `depends_on: db: condition: service_healthy`) blocks indefinitely.

**Non-goals:**
- Any change to pipeline business logic, prompt content, or LLM model configuration
- Changes to the synthesis temperature, max steps, or ReAct heuristics
- Any new features, endpoints, or eval cases
- Changes to `docker-compose.yml` service topology (names, ports, network, volumes)

---

## §2. Shared Contracts (relevant rows — verbatim from plan §2)

### Naming (binding for TA1)

| Symbol | Value |
|---|---|
| Docker services | `db`, `nlp`, `ui`, `ollama` — used as hostnames in `nivii-net` |
| Env vars (nlp) | `DB_URL`, `OLLAMA_URL`, `SQL_MODEL`, `SYNTHESIS_MODEL` — set in docker-compose; nlp reads via `os.environ` |
| Models | SQL: `qwen2.5-coder:14b` · Synthesis: `qwen3:32b` |
| Decision log path | TA1: `.dev/decision-logs/TA1-ollama-host-wiring.md` |

**Landed (to be added by executor when fix ships):**
> `Landed (TA1):` `OLLAMA_URL` is now consumed on the inference path. `LLMClient` initializes `ollama.Client(host=os.environ["OLLAMA_URL"])` (or sets `os.environ["OLLAMA_HOST"]` at module load). Health display continues to read `OLLAMA_URL` unchanged. If `OLLAMA_URL` is unset, `KeyError` is raised loudly at import time.

### Error Envelope (relevant)

| Service | Endpoint | Success shape | Error shape |
|---|---|---|---|
| `db` | `GET /health` | `{"status": "ok", "row_count": N}` | HTTP 500 |

The db healthcheck probe must be able to reach this endpoint. The fix must ensure the probe does not require a tool (`curl`) absent from the base image.

---

## §4. Subtask Spec

**Scope:** Wire `OLLAMA_URL` env var to Ollama Python SDK host; fix db healthcheck to not require `curl`.

**Files to touch:**
```
nlp/pipeline/llm_client.py          (F1 — explicit host from OLLAMA_URL)
db/Dockerfile                        (F2 — add wget OR switch healthcheck to Python)
docker-compose.yml                   (F2 — update healthcheck command if switching probe type)
.dev/decision-logs/TA1-ollama-host-wiring.md   (new — architectural tier required)
```

**Contract bindings:** §2 Naming (OLLAMA_URL consumption path); §2 Error Envelope (db healthcheck endpoint).

**Inputs:** None — standalone fix; no prior amendment subtask required.

**Outputs:**

1. **`nlp/pipeline/llm_client.py`** — `LLMClient._ollama_generate` uses an explicit `ollama.Client(host=…)` constructed from `os.environ["OLLAMA_URL"]`, OR sets `os.environ["OLLAMA_HOST"] = os.environ["OLLAMA_URL"]` at module load before any SDK call. The chosen approach must be documented in the decision log. `OLLAMA_URL` must not be silently ignored or fall back to localhost.

2. **db healthcheck fixed** — one of two acceptable approaches:
   - **Option A (preferred):** Add `RUN apt-get update && apt-get install -y --no-install-recommends wget && rm -rf /var/lib/apt/lists/*` to `db/Dockerfile`; leave `docker-compose.yml` healthcheck command as-is (swap `curl -sf` for `wget -q -O-`).
   - **Option B:** Change `docker-compose.yml` healthcheck `test` to `["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"]` — no Dockerfile change needed.
   Document chosen option in the decision log.

3. **`.dev/decision-logs/TA1-ollama-host-wiring.md`** — architectural decision log covering:
   - Choices considered for F1 (`ollama.Client(host=)` vs `os.environ["OLLAMA_HOST"]`) and rationale for choice made
   - Choices considered for F2 (Option A vs B) and rationale
   - The `Landed:` annotation for §2 Naming `OLLAMA_URL` row

4. **§2 Naming `OLLAMA_URL` row** back-annotated with `Landed:` bullet in the plan file (executor edits `plan.md` §2 Naming table or appends bullet below the row).

**Kill criteria:**
- HALT if `LLMClient._ollama_generate` still calls module-level `ollama.generate()` without an explicit `host` argument derived from `OLLAMA_URL`
- HALT if db healthcheck still uses `curl` and `curl` is not installed in `db/Dockerfile`
- HALT if `OLLAMA_HOST` approach is chosen but the env var is not set before any `ollama.*` call in the module
- HALT if `OLLAMA_URL` silently falls back to `http://127.0.0.1:11434` when unset — must raise loudly
- HALT if the decision log is absent (architectural tier — required)
- HALT if the decision log does not cover both F1 and F2 choice rationale

**Log tier:** architectural

**Risks & mitigations:**
- For F1, `ollama.Client(host=os.environ["OLLAMA_URL"])` is the cleanest option because it scopes the host to the client instance and does not mutate global env. The `os.environ["OLLAMA_HOST"]` approach mutates global state and may affect other threads. Prefer the client-instance approach unless the SDK version does not support `Client(host=)`.
- For F2 Option A, `wget` adds ~300 KB to the image but is the most robust probe. Option B avoids any image change but the Python `urllib` call does not follow HTTP redirects by default — acceptable since the health endpoint returns 200 directly.
- Do not add `requests` or `httpx` as a healthcheck dependency — both require installing packages not in the base image. Use `wget` or `python -c "import urllib.request; ..."` only.

---

## §5 (filtered) — Load-Bearing Assumptions relevant to TA1

From plan §5.2:

| Claim | Contract surface | Failure mode | Status |
|---|---|---|---|
| `LLMClient.generate(prompt, model=None, **kwargs)` signature stable across callers | §2 Types row "LLMClient", `nlp/pipeline/llm_client.py` | Signature drift breaks SQLGenerator, ResultSynthesizer, QueryClassifier silently | This assumption is preserved — TA1 only changes the internal host wiring inside `_ollama_generate`, not the public `.generate()` signature |
| Docker service name `db` resolves to the db container in `nivii-net` | §2 Naming, `docker-compose.yml` | DNS error on all db→nlp HTTP calls | Unaffected by TA1 |

From plan §5.4:

| Claim | Contract surface | Failure mode | Status | Subtask IDs |
|---|---|---|---|---|
| T4 serializes `PipelineResult` via `dataclasses.asdict()` for HTTP | §2 Types, `nlp/main.py` | Unaffected by TA1 | **confirmed** (unaffected) | T4, T5 |

**TA1-specific assumption (new):**
> If `OLLAMA_URL` is not set in the container environment (e.g., operator launches nlp outside Docker Compose), `LLMClient` raises `KeyError` at import time. This is intentional — a missing `OLLAMA_URL` is a misconfiguration that should fail loudly, not silently degrade to localhost.

---

## §5 (filtered) — Hidden Couplings relevant to TA1

From plan §5.4:

| Coupling | Impact on TA1 |
|---|---|
| `QueryClass` enum keys used in `FEW_SHOT_EXAMPLES` | Unaffected — TA1 does not touch query classification |
| T4 `asdict()` serialization / T5 dict consumption | Unaffected |
| T6 imports `nlp.pipeline.pipeline` transitively | Unaffected — TA1 only changes `llm_client.py` host wiring |

**New coupling introduced by TA1:**
> TA3 must supersede the T4 decision log prose that described OLLAMA_URL as an "acceptable assumption." After TA1 ships, that prose is stale — TA3 must add a supersession banner to `.dev/decision-logs/T4-react-loop-pipeline.md` pointing to `.dev/decision-logs/TA1-ollama-host-wiring.md`.

---

## DoD (Definition of Done)

- [ ] `nlp/pipeline/llm_client.py` uses explicit host from `OLLAMA_URL`; no module-level `ollama.generate()` call without host
- [ ] db healthcheck passes in `docker compose up` without manual intervention
- [ ] `.dev/decision-logs/TA1-ollama-host-wiring.md` exists with both F1 and F2 choice rationale
- [ ] `plan.md` §2 Naming `OLLAMA_URL` row has `Landed:` bullet
- [ ] No existing unit tests broken by host-wiring change (the public `.generate()` signature is unchanged)
