# Executor Packet — TA2: Eval Contract + db Idempotency

**Plan:** minivii-build · **Subtask:** TA2 · **Log tier:** standard  
**Executor skill:** executor-subtask-execution  
**Spec source (binding):** `mini-nivii-final-spec.md` at repo root  
**Amendment cycle:** v1.2 — post-audit remediation  
**Audit source:** `.dev/audits/2026-05-26-minivii-build.md` findings F3, F4, F5, F6, F8

---

## §1. Task Statement

Five concurrent contract fixes to the eval harness and db ingest layer.

**F3 — Eval Docker entrypoint mismatch:** The `nlp` Dockerfile sets `WORKDIR /app` and `COPY . .` from the `./nlp` build context, so inside the container the top-level packages are `eval`, `pipeline`, etc. — not `nlp.eval`. `python -m nlp.eval.harness` raises `ModuleNotFoundError`. README and the README contract test (`nlp/tests/test_readme_contract.py`) must both reference `python -m eval.harness`.

**F4 — db ingest not idempotent:** `load_csv_to_db` uses `CREATE TABLE IF NOT EXISTS` then unconditionally inserts all rows on every container startup. Any `docker compose restart db` doubles the row count. All aggregate analytics and ReAct cardinality heuristics are corrupted.

**F5 — Eval never asserts `query_class`:** Plan §2 Types table explicitly binds T6: "each case checks `pipeline_result.query_class` matches expected". `run_eval` records `query_class` in results but performs no assertion. Classifier regressions ship undetected.

**F6 — No ambiguity end-to-end gate in eval:** Plan §2 Types row for `ResolvedQuestion` explicitly names "T6 eval case 10 (ambiguity triggers)". Cases 10 and 11 never inspect `pipeline_result.resolved_question` or `pipeline_result.interpretations`. The core semantics-grounding differentiator has no integration gate.

**F8 — Cases 2/8 `expected_class` inconsistent with classifier:** Cases 2 and 8 set `expected_class="simple"` (or `QueryClass.SIMPLE`) but their questions contain `"how many"`, which maps to `QueryClass.AGGREGATION` in `KEYWORD_CLASS_MAP`. If F5 is fixed, these cases fail class checks immediately, masking the real classifier signal.

**Non-goals:**
- Any change to `LLMClient`, Ollama host wiring, or Docker infrastructure (that is TA1)
- Any change to pipeline business logic, ReAct loop, or synthesis
- Adding new test cases beyond the 12 specified in the plan
- Fixing minor findings F10–F14 (those are TA3)

---

## §2. Shared Contracts (relevant rows — verbatim from plan §2)

### Types / Interfaces (binding for TA2)

| Symbol | Owning subtask | Typed surface | Test |
|---|---|---|---|
| `ResolvedQuestion` | T3 | `nlp/pipeline/ambiguity_detector.py` dataclass | **T6 eval case 10 (ambiguity triggers)**; unit test `test_resolve_ambiguity` |
| `QueryClass(Enum)` | T3 | `nlp/pipeline/query_classifier.py` Enum | **T6 eval: each case checks `pipeline_result.query_class` matches expected** |
| `TestCase` | T6 | `nlp/eval/harness.py` dataclass | T6 self-referential: harness constructs and runs all 12 cases |
| `EvalReport` | T6 | `nlp/eval/harness.py` dataclass | T6 `run_eval` returns `EvalReport(results=[...])` |

### Tests (binding for TA2)

- **Framework:** Python standard assert statements + `pytest`
- **Location:** `nlp/tests/` for unit tests; `nlp/eval/harness.py` for the 12-case eval harness
- **Naming:** test files `test_*.py`; eval entrypoint `python -m eval.harness` (**inside container**; `python -m nlp.eval.harness` from repo root on host)
- **Eval gate:** `skip_judge=False` only in Phase 3 (Ollama). Phase 2 uses `skip_judge=True`.

**Landed (to be added by executor when fix ships):**
> `Landed (TA2):` Container eval command is `docker compose exec nlp python -m eval.harness`. Host-side command from repo root remains `python -m nlp.eval.harness`. README §Evaluation and `test_readme_contract.py` updated accordingly.

### Error Envelope (relevant for F4)

| Service | Endpoint | Success shape |
|---|---|---|
| `db` | `GET /health` | `{"status": "ok", "row_count": N}` |

After F4 fix: `row_count` must equal `24212` on every startup, including after container restarts.

---

## §4. Subtask Spec

**Scope:** Make db ingest idempotent; align eval entrypoint docs with container layout; add `query_class` assertion; add ambiguity assertions for cases 10/11; reconcile cases 2/8 with classifier behavior.

**Files to touch:**
```
db/ingest.py                              (F4 — idempotent ingest)
nlp/eval/harness.py                       (F3 partial, F5, F6, F8)
README.md                                 (F3 — eval command in Evaluation section)
nlp/tests/test_readme_contract.py         (F3 — README command assertion)
```

**Contract bindings:** §2 Types (`ResolvedQuestion` case 10 gate; `QueryClass` per-case assertion); §2 Tests (eval entrypoint literal, eval as final-pass gate).

**Inputs:** None — parallel with TA1. TA2 does not share files with TA1.

**Outputs:**

### F4 — db Idempotency

`db/ingest.py` `load_csv_to_db()` must truncate existing rows before inserting:
```python
# Preferred approach — keep schema, remove data
cursor.execute("DELETE FROM sales")
conn.commit()
# then proceed with existing INSERT loop
```
Alternatively: `DROP TABLE IF EXISTS sales` followed by `CREATE TABLE sales (...)` and INSERT. Either approach is acceptable — document the choice in a code comment. After fix, `GET /health` returns `row_count: 24212` on first startup and after any number of restarts.

### F3 — Eval Entrypoint Alignment

- **`nlp/eval/harness.py`** (or wherever the `__main__` block lives): Ensure the file is runnable as `python -m eval.harness` from `/app` inside the container. No code change needed if `nlp/eval/__main__.py` or `harness.py` has a `__main__` guard — verify it works with `python -m eval.harness`, not `python -m nlp.eval.harness`.
- **`README.md`** — find the eval run instruction and change it to:
  ```bash
  docker compose exec nlp python -m eval.harness
  # or with skip_judge for faster structural check:
  docker compose exec nlp python -m eval.harness --skip-judge
  ```
- **`nlp/tests/test_readme_contract.py`** — if this file contains an assertion that `README.md` contains the string `python -m nlp.eval.harness`, update the assertion to `python -m eval.harness`.

### F5 — `query_class` Assertion in `run_eval`

In `nlp/eval/harness.py`, `run_eval` processes each `TestCase` and `PipelineResult`. Add a `class_pass` check:

```python
class_pass = (
    pipeline_result.query_class == case.expected_class
    if hasattr(case, "expected_class") and case.expected_class is not None
    else True   # no expectation declared → skip
)
case_pass = sql_pass and class_pass   # both must be True for overall pass
```

The per-case result dict / dataclass must include `class_pass` field. The summary output must report class pass rate separately from SQL pass rate so failures are diagnosable.

### F8 — Reconcile Cases 2 and 8

Cases 2 and 8 have questions containing `"how many"`. The classifier `KEYWORD_CLASS_MAP` maps `"how many"` to `QueryClass.AGGREGATION` at the keyword-heuristic tier (before LLM fallback). After F5 is applied, these cases will fail `class_pass`.

**Chosen fix — change `expected_class` (lower-risk):**
Update `expected_class` for cases 2 and 8 to `QueryClass.AGGREGATION`. The questions genuinely ask for counts, so `AGGREGATION` is semantically correct. The original `simple` label was likely a spec transcription error.

**Alternative (higher-risk, do not choose unless you can verify):** Change the question text to not contain `"how many"` — but this changes the semantic coverage the case was designed to test. Avoid this path.

Document the choice in a code comment next to the case definition.

### F6 — Ambiguity Assertions for Cases 10 and 11

Cases 10 and 11 are designed to trigger the `AmbiguityDetector`. Plan §2 Types row for `ResolvedQuestion` explicitly names case 10 as the gate for ambiguity. After the pipeline runs, assert:

```python
# Case 10: ambiguity detection fired
assert pipeline_result.interpretations and len(pipeline_result.interpretations) > 0, \
    "Case 10: expected AmbiguityDetector to produce interpretations"
# Case 11: resolved_question reflects disambiguation
assert pipeline_result.resolved_question != pipeline_result.question, \
    "Case 11: expected resolved_question to differ from original"
```

These assertions run in `run_eval` as part of the per-case `sql_pass` logic (or as a separate `ambiguity_pass` field). If the ambiguity check fails, the case fails regardless of SQL structural match.

Exact assertion form may vary based on `PipelineResult` field shapes — inspect the dataclass and adapt. The binding requirement is that at least one per-case assertion checks `resolved_question` or `interpretations` being non-trivially populated for cases 10/11.

**Kill criteria:**
- HALT if `load_csv_to_db` still does unconditional INSERT without prior truncation/drop
- HALT if a second `docker compose up` (with existing db volume) would yield `row_count > 24212`
- HALT if `run_eval` still has no per-case comparison of `pipeline_result.query_class` to `case.expected_class`
- HALT if cases 2 and 8 would still fail `class_pass` check after fix (verify: classifier returns `AGGREGATION` for `"how many"` questions before LLM fallback fires)
- HALT if README eval section still contains the string `python -m nlp.eval.harness` as the container command
- HALT if `test_readme_contract.py` still asserts `python -m nlp.eval.harness` as the expected README string
- HALT if cases 10/11 add no assertion touching `resolved_question` or `interpretations`

**Log tier:** standard

**Risks & mitigations:**
- **db idempotency approach:** `DELETE FROM sales` preserves the schema and avoids re-running DDL. `DROP TABLE IF EXISTS` + `CREATE TABLE` also works but re-runs DDL on every startup — acceptable since DDL is deterministic. Document the choice. Either approach: the ingest function must verify `row_count == 24212` after insert and log/raise if mismatched.
- **Cases 2/8 reconciliation:** Before changing `expected_class`, confirm with: `from nlp.pipeline.query_classifier import QueryClassifier; c = QueryClassifier(None); print(c._keyword_classify("How many ..."))`. If it returns `AGGREGATION`, change `expected_class` to `AGGREGATION`. If the keyword map has changed, surface as a kill criterion violation.
- **Ambiguity assertions (F6):** The `PipelineResult` dataclass field for interpretations may be `interpretations: list[str]` or similar. Check the actual field type before writing the assertion. If the field is `None` rather than `[]` on non-ambiguous questions, use `if case.id in (10, 11): assert pipeline_result.interpretations` pattern.
- **README command dual audience:** README must distinguish host command (`python -m nlp.eval.harness` from repo root, where `nlp/` is a package) from container command (`python -m eval.harness` inside `/app`). Both are valid in their respective contexts — do not remove the host-side instruction; only add or correct the container instruction.

---

## §5 (filtered) — Load-Bearing Assumptions relevant to TA2

From plan §5.2:

| Claim | Contract surface | Failure mode | Impact on TA2 |
|---|---|---|---|
| `PipelineResult` field names stable at spec §5.9 shape | §2 Types row "PipelineResult", `nlp/pipeline/pipeline.py` | T5 Jinja2 and T6 eval both read fields | TA2 adds new assertions on `.query_class`, `.resolved_question`, `.interpretations` — verify these fields exist on the dataclass before writing assertions |
| db `POST /execute` returns `{"columns": [...], "rows": [[...]], "row_count": N}` | §2 Error Envelope, `db/main.py` | `_try_execute` parses exact keys | Unaffected by TA2 |

**TA2-specific note:** Eval assertions added in TA2 will fail at import time if `PipelineResult` does not expose `.query_class`, `.resolved_question`, and `.interpretations` as attributes. Verify these fields exist before writing assertions — they should be present per plan §2 and spec §5.9.

---

## §5 (filtered) — Hidden Couplings relevant to TA2

From plan §5.4:

| Coupling | Impact on TA2 |
|---|---|
| T6 imports `nlp.pipeline.pipeline` transitively | TA2 adds assertions to eval; the import chain is unchanged. Verify `harness.py` imports are correct after changes. |
| `QueryClass` enum values used as `FEW_SHOT_EXAMPLES` keys | TA2 changes `expected_class` on cases 2/8 from `SIMPLE` to `AGGREGATION` — this does not change the enum definition itself, only eval metadata |

---

## DoD (Definition of Done)

- [ ] `GET /health` returns `row_count: 24212` after a second `docker compose up` with existing db volume
- [ ] `run_eval` records `class_pass` per case; overall case pass requires both `sql_pass` and `class_pass`
- [ ] Cases 2 and 8 `expected_class` is `QueryClass.AGGREGATION`; they pass `class_pass` with keyword classifier
- [ ] Cases 10 and 11 assert `resolved_question` or `interpretations` non-trivially populated
- [ ] README Evaluation section uses `docker compose exec nlp python -m eval.harness` as container command
- [ ] `test_readme_contract.py` assertion matches updated README string
- [ ] All 39 existing unit tests still pass (`cd nlp && pytest tests/ -q`)
- [ ] §2 Tests `Landed:` bullet added to `plan.md`
