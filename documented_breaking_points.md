# Documented breaking points

Curated stress cases from manual UI probing and lab notes — **not** covered by the 12-case golden eval. Each entry is observed behavior, not a backlog item (see [open-questions.md](open-questions.md) for intended fixes).

**Severity:** `demo-ok` (expected weakness) · `trust-risk` (looks right, wrong story) · `eval-known` (in golden set) · `ops` (environment / routing)

---

## 1. Off-domain NL — narrative disconnect (airplane food)

| Field | Detail |
|-------|--------|
| **Query** | `what is the deal with airplane food?` |
| **Observed** | `query_class`: `simple` · `steps_taken`: 1 · execution OK · table: `airplane_food_transactions` = **19,291** |
| **SQL** | `SELECT COUNT(*) AS airplane_food_transactions FROM sales WHERE product_name LIKE '%Alfajor%' OR product_name LIKE '%Alf.%';` |
| **Narrative (excerpt)** | Claims **19,291 airplane food transactions**, “in-flight purchases,” menu variety / portion-size recommendations — treats the alias and question literally, not “count of Alfajor-pattern POS lines.” |
| **Why it breaks** | SQL model **reinterprets** off-domain wording onto schema (Alfajor / `Alf.%`); synthesizer reads the **count + column alias** and invents an aviation/meal story. Prompt is grounded on result rows, not SQL text; no OOD gate. User sees polished BI copy that does not match what was actually queried. |
| **Severity** | `trust-risk` |
| **Mitigation** | Accepted for demo — SQL + table visible in UI; no OOD or narrative–SQL consistency check. Not in golden eval by design. |
| **Source** | UI stress test, 2026-05-27 (pre-submission) |

---

## 2. Adversarial in-domain — prime quantity + wall-clock window

| Field | Detail |
|-------|--------|
| **Query** | `what is the name of the product with the smallest prime number as the total sold quantities from the last 30 days` |
| **Observed** | `query_class`: aggregation · `steps_taken`: 4 (max) · SQL used `strftime(..., 'now', '-30 days')` · 0 rows in 2024 dataset · warning: max steps without successful result |
| **Why it breaks** | Dataset is Sep–Nov **2024**, not “today”; prime constraint dropped; ReAct retries empty window. Ground truth on anchored window would be e.g. `Tableta 70 cacao x80g`, qty 2 (lab check). |
| **Severity** | `demo-ok` (honest failure) |
| **Mitigation** | Accepted — shows ReAct + date anchoring limits; related to temporal grounding in [open-questions.md](open-questions.md). |
| **Source** | adversarial run (prime + last 30 days) |

---

## 3. Execution exhaustion — “Recent sales”

| Field | Detail |
|-------|--------|
| **Query** | `Recent sales` |
| **Observed** | `time_filter` · 4 steps · SQL: `WHERE date >= strftime('%Y-%m-%d', 'now', '-30 days')` · `Query could not be executed. max steps reached without successful result` |
| **Why it breaks** | Wall-clock “recent” on static 2024 CSV → empty or wrong window; ReAct exhausts `max_steps=4`. v1.1 improves disambiguation text but **eval case 11** still fails execution. |
| **Severity** | `eval-known` |
| **Mitigation** | Documented in README eval table (Case 11). See [open-questions.md](open-questions.md) (case 11). |
| **Source** | golden eval Case 11 |

**Note:** A lab log entry pasted a Friday-busiest synthesis paragraph under this run; the pipeline only calls synthesis when `execution.success and execution.data` — the **UI shows an execution error**, not that narrative. Treat pasted synthesis as log noise, not product behavior.

---

## 4. Counterfactual / hypothetical BI — promotion bundles

| Field | Detail |
|-------|--------|
| **Query** | `what if we like stocked up on Alfajor Sin Azucar Suelto and ran a promotion for 12 unit bundles?` |
| **Observed** | Timeout / service unavailable · `POST /api/generate` ~8m51s · model swap ~96s · `0/65 layers offloaded to GPU` |
| **Why it breaks** | Counterfactual not in schema; model struggles → long inference → httpx/UI path surfaces outage. |
| **Severity** | `ops` + `demo-ok` |
| **Mitigation** | Accepted — not a supported question class; see [runtime_performance.md](runtime_performance.md) for GPU/timeout context. |
| **Source** | promotion stress test |

---

## 5. Classification drift — right answer, surprising label

| Field | Detail |
|-------|--------|
| **Query** | `Most bought product on Fridays` |
| **Observed** | `query_class`: `time_filter` (not `aggregation`) · 1 step · correct-looking SQL (`SUM(quantity)`, `week_day = 'Friday'`) · Alfajor, 850 units |
| **Why it breaks** | Keyword classifier map iteration; answer can be right while **eval `class_pass`** disagrees (Case 1 was fixed in v1.1 via aggregation override — UI ad-hoc runs may still show `time_filter` depending on phrasing). |
| **Severity** | `demo-ok` |
| **Mitigation** | Eval harness enforces class gates; v1.1 override for ranking + day-of-week co-occurrence. |
| **Source** | README eval Case 1 notes |

---

## 6. Host Ollama — synthesis 404 (models split across backends)

| Field | Detail |
|-------|--------|
| **Query** | Any UI query that completes SQL then calls synthesis (default models) |
| **Observed** | SQL stage OK (e.g. `qwen2.5-coder:14b` on host) · failure at synthesis: `model 'qwen3:32b' not found` (404) · `/health` may show `host.docker.internal:11434` while Compose pulled 32b only in container |
| **Why it breaks** | `resolve_ollama_url()` probes API reachability, not model tags; host and container have **separate** `ollama pull` caches. |
| **Severity** | `ops` |
| **Mitigation** | On host: `ollama pull qwen3:32b` (and 14b). Or force `OLLAMA_URL=http://ollama:11434` on `nlp`. Documented in [runtime_performance.md](runtime_performance.md#separate-model-libraries-host-vs-container). |
| **Source** | Final pre-submission UI test (2026-05-28) |

---

## Contrast — normal path (optional)

| Query | Outcome |
|-------|---------|
| `what's the most sold product` | ~7 min e2e (GPU host), aggregation, 1 step, Alfajor 4566 — matches expected POS behavior |
| `what's the bussiest day of the week` | Friday 1985 transactions; synthesis reasonable |

**Source:** normal-path UI runs

---

## How this relates to other docs

| Doc | Role |
|-----|------|
| [README.md](README.md) § Evaluation | Golden 12 — contract pass/fail |
| [open-questions.md](open-questions.md) | What we might fix next |
| [portability_check_on_my_laptop.md](portability_check_on_my_laptop.md) | Second machine, RAM/OOM |
| [runtime_performance.md](runtime_performance.md) | Host vs container latency and pulls |
| [handoff_notes_in_raw_criollo.md](handoff_notes_in_raw_criollo.md) | Informal operator notes (EN/ES) |
