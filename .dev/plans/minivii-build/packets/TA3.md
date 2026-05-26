# Executor Packet — TA3: Artifact & Narrative Cleanup

**Plan:** minivii-build · **Subtask:** TA3 · **Log tier:** standard  
**Executor skill:** executor-subtask-execution  
**Spec source (binding):** `mini-nivii-final-spec.md` at repo root  
**Amendment cycle:** v1.2 — post-audit remediation  
**Audit source:** `.dev/audits/2026-05-26-minivii-build.md` findings F7, F9, F10, F11, F12, F13, F14

---

## §1. Task Statement

Close all remaining minor and artifact findings after TA1 and TA2 are complete. TA3 has no new code logic — it is a narrative-alignment and evidence-archival pass.

**F7 — Missing T2 execution log:** `CHANGELOG.MD` references `.dev/execution-logs/T2-db-service.md` as kill-criteria evidence for T2. The file does not exist on disk or in HEAD. Post-merge archaeology for T2 smoke-test claims is broken.

**F9 — Eval gate without passing evidence:** The 12-case harness is the primary correctness signal and final-pass gate (plan §2 Tests). The last recorded run shows 12/12 FAIL (likely environment — db/Ollama unreachable). README describes how to run the harness but includes no results. The submission artifact chain ends without demonstrated pipeline correctness.

**F10 — JSONL log extra fields:** `Pipeline._log_stage` emits extra keys (`class`, `method`, `success`, `steps_taken`) beyond the 11-field §2 Logging schema. Minor contract drift that should be corrected.

**F11 — Test naming drift:** Plan §2 Types row for `ResolvedQuestion` specifies unit test `test_resolve_ambiguity`. Shipped tests in `nlp/tests/test_ambiguity_detector.py` use `test_resolve_*` pattern names but not the canonical name `test_resolve_ambiguity`. Minor naming contract violation.

**F12 — README dataset table missing `ticket_prefix`:** README lists 9 columns; `db/ingest.py` DDL and plan §2 (T2 output) define 10 columns including `ticket_prefix`. The submission table is wrong.

**F13 — T4 decision log stale prose:** T4 decision log states the OLLAMA_URL approach is an "acceptable assumption." After TA1 ships the fix, that prose narrates a broken state as acceptable without a supersession banner. The log must be superseded.

**F14 — T2 decision log informal:** T2 decision log is an informal paste rather than architectural-tier format. T2 is standard tier; no format enforcement required. **F14 is acknowledged and deferred — no action in TA3.**

**Non-goals:**
- Any code changes to `LLMClient`, db ingest, or eval harness assertions (those are TA1/TA2)
- Reworking T2 decision log format (F14 — explicitly deferred)
- Adding new pipeline features, test cases, or architecture decisions
- Restructuring the README beyond the specific table and eval results section

---

## §2. Shared Contracts (relevant rows — verbatim from plan §2)

### Logging (binding for F10)

Every pipeline stage must write a JSONL record with **exactly** these fields (no extra keys):

```json
{
  "run_id": "<ISO timestamp>",
  "stage": "<stage name>",
  "question": "...",
  "resolved_question": "...",
  "model": "<model name or null>",
  "step": "<int or null>",
  "sql_attempted": "<sql or null>",
  "observation_action": "<accept|refine|null>",
  "observation_message": "<str or null>",
  "latency_ms": "<int>"
}
```

The extra fields currently emitted (`class`, `method`, `success`, `steps_taken`) are outside this schema and must be removed.

### Tests (binding for F11)

- **Naming:** test files `test_*.py`; unit test for AmbiguityDetector composition logic must include a function named `test_resolve_ambiguity`
- **Coverage expectation:** unit tests for `AmbiguityDetector` composition logic (non-cascading) and `extract_sql` are required

### Naming (binding for F13)

| Symbol | Value |
|---|---|
| Decision log paths | T3: `.dev/decision-logs/T3-nlp-pipeline-core.md` · T4: `.dev/decision-logs/T4-react-loop-pipeline.md` |

T4 decision log must be superseded to reflect that TA1 resolves the OLLAMA_URL host wiring. The supersession banner must point to `.dev/decision-logs/TA1-ollama-host-wiring.md` as the new authority on Ollama host configuration.

---

## §4. Subtask Spec

**Scope:** Create missing T2 execution log; remove extra JSONL fields; add `test_resolve_ambiguity` name; fix README dataset table; supersede T4 decision log; run and archive eval evidence.

**Files to touch:**
```
.dev/execution-logs/T2-db-service.md          (F7 — create)
nlp/pipeline/pipeline.py                       (F10 — remove extra JSONL fields)
nlp/tests/test_ambiguity_detector.py           (F11 — add canonical test name)
README.md                                      (F12 — dataset table; F9 — eval results section)
.dev/decision-logs/T4-react-loop-pipeline.md   (F13 — supersession banner)
```

**Contract bindings:** §2 Logging (JSONL 11-field schema); §2 Tests (unit test naming); §2 Naming (T4 decision log supersession).

**Inputs:**
- TA1 must be complete: Ollama host wired, db healthcheck passing, stack bootable. TA3 needs a working Compose stack to produce F9 eval evidence.
- TA2 must be complete: db idempotent, eval assertions landed, container eval command correct. TA3 runs `python -m eval.harness` (the corrected command from TA2).

**Outputs:**

### F7 — Create T2 Execution Log

Create `.dev/execution-logs/T2-db-service.md` with the following content (adapt values to match actual observed behavior):

```markdown
# T2 Execution Log — db Service Smoke Test

**Date:** <date>
**Executor:** <executor>
**Kill criteria check:** T2 (plan §4)

## Evidence

### GET /health
Request: `curl http://localhost:8001/health`
Response: `{"status": "ok", "row_count": 24212}`
Status: PASS

### POST /execute — success
Request: `{"sql": "SELECT COUNT(*) FROM sales"}`
Response: `{"columns": ["COUNT(*)"], "rows": [[24212]], "row_count": 1}`
Status: PASS

### POST /execute — error shape
Request: `{"sql": "SELECT * FROM nonexistent"}`
Response: `{"error": "no such table: nonexistent", "sql": "SELECT * FROM nonexistent"}`
Status: PASS (error envelope includes "sql" key)

### GET /schema
Response includes `CREATE TABLE sales (` with `quantity REAL` and `ticket_prefix TEXT`
Status: PASS

### Startup sequencing
`load_csv_to_db` called synchronously in `@app.on_event("startup")` — no background task.
Status: PASS

## Kill criteria disposition
All 6 T2 kill criteria: PASS
```

If the actual values differ from above, use the real observed values. The file must exist and cover the 6 T2 kill criteria.

### F10 — Remove Extra JSONL Fields

In `nlp/pipeline/pipeline.py`, find `_log_stage` (or equivalent method that writes JSONL). Remove the extra keys `class`, `method`, `success`, `steps_taken` from the emitted record. The record must contain exactly the 11 fields in §2 Logging schema. If any information from the removed fields is needed for debugging, note in a code comment that it was removed per §2 contract — do not add an alternative sink.

Verify no test asserts the presence of these extra fields before removing them. If a test does assert them, update the test to not assert non-schema fields.

### F11 — Canonical Test Name

In `nlp/tests/test_ambiguity_detector.py`, ensure a function named exactly `test_resolve_ambiguity` exists. Options:
- Rename the most relevant existing `test_resolve_*` function to `test_resolve_ambiguity`, OR
- Add a new test function `test_resolve_ambiguity` that calls the composition logic (non-cascading) — the plan §2 binding is that this name exists and tests composition.

The canonical name must test that `detect_and_resolve` composes rules against the original question once (not cascading). Do not break existing tests.

### F12 — README Dataset Table

In `README.md`, find the dataset table (likely in a "Dataset" section). Update the column count from 9 to 10 and add `ticket_prefix` to the column list. The updated row should read approximately:

```
- 24,212 rows, 10 columns, 68 products, 11,771 tickets, 9 waiters
```

and the column list (if one exists) must include `ticket_prefix TEXT` (extracted from `ticket_number` at ingest).

### F13 — T4 Decision Log Supersession

Open `.dev/decision-logs/T4-react-loop-pipeline.md`. At the very top of the file, before any existing content, insert the supersession banner:

```markdown
> **⚠ SUPERSEDED (partial) — TA1:** The section below describing `OLLAMA_URL` as an acceptable assumption that routes to health display only has been resolved. See `.dev/decision-logs/TA1-ollama-host-wiring.md` for the authoritative description of how `OLLAMA_URL` is consumed on the inference path. All other sections of this log remain current.
```

Do not edit any other content of the T4 decision log — only prepend the banner.

### F9 — Run and Archive Eval Evidence

After TA1 and TA2 are complete (Ollama host wired, db idempotent, eval assertions correct), run the evaluation harness with `skip_judge=True`:

```bash
docker compose exec nlp python -m eval.harness --skip-judge
```

Or from outside the container (from `nlp/` directory with a running local db on localhost):

```bash
DB_URL=http://localhost:8001 OLLAMA_URL=http://localhost:11434 python -m eval.harness --skip-judge
```

Record the results. Add an **Evaluation Results** subsection to `README.md` under the Evaluation section:

```markdown
## Evaluation Results (structural, skip_judge=True)

Run date: <date>  
Environment: <Docker Compose GPU / local CPU / etc.>  
Command: `docker compose exec nlp python -m eval.harness --skip-judge`

| Case | Question summary | SQL pass | Class pass | Notes |
|------|-----------------|---------|-----------|-------|
| 1    | ...             | ✓/✗     | ✓/✗       | ...   |
...
| 12   | ...             | ✓/✗     | ✓/✗       | ...   |

**Structural pass rate: N/12 SQL, M/12 class**

Known failures: <list any known failures with brief reason>
```

If the Compose stack is unavailable (e.g., no GPU), document that explicitly:
```markdown
> **Note:** Full-stack eval run blocked on GPU availability. Structural SQL checks validated via unit tests (39 pass). Live eval run pending GPU provisioning.
```

**Kill criteria:**
- HALT if `.dev/execution-logs/T2-db-service.md` is absent after TA3 ships
- HALT if T4 decision log still describes OLLAMA_URL as acceptable assumption without supersession banner pointing to TA1 decision log
- HALT if `Pipeline._log_stage` still emits any field not in the §2 Logging 11-field schema
- HALT if README dataset table column count is still 9 (must be 10 with `ticket_prefix`)
- HALT if TA3 ships without at least one of: (a) an archived `skip_judge=True` eval result table in README, OR (b) an explicit documented blocker in README explaining why the run could not be completed (GPU unavailable, etc.)
- HALT if `test_resolve_ambiguity` function is absent from `nlp/tests/test_ambiguity_detector.py`

**Log tier:** standard

**Risks & mitigations:**
- **JSONL field removal (F10):** Grep for any file that reads the extra fields (`class`, `method`, `success`, `steps_taken`) from JSONL logs before removing them. If the eval harness or any analysis script reads these fields, update those consumers first, then remove from the emitter.
- **T4 decision log banner (F13):** Prepend only — do not rewrite the log. The supersession banner is narrow and surgical. The rest of the T4 log (ReAct loop design, synthesis temperature rationale, etc.) remains valid and current.
- **Eval run environment (F9):** If Compose GPU stack is unavailable, a partial run (structural only, localhost db) is acceptable evidence. Document the environment explicitly so the auditor can assess coverage. An undocumented "I couldn't run it" is not acceptable — the README must state the status.
- **F14 (T2 decision log format):** Explicitly deferred. The T2 log is informal but useful. Reformatting adds no correctness value and risks introducing new drift. Do not touch `.dev/decision-logs/T2.md`.

---

## §5 (filtered) — Load-Bearing Assumptions relevant to TA3

From plan §5.2:

| Claim | Impact on TA3 |
|---|---|
| `PipelineResult` field names stable | TA3 reads pipeline output for eval evidence; field stability assumed |
| `data.csv` exists at `/app/data.csv` in db container | Required for F9 eval run to work |

**TA3-specific assumption:**
> TA1 and TA2 are complete and the Compose stack is in a bootable state before TA3's F9 item executes. If TA1 is not complete, LLM calls fail silently (F1 unfixed) and the eval run is meaningless. If TA2 is not complete, the `class_pass` assertions are absent and the eval report is misleading. TA3 must not declare F9 closed with eval evidence generated before TA1+TA2 land.

---

## §5 (filtered) — Hidden Couplings relevant to TA3

From plan §5.4:

| Coupling | Impact on TA3 |
|---|---|
| T4 serialization / T5 dict consumption | Unaffected by TA3 |
| T6 imports `nlp.pipeline.pipeline` transitively | TA3 removes extra JSONL fields from `pipeline.py`. Verify the change doesn't break `import nlp.pipeline.pipeline` before running eval. |

**New coupling (TA3 → TA1 narrative):**
> TA3's F13 supersession banner must reference the TA1 decision log by its exact path: `.dev/decision-logs/TA1-ollama-host-wiring.md`. If TA1 saved its decision log under a different name, TA3 must use the actual path. Resolve before writing the banner.

---

## DoD (Definition of Done)

- [ ] `.dev/execution-logs/T2-db-service.md` exists and covers all 6 T2 kill criteria
- [ ] `Pipeline._log_stage` emits exactly the 11 §2-schema fields; no extra keys
- [ ] `test_resolve_ambiguity` function exists in `nlp/tests/test_ambiguity_detector.py`
- [ ] README dataset section lists 10 columns including `ticket_prefix`
- [ ] README Evaluation section includes results table (or documented environment blocker)
- [ ] T4 decision log has supersession banner at top pointing to TA1 decision log
- [ ] All 39 existing unit tests still pass (`cd nlp && pytest tests/ -q`)
- [ ] F14 (T2 decision log format) is explicitly marked deferred — no action taken
