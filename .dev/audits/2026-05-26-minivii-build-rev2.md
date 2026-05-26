# Audit Report — minivii-build (Re-Audit)

**Audit document revision:** 2  
**Supersedes:** `.dev/audits/2026-05-26-minivii-build.md` (revision 1, 2026-05-26) for verdict and open-finding status. Revision 1 remains on disk unchanged for traceability.  
**Date:** 2026-05-26  
**Plan:** `.dev/plans/minivii-build/plan.md` — HEAD committed v1.2; working tree v1.3 §8 handoff (uncommitted)  
**HEAD at audit:** `6447a460fbbfc6358b48372dd589927bdf070c8e`  
**Auditor focus areas:** Integration seams (mandatory — post-TA1/TA2 remediation verification), Failure paths (eval gate semantics vs ReAct exhaustion), Edge cases (keyword classifier precedence vs documented eval failures)

---

## 1. Audit metadata

| Field | Value |
|---|---|
| Task | Mini Nivii greenfield init build (T1–T7 + TA1–TA3 remediation) |
| Context map | Absent — greenfield; plan §0 documents deferral (valid) |
| Readiness at planning | READY (per plan §0) |
| Provenance SHA | N/A (no context map) |
| Working tree | **Dirty** — `.dev/plans/minivii-build/plan.md` modified (§8 auditor handoff + v1.3 status not in HEAD) |
| Unit tests run | `cd nlp && pytest tests/ -q` → **46 passed**, 2 `PytestCollectionWarning`; `cd db && pytest tests/ -q` → **2 passed** |
| Re-audit | Yes — follows revision 1 `fail` verdict after TA1/TA2/TA3 |

**Focus rationale:** Revision 1 flagged three stack-breaking integration defects. This pass verifies TA1/TA2/TA3 fixes on current HEAD, then stress-tests whether the eval gate now honestly represents pipeline success (ReAct exhaustion, `execution.success`, classifier precedence).

**Omission-free artifact checklist (surfaces that drove rev1 `fail`):**

| Surface | Opened in re-pass |
|---|---|
| Plan §1–§2, §8 (working tree) | Yes |
| Packets T1–T7, TA1–TA3 | Yes |
| Decision logs T2, T3, T4, TA1 | Yes |
| CHANGELOG.MD | Yes |
| `.dev/execution-logs/T2-db-service.md` | Yes |
| Code: `llm_client.py`, `docker-compose.yml`, `db/Dockerfile`, `db/ingest.py`, `nlp/eval/harness.py`, `pipeline.py` | Yes |
| Tests: full `nlp/tests/`, `db/tests/` | Yes (pytest) |
| Eval artifact `nlp/logs/eval_20260526T204618Z.json` | Yes |
| README §Evaluation + results table | Yes |
| Prior audit rev1 | Yes |

---

## 2. Provenance log

### Context map

- **Path:** absent (greenfield)
- **Verdict:** Plan §0 explicitly documents N/A — **not** a `context-map-missing` violation.

### SHA / staleness

- No context map provenance header.
- Binding artifact `mini-nivii-final-spec.md` present in HEAD.

### Working tree

- **Dirty paths:** `.dev/plans/minivii-build/plan.md` (§8 handoff, version bump 1.2→1.3, TA2 Landed bullet)
- Plan §8.1 claims “clean working tree” at close-out — **contradicted** at audit time.

### Scout grep coverage

- N/A (no context map).

### Plan-artifact provenance (HEAD vs disk)

| Artifact | Status |
|---|---|
| `.dev/plans/minivii-build/plan.md` (committed body) | present-in-HEAD (v1.2) |
| `.dev/plans/minivii-build/plan.md` (§8 handoff) | **on-disk-only** (uncommitted diff) |
| `.dev/plans/minivii-build/packets/T1–T7, TA1–TA3` | present-in-HEAD |
| `.dev/decision-logs/T3, T4, TA1` | present-in-HEAD |
| `.dev/decision-logs/T2.md` | present-in-HEAD |
| `.dev/execution-logs/T2-db-service.md` | present-in-HEAD (TA3) |
| `.dev/audits/2026-05-26-minivii-build.md` | present-in-HEAD |
| `CHANGELOG.MD`, `README.md` | present-in-HEAD |
| `.dev/architecture/minivii/**` | present-in-HEAD (commit `6447a46`) |
| Plan §8 closure SHA | Declared in uncommitted §8 as `6447a46`; matches HEAD |

### Provenance findings

| ID | Sev | Type | Description |
|---|---|---|---|
| P2 | minor | artifact-not-in-HEAD | Plan §8 auditor handoff (v1.3, §8.1–§8.6) exists only in working tree; HEAD plan remains v1.2 without §8. Process close-out incomplete until committed. |

---

## 3. Context chain completeness

| Artifact | Provided | Limits |
|---|---|---|
| Plan §1 + §2 | Yes | Phase 0 |
| Plan §3–§8 (committed + working tree) | Yes | Phase 1+ |
| Packets T1–T7, TA1–TA3 | Yes | Phase 1 |
| Decision logs T2, T3, T4, TA1 | Yes | Phase 3 |
| CHANGELOG.MD | Yes | Phase 1, 3 |
| Prior audit rev1 | Yes | Finding status table |
| Codebase + tests | Yes | All phases |
| Eval JSON on disk | Yes (`nlp/logs/eval_20260526T204618Z.json`) | Not in git (gitignored `logs/`) |
| Live full-stack `docker compose up` | Not executed | Compose boot adversarial scenarios marked **unknown** where not code-verifiable |
| Context map | Absent (documented) | Scout-prediction table empty |

**Phase 0 discipline:** Cold-read completed before reading decision logs, CHANGELOG, plan §3–§7 prose, and rev1 narrative sections.

---

## 4. Cold-read log (pinned — revision 2)

| ID | Sev (guess) | Finding |
|---|---|---|
| RC1 | — | TA1 appears fixed: `ollama.Client(host=os.environ["OLLAMA_URL"])` in `llm_client.py`. |
| RC2 | — | TA1 appears fixed: db healthcheck uses `wget`; Dockerfile installs `wget`. |
| RC3 | — | TA2 appears fixed: `DELETE FROM sales` before insert; row-count guard in `ingest.py`. |
| RC4 | — | TA2 appears fixed: eval asserts `class_pass`, `ambiguity_pass`, `case_pass`; README documents container `python -m eval.harness`. |
| RC5 | major | `case_pass` does not consult `pipeline_result.execution.success`; case 11 can PASS with `failure_reason: max steps reached`. |
| RC6 | major | Case 1: classifier returns `time_filter` (`on friday`) while `expected_class` is `aggregation` — documented in README but gate still fails class dimension. |
| RC7 | major | Case 12: structural SQL missing `total < 0` — documented known failure. |
| RC8 | minor | `nlp/main.py` health uses `os.environ.get("OLLAMA_URL", default)` while inference path requires env and raises `KeyError` — asymmetric typed surface. |
| RC9 | minor | `check_ambiguity(10)` only requires non-empty `interpretations`, not SUM(quantity) in SQL or resolved text. |
| RC10 | observation | `TestCase` dataclass triggers pytest collection warnings in two test modules. |
| RC11 | observation | README eval environment cites `qwen3:30b`; compose pins `qwen3:32b`. |

---

## 5. Findings table

| ID | Sev | Type | Phase | Subtask | One-line description |
|---|---|---|---|---|---|
| **R2-1** | major | contract-violation | 2 | T6 | Plan §2 requires eval to check `execution.success`; `case_pass` ignores failed ReAct (case 11 passes with max-steps failure) |
| **R2-2** | major | intent-drift | 1, 5 | T3/T6 | Case 1: `on friday` keyword wins over aggregation semantics; 10/12 `case_pass` not green gate |
| **R2-3** | major | coverage-gap | 5 | T6 | Case 12 returns SQL without `total < 0`; structural gate correctly fails — no fix, documented only |
| **R2-4** | minor | coverage-gap | 5 | T6 | `check_ambiguity` for case 10 does not assert SUM(quantity) disambiguation in SQL (plan §2 ResolvedQuestion row) |
| **R2-5** | minor | artifact-not-in-HEAD | 0.5 | T7 | Plan §8 handoff (v1.3) uncommitted; §8.1 “clean tree” claim false at audit time |
| **R2-6** | minor | contract-violation | 2 | T4 | `nlp/main.py` health endpoint defaults `OLLAMA_URL` if unset; inference path has no default |
| **R2-7** | minor | process-violation | 5 | T6/T7 | Full judge eval (`skip_judge=False`) not archived; README documents structural-only run |
| **R2-8** | minor | coverage-gap | 5 | T2 | Malformed CSV date still crashes startup unhandled (deferred in CHANGELOG) |
| **R2-9** | minor | coverage-gap | 5 | T4 | No multi-step ReAct refinement unit test (deferred to eval; eval does not assert success) |
| **R2-10** | observation | intent-drift | T1 | CPU fallback env documented; `ollama/entrypoint.sh` always pulls 14B+32B |
| **R2-11** | observation | — | — | README eval notes `qwen3:30b` vs compose `qwen3:32b` |
| **R2-12** | observation | — | — | PytestCollectionWarning on `eval.harness.TestCase` |

---

## 6. Detailed findings (major+)

### R2-1 — Eval `case_pass` ignores `execution.success` (major)

**Expected (plan §2 Types — `ExecutionResult`):** “T6 eval: all cases check `result.success`, `result.steps_taken`”

**Found:** `run_eval` sets `case_pass = sql_score["pass"] and class_pass and ambiguity_pass`. It records `steps_taken` and `failure_reason` in the result dict but never gates on `pipeline_result.execution.success`.

**Evidence:** `nlp/eval/harness.py:227-228`; `nlp/logs/eval_20260526T204618Z.json` case 11 — `"case_pass": true` with `"failure_reason": "max steps reached without successful result"`.

**Impact:** ReAct exhaustion can ship as PASS when substring checks happen to match SQL from a failed last attempt. Undermines the validation-loop story in the submission README.

**Classification:** contract-violation (plan stricter than spec pseudocode; executor followed TA2 structural gate, not plan §2 execution row).

---

### R2-2 — Classifier precedence vs case 1 + incomplete final-pass gate (major)

**Expected:** Eval as primary correctness signal; class checks per plan §2.

**Found:** Live structural run: **10/12 `case_pass`**, **11/12 `sql_pass`**, **11/12 `class_pass`**. Case 1 fails `class_pass` because `KEYWORD_CLASS_MAP` iterates `TIME_FILTER` before `AGGREGATION` and `"on friday"` matches before `"most"`. README documents this; harness metadata for case 1 still lists `expected_class="aggregation"`.

**Evidence:** `nlp/pipeline/query_classifier.py:59-63`; eval JSON case 1; README §Evaluation Results table.

**Impact:** Not stack-breaking (SQL often still correct), but the advertised “final-pass gate” is not green and the classifier design contradicts case 1 metadata unless expectations or keyword order are reconciled (TA2 fixed cases 2/8 only).

**Classification:** intent-drift (keyword heuristic vs eval metadata) + residual process gap vs rev1 F9.

---

### R2-3 — Case 12 structural SQL failure (major as known risk, documented)

**Expected:** Case 12 clauses include `total < 0` for returns.

**Found:** Generated SQL omits negative-total filter; `sql_pass: false`, `case_pass: false`. README lists as known failure.

**Evidence:** `nlp/logs/eval_20260526T204618Z.json` case 12; README row 12.

**Impact:** Returns analytics query class not validated end-to-end. Acceptable for **pass-with-conditions** only because failure is explicit in README; still a coverage gap on a spec eval case.

**Classification:** coverage-gap (known, documented).

---

## 7. Adversarial test log

| Scenario | Expected | Actual | Result |
|---|---|---|---|
| nlp → ollama in Compose | `OLLAMA_URL` drives `Client(host=...)` | `llm_client._ollama_client()` uses `os.environ["OLLAMA_URL"]`; unit test mocks path | **pass** (F1 resolved) |
| db healthcheck → nlp startup | db reaches healthy | `wget` in image + compose probe | **pass** (F2 resolved) |
| Docker eval entrypoint | Container command works | `python -m eval.harness` in README + contract test | **pass** (F3 resolved) |
| db restart idempotency | `row_count` stays 24212 | `DELETE FROM sales` + count guard; `db/tests/test_ingest.py` | **pass** (F4 resolved) |
| Eval class assertions | Per-case `expected_class` | `check_class_match` in `run_eval` | **pass** (F5 resolved) |
| Ambiguity cases 10/11 gate | End-to-end disambiguation signal | Non-empty `interpretations` / resolved≠question only | **partial** (F6 partially resolved — R2-4) |
| T2 execution log archaeology | CHANGELOG cite resolves | `.dev/execution-logs/T2-db-service.md` in HEAD | **pass** (F7 resolved) |
| Eval records execution success | `case_pass` requires success | Case 11 PASS with max-steps failure | **fail** (R2-1) |
| nlp `_try_execute` wire format | Exact db envelope keys | Implemented + unit tests | **pass** |
| ReAct enum path | No string sentinel | `Action` / `ObservationResult` | **pass** |
| Full Compose `docker compose up` | Stack boots without manual env | Not run in audit | **unknown** |
| Malformed CSV at ingest | Loud handled error | `strptime` uncaught → startup crash | **fail** (deferred, R2-8) |

**Integration seams waiver:** Not waived — four-container seams were re-tested; TA1/TA2 closed the rev1 critical path in code inspection + unit tests.

---

## 8. Coverage gap list (prioritized)

1. **Assert `execution.success` in `case_pass`** (R2-1) — highest priority; closes plan §2 ExecutionResult row honestly.
2. **Reconcile case 1 class** — reorder keywords, split day-of-week from TIME_FILTER bucket, or change `expected_class` to `time_filter` with spec justification (R2-2).
3. **Case 12 returns filter** — prompt/few-shot or post-SQL check for negative `total` (R2-3).
4. **Case 10 ambiguity depth** — assert `sum(quantity)` in SQL or resolved qualifier text, not only `interpretations` non-empty (R2-4).
5. **Commit plan §8** or amend §8.1 tree claim (R2-5).
6. **Full judge eval run** archived (`skip_judge=False`) — R2-7.
7. **Compose integration smoke** — one scripted health + `/query` (deferred from TA1/TA3).
8. **Malformed CSV date** — R2-8.
9. **Multi-step ReAct mock test** — R2-9.

---

## 9. Phase 1 — Intent traceability (summary)

| Layer | Assessment |
|---|---|
| Task statement → plan | Faithful; four containers, pipeline stages, eval, README delivered |
| Non-goals | Respected — no CI, no LLM ambiguity detector, single `sales` table |
| TA1–TA3 → rev1 findings | Critical integration findings addressed in code |
| Cold-read vs narrative | TA1/TA3 decision logs align with RC1–RC4; no concealment of R2-1 (not mentioned in CHANGELOG — new gap) |
| Plan §2 vs spec §7 eval | Plan added `query_class` + execution checks; executor exceeded spec on class/ambiguity (TA2) but not on `success` (R2-1) |
| Packet → diff | TA packets match remediation commits; T7 `test_readme_contract.py` beneficial drift |

---

## 10. Phase 2 — Contract compliance (summary)

| Contract surface | Status |
|---|---|
| Types / paths | Shipped at declared locations |
| `quantity REAL` | DDL + ingest |
| db / nlp error envelopes | Match §2 |
| `OLLAMA_URL` inference path | **Closed** (TA1) |
| Eval container command literal | **Closed** (TA2) |
| JSONL 11-field schema | **Closed** (TA3) — `pipeline._log` exact keys |
| Eval checks `execution.success` | **Open** (R2-1) |
| `test_resolve_ambiguity` | Present (`test_ambiguity_detector.py:38`) |

---

## 11. Phase 3 — Decision log audit (summary)

| Log | Verdict |
|---|---|
| TA1 | Accurate; matches `llm_client.py` and db Dockerfile |
| T4 | TA1 supersession banner present at top; stale OLLAMA assumption no longer operative |
| T3 | Matches code |
| T2 | Informal but adequate for standard tier |

No architectural-tier log missing for T3/T4/TA1.

---

## 12. Finding status vs prior revision (revision 1)

| Prior ID | Prior Sev | Prior Type | Status | Evidence at HEAD |
|---|---|---|---|---|
| F1 | critical | contract-violation | **resolved** | `llm_client._ollama_client()` + `test_llm_client.py` |
| F2 | critical | adversarial-fail | **resolved** | `wget` in `db/Dockerfile` + compose healthcheck |
| F3 | major | contract-violation | **resolved** | README + `test_eval_harness_run_command` |
| F4 | major | adversarial-fail | **resolved** | `DELETE FROM sales` + `db/tests/test_ingest.py` |
| F5 | major | contract-violation | **resolved** | `check_class_match` in `run_eval` |
| F6 | major | coverage-gap | **superseded** | `check_ambiguity` added; narrowed gap → **R2-4** (weaker than spec intent) |
| F7 | major | artifact-missing | **resolved** | `.dev/execution-logs/T2-db-service.md` in HEAD |
| F8 | major | intent-drift | **superseded** | Cases 2/8 reconciled; case 1 remains → **R2-2** |
| F9 | major | process-violation | **superseded** | README archives 10/12 structural run; not full green → **R2-2**, **R2-7** |
| F10 | minor | contract-violation | **resolved** | Extra JSONL keys removed |
| F11 | minor | contract-violation | **resolved** | `test_resolve_ambiguity` exists |
| F12 | minor | intent-drift | **resolved** | README 10 columns + `ticket_prefix` |
| F13 | minor | decision-log-stale | **resolved** | T4 banner + TA1 log |
| F14 | minor | process-violation | **open** | T2 log still informal (acceptable observation) |
| F15 | observation | intent-drift | **open** | `ollama/entrypoint.sh` unchanged → **R2-10** |
| F16 | observation | undeclared-change | **resolved** | `.dev/architecture/minivii/` now tracked in HEAD |

---

## 13. Scout-prediction reconciliation

No context map — table empty per skill requirement.

---

## 14. Verdict

### **`pass-with-conditions`**

All **critical** revision-1 findings (F1–F2) are **resolved** on current HEAD. The Compose integration path is code-correct for Ollama host wiring and db healthcheck. TA2 eval and db idempotency fixes hold under unit tests and the archived structural eval JSON.

**Conditions before treating submission as merge-ready without caveat:**

1. **R2-1** — Add `execution.success` (and optionally require `failure_reason is None`) to `case_pass`; re-run eval so case 11 cannot PASS on max-steps failure.
2. **R2-2** — Either fix classifier precedence for case 1 or align `expected_class` + README to the heuristic truth; target ≥11/12 `case_pass` or document explicit waiver in plan.
3. **R2-3** — Fix case 12 SQL generation or accept as documented known gap with eval row marked waived.
4. **R2-5** — Commit plan §8 handoff (v1.3) or remove inaccurate “clean tree” claim.

**Strengths preserved from rev1:** ReAct `Action` enum design, db↔nlp wire format, ambiguity unit tests, UI 600s timeout, README as submission artifact with honest partial eval table (major improvement over rev1 F9).

**Not re-failed:** Stack should boot in Compose assuming `data.csv` present and Ollama models pulled — not live-verified in this audit.

---

## 15. Finding status vs prior revision (re-audit only)

N/A — this section duplicates §12 for skill template compliance; authoritative table is §12.
