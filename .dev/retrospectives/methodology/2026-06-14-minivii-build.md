# Methodology Retrospective — minivii-build

## 1. Task identifier

- **Task:** `minivii-build` — greenfield Mini Nivii (four-container NL-to-SQL BI agent)
- **Dates:** 2026-05-26 (T1–T7 + audit + TA1–TA3); post-plan bring-up TA4 + portability check 2026-05-27; `eval-remediation` closed residual gate gaps 2026-05-27
- **Plan versions:** v1.0 → v1.1 (pre-build review) → v1.2 (post-audit amendments) → v1.3 (§8 auditor handoff)
- **Skills referenced:** orchestrator-planning, executor-subtask-execution, auditor-review
- **One line:** Build Docker Compose POS analytics agent (db / nlp / ui / ollama), 12-case eval harness, submission README — from `mini-nivii-final-spec.md`.

### Artifacts reviewed (full chain)

| Category | Path | Read |
|---|---|---|
| Binding spec | `mini-nivii-final-spec.md` | Plan/packet citations only — not line-audited against code |
| Plan | `.dev/plans/minivii-build/plan.md` (v1.3) | Full |
| Packets | `.dev/plans/minivii-build/packets/T1.md`–`T7.md`, `TA1.md`–`TA3.md` | Full (all 10) |
| Decision logs | `T2.md`, `T3-nlp-pipeline-core.md`, `T4-react-loop-pipeline.md`, `TA1-ollama-host-wiring.md` | Full |
| Execution log | `.dev/execution-logs/T2-db-service.md` | Full |
| Audits | `2026-05-26-minivii-build.md` (rev1), `2026-05-26-minivii-build-rev2.md` | Full |
| Changelog | `CHANGELOG.MD` (`minivii-build` + TA4 entries) | Full minivii-build section |
| Architecture | `.dev/architecture/minivii/changelog.md` (build-era entries) | Partial — confirms OLLAMA defect documented at audit time |
| Eval artifact | `nlp/logs/eval_20260526T204618Z.json` (cited in rev2) | **Absent from repo** (gitignored `logs/`) — rev2 findings used |
| Portability | `portability_check_on_my_laptop.md` | Full |
| Follow-on (closure spillover) | `.dev/plans/eval-remediation/plan.md`, `.dev/retrospectives/methodology/2026-05-27-eval-remediation.md` | For residual R2-* disposition only |
| Learning retro | `.dev/retrospectives/learning/2026-06-14-minivii-build.md` | Skimmed — domain learning; not methodology source |
| Git history | `5cf53f8`…`6447a46` + post-plan commits | Commit sequence verified |

---

## 2. Plan vs reality

### DAG

| Planned | Actual | Match? |
|---|---|---|
| `T1 → {T2 ∥ T3} → T4 → {T5 ∥ T6} → T7` | Commits `5cf53f8` → `5ce134b` in that order; T2/T3 parallel-safe; T5/T6 after T4 | Yes |
| `{TA1 ∥ TA2} → TA3` | `620c05e`, `71f5b9b`, `c1f0952` | Yes |
| — | **TA4** (ollama `curl` image, UI `3001:3000`) in CHANGELOG only — no packet, no plan §7 row | **DAG escape** |
| — | `.dev/architecture/minivii/**` tracked at `6447a46` — not in plan deliverables (rev1 F16) | Undeclared artifact |

**Parallelization:** `{T2,T3}` and `{T5,T6}` held — separate directories, no import races.

**Sequencing surprise:** T7 closed (`5ce134b`) before stack was honestly green; commit `1cfb631` message `t1-6 ran - running eval` with terminal 12/12 FAIL did not block T7.

### Packet → diff fidelity (executor lens)

| Subtask | Packet files-to-touch vs commits | Notable drift |
|---|---|---|
| T1 | Matched | Packet template still shows `curl` in db healthcheck and ollama entrypoint — shipped as-is; **F2/F15 seeds** |
| T2 | Matched | CHANGELOG cites `T2-db-service.md` before file existed; T2 log flags curl cross-task, no HALT |
| T3 | Matched + decision log | Packet lists `test_resolve_*` names; plan §2 cites `test_resolve_ambiguity` — fixed in TA3 |
| T4 | Matched + tests beyond packet | Decision log **Assumptions**: OLLAMA_URL health-only — stack-breaking; superseded TA3 |
| T5 | Matched | `test_readme_contract.py` added by T7, not T5 packet — beneficial drift (rev1 notes) |
| T6 | Matched (inline cases OK) | Packet `run_eval` pseudocode has **no** `class_pass` or `execution.success` gate — matches shipped hollow gate |
| T7 | Matched + `test_readme_contract.py` | Kill criteria omit green eval; README eval command wrong for container until TA2 |
| TA1 | Matched | `plan.md` §2 Landed bullet deferred to orchestrator follow-up per CHANGELOG |
| TA2 | Matched | Case 2 reconciled to **`time_filter`** (Saturday keyword wins before `how many`) — not TA2 packet's default `AGGREGATION` path |
| TA3 | Matched | T2 execution log **authored by TA3 executor**, not T2 — retroactive archaeology |

### Contracts at implementation surface

| §2 row | Landed? | Evidence reviewed |
|---|---|---|
| Types (dataclasses/enums) | Yes | Packets + rev2 §10; paths match |
| `quantity REAL` | Yes | T2 packet, execution log, ingest |
| db / nlp error envelopes | Yes | Rev1 adversarial log; unit tests |
| `OLLAMA_URL` consumption | **No until TA1** | T4 log L24; rev1 F1; TA1 log |
| Eval `query_class` assert | **No until TA2** | T6 packet pseudocode; rev1 F5 |
| Eval `execution.success` in `case_pass` | **No until eval-remediation** | Plan §2 Types row vs T6 packet; rev2 R2-1 |
| Ambiguity cases 10/11 | Partial post-TA2 | `interpretations` non-empty only — rev2 R2-4 |
| JSONL 11-field schema | Yes post-TA3 | TA3 packet F10 |
| Eval container entrypoint | Yes post-TA2 | TA2 packet F3 |
| `test_resolve_ambiguity` | Yes post-TA3 | TA3 packet F11 |

**Hollow-contract pattern:** 39 → 46 unit tests passed while F1–F3 remained broken — tests mock LLM/HTTP or run host-side (rev1 §3, portability §93).

### §2 / decision-log narrative survival

- **T4 log** OLLAMA assumption (L22–24) narrated broken state as acceptable → **F13**; TA3 supersession banner + TA1 authority — repaired same session.
- **CHANGELOG T2 entry** cited execution log before TA3 created it — **F7** narrative ahead of artifact.
- **TA2 CHANGELOG** documents case 2 as `time_filter` reconciliation; TA2 packet prose defaulted to `AGGREGATION` — executor chose iteration-order truth over packet default (correct).
- **Plan §2 Landed bullets** for TA1/TA2 added at v1.3 close-out; pre-amendment rows obsolete for those surfaces.

### Log tiers

| Subtask | Tier | Assessment |
|---|---|---|
| T3, T4 | architectural | Correct — pipeline + ReAct |
| TA1 | architectural | Correct — env consumption path change |
| T1, T2, T5, T6, T7, TA2, TA3 | standard | Correct; standard tier did not force integration proof |

### Closure vs committed reality

- **Code fixes:** TA1 `620c05e`, TA2 `71f5b9b`, TA3 `c1f0952`; docs/audit `6447a46`.
- **§8 v1.3:** Uncommitted at rev2 audit (R2-5); §8.1 "clean tree" false at audit time.
- **Eval JSON:** Referenced in rev2, not in git — F9 evidence on disk only.
- **Context map:** N/A greenfield — valid per plan §0.

---

## 3. HALTs and amendment cycles

### Executor HALTs (packet kill criteria)

| Subtask | HALT fired? | Evidence |
|---|---|---|
| T1 | No | GPU block omitted per v1.1 amendment; **did not HALT** on db `curl` healthcheck or ollama entrypoint `curl` on image without `curl` |
| T2 | **Explicit "HALT: none"** in CHANGELOG | Cross-task curl flag logged; synthetic CSV workaround documented in T2.md |
| T3 | No | Live LLM deferred to T6 per decision log |
| T4 | No | **Should have HALTed** on OLLAMA_URL not on inference path (T4 packet §2 Naming binds env vars) |
| T5 | No | 600s timeout shipped per amended kill criterion |
| T6 | No | **Should have HALTed** — plan §2 Types row requires `execution.success` check; packet pseudocode omits it |
| T7 | No | **Should have HALTed** — eval gate failing; kill criteria don't require green eval |
| TA1–TA3 | No | Amendment kill criteria satisfied per rev2 §12 |

**HALT-shaped gaps deferred as "adversarial gap" or cross-task flag:** 8+ instances across CHANGELOG (ReAct multi-step test, malformed CSV, compose restart test, JSONL key count test, live eval pass rate, etc.).

**Silent improvisation:** T2 execution log created retroactively by TA3 with template values — valid evidence shape but **not T2-era capture** (execution log dated TA3 executor).

### Amendment cycles

- **Rev1:** `fail` — F1–F16 (3 critical, 7 major, 4 minor + observations).
- **TA1–TA3:** Closed F1–F13 on declared surfaces; F14 informal T2 log accepted; F15/F16 open/resolved per rev2 §12.
- **Rev2:** `pass-with-conditions` — R2-1 (execution gate), R2-2 (case 1 class), R2-3 (case 12 returns), R2-5 (§8 uncommitted), R2-7 (no full judge run).
- **eval-remediation (2026-05-27):** Separate plan closed R2-1, R2-2, R2-3 partially; case 11 execution still 11/12 per follow-on retro.
- **TA4:** Outside amendment DAG — third integration seam (ollama entrypoint `curl` on image without `curl`).

**Amendment scope:** TA1–TA3 correctly avoided architectural fork. Did not close eval gate honesty — required second plan.

---

## 4. Adversarial pass calibration

### §5.1 Rejected decompositions — disposition

| Rejected | Held? | Later surprise |
|---|---|---|
| Merge db+nlp | Yes | — |
| Monolithic nlp | Yes | — |
| Ollama `sleep` vs poll | Yes | **But** poll uses `curl` on `ollama/ollama` image without `curl` — not in rejected list; fixed as TA4 |
| ChromaDB SchemaLinker | Yes | — |
| GPU `deploy.resources` omit (v1.1 A2) | Yes | **Confirmed** — `portability_check_on_my_laptop.md`: CPU-only compose up works |

### §5.2 Load-bearing assumptions

| Assumption | Held? |
|---|---|
| `LLMClient.generate()` signature | Yes (TA1 internal only) |
| db wire format | Yes |
| `PipelineResult` fields | Yes |
| Docker `db` DNS | Yes |
| `data.csv` mount | Yes |
| **`OLLAMA_URL` → inference** | **Failed** until TA1 |

### §5.3 Highest re-plan risk (T4 ReAct)

- **Predicted:** Refinement effectiveness, 51-row scalar edge case.
- **Actual:** Integration seams (F1–F3), eval contract hollow (F5, F9, R2-1), temporal grounding (case 11 — downstream eval-remediation).
- T4 ReAct design (`Action` enum, synthesis guard) **held** under both audits.

### §5.4 Hidden couplings — reviewed against code/audit

| Coupling | Status at rev2 |
|---|---|
| `QueryClass` / `FEW_SHOT_EXAMPLES` | Closed |
| T4 `asdict` / T5 dict | Closed |
| T6 import chain | Closed |
| T4/T6 `data[:10]` truncation | Closed (code inspection) |
| **Case 1: TIME_FILTER before AGGREGATION in map** | Open → R2-2; fixed in eval-remediation T4 override |
| **T6 `case_pass` vs `execution.success`** | Open → R2-1 |

---

## 5. Methodology gaps surfaced

### Orchestrator skill

- No **Compose integration smoke** subtask before T7 — three stack-breaking defects (nlp OLLAMA, db healthcheck `curl`, eval module path) plus fourth (ollama entrypoint `curl`) escaped to TA4.
- **§2 env vars** need declare / consume / verify — `OLLAMA_URL` row was vestigial until TA1.
- **T6 packet `run_eval` pseudocode** did not encode plan §2 `execution.success` row — plan/packet divergence allowed hollow gate.
- **Amendment slot for bring-up** (TA4-class fixes) missing from DAG.
- **v1.1 pre-build review** caught T5 timeout and GPU block but not db/ollama healthcheck tool mismatch.

### Executor skill

- **Cross-task flags ≠ HALT** — T2 CHANGELOG curl flag, T4 OLLAMA assumption in decision log.
- **Architectural log rationalized broken wire** (T4) instead of escalating.
- **Retroactive execution log** (T2 via TA3) satisfies audit archaeology but not kill-criteria-at-commit-time discipline.
- **TA2 packet default** (cases 2/8 → AGGREGATION) overridden by executor with better keyword-order analysis — good judgment, but packet should have required the probe command outcome in writing.

### Contracts schema

- Env var **consumption column** missing from §2.
- Eval **tier semantics** (`sql_pass`, `class_pass`, `ambiguity_pass`, `execution_pass`, `case_pass`) not frozen in T6 kill criteria.
- **Integration smoke** as contract row for multi-container plans.
- **Healthcheck probe ↔ image packages** coupling unnamed in T1 (db `curl`, ollama entrypoint `curl`).

*Do not edit skills here.*

---

## 6. Single sentence verdict

**Partially** — after full packet/audit/changelog review, the orchestrator decomposed work and the audit→TA1–TA3 loop closed critical integration drift, but executor HALT discipline was too weak (zero HALTs despite three stack-breaking seams), kill criteria and §2 diverged on the eval gate, and closure artifacts (execution log, §8 handoff, eval JSON) lagged or escaped the plan DAG until a second plan addressed residual conditions.
