# T1 — eval-remediation phase 1 (execution gate)

**Subtask:** T1 · P4-eval-phase1  
**Date:** 2026-05-27

## Chosen approach

- Added per-case `execution_pass` from `pipeline_result.execution.success` (verified on `ExecutionResult` in `sql_executor.py`).
- Redefined `case_pass` as `sql_pass ∧ class_pass ∧ ambiguity_pass ∧ execution_pass` (breaking composite gate).
- Added `EvalReport.tier_summary` with `"structural"`, `"execution"`, and `"composite"` counts as `"N/total"` strings, written to JSONL via `dataclasses.asdict(report)`.
- Documented multi-tier pass rates in README (Exec pass column + tier table).

## Alternatives rejected

- **Rich execution gate** (`failure_reason is None`, non-empty `data`, scalar exceptions): deferred to later waves; T1 contract binds only `execution.success` so the harness change stays minimal and falsifiable.
- **Additive `case_pass` with separate tier fields only**: rejected per plan Flag 6 — composite must break on execution failure so case 11 is not a false pass.

## Assumptions made

- `ExecutionResult.success` is authoritative for execution tier; ReAct exhaustion sets `success=False` (observed on case 11 in the 2026-05-26 run).
- Exception paths in `run_eval` imply `execution_pass=False` (no partial pipeline result).
- README archived run: case 11 exec failure inferred from `failure_reason` / max-steps notes; other cases treated as exec pass for the tier table.

## Items deferred

- Row-count / `failure_reason` checks in `execution_pass` (strategy §4a full formula) — out of T1 scope; may tighten in a later eval amendment.
- `known_answer` / `result_assertions` semantic tier — plan Wave-3 amendment.
- JSONL unit test asserting exact key set on each case row — adversarial gap; verified by code inspection and harness tests.
