# Learning Retrospective — minivii-build

## 1. Task context

- **Task:** `minivii-build` — greenfield Mini Nivii: a four-container Docker Compose NL-to-SQL BI agent over a 24k-row POS dataset, with a multi-stage NLP pipeline, transparent UI, and 12-case evaluation harness.
- **Dates:** Primary build and audit cycle 2026-05-26; follow-on `eval-remediation` 2026-05-27; portability verification on a second laptop 2026-05-27. This retrospective written 2026-06-14.
- **What it produced:** `db` / `nlp` / `ui` / `ollama` services; DIN-SQL-style pipeline (ambiguity → classify → generate → ReAct execute → synthesize); submission README; architecture folder; two audit passes and three amendment subtasks (TA1–TA3), then a separate eval-remediation plan that closed residual gate gaps.
- **Why this qualified:** Multiple architectural-tier subtasks (NLP pipeline core, ReAct loop, Ollama host wiring), a new multi-container pattern I had not shipped end-to-end before, and a full local-LLM operational surface (model pulls, RAM ceilings, inference latency) that only became real under integration — not under mocked unit tests.

---

## 2. What I now understand that I didn't before

### Multi-container systems fail at seams, not at business logic

The three bugs that actually blocked `docker compose up` were all boring integration mistakes:

1. **Env var declared ≠ env var consumed.** Compose set `OLLAMA_URL=http://ollama:11434`, but the Ollama Python SDK reads `OLLAMA_HOST` and defaults to `127.0.0.1:11434`. Health display in `main.py` read `OLLAMA_URL`, so the variable looked wired when it wasn't on the inference path. LLM calls from inside `nlp` silently hit localhost.

2. **Healthcheck probe must match image contents.** `db` used `python:3.11-slim` with a `curl`-based healthcheck. No `curl` in the image → healthcheck never passes → `nlp` never starts because of `depends_on: service_healthy`.

3. **Host PYTHONPATH ≠ container module layout.** On the host: `python -m nlp.eval.harness`. In the container (`WORKDIR /app`, package copied flat): `python -m eval.harness`. Same code, different import root.

I had treated these as "obvious Docker stuff" that executors would get right. They didn't — and neither did my plan's §2 contracts, which named env vars and eval entrypoints without requiring a consumption-path proof. **Green unit tests (39 → 46 passed) were compatible with all three bugs** because tests mocked HTTP/LLM or ran host-side without crossing container DNS.

The generalization: for Compose stacks, the contract row should be **declare → consume → verify in-network**, not just "this env var exists in yaml."

### Eval gates need explicit tiers; substring checks lie

Before remediation, the harness could report ~83% structural pass while composite `case_pass` was much lower. Structural checks (`sql_pass`: expected substrings present, forbidden absent) can pass when:

- SQL is syntactically plausible but queries an empty time window (case 11: `recent` resolved with `now - 30 days` against a static 2024 dataset evaluated in 2026).
- SQL omits a business-critical filter (`total < 0` for returns) while still containing generic clauses.
- Execution fails after four ReAct steps but the last attempted SQL still contains `where` and `date`.

I now understand **structural, execution, and judge** as three different epistemic claims:

| Tier | Claims | Can pass when wrong because… |
|------|--------|------------------------------|
| Structural | Generated SQL *looks* like the right shape | Substrings don't guarantee semantics |
| Execution | SQL ran and returned rows | Rows can be empty or wrong |
| Judge | Narrative matches data | Shares synthesis model; expensive |

The fix boundary was clear once written down: **grounding and gates before generation tuning.** Anchoring temporal disambiguation to `date_range.end` (not wall clock) is a contract fix, not a prompt-engineering fix. Adding `execution_pass` to `case_pass` is a measurement fix, not a model fix.

### Temporal grounding is a first-class NL-to-SQL problem

Case 11 taught the most durable domain lesson. The ambiguity rule fired correctly ("recent without explicit time window"). The disambiguation rule in `domain.yaml` said "default to last 30 days." The SQL generator translated that into `strftime(..., 'now', '-30 days')`. The dataset ends 2024-11-20. Eval ran 2026-05-27. Zero rows. ReAct observer said REFINE. Refinement kept relative-date logic. Four steps exhausted.

This is not "the model is bad at SQL." It is **calendar-relative language applied to a static snapshot without a dataset anchor.** The correct fix lives in disambiguation (`SemanticLayer.get_date_anchor()` → absolute window in `resolved_question`), with `_observe_result` injecting dataset bounds as a safety net — not in asking the LLM to "try harder."

I will recognize this failure mode again anywhere NL preprocessing emits relative time language against a non-live database.

### Keyword classifiers need ordering discipline and override hooks

Case 1 (`most bought product on Fridays`) failed `class_pass` because `"friday"` in `KEYWORD_CLASS_MAP` matched before aggregation signals. The classifier returned `time_filter` and pulled the wrong few-shot bucket — even though the SQL stage sometimes still produced correct aggregation SQL.

Heuristic-first classification is fast and deterministic, but **first-match wins** is a hidden policy. Production-shaped systems need explicit override predicates (e.g., aggregation phrases beat day-of-week keywords) or multi-label scoring — not just a longer keyword list.

### ReAct without grounding context mostly burns steps

The ReAct loop's `_observe_result` heuristics (0 rows → REFINE, >10K rows → REFINE, etc.) are reasonable for typo-level SQL errors. They do not fix systematic grounding errors: if every refinement still uses `now`, the observer has no lever except "try again" until `max_steps=4`.

I now see ReAct as **useful for local SQL repair, useless for upstream semantic mistakes.** The plan's highest re-plan risk pointed at T4 refinement effectiveness; the actual pain was upstream temporal resolution — a coupling the adversarial pass didn't name.

### Local LLM ops are a hardware contract, not an implementation detail

Portability testing on a 14 GB RAM laptop made this concrete:

- Default models (`qwen2.5-coder:14b` + `qwen3:32b`) need ~29 GB on disk and ~20 GB RAM for synthesis. SQL could complete on CPU in ~8–9 minutes; synthesis OOM'd with `model requires more system memory (20.0 GiB) than is available (13.0 GiB)`.
- `docker-compose.yml` hardcodes `environment:` values — shell `export SQL_MODEL=...` before `docker compose up` does **not** override them. Fallback requires `docker compose run -e` or editing compose.
- UI `httpx` default 5s read timeout fails during inference even when the browser shows a spinner — timeout must match inference latency (600s here).

**Portability of orchestration ≠ performance parity.** The stack boots identically on two Windows machines; full default-model e2e does not. That distinction matters for how I describe "it works" to reviewers vs. how I plan my own dev loop.

### Full schema injection is the right demo tradeoff

For a single `sales` table, `SchemaLinker.link()` ignoring the question and returning full DDL via `SemanticLayer.render_ddl()` is correct — not a shortcut. Retrieval (ChromaDB, embeddings) adds dependency surface and test complexity with no benefit at this scale. The production scale-out path (swap linker implementation, keep `POST /execute` boundary) is clean because the wire contract was frozen early.

### Non-cascading ambiguity resolution prevents a real bug class

Applying ambiguity rules sequentially to partially-resolved text (v7 spec bug) produces malformed questions. Collecting all triggers against the **original** question and composing qualifiers once is a pattern I can reuse anywhere rule-based NL preprocessing stacks multiple transforms.

---

## 3. Decisions I made and would make again

**Four-container separation with frozen wire contracts (`POST /execute`, `POST /query`).** Even at demo scale, forcing HTTP between `db` and `nlp` made the backend swappable and gave the auditor concrete seams to inspect. The bugs found there were cheaper than if `db` had been embedded in `nlp`.

**Rule-based `AmbiguityDetector` over LLM disambiguation.** 20–30s latency before SQL generation for a demo with known ambiguity axes wasn't worth it. Rules are auditable and testable without GPU.

**Omitting GPU `deploy.resources` from compose (Option 3).** Portability check confirmed: `ollama/ollama` detects CUDA at runtime; machines without NVIDIA Container Toolkit aren't blocked at compose parse time.

**Structured `ObservationResult` / `Action` enum instead of string sentinels (`"Accept." in observation`).** This held under audit. Refinement logic stays typed and grep-able.

**`case_pass` as explicit conjunction after remediation.** `sql ∧ class ∧ ambiguity ∧ execution` makes false positives visible. Should have been in the original plan §2, but the formula itself is right.

**Dataset-anchored temporal disambiguation (eval-remediation P1).** Fix the rule output deterministically rather than hoping the LLM infers dataset bounds from DDL comments.

**Decision logs for architectural subtasks (T3, T4, TA1).** Even when one log (T4) went stale, the supersession banner pattern (TA3 → TA1 authority) worked. The chain of rationale survived better than code comments alone.

---

## 4. Decisions I made that I would change

**Treating compose env vars as satisfied by declaration.** I would require each named env var to list: file that reads it, function that reads it, and one integration test or smoke command that fails if unwired. `OLLAMA_URL` in §2 Naming was vestigial until TA1.

**Closing T7 / §8 handoff with structural-only eval evidence and known failures.** README initially documented 10/12 structural with case 11 execution-failing — honest, but the plan called eval a "gate" without defining which tier gates submission. I would not call the build complete until `case_pass` formula was implemented and at least one composite run was archived — or explicitly downgrade "gate" to "smoke" in the plan.

**Letting T4 decision log rationalize `OLLAMA_URL` as acceptable (health display only).** That narrative concealed a stack-breaking bug until cold-read audit. Architectural logs should HALT on "assumed SDK default matches compose" — or cite a verified integration test. A log that explains away a missing wire is worse than no log.

**No mandatory `docker compose up` smoke subtask before T7.** Three critical defects would have been caught in one bring-up attempt. I would add a minimal integration checkpoint: all healthchecks green, one `POST /query` reaches Ollama, one `GET /health` returns 24212 rows.

**Deferring eval honesty to a second plan.** TA1–TA3 closed audit findings; `execution_pass` and temporal anchor required `eval-remediation`. One plan with the full gate formula would have been less churn — though the second plan benefited from a context map and clearer failure analysis.

**TA4 fixes (ollama image `curl`, UI host port 3001) outside the amendment DAG.** Ad hoc bring-up fixes escape traceability. I would reserve an "integration hardening" amendment slot in every multi-container plan.

---

## 5. Patterns in my own thinking

**Trusted unit-test green as integration proxy.** I watched 39 → 46 tests pass and felt progress. Most tests mock `LLMClient` and HTTP. That is appropriate for fast feedback but I mentally upgraded it to "the stack works." The audit's cold read — grep for `ollama.generate()` vs `Client(host=)` — found what tests couldn't.

**Underweighted SDK/library defaults vs. my compose contract.** I assumed "we set the URL in yaml" meant the app used it. Third-party SDKs have their own env var names (`OLLAMA_HOST`). I need a reflex: **when compose sets X, grep for X in application code**, not just in Dockerfile/compose.

**Overweighted T4 ReAct risk, underweighted disambiguation ↔ dataset coupling.** The plan's §5.3 highest re-plan risk was refinement effectiveness. Actual eval pain was temporal grounding and classifier ordering — upstream of ReAct. I planned adversarial depth where the architecture diagram looked sophisticated, not where the data contract was implicit.

**Accepted narrative closure before operational closure.** CHANGELOG cited `.dev/execution-logs/T2-db-service.md` before the file existed. §8 claimed clean tree while `plan.md` was uncommitted. I prioritize artifact completeness for reviewers — sometimes ahead of verified behavior. The discomfort is signal: **citation ahead of evidence** is a pattern to catch early.

**Reasonable portability optimism.** I believed README CPU fallback would "just work" with env vars before `compose up`. Hardware testing showed hardcoded compose `environment:` blocks that path. I should test documented fallbacks on a second machine *before* writing them as instructions, not after.

---

## 6. Open questions

- **How to test multi-container seams without a full GPU eval run?** Minimal smoke tests (healthchecks, one mocked-Ollama query, module path inside container) caught TA1-class bugs in retrospect — but what's the minimal permanent harness? Testcontainers? Compose profile `smoke`?

- **Classifier design beyond first-match keywords.** Option C overrides fixed eval cases — what does a maintainable priority system look like as keyword maps grow? Scored multi-label? Small classifier model?

- **When does retrieval-augmented schema linking pay for its complexity?** Single table was clear. Is there a row/column count heuristic that justifies the swap?

- **Eval judge independence.** Judge shares `SYNTHESIS_MODEL` — correlated failure modes. Is a smaller/different model enough, or do you need rule-based narrative checks for numbers-in-text?

- **Host Ollama vs. container Ollama for dev velocity.** `runtime_performance.md` hints at host install for Mac/Windows. I haven't internalized the tradeoff table (volume cache, DNS, GPU passthrough, reproducibility for reviewers).

- **Static dataset + relative language in production.** Dataset anchor works for demo eval. For a live warehouse, does disambiguation need a `temporal_mode: snapshot | rolling` flag in the semantic layer? I don't have a crisp rule yet.

---

## 7. Single paragraph synthesis

Building Mini Nivii taught me that **multi-agent plans and green unit tests can produce a convincing illusion of done while the actual system fails at Docker seams and eval semantics** — env vars that exist in compose but aren't read by the SDK, healthchecks that reference binaries not in the image, module paths that differ host vs. container. The interesting NL-to-SQL ideas (non-cascading ambiguity, ReAct with typed observations, full schema injection for one table) mostly held; what hurt was assuming calendar-relative disambiguation would work against a static dataset without anchoring to `date_range`, and measuring SQL substring presence without gating on `execution.success`. The compounding lesson: **integration contracts need consume-path evidence, and eval tiers must be explicit before you trust a pass rate** — otherwise you optimize prompts for a pipeline that is failing upstream for boring, deterministic reasons.
