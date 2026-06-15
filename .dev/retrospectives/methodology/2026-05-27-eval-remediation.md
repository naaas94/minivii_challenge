# Methodology retrospective — eval-remediation

## 1. Task identifier

**Task:** eval-remediation (five-priority eval harness + pipeline remediation, Waves 0–4)  
**Date:** 2026-05-27 (execution + audit); follow-up artifact commit `2250ae7`; post-audit eval-enhancement `e893240`  
**Plan versions:** v1.0 (draft) → v1.1 (COMPLETE, §8 handoff)  
**Skills:** orchestrator-planning, pre-plan-exploration v0.2, executor-subtask-execution, auditor-review v0.4  
**One line:** Break the false 83% structural pass rate by adding an execution tier gate, dataset-anchored temporal disambiguation, returns SQL guard, classifier override, and narrative/judge hardening across T1–T5.

**Artifacts reviewed for this retro:** strategy doc (825 lines), context map (309 lines), plan v1.1, packets T1–T5, decision logs T1/T2, audit report, CHANGELOG eval-enhancement section, all T1–T5 implementation files and tests, README eval table, `eval_20260527T211111Z.json`, `handoff_notes_for_nivii_en_criollo.md`, `runtime_performance.md` (follow-up scope). Portability doc read; separate task, not plan-scoped.

---

## 2. Plan vs reality

### DAG vs execution

- **Planned:** T1 → T2 → `{T3, T4}` parallel → T5.
- **Actual:** Five sequential commits in one session: T1 (`d2a0798`) → T2 (`6f04401`) → T3 (`74165e3`) → T4 (`dfaa3aa`) → T5 (`7e4ce46`). No parallel agent runs; file sets were disjoint for T3/T4 so sequential execution was safe.
- **Packet fidelity:** Each packet's files-to-touch matched its commit diff exactly — no undeclared production files (audit §9 confirmed; re-verified against `git log --name-only`).
- **Unsafe parallelization:** None observed; T3 packet explicitly forbade `TEST_CASES` edits and T4 owned case 1 `expected_class` confirmation — neither packet modified harness case metadata.
- **Re-planning:** None. T2 (flagged highest re-plan risk) landed without temporal audit escalation.

### Strategy → plan → code traceability

Read `.dev/eval-remediation-strategy.md` end-to-end against plan §1 and implementation:

| Strategy priority | Plan subtask | Landed as strategy described? |
|-------------------|--------------|----------------------------|
| P4 execution gate (Wave 0) | T1 | Yes — breaking `case_pass`, tier_summary. T1 decision log correctly defers strategy §4a "rich" execution formula (row-count / `failure_reason` checks). |
| P1 temporal Option A+B | T2 | Yes — `get_date_anchor`, anchored `recent`, 0-row observer hint. Matches strategy recommended Phase 1+2. Option C post-processor correctly omitted (Flag 8). |
| P2 returns prompt guard | T3 | Yes — `RETURNS_TRIGGERS`, constraint before `Question:` line, AGGREGATION few-shot with `total < 0`. Matches strategy; no post-gen lint (explicit non-goal). |
| P3 classifier override | T4 | Yes — Option C override only; map order unchanged. Context map Surface 4 root cause addressed. |
| P5 narrative/judge | T5 | Partial — synthesis constraints match strategy failure cluster (comparative/derived/temporal). Judge enrichment broader than T5 packet prose implied (see below). |

**Strategy success criteria not met:** Strategy §Success criteria demands case 11 `execution_pass: true` and 12/12 execution. Post-remediation eval (`eval_20260527T211111Z.json`) shows 11/12 execution, 11/12 composite — case 11 still `execution_pass: false`, max-steps. Strategy explicitly tied P1 fix to this criterion; plan Flag 4 waived the integration test that would have caught the gap before declare-done.

### Context map review

Read `.dev/plans/eval-remediation/context-map.md` (CONDITIONAL, scout `0f2d79ee`):

- All eight ambiguity flags were resolved in plan §0 before execution — no BLOCKED flags carried into packets. Flag resolutions in plan match what context map predicted (e.g. Flag 3 → new `test_query_classifier.py`; Flag 2 → no `TemporalContext`).
- Eleven coupling surfaces: audit §12 reconciled all against HEAD code. Surface 10 note in context map ("would disprove if distinct models") — code review confirms both `judge_synthesis` and synthesis use `self.synthesis_model` (`harness.py:242`, `result_synthesizer.py:28`); coupling **confirmed open**, not disproven.
- Surface 9 (resolved suffix → classifier): code review of `ambiguity_detector._anchored_recent_qualifier` confirms digit-only ISO literals; live eval case 1 passes `class_pass` with anchored suffix present — coupling closed as predicted.
- Map never refreshed after T1–T5; `detect_and_resolve` signature in map inventory still shows two-arg form. Staleness did not mislead audit (code re-read), but map would mislead a packet-only executor on a future amendment.

### Contracts at implementation surface

Reviewed each §2 row against landed code and tests (not plan §8 prose alone):

| §2 surface | Code + test review | Gap |
|------------|-------------------|-----|
| `get_date_anchor()` | `semantic_layer.py` validates ISO via `fromisoformat`; tests assert anchored dates `2024-10-21`/`2024-11-20` | No malformed-YAML rejection test (T2 log deferred) |
| `detect_and_resolve` kwarg | Additive `semantic_layer=None`; only `RECENT_AXIS` uses anchor | `semantic_layer=None` backwards-compat branch not regression-tested |
| 0-row observer hint | `sql_executor._observe_result` appends `Dataset date_range: {start} to {end}` when bounds set | Matches packet T2 |
| `RETURNS_TRIGGERS` / prompt injection | Constraint injected after few-shot, before `Question:` — matches T3 assumption 5 and packet kill criterion | Benign "return customers" false-positive untested (accepted residual) |
| `AGGREGATION_OVERRIDES` | `query_classifier.py:78` — TIME_FILTER match + override term; excludes bare `"most"` | 4 tests in `test_query_classifier.py` cover case 1, case 2, bare-`most` guard — matches packet risk matrix |
| `execution_pass` / `case_pass` / `tier_summary` | `harness.py:266-271`, `323-333`; tests mock failure paths | No test that persisted JSONL rows contain `execution_pass` (T1 deferred) |
| Synthesis constraints | `result_synthesizer.py:55-59` — sole path via `synthesize` → `_build_synthesis_prompt` | Matches T5 assumption 1 |
| Judge enrichment | `_judge_business_rules_block` fires on `known_answer` **or** `"return"`/`"refund"` in question (`harness.py:164-169`) | T5 packet §4 says enrichment when `known_answer` or returns/WoW — **implementation matches packet §4 scope line** but T5 packet §5 coupling #2 and CHANGELOG say case 12 enrichment "does not fire" — **wrong** for returns heuristic path. Test only covers `known_answer` path (F-006). |

**Live eval vs unit tests (`eval_20260527T211111Z.json`, read in full):**

| Case | Unit-test expectation | Live post-remediation |
|------|----------------------|------------------------|
| 1 | T4 override → AGGREGATION | `class_pass: true`, `heuristic_override` equivalent — **fixed** |
| 11 | T2 anchored string; T1 gate | `sql_pass: true`, `ambiguity_pass: true`, `execution_pass: false`, `class: time_filter` (LLM fallback — no keyword hits on suffix per audit CR-3) | 
| 12 | T3 returns constraint | `sql_pass: true`, `total < 0` in sql_detail — **fixed** |

Tier summary in log: structural **12/12**, execution **11/12**, composite **11/12**. Strategy target of 12/12 execution not met; handoff notes (`handoff_notes_for_nivii_en_criollo.md`) accept 11/12 and hypothesize case 11 needs ReAct observer tuning (10k-row false positive) — **outside plan scope**, explains why T2 anchor alone was insufficient.

### §2 / decision-log narrative vs later subtasks

- **T1 log:** Accurate — formula, tier keys, README intent. README table still archives **2026-05-26 pre-remediation run** (cases 1/11/12 as failures) despite T1 having updated tier columns. T1 log assumed inferred exec tiers for archived run; post-fix run never backfilled README.
- **T2 log:** Temporal rules audit table matches `ambiguity_detector` code — only `RECENT_AXIS` is dynamic; `last month` stays YAML-static October 2024. Accurate.
- **T3–T5:** No decision logs (correct tier). CHANGELOG entries match code except T5 case-12 judge line (F-007).
- **T5 packet internal tension:** §4 scope allows returns/WoW heuristics; §5 coupling #2 says case 12 enrichment absent — executor followed §4 (implemented heuristic) but changelog followed §5 coupling note (incorrect summary).

### Log tiers

| Subtask | Tier | Review assessment |
|---------|------|-------------------|
| T1 | architectural | OK — decision log substantive; breaking contract deserved tier |
| T2 | architectural | OK — temporal audit table in log is load-bearing; would be lost at standard tier |
| T3, T4, T5 | standard | OK for T3/T4. T5 borderline — judge path in `harness.py` is eval-contract adjacent, but no new typed fields; standard tier defensible |

### Closure vs committed reality

- **Code closure SHA:** `7e4ce464` — plan §8.1 matches; re-verified all named files present at that SHA.
- **First audit:** At `7e4ce464`, plan tree untracked — auditor cold-read on code/tests before logs/§8 (discipline held). F-002 accurate.
- **Artifact commit `2250ae7`:** Plan, map, packets, strategy, audit — all read; content consistent with execution reality.
- **Post-audit `e893240`:** Committed eval logs including `211111Z`; README tier table **not** updated to match (still shows 9/12 composite from pre-fix run). Handoff notes claim 11/12 success — aligns with log, not README.
- **Context map SHA:** Never updated; F-001 latent.

---

## 3. HALTs and amendment cycles

### Executor HALTs

**Count: 0** formal HALTs.

Packet kill-criteria review — all pre-checks that would trigger HALT were satisfiable without escalation:

- T1: `EvalReport` is dataclass; `ExecutionResult.success` exists; README had eval table.
- T2: `domain.yaml` date_range present; single `detect_and_resolve` call site in `pipeline.py`; ISO assertion writable.
- T3: `build_sql_prompt` signature matched context map; `FEW_SHOT_EXAMPLES` keyed by `QueryClass`.
- T4: `KEYWORD_CLASS_MAP` order confirmed; `classify` returns 2-tuple; case 2 regression test passable.
- T5: Signatures matched; `TestCase.known_answer` field exists.

**Silent gap (should have been HALT-shaped or escalated):** Strategy §Success criteria and context map Flag 4 both name case 11 execution proof. Plan §0 accepted unit-only path. Executor proceeded without noting in T2 changelog that **strategy Phase 3 eval assertion was explicitly deferred** — waiver is in plan, but strategy doc still lists it as success criterion, creating intent drift between strategy and closure narrative.

### Amendment cycles

**Count: 0** formal §7 rows.

Audit (`pass-with-conditions`) read in full — three conditions, none mapped to §7:

1. Commit artifacts → `2250ae7` (closed).
2. Post-remediation eval → `e893240` / `211111Z` log (closed).
3. Case 11 execution confirmed → **not closed** (still false in log). Audit said this would downgrade to `fail`; handoff notes and `e893240` message treat 11/12 as acceptable without re-audit.

No T6 packet, no re-audit after condition 3 failure. Amendment skill path unused despite architectural-tier audit conditions.

---

## 4. Adversarial pass calibration

### Rejected decompositions (plan §5.1)

Read against execution:

- **Wave 0 separate from T2:** Validated — T1 commit precedes T2; `test_eval_harness` mocks case 11 with `execution_pass: false` before anchor lands. Clean falsification story.
- **T3/T4 separate:** Validated — independent commits, no merge conflicts, T3 few-shot suspicion disproved in live eval (case 1 `sql_pass: true`).
- **No TemporalContext:** Validated — `get_date_anchor() -> tuple` sufficient; no orphan class in codebase.

### Load-bearing assumptions (plan §5.2)

Re-verified in code, not only audit §8.4:

1. YAML date_range — present, used in `get_date_anchor`.
2. Single call site — `pipeline.py` passes `semantic_layer=self.semantic_layer` once.
3. `execution.success` — boolean, used directly.
4. KEYWORD_CLASS_MAP order — bug was real; override compensates; live case 1 fixed.
5. Constraint injection position — before `Question:` in `build_sql_prompt`; case 12 live pass.
6. Sole synthesis prompt path — `synthesize` only calls `_build_synthesis_prompt`.

All closed at code level.

### Highest re-plan risk (T2)

Did not replan. Code review shows bounded change: 5 files, additive kwarg, temporal audit in decision log covers all `disambiguation_rules` axes. **Residual case 11 failure is not a T2 scope miss** — disambiguation and structural SQL pass; ReAct exhausts at 4 steps. Audit CR-3 and handoff notes point to observer/LLM-classification layers, not anchor logic. Re-plan risk was correctly scoped to temporal consistency; actual residual failure is downstream of T2.

### Hidden couplings (plan §5.4)

| Coupling | Packet/plan prediction | Review outcome |
|----------|------------------------|----------------|
| Suffix → classifier | T2/T4 packets warn ISO-only suffix | Confirmed in code and live eval |
| T1 fixture break | T1 packet §5 — grep `case_pass` | Tests updated in T1 commit |
| AGGREGATION few-shot → case 1 | T3 packet §5 suspected | Live eval disproves regression |
| Case 12 judge / `known_answer` | T5 packet §5 says absent | **Overstated** — returns heuristic in `_judge_business_rules_block` fires for case 12 question text; only `known_answer` path tested |
| Self-judge model | T5 packet §5 suspected | Confirmed — same `synthesis_model` param |

### Context map ambiguity flags — disposition after full read

| Flag | Predicted issue | Outcome |
|------|----------------|---------|
| 1 ownership anchor | Open at map time | Closed in plan §0 as Option C (both layers) |
| 2 TemporalContext | Vocabulary collision | Closed — tuple API |
| 3 classifier tests | Missing file | Closed — `test_query_classifier.py` |
| 4 case 11 integration | Missing execution proof | **Still open** — waived in plan, failed in live eval |
| 5 result_assertions | Coexisting models | Deferred — §7 empty |
| 6 case_pass breaking | Additive vs breaking | Breaking chosen — T1 |
| 7 case 11 ambiguity gap | Vocabulary | Resolved by Flag 1+6 sequencing |
| 8 post-processor scope | Deprecation | P1-A+B / P2-A+B boundary respected |

---

## 5. Methodology gaps surfaced

From reading the full chain (not inferring from plan path list):

- **Strategy ↔ plan closure gap:** Strategy doc is explicit that case 11 execution is the P1 proof point. Plan waived Flag 4; audit filed F-004; live eval still fails case 11 — yet no §7 amendment or downgrade. Orchestrator should require either (a) a closure subtask bound to strategy §Success criteria, or (b) explicit strategy amendment when waiving a success criterion.
- **Packet ↔ changelog drift:** T5 implemented returns heuristic per packet §4 scope; changelog copied packet §5 coupling limitation instead of describing what shipped. Executor skill should require changelog to match **code paths**, not risk footnotes.
- **README as living eval artifact:** T1 updated tier *columns* but archived a pre-fix *run*. Post-`e893240` log exists with better numbers; README never updated — undermines T1's stated goal of honest tier reporting (T1 decision log §Chosen approach).
- **Audit conditions without DAG home:** Three merge-blocking conditions had no executor packet; partial satisfaction (2/3) closed the session. Orchestrator should emit T6-shaped closure when audit lists conditions.
- **Context map refresh:** After five commits touching every `direct` file in the map, no refresh — pre-plan skill should prompt post-execution map append or explicit staleness banner in map header (not only plan §8 footnote).
- **Handoff knowledge not fed back:** `handoff_notes` identifies case 11 observer false-positive as next remediation — methodology has no slot for "operator findings after audit" unless a new plan is opened.

Do **not** edit skills as part of this retrospective.

---

## 6. Single sentence verdict

**Partially** — after reviewing strategy through live eval logs, decomposition and §2 implementation fidelity held up and three of five priority fixes are empirically confirmed in `211111Z`, but the methodology leaked by waiving strategy's case-11 execution proof without a formal amendment, leaving README stale, and closing the session on 11/12 while audit condition 3 explicitly required case-11 execution success.
