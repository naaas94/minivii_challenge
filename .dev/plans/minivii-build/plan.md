# Orchestrator Plan — Mini Nivii Build

**Plan name:** `minivii-build`  
**Version:** 1.2  
**Status:** Active — v1.2 amendment cycle (post-audit remediation)  
**Spec source:** `mini-nivii-final-spec.md` (FINAL, corrected from v7)  
**Created:** 2026-05-26

---

## §0. Context Map Intake

No context map exists. This is a **greenfield project** — the repository contains only `mini-nivii-final-spec.md`. All files-to-touch are new creations with paths known from the spec. The binding artifact for this plan is `mini-nivii-final-spec.md` itself, which is committed at repo root.

- **Path consumed:** N/A (greenfield)
- **Readiness verdict:** READY
- **Scope-area labels flagged:** none
- **Context map:** not applicable — all deliverable paths are explicitly defined in the spec

**Binding artifact resolvability:** `mini-nivii-final-spec.md` is at repo root (tracked). All spec sections cited in §2 and §4 resolve to content within that file.

---

## §1. Task Statement

Build Mini Nivii — a domain-scoped, semantics-grounded NL-to-SQL BI agent — from scratch as a Docker Compose application with four containers (`db`, `nlp`, `ui`, `ollama`). The `db` service ingests a 24,212-row POS CSV into SQLite with ISO date normalization and exposes a query API. The `nlp` service implements a multi-stage pipeline (AmbiguityDetector → QueryClassifier → SQLGenerator → SQLExecutor ReAct loop → ResultSynthesizer) backed by two Ollama models (qwen2.5-coder:14b for SQL, qwen3:32b for synthesis). The `ui` service serves a single transparent HTML page showing SQL, result table, and narrative. A 12-case evaluation harness validates the pipeline across all query classes. The README is a submission artifact presenting architectural decisions and tradeoff reasoning.

**Non-goals:**
- Multi-tenant or production-grade deployment (SQLite is intentional for demo scope)
- CI pipeline or automated regression testing (eval harness is a final-pass gate, not continuous)
- LLM-based AmbiguityDetector (rule-based is specified; LLM path is documented as a production enhancement)
- Any external network calls in the submitted system (all inference is local via Ollama)
- Database schema beyond the single `sales` table (no joins, no multi-table queries)

---

## §2. Shared Contracts

All subtask executors are bound by the following. Mark **N/A** only where explicitly noted.

### Types / Interfaces

All dataclasses and enums below must be implemented exactly as specified. Owning subtask, typed surface, and round-trip test are listed.

| Symbol | Owning subtask | Typed surface | Test |
|---|---|---|---|
| `ResolvedQuestion` | T3 | `nlp/pipeline/ambiguity_detector.py` dataclass | T6 eval case 10 (ambiguity triggers); unit test `test_resolve_ambiguity` |
| `QueryClass(Enum)` | T3 | `nlp/pipeline/query_classifier.py` Enum | T6 eval: each case checks `pipeline_result.query_class` matches expected |
| `Action(Enum)` | T4 | `nlp/pipeline/sql_executor.py` Enum | T4 unit path: `ObservationResult(action=Action.ACCEPT, ...)` |
| `ObservationResult` | T4 | `nlp/pipeline/sql_executor.py` dataclass | T4 kill criterion: no string sentinel in `decide_action` path |
| `ExecutionResult` | T4 | `nlp/pipeline/sql_executor.py` dataclass | T6 eval: all cases check `result.success`, `result.steps_taken` |
| `PipelineResult` | T4 | `nlp/pipeline/pipeline.py` dataclass | T5 UI renders all fields; T6 eval reads `.sql`, `.execution`, `.narrative` |
| `TestCase` | T6 | `nlp/eval/harness.py` dataclass | T6 self-referential: harness constructs and runs all 12 cases |
| `JudgeScore` | T6 | `nlp/eval/harness.py` dataclass | T6 `judge_synthesis` returns `JudgeScore(**parse_json(response))` |
| `EvalReport` | T6 | `nlp/eval/harness.py` dataclass | T6 `run_eval` returns `EvalReport(results=[...])` |

**Quantity column type:** `REAL` (not INTEGER) everywhere — DDL, YAML descriptor, Pydantic models if any.

### Error Envelope

| Service | Endpoint | Success shape | Error shape |
|---|---|---|---|
| `db` | `POST /execute` | `{"columns": [...], "rows": [[...], ...], "row_count": N}` | `{"error": "message", "sql": "..."}` |
| `db` | `GET /schema` | `{"ddl": "CREATE TABLE sales (...)"}` | HTTP 500 with `{"error": "..."}` |
| `db` | `GET /health` | `{"status": "ok", "row_count": N}` | HTTP 500 |
| `nlp` | `POST /query` | Serialized `PipelineResult` as JSON | `{"error": "message"}` with HTTP 200 (never 500 for handled errors) |

**Binding rule:** `nlp`'s `_try_execute` (in SQLExecutor) must parse the db `POST /execute` response with exact field names `columns`, `rows`, `row_count`, `error`. Any deviation in T2 is a contract violation.

### Naming

| Symbol | Path | Notes |
|---|---|---|
| Docker services | `db`, `nlp`, `ui`, `ollama` | Used as hostnames in `nivii-net` |
| Docker network | `nivii-net` | Bridge driver |
| Docker volume | `ollama_cache` | Persists model weights |
| Ports | db:8001, nlp:8002, ui:3000, ollama:11434 | Frozen; do not change |
| Env vars (nlp) | `DB_URL`, `OLLAMA_URL`, `SQL_MODEL`, `SYNTHESIS_MODEL` | Set in docker-compose; nlp reads via `os.environ` |
| | | **Landed (TA1):** `OLLAMA_URL` is consumed on the inference path via `ollama.Client(host=os.environ["OLLAMA_URL"])` in `LLMClient._ollama_generate`. Health display in `nlp/main.py` unchanged. Missing `OLLAMA_URL` raises `KeyError` on first Ollama generate call — no silent localhost fallback. See `.dev/decision-logs/TA1-ollama-host-wiring.md`. |
| Models | SQL: `qwen2.5-coder:14b` · Synthesis: `qwen3:32b` | Fallback: `qwen2.5-coder:7b` / `qwen3:8b` for CPU-only |
| nlp package layout | `nlp/pipeline/` for pipeline components, `nlp/eval/` for harness, `nlp/schema/` for YAML | |
| Decision log paths | T3: `.dev/decision-logs/T3-nlp-pipeline-core.md` · T4: `.dev/decision-logs/T4-react-loop-pipeline.md` | Architectural subtask requirement |

### Logging

Every pipeline stage writes a structured JSONL record to `logs/runs/{run_id}.jsonl` (inside the `nlp` container, mounted or ephemeral). Required fields:

```json
{
  "run_id": "<ISO timestamp>",
  "stage": "<stage name>",
  "question": "...",
  "resolved_question": "...",
  "model": "<model name or null>",
  "step": <int or null>,
  "sql_attempted": "<sql or null>",
  "observation_action": "<accept|refine|null>",
  "observation_message": "<str or null>",
  "latency_ms": <int>
}
```

### Tests

- **Framework:** Python standard assert statements + `pytest` (installed in nlp requirements)
- **Location:** `nlp/tests/` for unit tests; `nlp/eval/harness.py` for the 12-case eval harness
- **Naming:** test files `test_*.py`; eval entrypoint `python -m nlp.eval.harness`
- **Coverage expectation:** the 12 eval cases are the primary correctness signal; unit tests for AmbiguityDetector composition logic and SQL extraction (`extract_sql`) are required
- **Eval gate:** run with `skip_judge=False` only in Phase 3 (Ollama). Phase 2 uses `skip_judge=True`. This is not a CI regression suite.

### CLI Surface

No CLI flags. Configuration is via environment variables listed in Naming above.

**CPU-only fallback** (documented in README, not in code):
```
SQL_MODEL=qwen2.5-coder:7b
SYNTHESIS_MODEL=qwen3:8b
```

---

## §3. Dependency DAG

```
T1 (scaffold + infra)
├── T2 (db service)        ─┐
└── T3 (nlp pipeline core) ─┤ parallel after T1
                             ↓
                     T4 (ReAct + synthesis + pipeline + FastAPI)
                     ├── T5 (ui service)         ─┐ parallel after T4
                     └── T6 (eval harness)        ─┘
                                  ↓
                          T7 (README + final)
```

**Parallel groups:**
- `{T2, T3}` — may run in parallel after T1 completes
- `{T5, T6}` — may run in parallel after T4 completes

**Soft dependencies:**
- T4 needs T2's wire format (db API) to implement `_try_execute`, but does not require T2 to be executing. Wire format is frozen in §2. T4 can be implemented while T2 is being written.
- T5 and T6 both need T4 to be complete and importable. They do not conflict with each other (T5 touches `ui/`, T6 touches `nlp/eval/`).

---

## §4. Subtask Specs

---

### T1 — Project Scaffold + Docker Infrastructure

> **Amendment (post-review):** GPU `deploy.resources` block **omitted** from `docker-compose.yml`. The `driver: nvidia` reservation causes unconditional failure on machines without NVIDIA Container Toolkit regardless of runtime GPU presence. Decision: Option 3 — omit entirely. The `ollama/ollama` image detects and uses CUDA at runtime automatically. Kill criterion added to enforce this.

| Field | Value |
|---|---|
| **ID** | T1 |
| **Scope** | Create all directory structure, Dockerfiles, `docker-compose.yml`, `ollama` entrypoint script, `requirements.txt` files, and the YAML semantic layer descriptor. No Python business logic — scaffold only. |
| **Files to touch** | `docker-compose.yml`, `ollama/entrypoint.sh`, `db/Dockerfile`, `db/requirements.txt`, `nlp/Dockerfile`, `nlp/requirements.txt`, `nlp/schema/domain.yaml`, `ui/Dockerfile`, `ui/requirements.txt`, `.gitignore`, directory stubs (`db/`, `nlp/pipeline/`, `nlp/eval/`, `nlp/tests/`, `nlp/logs/`, `nlp/schema/`, `ui/templates/`) |
| **Contract bindings** | All §2 Naming (service names, ports, network, volume, env vars, model names), §2 Error Envelope (env var names used in docker-compose), §2 Logging (log dir convention) |
| **Inputs** | None |
| **Outputs** | Full directory tree runnable with `docker compose build`; `domain.yaml` (verbatim from spec §5.2); `entrypoint.sh` with polling healthcheck + `models_ready` sentinel; `docker-compose.yml` with all services, healthchecks, `depends_on` conditions, env vars |
| **Kill criteria** | HALT if: (1) any port deviates from 8001/8002/3000/11434; (2) `ollama` entrypoint uses `sleep N` instead of polling loop; (3) `nlp depends_on ollama` not `service_healthy`; (4) `models_ready` sentinel deviates from `/tmp/models_ready`; (5) `domain.yaml` deviates from spec §5.2; (6) `data.csv` COPYed instead of volume-mounted; **(7) `docker-compose.yml` includes `deploy.resources.reservations.devices` — must be omitted entirely** |
| **Log tier** | standard |
| **Risks & mitigations** | GPU block omitted from primary compose (Option 3). `ollama/ollama` detects CUDA at runtime — no explicit reservation needed. CPU-only machines work without modification. Document in README. |

---

### T2 — db Service

> **Amendment (post-review):** Startup sequencing specified. `load_csv_to_db` must be called synchronously inside `@app.on_event("startup")` — not via `BackgroundTask` or `asyncio.create_task`. Kill criterion updated.

| Field | Value |
|---|---|
| **ID** | T2 |
| **Scope** | Implement the `db` FastAPI service: CSV ingestion with ISO date normalization, SQLite persistence, and three endpoints (`POST /execute`, `GET /schema`, `GET /health`). |
| **Files to touch** | `db/main.py`, `db/ingest.py` (or inline in main.py), `db/requirements.txt` (add FastAPI, uvicorn, pydantic) |
| **Contract bindings** | §2 Error Envelope (exact JSON shapes for all three endpoints), §2 Naming (port 8001), §2 Types (quantity REAL) |
| **Inputs** | T1 (directory scaffold, Dockerfile, requirements.txt starter) |
| **Outputs** | `db/main.py` implementing all three endpoints; `db/ingest.py` with `load_csv_to_db()` using ISO normalization (verbatim from spec §5.1); DDL includes `ticket_prefix TEXT` column extracted from `ticket_number`; smoke test passes: `GET /health` returns `{"status": "ok", "row_count": 24212}` |
| **Kill criteria** | HALT if: (1) date normalization uses `substr()` instead of `datetime.strptime('%m/%d/%Y')`; (2) `quantity` column type in DDL is INTEGER instead of REAL; (3) `POST /execute` error response omits `"sql"` key; (4) `GET /health` does not include `row_count`; (5) `ticket_prefix` column is missing from DDL; (6) `load_csv_to_db` is not called at container startup (must run before any endpoint serves requests) |
| **Log tier** | standard |
| **Risks & mitigations** | The CSV `data.csv` is volume-mounted read-only at `/app/data.csv`. If the file doesn't exist at startup, the service must fail loudly (not silently). Add an explicit file-existence check before `load_csv_to_db`. |

---

### T3 — NLP Pipeline Core

> **Amendment (post-review):** Scope characterization corrected — "pure-logic, side-effect-free" was misleading. T3 includes live LLM calls (`QueryClassifier._llm_classify`, `SQLGenerator.generate_sql`). "Upstream" means no HTTP calls to `db` and no ReAct loop — not no LLM calls. Kill criterion added for window `FEW_SHOT_EXAMPLES` using `strftime` not `substr`.

| Field | Value |
|---|---|
| **ID** | T3 |
| **Scope** | Implement all upstream pipeline components in `nlp/pipeline/`: `LLMClient`, `SemanticLayer`, `AmbiguityDetector`, `SchemaLinker`, `QueryClassifier`, `SQLGenerator` (including `extract_sql` and `FEW_SHOT_EXAMPLES`). These are the pure-logic, side-effect-free components. |
| **Files to touch** | `nlp/pipeline/__init__.py`, `nlp/pipeline/llm_client.py`, `nlp/pipeline/semantic_layer.py`, `nlp/pipeline/ambiguity_detector.py`, `nlp/pipeline/schema_linker.py`, `nlp/pipeline/query_classifier.py`, `nlp/pipeline/sql_generator.py`, `nlp/tests/test_ambiguity_detector.py`, `nlp/tests/test_sql_generator.py` |
| **Contract bindings** | §2 Types (`ResolvedQuestion`, `QueryClass`), §2 Naming (decision log path), §2 Tests (unit tests for AmbiguityDetector and `extract_sql`) |
| **Inputs** | T1 (directory scaffold, `nlp/schema/domain.yaml`) |
| **Outputs** | All six pipeline component files; unit tests for `detect_and_resolve` (composition logic, non-cascading) and `extract_sql` (markdown fence stripping, SELECT/WITH extraction, semicolon truncation); decision log at `.dev/decision-logs/T3-nlp-pipeline-core.md` |
| **Kill criteria** | HALT if: (1) `detect_and_resolve` cascades rules instead of composing once against original; (2) `QueryClass` enum values deviate; (3) `FEW_SHOT_EXAMPLES` keys don't match all four `QueryClass` members; (4) `extract_sql` raises on no-match; (5) `LLMClient` doesn't support `{"ollama","groq","together"}`; (6) prompt order deviates; **(7) `FEW_SHOT_EXAMPLES[QueryClass.WINDOW]` uses `substr(` instead of `strftime` for date handling**; (8) unit tests require a running LLM |
| **Log tier** | architectural |
| **Risks & mitigations** | `SchemaLinker` is referenced in the spec as injecting the full schema (single table, so "full injection"). Implement as `render_ddl()` passthrough — no retrieval logic needed at this scope. The scale-out to retrieval-augmented linking is a production enhancement documented in the README (not implemented here). HALT if the executor adds ChromaDB or any retrieval dependency to T3. |

---

### T4 — ReAct Loop, Synthesis, Pipeline Orchestration + FastAPI

| Field | Value |
|---|---|
| **ID** | T4 |
| **Scope** | Implement the downstream pipeline components: `SQLExecutor` (ReAct loop with `ObservationResult` enum), `ResultSynthesizer` (with success guard), `Pipeline` (orchestration + structured JSONL logging), and the `nlp` FastAPI service wrapper (`POST /query`). |
| **Files to touch** | `nlp/pipeline/sql_executor.py`, `nlp/pipeline/result_synthesizer.py`, `nlp/pipeline/pipeline.py`, `nlp/main.py` |
| **Contract bindings** | §2 Types (all remaining: `Action`, `ObservationResult`, `ExecutionResult`, `PipelineResult`), §2 Error Envelope (db `POST /execute` response shape parsed by `_try_execute`), §2 Logging (JSONL structure and path), §2 Naming (env vars `DB_URL`, `OLLAMA_URL`, `SQL_MODEL`, `SYNTHESIS_MODEL`), §2 Naming (decision log path) |
| **Inputs** | T3 (all six pipeline components importable), T2 (wire format of `POST /execute` known from §2 — T2 need not be running) |
| **Outputs** | `sql_executor.py` with `execute_react`, `_observe_result`, `_try_execute`, `build_refinement_prompt`; `result_synthesizer.py` with `synthesize` (guarded) and `_build_synthesis_prompt` (truncates to top 10 rows); `pipeline.py` with `PipelineResult` dataclass and `Pipeline.run()`; `nlp/main.py` FastAPI app on port 8002 with `POST /query`; decision log at `.dev/decision-logs/T4-react-loop-pipeline.md` |
| **Kill criteria** | HALT if: (1) `_observe_result` uses string sentinel (`"Accept." in observation`) instead of `ObservationResult` with `Action` enum; (2) `synthesize` calls the LLM when `result.success is False` or `result.data` is empty/None; (3) `build_refinement_prompt` is a stub — must be fully specified per §5.6; (4) `execute_react` default `max_steps` deviates from 4; (5) `_build_synthesis_prompt` does not truncate result data to top 10 rows before injection; (6) `Pipeline.run()` calls `synthesize` outside the `if execution.success and execution.data` guard; (7) `nlp/main.py` returns HTTP 500 for handled pipeline errors (must return HTTP 200 with `{"error": "..."}` in body) |
| **Log tier** | architectural |
| **Risks & mitigations** | `_try_execute` calls the db service over HTTP. Use `httpx` or `requests` with a reasonable timeout (30s). If db is unreachable, return `ExecutionResult(success=False, failure_reason="db unreachable: <error>")` — do not raise. The synthesis temperature is 0.3 (not 0.0); do not change this without documenting rationale. |

---

### T5 — UI Service

> **Amendment (post-review):** httpx timeout made explicit kill criterion. `httpx.AsyncClient(timeout=httpx.Timeout(600.0))` is required — the default 5s read timeout causes `httpx.ReadTimeout` during inference regardless of browser-side spinner state. Serialization clarified: T5 receives a plain dict from `response.json()` and never calls `dataclasses.asdict()`.

| Field | Value |
|---|---|
| **ID** | T5 |
| **Scope** | Implement the `ui` FastAPI + Jinja2 service: single HTML page with NL input, loading state, narrative (bold), SQL (collapsible), result table, and interpretation notes when disambiguation fired. |
| **Files to touch** | `ui/main.py`, `ui/templates/index.html`, `ui/requirements.txt` (add FastAPI, uvicorn, jinja2, httpx) |
| **Contract bindings** | §2 Error Envelope (nlp `/query` response shape), §2 Naming (port 3000, env var `NLP_URL` or hardcoded `http://nlp:8002`), §2 Types (`PipelineResult` field names for template rendering) |
| **Inputs** | T4 (PipelineResult field names: `question`, `resolved_question`, `interpretations`, `query_class`, `sql`, `execution.success`, `execution.data`, `execution.columns`, `execution.steps_taken`, `narrative`) |
| **Outputs** | `ui/main.py` with `GET /` (form) and `POST /` (submit query, render result); `ui/templates/index.html` rendering all required fields; loading state visible during inference; collapsible SQL section; interpretation notes shown when `interpretations` list is non-empty |
| **Kill criteria** | HALT if: (1) UI shows a raw Python traceback or HTTP 500 on any handled error; (2) SQL section is not collapsible; (3) loading/spinner absent; (4) narrative not visually differentiated; **(5) `httpx.AsyncClient` constructed without `timeout=httpx.Timeout(600.0)` — default 5s read timeout fires during inference regardless of spinner** |
| **Log tier** | standard |
| **Risks & mitigations** | Inference latency is 3–7 minutes. Use `async def POST /` with `httpx.AsyncClient(timeout=httpx.Timeout(600.0))`. T5 receives a plain dict from `response.json()` — never holds the dataclass object and never calls `dataclasses.asdict()`. Jinja2 resolves dict keys via dot notation natively. |

---

### T6 — Evaluation Harness

> **Amendment (post-review):** `expected_clauses` pinned for cases 6, 10, and 11 — the three load-bearing disambiguation and date-normalization correctness checks. Kill criteria added to enforce them. Case 6 must have `strftime` in expected and `substr(` in forbidden. Case 10 must have `sum(quantity)` in expected and `sum(total)` in forbidden. Case 11 must have both `where` and `date` in expected.

| Field | Value |
|---|---|
| **ID** | T6 |
| **Scope** | Implement the 12-case evaluation harness: `TestCase` dataclass, `check_sql_structure`, `judge_synthesis`, `run_eval`, and `EvalReport`. All 12 test cases from spec §7 with expected clauses and forbidden clauses. |
| **Files to touch** | `nlp/eval/__init__.py`, `nlp/eval/harness.py`, `nlp/eval/test_cases.py` (or inline in harness.py) |
| **Contract bindings** | §2 Types (`TestCase`, `JudgeScore`, `EvalReport`), §2 Tests (`skip_judge` parameter, eval as final-pass gate), all 12 test cases from spec §7 |
| **Inputs** | T4 (Pipeline importable; `PipelineResult` fields `sql`, `execution.data`, `narrative`, `query_class`, `total_latency_ms`, `execution.steps_taken`, `execution.failure_reason`) |
| **Outputs** | `nlp/eval/harness.py` with all four functions; 12 `TestCase` instances with `expected_clauses` and `forbidden_clauses` filled; `run_eval` writes a JSON report to `logs/eval_{timestamp}.json`; `skip_judge=True` path uses only structural check; `JudgeScore` parsed from synthesis model JSON response |
| **Kill criteria** | HALT if: (1) any test case references a non-POS domain question; (2) `check_sql_structure` uses exact match instead of substring; (3) `judge_synthesis` calls LLM when `narrative` is None; (4) `run_eval` raises unhandled exception per-case; (5) case #1 `expected_clauses` missing `week_day` and `friday`; **(6) case #6 missing `strftime` in expected or missing `substr(` in forbidden**; **(7) case #10 missing `sum(quantity)` in expected or missing `sum(total)` in forbidden**; **(8) case #11 missing `where` and `date` in expected**; (9) `JudgeScore` has no parse fallback |
| **Log tier** | standard |
| **Risks & mitigations** | The judge prompt expects JSON response from the synthesis model. Add `parse_json` with a fallback that returns `JudgeScore(factual_accuracy=0, interpretation_fidelity=0, issues="parse_error")` rather than raising. The full eval (12 cases × synthesis + judge) takes 90–120 min on GPU — the harness should print per-case progress. |

---

### T7 — README + Final Submission Polish

| Field | Value |
|---|---|
| **ID** | T7 |
| **Scope** | Write the README as a submission artifact presenting architecture decisions, tradeoffs, setup instructions, evaluation results, limitations, scale-out section, and production delta. Also do final submission polish: verify `.gitignore` covers logs and `__pycache__`, verify `data.csv` is not committed (volume-mounted only). |
| **Files to touch** | `README.md`, `.gitignore` (final check) |
| **Contract bindings** | §2 Naming (all model names, ports, env vars), §2 Tests (eval harness described as final-pass gate), all architecture decisions from spec §9 |
| **Inputs** | T1 (docker setup), T2 (db design), T3 (pipeline components), T4 (ReAct loop design), T5 (UI), T6 (eval results if available) |
| **Outputs** | `README.md` with: (1) architecture decision table (10 decisions from spec §9); (2) setup instructions including `docker compose up`; (3) `~29 GB` first-run download warning (mandatory, not ~9 GB); (4) CPU-only fallback env var instructions; (5) scale-out section (3 scenarios from spec §9); (6) production delta section; (7) limitations section; (8) eval harness described as final-pass gate |
| **Kill criteria** | HALT if: (1) README states first-run download as anything other than ~29 GB; (2) README omits CPU-only fallback configuration; (3) architecture decision table has fewer than 8 of the 10 decisions from spec §9; (4) `data.csv` appears to be added to git (check `.gitignore`) |
| **Log tier** | standard |
| **Risks & mitigations** | T7 is informational, but incorrect download size warning (§C6 correction) could cause evaluator disk-space failures. This is the highest-impact accuracy requirement in T7. |

---

## §5. Adversarial Pass

### §5.1 Rejected Decompositions

1. **Merge `db` + `nlp` into a single container.** Rejected because: (a) spec §3 explicitly requires 4 containers with distinct service names used as hostnames; (b) the `db` service isolation is a deliberate architectural argument about data-layer separation; (c) the `POST /execute` wire boundary is what enables future db backend swaps (SQLite → Postgres).

2. **Build the full `nlp` pipeline as a single monolithic file.** Rejected because: the `QueryClass` enum and `ResolvedQuestion` dataclass are shared contract surfaces between T3 and T4 components. A monolith would prevent meaningful parallel execution and make the contract boundaries invisible to auditors.

3. **Start Ollama model pulls during `docker compose up` with synchronous wait.** Rejected because: spec §6 explicitly corrects the `sleep 5` approach and mandates a polling loop + `models_ready` sentinel file. The `depends_on: service_healthy` condition for `nlp` is the contract mechanism — any shortcut here causes race conditions on slow machines.

4. **Implement `SchemaLinker` with retrieval (ChromaDB).** Rejected because: spec §5.3 explicitly states "full injection, single table" at this scope, with retrieval-augmented linking called out as a production enhancement. Adding ChromaDB would violate the single-dependency principle and add T3 complexity without benefit at demo scale.

### §5.2 Load-Bearing Assumptions

| Claim | Contract surface | Failure mode | Subtask IDs |
|---|---|---|---|
| `LLMClient.generate(prompt, model=None, **kwargs)` signature is stable across all callers | §2 Types row "LLMClient", `nlp/pipeline/llm_client.py` | SQLGenerator, ResultSynthesizer, QueryClassifier (LLM fallback) all call `.generate()` — signature drift breaks all three silently | T3, T4 |
| db `POST /execute` returns `{"columns": [...], "rows": [[...]], "row_count": N}` on success, `{"error": "...", "sql": "..."}` on failure | §2 Error Envelope row, `db/main.py` | `SQLExecutor._try_execute` parses these exact keys — any deviation produces `KeyError` or silent wrong-field reads | T2, T4 |
| `PipelineResult` field names are stable at the shape defined in §5.9 of spec | §2 Types row "PipelineResult", `nlp/pipeline/pipeline.py` | T5 Jinja2 template renders `{{ result.narrative }}` etc.; T6 eval reads `pipeline_result.sql`, `.execution.data`, `.narrative` — field rename breaks both | T4, T5, T6 |
| Docker service name `db` resolves to the db container in `nivii-net` | §2 Naming row "Docker services", `docker-compose.yml` | `DB_URL=http://db:8001` in nlp env var; if service name changes, all HTTP calls from nlp to db fail with DNS error | T1, T4 |
| `data.csv` exists at `/app/data.csv` in the `db` container at startup | §2 (implicit, from docker-compose volumes), `docker-compose.yml` | `load_csv_to_db` is called on startup and will FileNotFoundError if mount is wrong; entire db service fails to start | T1, T2 |

### §5.3 Highest Re-Plan Risk

**T4 (ReAct loop + synthesis).** The `_observe_result` heuristics (0 rows, >10K rows, scalar indicator check for >50 rows) are rule-based but calibrated against the spec's intuition about the POS dataset. If the actual model's SQL generation patterns produce edge cases not covered by these rules — e.g., an aggregation query that legitimately returns 51 rows — the loop will trigger unnecessary refinement. The `build_refinement_prompt` effectiveness is the highest-uncertainty component: if the model doesn't follow the "fix only the specific problem" instruction, refinement may degrade the SQL.

*Process risk note:* T3 and T4 share the `nlp/pipeline/` directory. If T3 and T4 execute in parallel (which this plan prohibits via the T3→T4 edge), file-system race conditions on `__init__.py` or shared type imports could produce subtle bugs. The sequential constraint is enforced by the DAG.

### §5.4 Hidden Couplings

| Claim | Contract surface | Failure mode | Status | Subtask IDs |
|---|---|---|---|---|
| `QueryClass` enum values `{TIME_FILTER, WINDOW, AGGREGATION, SIMPLE}` used as `FEW_SHOT_EXAMPLES` dict keys in T3 AND as comparison target in T4's SQLGenerator call | §2 Types row "QueryClass", `nlp/pipeline/query_classifier.py` and `nlp/pipeline/sql_generator.py` | If T3 renames any enum member (e.g., `TIME_FILTER` → `TIMEFILTER`), `FEW_SHOT_EXAMPLES[query_class]` in T4's `generate_sql` raises `KeyError` at runtime — not a syntax error, not caught at import | **confirmed** (same dict keyed by enum) | T3, T4 |
| T4 serializes `PipelineResult` via `dataclasses.asdict()` for HTTP; T5 receives plain dict from `response.json()` — Jinja2 resolves `result.execution.data` natively as dict key access | §2 Types rows "PipelineResult" and "ExecutionResult", `nlp/main.py` | If T4 omits `asdict()`, `JSONResponse` fails (dataclass not JSON-serializable). If T5 wrongly calls `asdict()` on the dict it already holds, it raises `TypeError`. Ownership: T4 serializes for wire; T5 consumes wire output only. | **confirmed** | T4, T5 |
| T6 eval harness calls `Pipeline.run(question)` directly (not via HTTP) — so T6 imports from `nlp.pipeline.pipeline`, which transitively imports T3 and T4 components | §2 Types row "Pipeline", `nlp/eval/harness.py` | If T4 is not complete when T6 executes, `import nlp.pipeline.pipeline` will raise `ImportError` — T6 has a hard dependency on T4's files existing | **confirmed** (import chain) | T4, T6 |
| The synthesis prompt truncation logic (top 10 rows) in `_build_synthesis_prompt` (T4) matches the judge prompt truncation in `judge_synthesis` (T6) | §2 implicit (both use `data[:10]` per spec §5.7 and §7) | If T4 changes truncation threshold and T6 uses a different threshold, judge scores may evaluate a different data slice than what the narrative was generated from | **suspected** (spec says 10 in both places; divergence possible if executor changes one without the other) | T4, T6 |

---

## §6. Executor Packets

Packets are saved to `.dev/plans/minivii-build/packets/T{n}.md`. Each packet is self-contained.

- [T1 packet](.dev/plans/minivii-build/packets/T1.md)
- [T2 packet](.dev/plans/minivii-build/packets/T2.md)
- [T3 packet](.dev/plans/minivii-build/packets/T3.md)
- [T4 packet](.dev/plans/minivii-build/packets/T4.md)
- [T5 packet](.dev/plans/minivii-build/packets/T5.md)
- [T6 packet](.dev/plans/minivii-build/packets/T6.md)
- [T7 packet](.dev/plans/minivii-build/packets/T7.md)

**Amendment packets (v1.2 — post-audit):**
- [TA1 packet](.dev/plans/minivii-build/packets/TA1.md) — Infra integration fixes (F1, F2)
- [TA2 packet](.dev/plans/minivii-build/packets/TA2.md) — Eval contract + db idempotency (F3, F4, F5, F6, F8)
- [TA3 packet](.dev/plans/minivii-build/packets/TA3.md) — Artifact & narrative cleanup (F7, F9, F10, F11, F12, F13, F14)

---

## §7. Amendment Subtasks (v1.2 — Post-Audit Remediation)

**Audit source:** `.dev/audits/2026-05-26-minivii-build.md`  
**Verdict:** `fail` — three critical, five major findings must be resolved before submission.  
**Amendment scope:** close all critical and major findings (F1–F9) from the audit; resolve minors in same cycle. No new architectural forks.

### Amendment DAG

```
TA1 (infra integration fixes) ─┐
                                ├──→ TA3 (artifact & narrative)
TA2 (eval + db idempotency)  ─┘
```

**Parallel group:** `{TA1, TA2}` — independent file sets; may execute simultaneously.  
**Sequential:** TA3 requires TA1 (Ollama host fixed, stack bootable) and TA2 (eval assertions landed, db idempotent) to produce a valid archived eval run for F9.

**DAG edges from consumers into amendment nodes:**
- `nlp/pipeline/llm_client.py` → TA1 (F1 fix)
- `docker-compose.yml` / `db/Dockerfile` → TA1 (F2 fix)
- `db/ingest.py` → TA2 (F4 fix)
- `nlp/eval/harness.py` → TA2 (F5, F6, F8 fix)
- `README.md` (eval command) + `nlp/tests/test_readme_contract.py` → TA2 (F3 fix)
- `.dev/decision-logs/T4-react-loop-pipeline.md` → TA3 (F13 supersession)
- `nlp/pipeline/pipeline.py` (JSONL fields) → TA3 (F10 fix)
- `nlp/tests/test_ambiguity_detector.py` → TA3 (F11 fix)
- `README.md` (dataset table + eval results) → TA3 (F12, F9 fix)
- `.dev/execution-logs/T2-db-service.md` → TA3 (F7 create)

---

### TA1 — Infra Integration Fixes

| Field | Value |
|---|---|
| **ID** | TA1 |
| **Scope** | Fix two stack-breaking integration failures: (1) wire `OLLAMA_URL` compose env var to the Ollama Python SDK so LLM calls reach the `ollama` container instead of localhost; (2) fix db healthcheck so the db container reaches `service_healthy` without requiring `curl`. |
| **Files to touch** | `nlp/pipeline/llm_client.py` (F1); `db/Dockerfile` and/or `docker-compose.yml` healthcheck (F2) |
| **Contract bindings** | §2 Naming (`OLLAMA_URL` env var — consumption path now required, not just presence); §2 Error Envelope (db healthcheck must pass so nlp starts) |
| **Inputs** | None — standalone infra fix; no prior amendment subtask required |
| **Outputs** | (1) `LLMClient._ollama_generate` passes explicit host derived from `OLLAMA_URL` to `ollama.Client(host=…)` or sets `OLLAMA_HOST` env before SDK init; (2) db healthcheck probe does not require `curl` — either `wget -q -O- http://localhost:8001/health` (if `wget` added to Dockerfile) or a Python-based probe (`python -c "import urllib.request; …"`) in docker-compose healthcheck; (3) §2 Naming row `OLLAMA_URL` back-annotated with `Landed:` bullet describing the consumption path; (4) TA1 feeds into TA3's supersession of T4 decision log (F13 — T4 log stated OLLAMA_URL assumption as acceptable; must receive supersession banner) |
| **Kill criteria** | HALT if `LLMClient._ollama_generate` still calls module-level `ollama.generate()` without an explicit `host` parameter derived from env; HALT if db healthcheck still uses `curl` and `curl` is not installed in `db/Dockerfile`; HALT if `OLLAMA_HOST` env approach is used but the var is not set in docker-compose before nlp starts; HALT if `OLLAMA_URL` is consumed in health display only and not on the inference path |
| **Log tier** | architectural — `OLLAMA_URL` typed env surface changes from declared-but-unused to consumed-on-inference-path; decision log at `.dev/decision-logs/TA1-ollama-host-wiring.md` |
| **Risks & mitigations** | Two acceptable fixes for F1: (a) `ollama.Client(host=os.environ["OLLAMA_URL"])` — cleanest; (b) `os.environ["OLLAMA_HOST"] = os.environ["OLLAMA_URL"]` set at module load — acceptable if (a) not possible. Either approach must be chosen and documented in the TA1 decision log. Do not silently fall back to localhost if `OLLAMA_URL` is unset — raise `KeyError` loudly. For F2, prefer `wget` in Dockerfile over Python probe if python startup latency is a concern; both are acceptable. |

---

### TA2 — Eval Contract + db Idempotency

| Field | Value |
|---|---|
| **ID** | TA2 |
| **Scope** | Five concurrent fixes: (1) make db ingest idempotent; (2) align eval entrypoint docs with container module layout; (3) add `query_class` assertion to `run_eval`; (4) add ambiguity end-to-end assertions for cases 10 and 11; (5) reconcile cases 2 and 8 `expected_class` with classifier keyword heuristic behavior. |
| **Files to touch** | `db/ingest.py`, `nlp/eval/harness.py`, `README.md` (eval command section), `nlp/tests/test_readme_contract.py` |
| **Contract bindings** | §2 Types (`ResolvedQuestion` — case 10 ambiguity gate; `QueryClass` — per-case assertion); §2 Tests (eval entrypoint literal, eval as final-pass gate) |
| **Inputs** | None — parallel with TA1; no shared files |
| **Outputs** | (1) `load_csv_to_db` truncates (`DELETE FROM sales` or `DROP TABLE IF EXISTS` + recreate) before inserting rows so double-start yields `row_count == 24212`; (2) `run_eval` per-case result includes `class_pass: pipeline_result.query_class == case.expected_class`; overall case passes only if both `sql_pass` and `class_pass` are True; (3) cases 2 and 8 `expected_class` corrected to `QueryClass.AGGREGATION` (matching classifier keyword `"how many"` in `KEYWORD_CLASS_MAP`), OR question text changed to not trigger keyword heuristic — chosen approach documented; (4) cases 10 and 11 add assertion that `resolved_question` or `interpretations` is non-empty (ambiguity fired); (5) README eval section updated to `docker compose exec nlp python -m eval.harness`; `nlp/tests/test_readme_contract.py` README-command assertion updated to match; (6) §2 Tests `Landed:` bullet noting container eval command is `python -m eval.harness` |
| **Kill criteria** | HALT if `load_csv_to_db` still does unconditional INSERT without prior truncation/drop; HALT if `run_eval` still has no per-case comparison of `pipeline_result.query_class` to `case.expected_class`; HALT if cases 2 and 8 would still fail `class_pass` check after fix; HALT if README and README contract test still reference `python -m nlp.eval.harness`; HALT if cases 10/11 add no assertion touching `resolved_question`, `interpretations`, or disambiguation clause |
| **Log tier** | standard |
| **Risks & mitigations** | For cases 2/8 reconciliation: changing `expected_class` to `AGGREGATION` is the low-risk path (matches classifier). Changing the question text carries risk of altering the semantic coverage the case was designed to test. Document the chosen approach. For db idempotency: `DELETE FROM sales` (keep schema) is safer than `DROP TABLE` (re-runs DDL, may affect schema migrations if any). Prefer `DELETE FROM sales` followed by the existing INSERT loop unless schema changes are needed. |

---

### TA3 — Artifact & Narrative Cleanup

| Field | Value |
|---|---|
| **ID** | TA3 |
| **Scope** | Close all remaining minor/artifact findings after TA1 and TA2 are complete: create missing T2 execution log, run and archive a `--skip-judge` eval report, remove extra JSONL fields, rename drifted test functions, fix README dataset table to include `ticket_prefix`, supersede T4 decision log stale prose on OLLAMA_URL. |
| **Files to touch** | `.dev/execution-logs/T2-db-service.md` (create), `nlp/pipeline/pipeline.py` (JSONL fields), `nlp/tests/test_ambiguity_detector.py` (rename), `README.md` (dataset table + eval results section), `.dev/decision-logs/T4-react-loop-pipeline.md` (supersession banner) |
| **Contract bindings** | §2 Logging (JSONL required fields — no extra keys); §2 Tests (unit test naming `test_resolve_ambiguity`); §2 Naming (decision log paths for T4 architectural log) |
| **Inputs** | TA1 (Ollama host wired — LLM inference reaches `ollama` container); TA2 (db idempotent, eval assertions landed, container eval command correct) |
| **Outputs** | (1) `.dev/execution-logs/T2-db-service.md` created with smoke-test evidence (`row_count: 24212`, endpoint responses); (2) `Pipeline._log_stage` emits only the 11 fields from §2 Logging schema — extra keys `class`, `method`, `success`, `steps_taken` removed; (3) ambiguity detector unit test function renamed from `test_resolve_*` pattern to include canonical `test_resolve_ambiguity` (or additional function with that name); (4) README dataset table updated to list 10 columns including `ticket_prefix`; (5) at least one `--skip-judge` eval run executed, results (pass/fail per case, overall structural pass rate) documented in README Evaluation section; (6) T4 decision log receives supersession banner at top citing TA1 as the authority on OLLAMA_URL host wiring; §2 Naming `OLLAMA_URL` row and T4 log both annotated with `Landed:` bullets |
| **Kill criteria** | HALT if T4 decision log still describes `OLLAMA_URL` as acceptable assumption without supersession banner pointing to TA1 decision log; HALT if JSONL records still emit any field not in the §2 Logging 11-field schema; HALT if README dataset table column count still shows 9 (must show 10 with `ticket_prefix`); HALT if TA3 ships without at least one archived `skip_judge=True` eval result documented in README; HALT if `.dev/execution-logs/T2-db-service.md` is still absent |
| **Log tier** | standard |
| **Risks & mitigations** | The eval run (F9) requires TA1 + TA2 to be complete and a running Docker Compose stack with GPU or CPU-only fallback. If the full GPU stack is unavailable, a `skip_judge=True` run on a locally-mocked db (localhost) is acceptable for structural pass-rate evidence — document the environment explicitly. The JSONL field removal (F10) must not break any downstream consumer that reads those extra fields; verify no test asserts their presence before removing. |

---

## Validation Checklist

**Plan version:** 1.1 — post-review amendments applied 2026-05-26. All 7 issues resolved.

- [x] Every subtask has all required fields; no TBD in kill criteria
- [x] DAG has no cycles; T1→{T2∥T3}→T4→{T5∥T6}→T7
- [x] Parallel safety: T2 and T3 touch different directories (`db/` vs `nlp/pipeline/`); T5 and T6 touch different directories (`ui/` vs `nlp/eval/`)
- [x] Adversarial pass includes 4 rejected alternatives and 5 load-bearing assumptions
- [x] Log tiers assigned: T1 standard, T2 standard, T3 architectural, T4 architectural, T5 standard, T6 standard, T7 standard
- [x] Packet emission: complete — T1–T7 at `.dev/plans/minivii-build/packets/`
- [x] Typed-surface binding satisfied: all §2 Types rows have owning subtask, typed surface, test
- [x] CLI strings frozen: env vars named in §2 and frozen against T1 docker-compose output
- [x] Wire contract matches shipped behavior: db error envelope and nlp error envelope defined in §2
- [x] Decision log paths frozen: T3 → `.dev/decision-logs/T3-nlp-pipeline-core.md`; T4 → `.dev/decision-logs/T4-react-loop-pipeline.md`
- [x] §5.2 and §5.4 entries conform to required tuple shape with explicit Tn IDs
- [x] §5 answered using packet-only executor persona lens
- [x] Context map: greenfield — not required

### v1.2 Amendment Record (post-audit)

**Audit:** `.dev/audits/2026-05-26-minivii-build.md` · **Verdict:** `fail`

| # | Sev | Finding | Amendment | Packets |
|---|---|---|---|---|
| B1 | **critical** | F1: `OLLAMA_URL` set in compose but Ollama SDK reads `OLLAMA_HOST` → LLM calls hit localhost | TA1: `LLMClient` wired to explicit host from `OLLAMA_URL`; §2 Naming `Landed:` bullet; TA1 decision log at `.dev/decision-logs/TA1-ollama-host-wiring.md` | TA1.md |
| B2 | **critical** | F2: db healthcheck uses `curl`; missing from `python:3.11-slim` image → db never healthy | TA1: db Dockerfile adds `wget` or docker-compose switches to Python probe | TA1.md |
| B3 | major | F3: README + contract test reference `python -m nlp.eval.harness` which fails inside container (`nlp/` not in PYTHONPATH) | TA2: README and test corrected to `python -m eval.harness`; §2 Tests `Landed:` bullet | TA2.md |
| B4 | major | F4: `load_csv_to_db` unconditional INSERT duplicates rows on restart | TA2: idempotent ingest via `DELETE FROM sales` before insert | TA2.md |
| B5 | major | F5: `run_eval` records `query_class` but never asserts it against `expected_class` | TA2: per-case `class_pass` assertion added; overall pass requires both `sql_pass` and `class_pass` | TA2.md |
| B6 | major | F6: cases 10/11 have no assertion on `resolved_question`/`interpretations` | TA2: ambiguity assertion added for cases 10/11 | TA2.md |
| B7 | major | F7: CHANGELOG cites `.dev/execution-logs/T2-db-service.md` which does not exist | TA3: file created with smoke-test evidence | TA3.md |
| B8 | major | F8: cases 2/8 `expected_class="simple"` but classifier returns `aggregation` for `"how many"` questions | TA2: `expected_class` corrected to `AGGREGATION` or question text adjusted | TA2.md |
| B9 | major | F9: eval gate declared but no passing run documented; terminal shows 12/12 FAIL | TA3: `skip_judge=True` eval run archived; results documented in README | TA3.md |
| B10 | minor | F10: JSONL records emit extra fields outside §2 Logging schema | TA3: extra fields removed from `Pipeline._log_stage` | TA3.md |
| B11 | minor | F11: test naming drift (`test_resolve_*` vs required `test_resolve_ambiguity`) | TA3: canonical name added/restored | TA3.md |
| B12 | minor | F12: README dataset table shows 9 columns, missing `ticket_prefix` | TA3: table updated to 10 columns | TA3.md |
| B13 | minor | F13: T4 decision log describes OLLAMA_URL assumption as acceptable; breaks at runtime | TA3: supersession banner added to T4 log pointing to TA1 decision log | TA3.md |
| B14 | minor | F14: T2 decision log informal format | Acknowledged; not reworked — T2 was standard tier; informal log still useful. No action. | — |

### v1.1 Amendment Record

| # | Severity | Issue | Resolution | Packets updated |
|---|---|---|---|---|
| A1 | **BLOCKING** | T5: httpx default 5s read timeout fires during inference regardless of browser spinner | Kill criterion added: `httpx.Timeout(600.0)` required in `AsyncClient` constructor | T5.md |
| A2 | **BLOCKING** | T1: `deploy.resources.reservations.devices` GPU block fails unconditionally without NVIDIA Container Toolkit | Decision: Option 3 — block omitted. `ollama/ollama` detects CUDA at runtime. Kill criterion (7) added to T1 | T1.md |
| A3 | Structural | T3: "pure-logic, side-effect-free" scope was misleading — `QueryClassifier._llm_classify` and `SQLGenerator.generate_sql` make live LLM calls | Corrected: T3 includes live LLM calls; "upstream" means no db HTTP and no ReAct loop — not no LLM | T3.md |
| A4 | Structural | T6: `expected_clauses` underspecified for cases 10, 11; case 6 was already correct | Cases 10 and 11 pinned; kill criteria (6)–(8) added for cases 6/10/11 | T6.md |
| A5 | Structural | T4/T5: serialization ownership conflated — Jinja2 receives raw dataclass vs. plain dict was ambiguous | Clarified: T4 uses `asdict()` for HTTP wire only; T5 receives `response.json()` dict — no `asdict()` in T5 | T4.md, T5.md |
| A6 | Minor | T2: startup sequencing unspecified — background task could race with first request | Kill criterion added: synchronous `@app.on_event("startup")`; `BackgroundTask` prohibited for ingestion | T2.md |
| A7 | Minor | T3: window `FEW_SHOT_EXAMPLES` not guarded against transcribing the broken v7 `substr()` formula | Kill criterion (7) added: window example must use `strftime`, not `substr(` | T3.md |
