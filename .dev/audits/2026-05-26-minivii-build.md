# Audit Report — minivii-build (Initial Build)

**Audit document revision:** 1 (initial)  
**Date:** 2026-05-26  
**Plan:** `.dev/plans/minivii-build/plan.md` v1.0 (validation checklist claims v1.1)  
**HEAD at audit:** `5ce134bd87324a3d27ece224a207a557d1756b7b`  
**Auditor focus areas:** Integration seams (mandatory), Failure paths (db lifecycle / startup), Edge cases (classifier heuristics vs eval expectations)

---

## 1. Audit metadata

| Field | Value |
|---|---|
| Task | Mini Nivii greenfield init build (T1–T7) |
| Context map | Absent — greenfield; plan §0 documents deferral (valid) |
| Readiness at planning | READY (per plan §0) |
| Provenance SHA | N/A (no context map) |
| Working tree | Dirty — `.dev/architecture/` untracked (12 files) |
| Unit tests run | `cd nlp && pytest tests/ -q` → **39 passed**, 1 PytestCollectionWarning |
| Re-audit | No prior audit |

**Focus rationale:** This is a four-container NL-SQL system whose correctness lives at integration seams (Docker health, Ollama host wiring, db wire format, eval entrypoint). Cold read surfaced three stack-breaking issues before narrative review; adversarial pass concentrated on those plus db idempotency and eval contract gaps.

---

## 2. Provenance log

### Context map

- **Path:** absent (greenfield)
- **Verdict:** Plan §0 explicitly documents N/A — **not** a `context-map-missing` violation.

### SHA / staleness

- No context map provenance header to compare.
- Plan binding artifact `mini-nivii-final-spec.md` present in HEAD.

### Working tree

- **Dirty paths:** `.dev/architecture/**` (untracked, not declared as plan deliverable)
- No scout-flagged items affected.

### Scout grep coverage

- N/A (no context map).

### Plan-artifact provenance (HEAD vs disk)

| Artifact | Status |
|---|---|
| `.dev/plans/minivii-build/plan.md` | present-in-HEAD |
| `.dev/plans/minivii-build/packets/T1–T7.md` | present-in-HEAD |
| `.dev/decision-logs/T3-nlp-pipeline-core.md` | present-in-HEAD |
| `.dev/decision-logs/T4-react-loop-pipeline.md` | present-in-HEAD |
| `.dev/decision-logs/T2.md` | present-in-HEAD (informal format) |
| `CHANGELOG.MD` | present-in-HEAD |
| `README.md` | present-in-HEAD |
| `.dev/execution-logs/T2-db-service.md` | **absent-from-disk** (cited in CHANGELOG) |
| `.dev/architecture/minivii/**` | on-disk-only (untracked) |
| Plan §8 closure SHA | not declared in plan |

### Provenance findings

| ID | Sev | Type | Description |
|---|---|---|---|
| P1 | major | artifact-missing | CHANGELOG.MD references `.dev/execution-logs/T2-db-service.md` as T2 kill-criteria evidence; file does not exist on disk or in HEAD. |

---

## 3. Context chain completeness

| Artifact | Provided | Limits |
|---|---|---|
| Plan §1 task statement + §2 contracts | Yes | Phase 0 inputs |
| Plan §3–§8 (full prose) | Yes | Phase 1+ |
| Packets T1–T7 | Yes | Phase 1 |
| Decision logs T2, T3, T4 | Yes (T2 informal) | Phase 3 |
| CHANGELOG.MD | Yes | Phase 1, 3 |
| Codebase (T1–T7 commits) | Yes | All phases |
| Unit tests | Yes (39 tests) | Phase 2, 5 |
| Eval JSON reports | Referenced in terminal history; files gitignored / not in workspace read | Phase 4, 5 — cannot re-verify case-level failure reasons from artifacts |
| Context map | Absent (documented greenfield) | Scout-prediction table empty |
| Live Docker / GPU eval run | Not executed in this audit | Adversarial scenarios for full stack marked **unknown** where noted |

**Phase 0 discipline:** Cold-read completed before reading decision logs, CHANGELOG, or plan §3–§8.

---

## 4. Cold-read log (pinned)

| ID | Sev (guess) | Finding |
|---|---|---|
| C1 | critical | `LLMClient` calls `ollama.generate()` with no host configuration; compose sets `OLLAMA_URL` but Ollama Python SDK reads `OLLAMA_HOST` (defaults `127.0.0.1:11434`). NLP container cannot reach `ollama` service. |
| C2 | critical | `docker-compose.yml` db healthcheck uses `curl`; `db/Dockerfile` is `python:3.11-slim` with no `curl` install. Healthcheck likely never passes → `nlp depends_on: db: service_healthy` blocks stack. |
| C3 | major | README / plan eval entrypoint `python -m nlp.eval.harness` mismatches Docker layout: nlp image copies package contents to `/app` (modules `eval`, `pipeline`), not `/app/nlp/`. Container command should be `python -m eval.harness`. |
| C4 | major | `db/ingest.py` inserts all CSV rows on every startup with no truncate/dedup; container restart doubles `row_count`. |
| C5 | major | Eval harness records `expected_class` on each `TestCase` but never asserts `pipeline_result.query_class == case.expected_class` despite plan §2 contract table. |
| C6 | minor | JSONL logging writes extra keys (`class`, `method`, `success`, `steps_taken`) beyond §2 Logging schema. |
| C7 | observation | `ollama/entrypoint.sh` hard-pulls `qwen2.5-coder:14b` and `qwen3:32b`; CPU fallback env vars change nlp models but not ollama pulls. |
| C8 | observation | Terminal history shows local eval run: 12/12 structural FAIL (environment likely missing db/Ollama). |

---

## 5. Findings table

| ID | Sev | Type | Phase | Subtask | One-line description |
|---|---|---|---|---|---|
| F1 | **critical** | contract-violation | 2, 4 | T3/T4 | `OLLAMA_URL` env var not wired to Ollama SDK (`OLLAMA_HOST`); LLM calls hit localhost inside nlp container |
| F2 | **critical** | adversarial-fail | 4 | T1/T2 | db healthcheck requires `curl` missing from db image; stack startup blocked |
| F3 | major | contract-violation | 2 | T6/T7 | Docker eval command `python -m nlp.eval.harness` wrong for container module layout |
| F4 | major | adversarial-fail | 4 | T2 | CSV re-ingestion on every db startup duplicates rows |
| F5 | major | contract-violation | 2 | T6 | Eval never asserts `query_class` against `expected_class` (plan §2 Types row) |
| F6 | major | coverage-gap | 5 | T6 | No eval assertion for ambiguity resolution on cases 10/11 (plan §2 binds to case 10) |
| F7 | major | artifact-missing | 0.5 | T2 | CHANGELOG cites missing `.dev/execution-logs/T2-db-service.md` |
| F8 | major | intent-drift | 1, 5 | T6 | Test cases 2/8 label `expected_class=simple` but classifier heuristic `"how many"` → `aggregation` |
| F9 | major | process-violation | 5 | T6/T7 | Eval gate declared but no documented passing run; terminal shows 12/12 FAIL |
| F10 | minor | contract-violation | 2 | T4 | JSONL log records include fields outside §2 Logging schema |
| F11 | minor | contract-violation | 2 | T3 | Plan §2 cites unit test `test_resolve_ambiguity`; shipped tests use `test_resolve_*` names |
| F12 | minor | intent-drift | 1 | T7 | README dataset table lists 9 columns; schema has 10 (`ticket_prefix` omitted) |
| F13 | minor | decision-log-stale | 3 | T4 | T4 log states OLLAMA_URL assumption is acceptable; runtime failure contradicts without supersession banner |
| F14 | minor | process-violation | 3 | T2 | T2 decision log is informal paste, not architectural-tier format |
| F15 | observation | intent-drift | 1 | T1 | CPU fallback documented in README but ollama entrypoint always pulls 14B+32B models |
| F16 | observation | undeclared-change | — | — | `.dev/architecture/minivii/` exists untracked (post-build; not in plan scope) |

---

## 6. Detailed findings (major+)

### F1 — OLLAMA_URL not wired to Ollama SDK (critical)

**Expected (plan §2 Naming, spec):** nlp reads `OLLAMA_URL=http://ollama:11434` from compose; all inference local via Ollama service.

**Found:** `nlp/main.py` reads `OLLAMA_URL` only for `/health` display. `LLMClient._ollama_generate` calls module-level `ollama.generate()` which uses `Client()` defaulting to `OLLAMA_HOST` → `http://127.0.0.1:11434` when unset.

**Evidence:**
- `docker-compose.yml` sets `OLLAMA_URL`, not `OLLAMA_HOST`
- `nlp/pipeline/llm_client.py:14-18` — no host parameter
- Ollama SDK `_parse_host(None)` → `http://127.0.0.1:11434`

**Impact:** In Docker Compose, SQL generation, refinement, classification fallback, synthesis, and eval judge all fail to connect unless operator manually sets `OLLAMA_HOST`. T4 decision log documents this as an assumption but does not banner-supersede the failure mode.

**Classification:** contract-violation (typed env surface `OLLAMA_URL` admitted in compose but not consumed on inference path).

---

### F2 — db healthcheck curl missing (critical)

**Expected:** db becomes `service_healthy`; nlp starts after db + ollama healthy.

**Found:** `docker-compose.yml` healthcheck: `curl -sf http://localhost:8001/health`. `db/Dockerfile` installs only FastAPI stack — no `curl`.

**Evidence:** CHANGELOG and T2 decision log acknowledge this cross-task flag but neither T1 amendment nor T7 fixed it.

**Impact:** db may never reach healthy state → nlp blocked indefinitely on `depends_on: condition: service_healthy`.

**Classification:** adversarial-fail at integration seam (confirmed coupling from plan §5.2 `data.csv` mount + db startup).

---

### F3 — Eval Docker entrypoint module path (major)

**Expected (plan §2 Tests, README):** `docker compose exec nlp python -m nlp.eval.harness`

**Found:** nlp `Dockerfile` sets `WORKDIR /app` and `COPY . .` from `./nlp` context → top-level packages `eval`, `pipeline`, not `nlp.eval`.

**Evidence:**
- From repo root (host): `python -m nlp.eval.harness` works (repo contains `nlp/` directory on PYTHONPATH)
- From `nlp/` dir: `python -m nlp.eval.harness` → `ModuleNotFoundError`
- From `nlp/` dir: `python -m eval.harness` → works
- `nlp/tests/test_readme_contract.py` locks in the incorrect Docker command string

**Impact:** Evaluator following README inside container gets immediate `ModuleNotFoundError`.

---

### F4 — db ingest not idempotent (major)

**Expected:** Stable `row_count: 24212` for health/smoke and analytical correctness.

**Found:** `load_csv_to_db` uses `CREATE TABLE IF NOT EXISTS` then unconditional `INSERT INTO sales VALUES ...` for all rows on every lifespan startup. No `DELETE`, `DROP`, or row-count guard.

**Evidence:** `db/ingest.py:8-45`, `db/main.py:47-51`

**Impact:** Any db container restart corrupts aggregates (double revenue, wrong rankings). ReAct 0-row / cardinality heuristics may misfire on duplicated data.

---

### F5 — Eval does not validate query_class (major)

**Expected (plan §2 Types table):** "T6 eval: each case checks `pipeline_result.query_class` matches expected"

**Found:** `run_eval` records `"class": pipeline_result.query_class` but pass/fail is only `sql_pass` from structural clauses. No comparison to `case.expected_class`.

**Evidence:** `nlp/eval/harness.py:214-223`; grep shows zero `expected_class ==` assertions in eval code.

**Impact:** Classifier regressions (including systematic misclassification of "how many" questions) ship undetected despite contract.

---

### F6 — Ambiguity not validated in eval (major)

**Expected (plan §2 Types row `ResolvedQuestion`):** "T6 eval case 10 (ambiguity triggers)"

**Found:** Harness never inspects `pipeline_result.resolved_question`, `interpretations`, or disambiguation clause effects for cases 10/11. Spec §7 case 10 explicitly requires ambiguity → `SUM(quantity)`.

**Evidence:** Unit tests cover ambiguity in isolation (`test_ambiguity_detector.py`); eval only checks SQL substrings.

**Impact:** Core differentiator (semantics-grounded disambiguation) has no end-to-end gate.

---

### F7 — Missing T2 execution log artifact (major)

**Expected:** CHANGELOG cites `.dev/execution-logs/T2-db-service.md` as kill-criteria evidence.

**Found:** File absent from disk and HEAD.

**Impact:** Post-merge audit archaeology broken for T2 smoke-test claims (`row_count: 24212`).

---

### F8 — expected_class vs classifier heuristic mismatch (major)

**Expected:** Case metadata should be consistent with classifier behavior when class checking is enforced.

**Found:** Cases 2 and 8 set `expected_class="simple"` but questions contain `"how many"`, which is a keyword in `KEYWORD_CLASS_MAP[QueryClass.AGGREGATION]`. Classifier returns `aggregation` before LLM fallback.

**Evidence:** `nlp/pipeline/query_classifier.py:41-47`, `nlp/eval/harness.py` cases 2 and 8.

**Impact:** Even if F5 is fixed, these cases would fail class checks unless keywords or expectations are reconciled. Masks classifier correctness signal.

---

### F9 — Eval gate without passing evidence (major)

**Expected:** 12-case harness is the primary correctness signal / final-pass gate before submission (plan §2 Tests, T7 inputs).

**Found:**
- Commit message: `t1-6 ran - running eval`
- Terminal history: `python -m nlp.eval.harness` → **12/12 FAIL** (structural)
- README documents how to run eval but includes **no results**, pass rates, or known failures
- No eval JSON in repo (gitignored under `logs/`)

**Impact:** Submission artifact chain ends without demonstrated pipeline correctness. Combined with F1/F2, failures may be environmental — but that is exactly what the gate should validate before README polish.

**Classification:** `process-violation` (orchestrator/T7) + `coverage-gap` — kill criterion observability without verification path that was actually green.

---

## 7. Adversarial test log

| Scenario | Expected | Actual | Result |
|---|---|---|---|
| nlp → ollama inference in Compose | Calls `http://ollama:11434` | SDK defaults to `127.0.0.1:11434`; `OLLAMA_URL` ignored | **fail** (F1) |
| db healthcheck → nlp startup | db healthy within retries | `curl` missing in db image | **fail** (F2) |
| Docker eval entrypoint | README command succeeds in nlp container | `python -m nlp.eval.harness` → ModuleNotFoundError | **fail** (F3) |
| db restart idempotency | `row_count` stays 24212 | Re-insert all rows | **fail** (F4) |
| nlp `_try_execute` parses db envelope | Exact keys `columns`, `rows`, `row_count`, `error` | Implemented correctly + unit tested | **pass** |
| ReAct uses enum not string sentinel | `ObservationResult` + `Action` | Implemented; unit tests cover | **pass** |
| Synthesis guard | No LLM on failed/empty execution | Guard + unit tests | **pass** |
| UI 600s timeout | Survives long inference | `httpx.Timeout(600.0)` in `ui/main.py` | **pass** (code-level) |
| Scalar question + 51 rows triggers refine | REFINE action | `_observe_result` heuristic + unit test | **pass** |
| Aggregation legitimately returning 51 rows | Should ACCEPT | Heuristic REFINEs if question contains "total", "most", etc. | **unknown** (needs live data) |
| Full 12-case eval on GPU stack | Majority structural pass | Terminal: 0/12 pass locally; no green report archived | **fail** / **unknown** |
| Malformed CSV date at ingest | Loud failure or handled error | `datetime.strptime` uncaught → startup crash | **fail** (acknowledged deferral) |

**Integration seams waiver:** Not waived — plan §5.4 lists four confirmed couplings; three fail in Docker path (F1, F2, F3).

---

## 8. Coverage gap list (prioritized)

1. **Stack integration smoke test** — single test/script asserting db healthcheck passes, nlp reaches ollama, one `/query` returns 200 with SQL (F1, F2). *Highest priority.*
2. **`query_class` assertion in eval** — plan §2 explicit (F5).
3. **Ambiguity end-to-end checks** — cases 10/11 resolved_question / interpretations (F6).
4. **db idempotency test** — double startup → `row_count == 24212` (F4).
5. **Docker eval command test** — README contract test should assert container-valid module path (F3).
6. **ReAct multi-step refinement** — deferred to T6 per CHANGELOG; still no mocked multi-step test (T4 adversarial gap).
7. **Malformed CSV date** — deferred in CHANGELOG; no test (T2).
8. **Live eval pass rate** — no archived green run (F9).

**Kill-criterion / coverage-scope note:** Plan explicitly waives CI regression but **not** the final-pass gate itself. F9 is a process gap: gate defined, not shown green.

---

## 9. Phase 1 — Intent traceability (summary)

| Layer | Assessment |
|---|---|
| Task statement → plan | Faithful — four containers, pipeline stages, eval harness, README artifact all scoped |
| Non-goals | Respected — no CI, no LLM ambiguity detector, no multi-table schema |
| Subtask → code | T1–T7 deliverables largely present in expected paths |
| Packet files-to-touch → diff | Minor drift: T6 packet mentions `test_cases.py` optional split (inline OK); T7 added `test_readme_contract.py` beyond packet (beneficial) |
| Cold-read reconciliation | T4 decision log partially explains F1 as assumption but does not treat it as HALT — **narrative-concealment risk** on stack-breaking issue (F13) |
| Plan §2 vs spec §7 | Plan added stricter `query_class` check than spec `run_eval` pseudocode — executor followed spec, violated plan §2 (F5) |

**Intent drift (semantic):** "Eval as final-pass gate" in intent → README describes gate but submission does not include results or "blocked on infra" status (F9).

---

## 10. Phase 2 — Contract compliance (summary)

| Contract surface | Status |
|---|---|
| Types dataclasses/enums | Shipped at declared paths; fields match spec |
| `quantity REAL` | DDL + ingest use REAL/float |
| db error envelope | Correct shapes; HTTP 200 on SQL error with body |
| nlp error envelope | HTTP 200 + `{"error"}` on handled failures |
| Env vars in compose | Names match §2 |
| **`OLLAMA_URL` typed admission leg (b→c)** | **Broken** — env set but not consumed on inference path (F1) |
| Eval entrypoint literal | **`python -m nlp.eval.harness` wrong in Docker** (F3) |
| Logging JSONL required fields | Present; extra fields added (F10 minor) |
| Unit tests | 39 pass; naming drift on `test_resolve_ambiguity` (F11) |

---

## 11. Phase 3 — Decision log audit (summary)

| Log | Verdict |
|---|---|
| T3 | Matches code; deferred logging to T4 is accurate |
| T4 | **Stale prose:** "OLLAMA_URL read for health; LLMClient uses default host" describes behavior that breaks Compose — should be banner-superseded or fixed (F13) |
| T2 | Informal paste; documents curl gap and missing data.csv workaround — useful but not architectural-tier standard (F14) |

No architectural subtask shipped without a decision log (T3, T4 OK). T2 was standard tier but got an informal log anyway.

---

## 12. Scout-prediction reconciliation

No context map — table empty per skill requirement.

---

## 13. Verdict

### **`fail`**

Three **critical** stack-breaking issues (F1 Ollama host wiring, F2 db healthcheck curl, and by extension the undeployable default Compose path) must be resolved before merge/submission. Major gaps on eval contract enforcement (F5, F6), db idempotency (F4), Docker eval command (F3), and missing final-pass evidence (F9) should be resolved in the same fix cycle.

**Minimum fix set to re-audit:**
1. Wire Ollama host (`OLLAMA_HOST` from `OLLAMA_URL` or explicit client host in `LLMClient`).
2. Fix db healthcheck (install curl/wget **or** Python-based healthcheck **or** change probe).
3. Align eval entrypoint docs + README contract test with container layout (`python -m eval.harness`).
4. Make db ingest idempotent.
5. Add eval assertions for `query_class` (+ reconcile cases 2/8 keywords) and ambiguity cases 10/11.
6. Run and archive at least one `--skip-judge` eval report on full Compose stack; document results in README.

**Strengths (do not regress):**
- Pipeline decomposition matches DIN-SQL intent; ReAct loop uses structured `Action` enum correctly.
- db ↔ nlp wire format and `_try_execute` parsing are clean with good unit tests.
- Ambiguity composition logic is correct and well unit-tested in isolation.
- UI timeout/spinner pattern matches amended T5 kill criterion.
- README kill-criteria strings (~29 GB, CPU fallback, 10 architecture decisions) verified by tests.

---

## 14. Finding status vs prior revision

N/A — initial audit.
