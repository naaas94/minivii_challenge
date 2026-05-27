# Open questions

Backlog for post-demo hardening — not blockers for running the stack.

## Case 11 — recent sales execution

How should case 11 ("recent sales") achieve `execution_pass` — tighter date window, different `query_class`, ReAct observer tuning, or eval expectation change?

**Impact:** `ambiguity_detector.py`, `sql_executor.py`, `eval/harness.py` TEST_CASES case 11

**Closes when:** Post-remediation eval shows case 11 `execution_pass` true, or case is explicitly reclassified as known residual with documented rationale.

**Note:** T2 anchors disambiguation and `ambiguity_pass` passes; `eval_20260527T211111Z` still shows `execution_pass` false with max steps exhausted.

## Read-only SQL on `/execute`

Should `db` `/execute` restrict SQL to read-only (SELECT/WITH) for NL-derived queries?

**Impact:** `db/main.py`, security posture for prompt-injection surface

**Closes when:** Explicit allow/deny policy implemented or accepted as demo-scope risk with documented rationale.

## CPU fallback vs entrypoint model pulls

How should CPU fallback (7b/8b env overrides) stay consistent with `ollama/entrypoint.sh` hardcoded 14b/32b pulls?

**Impact:** `ollama/entrypoint.sh`, `docker-compose.yml`, README CPU fallback section

**Closes when:** Entrypoint reads model names from env, or README documents that CPU fallback requires entrypoint edit, or parameterized compose profile exists.

## Dual DDL sources

Should dual DDL (`db` SCHEMA_DDL vs `domain.yaml` `render_ddl`) be unified or is accepted debt sufficient for submission?

**Impact:** `db/main.py`, `nlp/schema/domain.yaml`, `nlp/pipeline/semantic_layer.py`

**Closes when:** Single source of truth chosen, or explicit "accepted debt" recorded with no `/schema` consumer dependency.

**Note:** Reclassified from blocker to maintainability debt — NLP runtime path uses YAML only; drift affects `/schema` endpoint and manual sync.

## Host-Ollama integration test in Compose

Should host-Ollama routing be integration-tested inside a running Compose stack?

**Impact:** `nlp/tests/test_llm_client.py`, docker-compose CI

**Closes when:** Integration test probes host then container fallback in compose, or gap explicitly accepted with `runtime_performance.md` as manual gate.

**Note:** Unit tests mock urllib probe; no compose-level integration test yet.

## Resolved

- **Schema retrieval vs full injection:** Resolved — demo uses full injection via `SchemaLinker.link()` ignoring question; retrieval documented as README scale-out future work only.
- **OLLAMA_URL vs OLLAMA_HOST Compose wiring:** Resolved 2026-05-27 — `resolve_ollama_url()` probes host Ollama, falls back to container, passes explicit host to `ollama.Client`; compose no longer sets hardcoded `OLLAMA_URL`; `/health` reports resolved URL.
- **db healthcheck curl on slim image:** Resolved 2026-05-27 — compose healthcheck uses wget (TA1).
