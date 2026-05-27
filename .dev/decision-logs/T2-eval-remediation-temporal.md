# T2 — P1 temporal disambiguation anchor

**Plan:** eval-remediation v1.0  
**Subtask:** T2  
**Date:** 2026-05-27

## Chosen approach

**Option C (both layers)** per plan Flag 1 resolution:

1. **`SemanticLayer.get_date_anchor()`** — reads `tables.sales.date_range.start` and `.end` from loaded `domain.yaml`, validates both strings with `datetime.date.fromisoformat`, returns `(start, end)`.

2. **`detect_and_resolve` anchored window** — when the `recent` / `latest` trigger fires and `semantic_layer` is provided, the `recent without explicit time window` rule’s `apply` text is replaced with an absolute SQL-oriented window:
   - `date >= '<end - 30 days>' AND date <= '<end>'`
   - For the demo dataset (`end = 2024-11-20`): `date >= '2024-10-21' AND date <= '2024-11-20'`.
   - Optional observability: `date_anchor:2024-09-21..2024-11-20` appended to `interpretations_applied`.

3. **`SQLExecutor._observe_result` safety net** — 0-row observation messages include `Dataset date_range: <start> to <end>` when `dataset_date_bounds` is set (wired from `Pipeline` via `get_date_anchor()`).

Backwards compatibility: callers passing only `(question, domain_descriptor)` keep calendar-relative `apply` text from YAML for the `recent` axis.

## Anchor computation logic

- Anchor end = `domain.yaml` → `tables.sales.date_range.end` (not wall-clock `now`).
- Recent window start = `end_date - timedelta(days=30)` (inclusive lower bound), formatted as ISO `YYYY-MM-DD`.
- Suffix uses digit/hyphen literals only (no day-of-week words) to avoid classifier keyword collisions (context map Surface 9).

## Alternatives rejected

- **Option A (detector only):** Fixes resolved-question text but leaves ReAct observer blind to dataset bounds on 0-row refinement loops.
- **Option B (observer only):** Hints at bounds after failure without correcting the upstream disambiguation that drives SQL generation.
- **`TemporalContext` class:** Rejected in plan §0 Flag 2 — tuple return on `SemanticLayer` is sufficient surface area.

## Assumptions made

- `date_range.end` in `domain.yaml` remains `2024-11-20` (ISO parseable); demo scope intentionally ties “recent” to static data, not live calendar.
- `detect_and_resolve` has a single production call site in `pipeline.py` (verified by grep).
- Other temporal rules (`last month / this month` → October 2024 `strftime`) remain YAML-static; they are already dataset-aligned, not wall-clock relative.

## Temporal rules audit (`disambiguation_rules`)

| Rule axis | Apply text | Calendar-relative? | Notes |
|-----------|------------|--------------------|-------|
| most bought / most popular product | `SUM(quantity) DESC` | No | Metric default |
| top N without explicit metric | `SUM(total) DESC` | No | Metric default |
| **recent without explicit time window** | Was “last 30 days using date column” | **Yes (fixed in T2)** | Now anchored when `semantic_layer` passed |
| busiest / most active | `COUNT(DISTINCT ticket_number) DESC` | No | Metric default |
| last month / this month | `strftime('%Y-%m', date) = '2024-10'` | No (fixed month) | Already references October 2024 full month |

No other rules use `now` or rolling wall-clock windows.

## Items deferred

- **`reference_date` env var** — deferred; anchor is hard-wired to YAML `date_range.end` for demo reproducibility. A future amendment could override end via env without changing call signatures.
- **SQL post-processor (`now`-pattern rewriter)** — out of scope per plan Flag 8.
- **`result_assertions` / semantic assertion vocabulary** — Wave-3 amendment.
- **Broader re-anchor of “last month” rule to `end`-derived month** — October 2024 string is already correct for this dataset; changing it would be behavior-neutral churn.

## Adversarial test gap (deferred)

No unit test asserts `get_date_anchor()` raises when `date_range.start` is present but non-ISO; kill criteria cover orchestrator pre-check, not runtime malformed YAML after load.
