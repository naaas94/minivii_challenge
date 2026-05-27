# Audit Report — eval-remediation

**Date:** 2026-05-27  
**Plan:** `.dev/plans/eval-remediation/plan.md` v1.1 (COMPLETE; **on-disk-only**, not in HEAD)  
**HEAD at audit:** `7e4ce464b160f463ae117180591fed31dcc9d664`  
**Closure SHA (plan §8.1):** `7e4ce464b160f463ae117180591fed31dcc9d664` — matches HEAD  
**Auditor focus areas:** Integration seams (mandatory — scout §Coupling surfaces 1, 3, 5, 9, 11); Failure paths (execution gate vs ReAct exhaustion, exception rows); Regression surface (classifier override narrowness vs case 2 / bare-`most` guard)

---

## 1. Audit metadata

| Field | Value |
|---|---|
| Task | Five-priority eval remediation (Waves 0–4): execution gate, temporal anchor, returns constraint, classifier override, narrative/judge hardening |
| Context map | `.dev/plans/eval-remediation/context-map.md` — CONDITIONAL at planning; **stale** vs HEAD (see §2) |
| Scout SHA | `0f2d79eeaaf542d3ac4a1400056c2364304429f4` |
| Working tree at scout | dirty (`.dev/eval-remediation-strategy.md` untracked) |
| Working tree at audit | dirty (`.dev/eval-remediation-strategy.md`, `.dev/plans/eval-remediation/` untracked) |
| Unit tests run | `pytest nlp/tests/ -x --tb=short -q` → **59 passed**, 2 `PytestCollectionWarning`; `pytest nlp/tests/test_readme_contract.py -q` → **8 passed** |
| Phase 0 discipline | Cold read completed on task §1, plan §2, code diff `0f2d79ee..HEAD`, and tests **before** consuming decision logs, CHANGELOG narrative, or plan §8 prose |

**Focus rationale:** Remediation is a cross-stage seam change (disambiguation suffix → classifier → SQL prompt → harness tiers). Integration-seam stress-testing is mandatory per skill; failure-path focus validates the breaking `case_pass` contract; regression focus targets the narrow `AGGREGATION_OVERRIDES` predicate that guards case 2.

---

## 2. Provenance log

### Context map

| Field | Value |
|---|---|
| Path | `.dev/plans/eval-remediation/context-map.md` |
| Readiness at planning | CONDITIONAL |
| Scout SHA | `0f2d79eeaaf542d3ac4a1400056c2364304429f4` |
| HEAD SHA | `7e4ce464b160f463ae117180591fed31dcc9d664` |
| SHA comparison | **diverged** — 5 remediation commits (`d2a0798`..`7e4ce464`) modified all in-scope Python files after scout |

**Diverged in-scope files (from §File map `direct`):**  
`nlp/eval/harness.py`, `nlp/pipeline/ambiguity_detector.py`, `nlp/pipeline/semantic_layer.py`, `nlp/pipeline/sql_executor.py`, `nlp/pipeline/sql_generator.py`, `nlp/pipeline/query_classifier.py`, `nlp/pipeline/result_synthesizer.py`, `nlp/pipeline/pipeline.py`, `nlp/tests/test_ambiguity_detector.py`, `nlp/tests/test_sql_executor.py`, `nlp/tests/test_sql_generator.py`, `nlp/tests/test_eval_harness.py`, `nlp/tests/test_harness.py`, `nlp/tests/test_query_classifier.py` (new), `nlp/tests/test_result_synthesizer.py`, `README.md`.

### Working tree

| State | Paths |
|---|---|
| Scout-time dirty | `.dev/eval-remediation-strategy.md` (out of code scope) |
| Audit-time dirty | Same strategy doc + entire `.dev/plans/eval-remediation/` tree |

Findings against scout-flagged symbols on diverged files carry **`context-map-stale` caveat** unless re-verified against current HEAD code (this audit re-verified code directly).

### Scout grep coverage

Context map §Coupling surfaces records all patterns required by orchestrator §5.4 contract vocabulary (`AMBIGUITY_TRIGGERS`, `date_range`, `KEYWORD_CLASS_MAP`, `case_pass`, `execution.success`, `--skip-judge`, env vars, etc.). **No `scout-incomplete` finding.**

### Plan-artifact provenance (`git show HEAD:<path>`)

| Artifact | Status at HEAD |
|---|---|
| `.dev/plans/eval-remediation/plan.md` | **on-disk-only** |
| `.dev/plans/eval-remediation/context-map.md` | **on-disk-only** |
| `.dev/plans/eval-remediation/packets/T1–T5.md` | **on-disk-only** |
| `.dev/decision-logs/T1-eval-remediation-phase1.md` | present-in-HEAD |
| `.dev/decision-logs/T2-eval-remediation-temporal.md` | present-in-HEAD |
| `CHANGELOG.MD` (eval-remediation section) | present-in-HEAD |
| `README.md` (tier table edits) | present-in-HEAD |
| `.dev/eval-remediation-strategy.md` | **on-disk-only** (referenced intent; not plan §8 row) |

**Closure SHA verification:** Plan §8.1 records `7e4ce464` — matches HEAD and contains all committed code artifacts. Plan/packet artifacts are **not** in that SHA.

### Provenance findings filed here

| ID | Severity | Type | Description |
|---|---|---|---|
| F-001 | major | `context-map-stale` | Scout SHA `0f2d79ee`; all direct-scope Python files modified in T1–T5. Map predictions for `suspect_modified` symbols are historical. |
| F-002 | major | `artifact-not-in-HEAD` | Entire `.dev/plans/eval-remediation/` (plan, context map, 5 packets) exists on disk but absent from HEAD. Plan §8.2 pre-check acknowledges this; §8 handoff is explicitly incomplete until committed. |

---

## 3. Context chain completeness

| Artifact | Provided | Limits |
|---|---|---|
| Context map | Yes (stale) | File/interface predictions pre-date implementation; coupling tuples still useful for adversarial seeding |
| Pre-plan analysis | Yes (`.dev/eval-remediation-strategy.md`, untracked) | Source intent for five priorities |
| Orchestrator plan | Yes (untracked v1.1) | §0 flag resolutions, §2 contracts, DAG, §8 handoff |
| Shared contracts | Yes (plan §2) | Used in Phase 0 |
| Decision logs | Yes (T1, T2 in HEAD) | T3–T5 standard tier — none required |
| Changelog | Yes (`CHANGELOG.MD`) | Per-subtask narrative + deferred gaps |
| Codebase | Yes (`0f2d79ee..HEAD`, 19 files) | Authoritative |
| Test suite | Yes (59 tests) | No live LLM/DB integration tests |
| Eval logs | Partial | `nlp/logs/eval_20260526T204618Z.json`, `eval_20260527T034521Z.json` — **pre-T1 schema** (no `execution_pass`, no `tier_summary`) |
| Architecture index | Yes (`.dev/architecture/minivii/INDEX.md`) | Stale after 2026-06-25; failure-taxonomy update deferred by plan non-goal |

**Phase 0 completed before narrative artifacts:** Yes.

---

## 4. Cold-read log (pinned)

Issues surfaced from task §1, plan §2, and code/tests only:

1. **CR-1 (major guess):** No eval JSON on disk contains `execution_pass` or `tier_summary` — end-to-end remediation impact unverified at the measurement layer.
2. **CR-2 (minor):** README tier table uses 2026-05-26 run data; case 1/11/12 rows still show pre-fix failure modes after T2–T4 code landed.
3. **CR-3 (observation):** Case 11 resolved string has **zero** `KEYWORD_CLASS_MAP` hits; classification remains LLM-fallback-dependent (`time_filter` in last live log, not guaranteed).
4. **CR-4 (pass):** `case_pass` formula at `harness.py:267–271` matches §2 contract (`sql ∧ class ∧ ambiguity ∧ execution`).
5. **CR-5 (pass):** `get_date_anchor()` validates ISO via `date.fromisoformat` before return; anchored recent window uses digit-only literals (Surface 9 guard).
6. **CR-6 (pass):** `AGGREGATION_OVERRIDES` excludes bare `"most"` / `"how many"`; override requires TIME_FILTER match first — case 2 regression guard present in code and tests.
7. **CR-7 (observation):** Judge and synthesis share `self.synthesis_model` in `judge_synthesis` (`harness.py:242`) — self-judge bias risk unchanged.
8. **CR-8 (question):** `EvalReport` now requires `tier_summary`; only constructed inside `run_eval` — no external caller breakage found.

---

## 5. Findings table

| ID | Sev | Type | Phase | Subtask | Description |
|---|---|---|---|---|---|
| F-001 | major | `context-map-stale` | 0.5 | — | Scout SHA predates all remediation commits on in-scope files |
| F-002 | major | `artifact-not-in-HEAD` | 0.5 | — | Plan, context map, packets untracked; §8 archaeology invalid |
| F-003 | major | `coverage-gap` | 5 | T1–T5 | No post-remediation eval log with new harness fields; strategy tier targets unverified |
| F-004 | major | `coverage-gap` | 5 | T2,T1 | Flag 4 accepted: no integration test that case 11 achieves `execution_pass: true` after anchor |
| F-005 | minor | `intent-drift` | 1 | T1 | README archived run still lists case 1/11/12 as known failures without post-fix re-eval disclaimer beyond tier columns |
| F-006 | minor | `coverage-gap` | 5 | T5 | Judge returns heuristic fires for case 12 (`known_answer=None`) but no isolated test |
| F-007 | minor | `narrative-concealment` | 3 | T5 | CHANGELOG T5 says case 12 judge enrichment "does not fire" — code `_judge_business_rules_block` **does** inject returns rules via question heuristic |
| F-008 | minor | `coverage-gap` | 5 | T2 | No test that `get_date_anchor()` rejects malformed ISO post-load (deferred in T2 log) |
| F-009 | minor | `coverage-gap` | 5 | T3 | No test for false-positive `RETURNS_TRIGGERS` on benign "return customers" phrasing (accepted residual) |
| F-010 | minor | `coverage-gap` | 5 | T4 | No test for override when TIME_FILTER keyword appears only in ISO date suffix on `resolved` (CHANGELOG deferred) |
| F-011 | observation | `intent-drift` | 1 | — | Architecture docs (`failure-taxonomy`, `known-coupling-surfaces`) not updated — explicit plan non-goal |
| F-012 | observation | `adversarial-fail` | 4 | T5 | Self-judge same model (Surface 10) — open, acknowledged in plan §8.4 |

---

## 6. Detailed findings (above minor)

### F-001 — `context-map-stale` (major)

**Expected:** Context map provenance SHA matches implementation commit or plan §0 documents intentional staleness.  
**Found:** Map frozen at `0f2d79ee`; remediation landed in five commits through `7e4ce464`. Plan §0 notes handoff staleness informally but map was not refreshed.  
**Evidence:** `git log 0f2d79ee..HEAD --oneline`; diff stat 19 files / 527 insertions.  
**Impact:** Scout `suspect_modified` / ambiguity-flag predictions cannot be treated as execution ground truth without code re-read (done in this audit).

### F-002 — `artifact-not-in-HEAD` (major)

**Expected:** Plan §8 artifact chain committable via `git show HEAD:<path>`.  
**Found:** `git show HEAD:.dev/plans/eval-remediation/plan.md` → fatal. Same for context map and all packets. Plan §8.2 pre-check explicitly warns.  
**Evidence:** `git status --short` shows `?? .dev/plans/eval-remediation/`; plan §8.2 validity note.  
**Impact:** Post-merge audit archaeology broken; orchestrator closure tree incomplete for process compliance.

### F-003 — `coverage-gap` (major)

**Expected:** After T1–T5, at least one eval artifact demonstrates new harness fields and improved case outcomes per strategy success criteria (§4 targets: case 11 `execution_pass: true`, structural/execution 12/12 aspirational).  
**Found:** Grep across `nlp/logs/eval_*.json` — **zero** files contain `execution_pass` or `tier_summary`. Latest log `eval_20260527T034521Z.json` still uses pre-T1 row shape; case 11 shows `case_pass: true` with `failure_reason: "max steps reached without successful result"` (false composite pass under new formula).  
**Evidence:** `nlp/logs/eval_20260527T034521Z.json` lines 372–397; plan §8.4 coupling #3 status **open**.  
**Impact:** Code + unit tests align with contracts, but **remediation effectiveness is not empirically demonstrated**. Cannot confirm T2 fixed case 11 execution, T4 fixed case 1 class, or T3 fixed case 12 SQL in live stack.

### F-004 — `coverage-gap` (major, plan-waived)

**Expected:** Flag 4 resolution accepted unit-only path; kill criterion / strategy still describe execution proof gap.  
**Found:** `test_ambiguity_detector.py` asserts anchored ISO substring only. `test_eval_harness.py` mocks case 11 with `execution_pass: false` (T1 gate), not `true` (T2 fix). No `@pytest.mark.integration` case-11 execution test.  
**Evidence:** Plan §0 Flag 4 "Accept gap"; T2 decision log adversarial gap; strategy §Success criteria case 11 execution target.  
**Impact:** Known risk shipped with documented waiver — not a contract violation, but highest-priority untested kill-scenario.

---

## 7. Adversarial test log

| # | Focus | Scenario | Expected | Actual | Result |
|---|---|---|---|---|---|
| A-1 | Integration | Case 1 keyword path after T4 | `AGGREGATION`, method `heuristic_override` | `classify("What is the most bought product on Fridays?")` → `aggregation`, `heuristic_override` | **pass** |
| A-2 | Integration | Case 2 regression | `TIME_FILTER`, not overridden | Test + live keyword scan: `"how many"` not in `AGGREGATION_OVERRIDES` | **pass** |
| A-3 | Integration | Bare `"most"` + `"what day"` | Stay `TIME_FILTER` | `test_bare_most_with_what_day_stays_time_filter` | **pass** |
| A-4 | Integration | Surface 9: anchored recent suffix vs classifier | No spurious TIME_FILTER from date literals | Resolved case 11 suffix `date >= '2024-10-21'...` — keyword scan hits **empty**; LLM path used | **pass** (suffix safe; **unknown** LLM stability) |
| A-5 | Integration | Multi-trigger `top recent` + `semantic_layer` | Anchored recent + non-colliding class | Resolved contains both `SUM(total) DESC` and anchored dates; class `aggregation` heuristic | **pass** |
| A-6 | Integration | Surface 5: execution gate on failed ReAct | `execution_pass=false` → `case_pass=false` | Mock tests + pre-T1 log shows old false pass | **pass** (code); **unknown** (live post-T2) |
| A-7 | Failure path | Pipeline exception in `run_eval` | All gates false incl. `execution_pass` | `test_run_eval_isolates_pipeline_failures` | **pass** |
| A-8 | Integration | Surface 11: returns constraint injection | `-- REQUIRED: filter return rows...` before question | `test_returns_prompt_injects_constraint` | **pass** |
| A-9 | Integration | Case 12 judge returns rules without `known_answer` | Returns business rules in judge prompt | `_judge_business_rules_block(case12.question)` length 196, contains `total < 0` | **pass** (implementation); **fail** (no dedicated test — F-006) |
| A-10 | Regression | T3 returns few-shot in AGGREGATION bucket confuses case 1 SQL | case 1 `sql_pass` unchanged | No post-remediation eval | **unknown** (plan §8.4 #3 open) |
| A-11 | Integration | Surface 10 self-judge | Distinct judge model reduces bias | `judge_synthesis` uses `model=self.synthesis_model` | **fail** (open, deferred) |

**§Coupling surfaces disposition:**

| Surface | Scout | Result |
|---|---|---|
| 1 Calendar-relative recent vs static dataset | confirmed | **verified** — T2 anchor replaces apply text when `semantic_layer` passed |
| 3 Class ↔ few-shot ↔ expected_class | confirmed | **verified** for case 1 override; SQL outcome **unknown** without re-eval |
| 5 `case_pass` ignores execution | confirmed | **verified** — T1 closes |
| 9 Resolved suffix → classify | confirmed | **verified** — digit-only anchor suffix; no false TIME_FILTER |
| 11 Returns semantics not enforced | confirmed | **partial** — prompt constraint + few-shot added; live SQL compliance **unknown** |
| 10 Self-judge model | suspected | **confirmed** — same model param |

---

## 8. Coverage gap list (prioritized)

1. **P0 — Full post-remediation eval** (`--skip-judge` minimum) writing JSON with `execution_pass` + `tier_summary`; update README table (F-003).
2. **P1 — Case 11 execution integration** after T2 anchor (F-004; plan-waived but strategy-critical).
3. **P2 — Judge returns heuristic** without `known_answer` (F-006; implementation exists).
4. **P3 — Deferred unit gaps** from CHANGELOG/T2 log: malformed ISO anchor (F-008), returns false positive (F-009), classifier + date suffix (F-010).
5. **P4 — Distinct `JUDGE_MODEL`** env (F-012 / Surface 10) — out of plan scope.

---

## 9. Intent traceability (Phase 1 summary)

| Layer | Assessment |
|---|---|
| Task §1 → plan §1 | Faithful — five priorities mapped to T1–T5 waves |
| Plan non-goals | Respected — no `result_assertions`, no SQL post-processor, no architecture doc edits, no UI/db/infra changes |
| Flag resolutions §0 | Landed: Flag 1 C both layers, Flag 6 breaking `case_pass`, Flag 3 new classifier tests, Flag 8 P1-A+B only, Flag 5 deferred |
| Packet files-to-touch → diff | Clean per commit: T1 (6 files), T2 (8), T3 (3), T4 (3), T5 (5); no undeclared production files |
| §2 contracts → code | **All 14 typed rows verified** (see plan §8.3; auditor independently confirmed line refs) |
| Cold-read reconciliation | CR-1/2 acknowledged in plan §8.4 and T1 decision log; not concealed. CR-7 acknowledged open. F-007: CHANGELOG overstates case 12 judge gap |

**Map-to-plan (context map):**

- All `direct` file map rows touched appear in plan §4 or transitive test extensions — no silent scope drop.
- `test_query_classifier.py` created as Flag 3 predicted (24/40 headroom).
- `SemanticLayer.get_date_anchor` added as Flag 2 resolution (no `TemporalContext`).

---

## 10. Contract compliance (Phase 2 summary)

| Contract area | Status |
|---|---|
| Types/interfaces (§2 table) | **Compliant** — signatures, locations, and behaviors match |
| Typed-surface admission | `execution_pass`, `tier_summary`, `get_date_anchor`, constants admitted at declared sites with round-trip tests |
| Error envelope | No new exceptions; harness failures → `case_pass: false` rows |
| Naming | ALL_CAPS constants, snake_case report fields, new test module name correct |
| Logging | `execution_pass` added to case rows; existing keys retained; `--skip-judge` untouched |
| Literal-string parity | `RETURNS_CONSTRAINT` byte-equal to contract quote; synthesis constraint substrings match test assertions |
| Tests | 59/59 pass; mock-only fast gate honored |

**Not a violation:** `build_sql_prompt` uses inlined trigger check rather than new parameter — permitted by §2 "or inlines trigger check".

---

## 11. Decision log audit (Phase 3 summary)

| Log | Implemented? | Stale prose? |
|---|---|---|
| T1-eval-remediation-phase1 | Yes — formula, tier_summary, README tiers | No |
| T2-eval-remediation-temporal | Yes — anchor, pipeline wire, observer hint, temporal audit table | No |

T3–T5: correctly no architectural logs. CHANGELOG adversarial deferrals match code inspection.

**F-007 note:** T5 CHANGELOG line "judge enrichment does not fire" for case 12 is **imprecise** — `_judge_business_rules_block` fires on `"return"` in question text regardless of `known_answer`. Missing test ≠ missing feature.

---

## 12. Scout-prediction reconciliation

| Prediction | Type | Outcome | Finding |
|---|---|---|---|
| Surface 1: calendar-relative recent vs static dataset | suspected_coupling | **verified** (T2) | — |
| Surface 2: date_range.end not propagated | suspected_coupling | **verified** closed | — |
| Surface 3: QueryClass ↔ few-shot ↔ expected_class | suspected_coupling | **verified** (T4 override) | F-003 for SQL outcome |
| Surface 4: KEYWORD_CLASS_MAP order | suspected_coupling | **verified**; override compensates | — |
| Surface 5: case_pass ignores execution | suspected_coupling | **verified** closed (T1) | — |
| Surface 9: resolved suffix → classify | suspected_coupling | **verified** safe suffix | F-010 edge untested |
| Surface 10: self-judge same model | suspected_coupling | **confirmed** open | F-012 |
| Surface 11: returns not enforced | suspected_coupling | **partial** — prompt layer only | F-003 |
| Flag 3: no classifier tests | ambiguity_flag | **verified** closed | — |
| Flag 4: no case 11 integration test | ambiguity_flag | **verified** still open | F-004 |
| Flag 6: case_pass breaking vs additive | ambiguity_flag | **verified** breaking chosen | — |
| `detect_and_resolve` suspect_modified | suspect_modified | **verified** extended | — |
| `classify` suspect_modified, no tests | suspect_modified | **verified** closed (T4) | — |
| `SemanticLayer` suspect_modified, no class tests | suspect_modified | **verified** via anchor tests | F-008 |

---

## 13. Verdict

### **`pass-with-conditions`**

Implementation matches plan §2 contracts, flag resolutions, and non-goals. Unit test gate is green (59/59). Decision logs T1/T2 are accurate. No critical runtime contract defects found in cold read or adversarial integration reasoning.

**Merge-blocking conditions (process + verification):**

1. **Commit audit artifacts** — Add `.dev/plans/eval-remediation/` (and optionally `.dev/eval-remediation-strategy.md`) to HEAD so F-002 closes and plan §8 archaeology is valid.
2. **Run post-remediation eval** — At minimum `docker compose exec nlp python -m eval.harness --skip-judge`; persist JSON with `execution_pass` / `tier_summary`; update README tier table and known-failures prose (F-003, F-005).
3. **Confirm case 11 execution tier** — Verify `execution_pass: true` on case 11 in that run (closes F-004 empirically even if automated integration test remains deferred).

**Non-blocking (minor / deferred):**

- F-006–F-010 unit-test gaps explicitly deferred in CHANGELOG/decision logs  
- F-011 architecture doc staleness — tracked for Wave-3 amendment  
- F-012 self-judge model split — acknowledged open in plan §8.4  

**Would upgrade to `pass` after:** conditions 1–3 satisfied and case 11 execution confirmed in fresh eval log.

**Would downgrade to `fail` if:** post-remediation eval shows case 11 still `execution_pass: false` (T2 ineffective) or case 1 still `class_pass: false` (T4 ineffective) — indicating intent drift despite green unit tests.

---

## 14. §2 contract evidence (auditor spot-check)

| §2 row | Landed | Test |
|---|---|---|
| `get_date_anchor()` | `semantic_layer.py:18-30` | `test_get_date_anchor_returns_iso_strings`, `test_resolve_recent_uses_dataset_anchored_window` |
| `detect_and_resolve` + kwarg | `ambiguity_detector.py:43-47` | anchored recent test |
| 0-row observer hint | `sql_executor.py:128-142` | `test_observe_result_zero_rows_refines` |
| `RETURNS_TRIGGERS` | `sql_generator.py:7` | `test_returns_prompt_injects_constraint` |
| `FEW_SHOT` returns example | `sql_generator.py:31-38` | `test_aggregation_few_shot_contains_returns_filter` |
| `AGGREGATION_OVERRIDES` | `query_classifier.py:60-71` | 4 tests in `test_query_classifier.py` |
| `execution_pass` / `case_pass` | `harness.py:266-288` | 3 tests in `test_eval_harness.py` |
| `tier_summary` | `harness.py:323-333` | `test_run_eval_skips_judge_when_requested`, `test_eval_report_includes_tier_summary_keys` |
| Synthesis constraints | `result_synthesizer.py:55-59` | `test_build_synthesis_prompt_includes_constraint_block` |
| Judge enrichment | `harness.py:150-184`, wired at `:228` | `test_judge_synthesis_includes_business_rules_for_known_answer_case` |

---

*Auditor: post-execution review per auditor-review skill v0.4. No code fixes applied in this pass.*
