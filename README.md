# Mini Nivii

A domain-scoped, semantics-grounded NL-to-SQL business intelligence agent.

Mini Nivii takes a natural language question about point-of-sale data and returns a structured analytical narrative — SQL, result table, and recommendation-grade insight — not just raw rows. The pipeline decomposes the problem into auditable stages (DIN-SQL pattern) with explicit tradeoff reasoning at each layer.

---

## Quick Start

```bash
git clone <repo>
cd minivii_challenge
# Place data.csv in the repo root (not committed — volume-mounted)
docker compose up
# Open http://localhost:3000
```

**⚠️ First-run note: ~29 GB download** (`qwen2.5-coder:14b` ~9 GB + `qwen3:32b` ~20 GB). Subsequent runs use the cached `ollama_cache` volume — no re-download.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DB_URL` | `http://db:8001` | Database service endpoint |
| `OLLAMA_URL` | `http://ollama:11434` | Ollama inference endpoint |
| `SQL_MODEL` | `qwen2.5-coder:14b` | SQL generation and refinement |
| `SYNTHESIS_MODEL` | `qwen3:32b` | Narrative synthesis |

### Service ports

| Service | Port |
|---|---|
| `db` | 8001 |
| `nlp` | 8002 |
| `ui` | 3000 |
| `ollama` | 11434 (internal) |

---

## CPU-Only Fallback

On machines without a GPU, override the model environment variables before starting:

```bash
SQL_MODEL=qwen2.5-coder:7b SYNTHESIS_MODEL=qwen3:8b docker compose up
```

**Warning:** CPU-only generation runs at 2–4 tok/s. SQL generation: 8–15 min/step. Full pipeline: 45–90 min per query. GPU is strongly recommended for evaluation.

---

## Architecture Overview

Four-container Docker Compose layout on bridge network `nivii-net`:

```
┌──────────────────────────────────────────────────────────┐
│  docker-compose.yml                                      │
│                                                          │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────┐  │
│  │  db      │    │  nlp         │    │  ui            │  │
│  │  FastAPI │◄───│  FastAPI     │◄───│  FastAPI +     │  │
│  │  SQLite  │    │  Pipeline    │    │  Jinja2 HTML   │  │
│  │  :8001   │    │  :8002       │    │  :3000         │  │
│  └──────────┘    └──────┬───────┘    └────────────────┘  │
│                         │                                │
│                  ┌──────▼───────┐                        │
│                  │  ollama      │                        │
│                  │  :11434      │                        │
│                  └──────────────┘                        │
└──────────────────────────────────────────────────────────┘
```

- **`db`** — ingests `data.csv`, normalizes dates to ISO at load time, exposes `POST /execute`, `GET /schema`, `GET /health`.
- **`nlp`** — multi-stage NL-to-SQL pipeline; calls `db` and Ollama.
- **`ui`** — single-page interface; async POST to `nlp` with 600s timeout.
- **`ollama`** — pulls and serves `SQL_MODEL` and `SYNTHESIS_MODEL` on first run.

---

## Pipeline Stages

```
NL Question
    │
    ▼
AmbiguityDetector     Rule-based pre-generation: resolve underspecified axes (zero latency)
    │
    ▼
QueryClassifier       Keyword heuristic (60–70% coverage) + LLM fallback
    │
    ▼
SchemaLinker          Injects CREATE TABLE DDL from semantic layer (full schema, single table)
    │
    ▼
SQLGenerator          NL + linked schema → SQL (qwen2.5-coder:14b)
    │
    ▼
SQLExecutor           ReAct loop: execute → observe → decide → refine (semantic failure detection)
    │
    ▼
ResultSynthesizer     Result set → narrative (qwen3:32b; guarded on execution success)
    │
    ▼
Structured answer (SQL + table + narrative)
```

Each stage writes structured JSONL logs under `logs/runs/` for auditability.

---

## Architecture Decision Table

| Decision | Why | Tradeoff |
|---|---|---|
| DIN-SQL stage decomposition | Token budget management per stage; enables two-model strategy on local hardware | More code; each stage is a failure point |
| CREATE TABLE over natural language schema | Forces correct column reference and type awareness | Slightly more verbose in prompt |
| Date normalization at ingestion (not in SQL) | Source M/D/YYYY; fixed-position `substr()` fails for 48% of rows | Requires Python preprocessing step in `db` service |
| ReAct over fixed retry | Detects semantic failures (0 rows, wrong cardinality) that syntax retry misses | More complex; 2× latency per correction step |
| Rule-based AmbiguityDetector | Zero latency; LLM call adds 20–30s before SQL generation | Coverage is finite; open-domain queries may not resolve |
| Keyword heuristic QueryClassifier | Fires for 60–70% of questions at near-zero cost | May misclassify edge cases |
| SQLite over Postgres | Simplest possible db for demo scope; no infrastructure overhead | Not production-grade for concurrency |
| Four containers over monolith | Each service independently scalable; clear separation of concerns | More orchestration complexity |
| Two-model strategy (14B SQL + 32B synthesis) | Task-matched: SQL needs code precision, synthesis needs narrative reasoning | ~29 GB download; synthesis 2–5 min |
| Structural few-shot examples | Demonstrates expected SQL shape per class without overfitting to specific values | One example per class may not cover all variations |

---

## Evaluation Harness

The evaluation harness is a **final-pass gate, not a CI regression suite**. A full run (12 cases, with judge) takes **90–120 minutes on GPU**.

- **12 POS-domain test cases** across 4 query classes (aggregation, filter, window, comparison)
- **Two-layer validation:** structural SQL clause checks + LLM-as-judge on narrative quality
- Per-case failure isolation; `--skip-judge` available for faster structural-only runs

From the repo root on the host (with `nlp/` on `PYTHONPATH`):

```bash
python -m nlp.eval.harness --skip-judge
```

Inside the `nlp` container (`WORKDIR /app`; top-level package is `eval`, not `nlp.eval`):

```bash
docker compose exec nlp python -m eval.harness
# or structural-only (Phase 2):
docker compose exec nlp python -m eval.harness --skip-judge
```

Results are written to `logs/eval_{timestamp}.json`.

### Evaluation Results (structural, skip_judge=True)

Run date: 2026-05-26  
Environment: Docker `nlp` container (Linux), host GPU Ollama via `host.docker.internal:11434`; models `qwen2.5-coder:14b` / `qwen3:30b`  
Command: `docker compose run --no-deps nlp python -m eval.harness --skip-judge` (db on Compose network; `nlp` service not started — equivalent to `docker compose exec nlp python -m eval.harness --skip-judge` when stack is up)

| Case | Question summary | SQL pass | Class pass | Notes |
|------|-----------------|---------|-----------|-------|
| 1 | Most bought product on Fridays | ✓ | ✗ | SQL correct; keyword classifier returned `time_filter` (Friday) vs expected `aggregation` |
| 2 | Transactions on Saturdays | ✓ | ✓ | |
| 3 | Busiest hours on weekdays | ✓ | ✓ | |
| 4 | Total revenue October 2024 | ✓ | ✓ | |
| 5 | Waiter most revenue | ✓ | ✓ | |
| 6 | Week-over-week revenue trend | ✓ | ✓ | |
| 7 | Top 5 products by revenue | ✓ | ✓ | |
| 8 | Transactions in November | ✓ | ✓ | |
| 9 | Average ticket value per waiter | ✓ | ✓ | |
| 10 | Most popular product (ambiguity) | ✓ | ✓ | Ambiguity resolution applied |
| 11 | Recent sales (ambiguity) | ✓ | ✓ | ReAct hit max steps; structural SQL still matched |
| 12 | Products with most returns | ✗ | ✓ | Generated SQL omitted `total < 0` return filter |

**Structural pass rate: 11/12 SQL, 11/12 class**

Known failures: Case 1 — classifier keyword precedence (`Friday` → `time_filter`); Case 12 — missing negative-total filter in generated SQL.

---

## Scale-Out

Three scenarios for growing beyond this demo scope:

1. **More tables / larger schema** — Replace full schema injection in `SchemaLinker` with retrieval-augmented linking (ChromaDB or pgvector). Store table embeddings; retrieve top-k tables by cosine similarity to the question. Pipeline orchestration code unchanged; only `SchemaLinker` implementation swaps from `render_ddl()` to `retrieve_and_render(question)`.

2. **More data** — SQLite → PostgreSQL with read replicas. The `db` service interface (`POST /execute`) stays unchanged. Swap the backend, add connection pooling, adjust Compose.

3. **High traffic** — The `nlp` service is the bottleneck (3–7 min inference per query on GPU). Scale horizontally with multiple `nlp` replicas behind a load balancer. Add a Redis job queue between `ui` and `nlp` for async processing — UI submits job, polls for result — so the frontend stays responsive under concurrent load.

---

## Production Delta

What would change for a real Nivii deployment beyond this demo:

- **Automated schema enrichment** — profile new tables, generate descriptions, detect date format patterns
- **LLM-path AmbiguityDetector** — handle open-domain queries beyond finite rule coverage
- **Kubernetes per-client deployment** — data never leaves client environment
- **Continuous evaluation pipeline** — every prompt change triggers an eval run
- **Synthesis plausibility filter** — sanity-check narrative numbers against result data before returning
- **CHASE-SQL candidate consistency** — generate N=3 SQL candidates, execute all, select by result majority vote for business-critical queries

---

## Limitations

- **Local model SQL reliability** — small models can produce syntactically valid but semantically wrong SQL. The ReAct loop catches common semantic failures but not all.
- **Latency on CPU-only machines** — see [CPU-Only Fallback](#cpu-only-fallback); 45–90 min per query.
- **Dataset scope** — 60 days (Sep 21 – Nov 20, 2024); annual or year-over-year queries return partial results only.
- **AmbiguityDetector rule coverage** — finite rule set; novel phrasings may not trigger resolution.
- **Eval harness scope** — final-pass gate, not continuous regression in CI.

---

## Dataset

| Property | Value |
|---|---|
| Rows | 24,212 |
| Columns | 10 (`date`, `week_day`, `hour`, `ticket_number`, `ticket_prefix`, `waiter`, `product_name`, `quantity`, `unitary_price`, `total`) |
| Unique products | 68 |
| Unique tickets | 11,771 |
| Unique waiters | 9 |
| Date range | **60 days: Sep 21 – Nov 20, 2024** |
| Revenue | Sep 34.3M ARS · Oct 110.6M ARS · Nov 70.3M ARS |

`data.csv` is **not committed** to this repository. Place it at the repo root before running `docker compose up`; it is volume-mounted read-only into the `db` container.

**Column note:** `ticket_prefix TEXT` is extracted from `ticket_number` at ingest (register/type code: FCA, FCB, NCA, NCB).

**Date handling:** source dates are `M/D/YYYY` (not zero-padded). Dates are normalized to ISO at ingestion — all SQL uses `strftime()` on the normalized column, never fixed-position `substr()` on raw strings.
