# Mini Nivii — Final Build Specification

> Version: FINAL (corrected from v7 semifinal)
> Status: Build-ready. All critical findings from pre-build audit addressed.
> Challenge window: 72 hours from Tuesday 15:44.
> Corrections applied: 8 critical, 4 structural. See §10 for diff against v7.

---

## 1. Product Context

### What Nivii Actually Is

Not a copilot. A **domain-scoped, semantics-grounded business intelligence agent** that takes a natural language question and returns a structured analytical narrative — not a chart, not raw data, but a recommendation-grade insight. The McKinsey framing is precise: they are automating the *output format* of a consulting engagement, not just data retrieval.

The human is upstream (asking) and downstream (acting). The system reasons autonomously in between.

### Core Value Chain

```
NL Question → [semantic context] → SQL generation → execution → narrative synthesis → actionable answer
```

### Evaluation Signal (CTO's verbatim criteria)

"Architectural decisions and trade-offs matter most... a smaller model is easier to host... explain how you mitigate quality (prompting strategy, constrained decoding, schema injection, examples, validation loops, retries, etc.)."

This is a near-exact description of the pipeline architecture below. The README is as much a submission artifact as the code.

### What This Challenge Actually Tests

1. Architecture decomposition and tradeoff reasoning (stated explicitly)
2. Docker/containerized deployment — portability and reproducibility
3. Schema-aware SQL generation with date handling traps
4. Graceful failure handling — validation loops, retries mentioned verbatim
5. Product thinking — transparent UI showing SQL + result + narrative
6. README quality as a submission artifact

---

## 2. Dataset Contract

### Authoritative Profile (from actual data.csv)

| Property | Value |
|---|---|
| Rows | 24,212 |
| Columns | 9 |
| Unique products | 68 |
| Unique tickets | 11,771 |
| Unique waiters | 9 (IDs: 0, 51, 52, 101, 102, 103, 104, 105, 116) |
| **Actual date range** | **September 21, 2024 – November 20, 2024 (60 days)** |
| Negative total rows | 38 (returns/refunds) |
| Float quantity rows | 1 (`Galletita choc limon caja x12u`, qty = 0.5) |
| Revenue by month | Sep: 34,297,200 ARS / Oct: 110,614,650 ARS / Nov: 70,289,725 ARS |

> **Correction from v7:** The dataset spans 60 days, not ~1 year. All eval test cases
> and any README language about data coverage must reflect this.

### Schema

```
date, week_day, hour, ticket_number, waiter, product_name, quantity, unitary_price, total
```

### Critical Data Properties

**Date column format: `M/D/YYYY` — not zero-padded, not ISO.**

Examples: `9/22/2024`, `10/4/2024`, `11/20/2024`. The month and day are single-digit when < 10.
48.2% of rows have a single-digit month or day. Any fixed-position `substr()` formula
that assumes `MM/DD/YYYY` will produce garbage for these rows.

```
# Proof: spec v7 formula on actual data
substr('9/22/2024', 7, 4) = '024'   ← wrong
substr('10/4/2024', 4, 2) = '4/'    ← wrong
substr('11/20/2024', ...) = correct  ← only zero-padded rows work
```

**Resolution: normalize at ingestion. See §5 db service.**

**Ticket number prefixes: FCA, FCB, NCA, NCB.**

Four distinct prefixes exist, present across all months. Likely represent different registers or transaction types. Document in schema but do not assign business meaning without confirmation.

**Quantity is REAL, not INTEGER.**

One row has `quantity = 0.5`. Schema type must be `REAL` or `NUMERIC` throughout — DDL, YAML descriptor, and any Pydantic models.

**`week_day` is reliable.** Verified against parsed dates across all 24,212 rows — zero mismatches. Use this column for all day-of-week filtering. Do not use the date column for day-of-week.

**Top products (by quantity, sales only):**

| Rank | Product | Total Qty |
|---|---|---|
| 1 | Alfajor Sin Azucar Suelto | 4,566 |
| 2 | Alf. 150 aniv. Suelto | 3,801 |
| 3 | Alfajor mixto caja x12un | 1,702 |
| 4 | Alfajor 70 cacao x un | 1,641 |
| 5 | Alfajor choc x un | 1,475 |

**Top product on Fridays (canonical demo query): `Alfajor Sin Azucar Suelto` (850 units).**

---

## 3. Architecture

### Design Philosophy

This submission is an **architectural argument implemented in code**. The argument: here is the correct mental model for this problem, decomposed into auditable stages, with explicit tradeoff reasoning and a reliability layer.

The decomposition follows the DIN-SQL pattern — not just for quality but for **token budget management**: each stage gets a focused, short context, which is what makes the two-model strategy viable on local hardware.

### Service Architecture (Docker Compose — 4 containers)

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

**Networking:** all services on `nivii-net` Docker bridge network.
`nlp` calls `http://db:8001` and `http://ollama:11434`.
`ui` calls `http://nlp:8002`.
No external network calls in the submitted system.

### Pipeline Structure (nlp service internal)

```
MiniNivii Pipeline
├── SemanticLayer            # YAML descriptor → CREATE TABLE DDL rendering
├── AmbiguityDetector        # pre-generation: underspecified axis resolution (rule-based)
├── SchemaLinker             # question → schema injection (full injection, single table)
├── QueryClassifier          # route to generation strategy (keyword heuristic + LLM fallback)
├── SQLGenerator             # NL + linked schema → SQL
├── SQLExecutor              # ReAct loop: execute → observe → decide → refine
├── ResultSynthesizer        # result set → narrative (synthesis model, guarded on success)
├── Pipeline                 # orchestrates stages, structured JSONL logging per step
└── EvaluationHarness        # 12 POS-domain test cases, SQL structural check + judge
```

### Empirical Failure Distribution (production NL-to-SQL research)

| Failure type | Share | Primary mitigation |
|---|---|---|
| Schema linking errors | ~40% | Schema enrichment (CREATE TABLE + comments + sample values) |
| SQL logic errors | ~35% | ReAct loop with semantic observation |
| Value errors | ~25% | Schema enrichment (sample values, type documentation, date format warning) |

Engineering effort follows this distribution. Schema enrichment has higher expected return than prompt tuning.

---

## 4. Model Strategy

### Two-Model Allocation

| Stage | Model | Rationale |
|---|---|---|
| Classification, SQL generation, self-correction | `qwen2.5-coder:14b` | Best SQL generation quality at this size in Ollama. Context stays short per stage. |
| Narrative synthesis | `qwen3:32b` | Strongest available reasoning for narrative output. Input context is short (question + result set). |

> **Correction from v7:** "qwen3.5:27b" does not exist in Ollama's registry.
> Confirmed model name: `qwen3:32b`.
> Fallback (CPU-only or disk-constrained): `qwen3:14b` for synthesis.
> **Verify with `ollama pull qwen3:32b` before writing any code that calls it.**

### First-Run Download Size

| Model | Approximate size |
|---|---|
| `qwen2.5-coder:14b` | ~9 GB |
| `qwen3:32b` | ~20 GB |
| **Total first run** | **~29 GB** |

> **Correction from v7:** README and any user-facing documentation must state ~29 GB,
> not ~9 GB. Failure to warn will cause disk-space errors on evaluator machines.
> Subsequent runs use cached named volume — no re-download.

### CPU-Only Fallback

The latency estimates below assume CUDA throughput (~34 tok/s at 14B). On CPU-only machines, generation is 2–4 tok/s — SQL generation takes 8–15 minutes per step; full synthesis pipeline 45–90 minutes.

**Fallback configuration for CPU-only evaluation:**

```yaml
# docker-compose.yml environment override for cpu-only machines
nlp:
  environment:
    - SQL_MODEL=qwen2.5-coder:7b
    - SYNTHESIS_MODEL=qwen3:8b
```

Document this in the README with a clear note: "If running on CPU only, set these environment variables before `docker compose up`."

### Per-Stage Latency (GPU baseline)

| Stage | Est. input tokens | Model | Est. latency |
|---|---|---|---|
| Query classification (heuristic) | ~0 | none | <10ms |
| Query classification (LLM fallback) | ~300 | 14B | <20s |
| SQL generation | 800–1,200 | 14B | 45–90s |
| Self-correction step (if triggered) | ~1,000 + error | 14B | ~60s |
| Narrative synthesis | 500–800 | 32B | 2–5 min |
| **Typical total** | | | **~3 min** |
| **Worst case (2 correction steps)** | | | **~7 min** |

### Three-Phase Dev Workflow

- **Phase 1 — Rapid iteration (Groq):** `backend="groq"`, `model="groq/qwen3-32b"`. 600+ tok/s, free tier. Use for all prompt engineering and pipeline logic development. Avoid reasoning/R1-distill variants — chain-of-thought verbosity breaks SQL extraction.
- **Phase 2 — Model-aligned validation (Together.ai):** `backend="together"`, `model="together_ai/Qwen/Qwen2.5-Coder-7B-Instruct"`. Closer to submission model profile. Run SQL-layer eval here (`skip_judge=True`).
- **Phase 3 — Submission validation (Ollama):** `backend="ollama"`, `qwen2.5-coder:14b` + `qwen3:32b`. Fix any prompt-transfer gaps. Full eval harness including judge scores.

---

## 5. Component Specifications

### 5.1 db Service

**Responsibility:** ingest `data.csv` into SQLite at container startup, expose query and schema endpoints. This is the only service that touches the raw data file.

**Critical: ISO date normalization at ingestion.**

```python
import csv
import sqlite3
from datetime import datetime

def load_csv_to_db(csv_path: str, db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            date          TEXT,         -- ISO format YYYY-MM-DD (normalized from source M/D/YYYY)
            week_day      TEXT,
            hour          TEXT,
            ticket_number TEXT,
            ticket_prefix TEXT,         -- FCA | FCB | NCA | NCB (extracted from ticket_number)
            waiter        TEXT,
            product_name  TEXT,
            quantity      REAL,         -- REAL: source data contains fractional values (e.g. 0.5)
            unitary_price INTEGER,
            total         INTEGER
        )
    """)

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            # Normalize date from M/D/YYYY to ISO YYYY-MM-DD at load time.
            # This is the single correct fix for the variable-width date format.
            # Do not attempt substr() conversion in SQL — it is wrong for 48% of rows.
            iso_date = datetime.strptime(r['date'], '%m/%d/%Y').strftime('%Y-%m-%d')
            ticket_prefix = r['ticket_number'].split()[0]  # FCA, FCB, NCA, NCB
            rows.append((
                iso_date,
                r['week_day'],
                r['hour'],
                r['ticket_number'],
                ticket_prefix,
                r['waiter'],
                r['product_name'],
                float(r['quantity']),   # float() handles '0.5' without error
                int(r['unitary_price']),
                int(r['total']),
            ))

    conn.executemany(
        "INSERT INTO sales VALUES (?,?,?,?,?,?,?,?,?,?)",
        rows
    )
    conn.commit()
    conn.close()
```

**Endpoints:**

```
POST /execute   — body: {"sql": "SELECT ..."}
                  returns: {"columns": [...], "rows": [[...], ...], "row_count": N}
                  on error: {"error": "message", "sql": "..."}

GET  /schema    — returns CREATE TABLE DDL as rendered by SemanticLayer
GET  /health    — returns {"status": "ok", "row_count": N}
```

---

### 5.2 SemanticLayer

The YAML descriptor is the **source of truth** and the **only domain boundary**. All domain-specific content lives here. Swapping domains means rewriting this file only.

```yaml
domain: point_of_sale
tables:
  sales:
    description: >
      Individual line items from POS transactions at an Argentine confectionery shop.
      Each row is one product sold within a ticket (receipt).
      Multiple rows share the same ticket_number.
    columns:
      date:
        type: TEXT
        description: >
          Transaction date in ISO format YYYY-MM-DD (normalized from source M/D/YYYY at ingestion).
          Use standard SQLite date functions: strftime('%Y-%m', date) for month grouping,
          strftime('%W', date) for week number. Do NOT use substr() for date conversion —
          the column is already ISO.
      week_day:
        type: TEXT
        description: >
          Pre-computed day of week. Values: Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday.
          Use this column for all day-of-week filters — it is more reliable than extracting
          weekday from the date column.
      hour:
        type: TEXT
        description: >
          Transaction time as HH:MM (e.g. '14:32').
          Use CAST(substr(hour,1,2) AS INTEGER) to extract hour as integer.
      ticket_number:
        type: TEXT
        description: >
          Unique receipt identifier (e.g. 'FCB 0003-000024735').
          Use COUNT(DISTINCT ticket_number) for transaction counts, not COUNT(*).
      ticket_prefix:
        type: TEXT
        description: >
          Transaction type/register code extracted from ticket_number.
          Values: FCA | FCB | NCA | NCB. Present across all date ranges.
          Use for queries about transaction types or register-level analysis.
      waiter:
        type: TEXT
        description: >
          Staff member ID stored as text. Values: 0, 51, 52, 101, 102, 103, 104, 105, 116.
          Not a name — filter by numeric ID string.
      product_name:
        type: TEXT
        description: >
          Product sold. 68 unique Argentine confectionery items.
          Note: 'ART. INEXISTENTE' is a placeholder for unregistered items.
      quantity:
        type: REAL
        description: >
          Units sold. Negative values indicate returns/refunds.
          May be fractional (e.g. 0.5 for bulk items).
      unitary_price:
        type: INTEGER
        description: Price per unit in Argentine pesos (ARS).
      total:
        type: INTEGER
        description: >
          Line item total = quantity * unitary_price.
          Negative for returns/refunds (38 rows in dataset).
    sample_values:
      week_day:     [Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday]
      product_name:
        - "Alfajor Sin Azucar Suelto"
        - "Alf. 150 aniv. Suelto"
        - "Alfajor 70 cacao x un"
        - "Alfajor mixto caja x12un"
        - "Alfajor choc x un"
        - "Conito choc x un"
        - "Tableta 70 cacao x80g"
        - "ART. INEXISTENTE"
      waiter:       ["0", "51", "52", "101", "102", "103", "104", "105", "116"]
      ticket_prefix: [FCA, FCB, NCA, NCB]
    date_range:
      start: "2024-09-21"
      end:   "2024-11-20"
      span_days: 60
      note: >
        Dataset covers approximately 2 months (Sep 21 – Nov 20, 2024).
        Queries referencing annual or quarterly periods will have partial data.
        Available full months: October 2024. Partial months: September, November 2024.

relationships: []  # single table — no joins

kpis:
  - name: total_revenue
    definition: "SUM(total)"
    note: "Includes returns (negative totals). Add WHERE total > 0 to exclude returns."
  - name: total_units_sold
    definition: "SUM(quantity)"
  - name: avg_ticket_value
    definition: "SUM(total) * 1.0 / COUNT(DISTINCT ticket_number)"
  - name: transaction_count
    definition: "COUNT(DISTINCT ticket_number)"

disambiguation_rules:
  - when: "most bought / most popular product"
    apply: "default to SUM(quantity) DESC"
    note: "Quantity, not revenue, is the conventional 'most bought' metric."
    state_in_output: true
  - when: "top N without explicit metric"
    apply: "default to SUM(total) DESC"
    note: "Revenue is the default ranking metric when none specified."
    state_in_output: true
  - when: "recent without explicit time window"
    apply: "default to last 30 days using date column"
    note: "Dataset spans 60 days total; 30-day window is meaningful."
    state_in_output: true
  - when: "busiest / most active"
    apply: "default to COUNT(DISTINCT ticket_number) DESC"
    state_in_output: true
  - when: "last month / this month"
    apply: "use October 2024 as the reference full month (strftime('%Y-%m', date) = '2024-10')"
    note: "October is the only complete month in the dataset."
    state_in_output: true
```

**Rendered CREATE TABLE for LLM injection:**

```sql
-- Table: sales | Domain: Point-of-Sale | Argentine confectionery shop
-- Each row = one product sold within a receipt. Multiple rows share ticket_number.
-- Dataset: 24,212 rows | Sep 21 – Nov 20, 2024 (60 days) | 68 products | 11,771 tickets
CREATE TABLE sales (
    date          TEXT,    -- ISO date YYYY-MM-DD. Use strftime() for grouping. Already normalized.
    week_day      TEXT,    -- Day of week: Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday
    hour          TEXT,    -- Transaction time HH:MM. Use CAST(substr(hour,1,2) AS INTEGER) for hour int.
    ticket_number TEXT,    -- Unique receipt ID. Use COUNT(DISTINCT ticket_number) for transactions.
    ticket_prefix TEXT,    -- Register/type code: FCA | FCB | NCA | NCB
    waiter        TEXT,    -- Staff ID as text: 0, 51, 52, 101, 102, 103, 104, 105, 116
    product_name  TEXT,    -- Product sold (68 unique items; 'ART. INEXISTENTE' = unregistered)
    quantity      REAL,    -- Units sold. Negative = return/refund. May be fractional.
    unitary_price INTEGER, -- Price per unit in ARS (Argentine pesos)
    total         INTEGER  -- Line total = quantity * unitary_price. Negative for returns.
);

-- Sample product values: 'Alfajor Sin Azucar Suelto', 'Alf. 150 aniv. Suelto',
--   'Alfajor 70 cacao x un', 'Conito choc x un', 'Tableta 70 cacao x80g'
-- Sample week_day values: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday
-- Sample waiter values: '0', '51', '52', '101', '102', '103', '104', '105', '116'

-- KPI expressions:
-- total_revenue:      SUM(total)       [add WHERE total > 0 to exclude returns]
-- total_units_sold:   SUM(quantity)
-- avg_ticket_value:   SUM(total) * 1.0 / COUNT(DISTINCT ticket_number)
-- transaction_count:  COUNT(DISTINCT ticket_number)
```

---

### 5.3 AmbiguityDetector

Pre-generation step. Rule-based, no LLM call. Pattern-matches the question against known underspecified triggers and applies resolution templates from the YAML descriptor.

**Decision: rule-based, not LLM-based.** An LLM call here adds 20–30s before SQL generation starts. The rule-based path is sufficient for a scoped demo dataset. LLM disambiguation is a production enhancement, documented in README.

> **Correction from v7:** Template application with sequential composition was structurally
> fragile — multi-trigger questions produced malformed NL with unresolved fragments
> (e.g., "recently?" remaining in the string after "in the last 30 days" was appended).
> Fix: resolve all matching triggers against the *original* question, then construct a
> single composed resolved string, rather than piping the output of each rule into the next.

```python
from dataclasses import dataclass, field

@dataclass
class ResolvedQuestion:
    original: str
    resolved: str
    interpretations_applied: list[str] = field(default_factory=list)

AMBIGUITY_TRIGGERS: dict[str, str] = {
    "most":     "most bought / most popular product",
    "popular":  "most bought / most popular product",
    "top":      "top N without explicit metric",
    "best":     "top N without explicit metric",
    "recent":   "recent without explicit time window",
    "latest":   "recent without explicit time window",
    "busiest":  "busiest / most active",
    "active":   "busiest / most active",
    "last month":  "last month / this month",
    "this month":  "last month / this month",
}

def detect_and_resolve(question: str, domain_descriptor: dict) -> ResolvedQuestion:
    fired_axes: dict[str, dict] = {}

    # Collect all matching rules against the ORIGINAL question.
    # Do not apply rules incrementally — prevents composition artifacts.
    for trigger, axis in AMBIGUITY_TRIGGERS.items():
        if trigger in question.lower() and axis not in fired_axes:
            rule = lookup_disambiguation_rule(axis, domain_descriptor)
            if rule:
                fired_axes[axis] = rule

    if not fired_axes:
        return ResolvedQuestion(original=question, resolved=question)

    # Build qualifiers from all fired rules, then append once to the original question.
    qualifiers = []
    interpretations = []
    for axis, rule in fired_axes.items():
        qualifier = rule.get("apply", "")
        if qualifier:
            qualifiers.append(qualifier)
        interpretations.append(f"{axis}: {qualifier}")
        log_interpretation(axis, rule)

    # Single composition: original question + joined qualifiers.
    # Strips trailing punctuation from original before appending.
    base = question.rstrip("?.!")
    resolved = base + " — " + "; ".join(qualifiers) if qualifiers else question

    return ResolvedQuestion(
        original=question,
        resolved=resolved,
        interpretations_applied=interpretations,
    )
```

---

### 5.4 QueryClassifier

Routes the resolved question to a generation strategy before SQL generation. Classification drives both the prompt template and the structural few-shot example injected.

**Decision: keyword heuristic first, LLM fallback.** On hardware where every 14B call costs 15–20s, a keyword pass fires for 60–70% of questions at near-zero cost.

```python
from enum import Enum

class QueryClass(Enum):
    TIME_FILTER  = "time_filter"
    WINDOW       = "window"
    AGGREGATION  = "aggregation"
    SIMPLE       = "simple"

# Priority order is explicit and intentional — more specific classes first.
# TIME_FILTER > WINDOW > AGGREGATION > SIMPLE (via LLM fallback)
# Do not reorder — precedence is load-bearing.
KEYWORD_CLASS_MAP: dict[QueryClass, list[str]] = {
    QueryClass.TIME_FILTER: [
        "on monday", "on tuesday", "on wednesday", "on thursday", "on friday",
        "on saturday", "on sunday", "on weekends", "on weekdays",
        "in the morning", "in the afternoon", "peak hour", "busiest hour",
        "what hour", "what time", "what day",
    ],
    QueryClass.WINDOW: [
        "trend", "week-over-week", "month-over-month", "over time",
        "growth", "change over", "evolution", "compared to last",
    ],
    QueryClass.AGGREGATION: [
        "most", "top", "best", "total", "average", "how many",
        "sum", "by product", "by waiter", "per product", "per waiter",
        "breakdown", "ranking",
    ],
}

def classify(question: str, llm_client) -> tuple[QueryClass, str]:
    """Returns (QueryClass, method) where method is 'heuristic' or 'llm'."""
    q = question.lower()
    for cls, keywords in KEYWORD_CLASS_MAP.items():
        if any(kw in q for kw in keywords):
            return cls, "heuristic"
    return _llm_classify(question, llm_client), "llm"

def _llm_classify(question: str, llm_client) -> QueryClass:
    prompt = f"""Classify this SQL query question into exactly one category.

Categories:
- time_filter: filtering by day of week, hour of day, or time period
- window: trends over time, week-over-week or month-over-month comparisons
- aggregation: GROUP BY queries, totals, counts, rankings by product/waiter
- simple: single-condition filter with no grouping

Question: {question}

Respond with exactly one word: time_filter, window, aggregation, or simple"""

    response = llm_client.generate(prompt, temperature=0.0)
    label = response.strip().lower()
    try:
        return QueryClass(label)
    except ValueError:
        return QueryClass.SIMPLE  # safe fallback
```

---

### 5.5 SQLGenerator

```python
def generate_sql(
    resolved_question: ResolvedQuestion,
    linked_schema: str,
    query_class: QueryClass,
    kpi_definitions: list[dict],
    llm_client,
) -> str:
    prompt = build_sql_prompt(
        question=resolved_question.resolved,
        schema=linked_schema,
        query_class=query_class,
        kpi_definitions=kpi_definitions,
        few_shot_example=FEW_SHOT_EXAMPLES[query_class],
    )
    response = llm_client.generate(prompt, temperature=0.0)
    return extract_sql(response)
```

**Prompt structure (order is load-bearing):**
1. CREATE TABLE schema — first, so it anchors the model's schema understanding
2. KPI definitions — second, resolves semantic ambiguity in metric terms
3. Structural few-shot example — third, demonstrates expected SQL shape
4. Resolved question — fourth
5. Output instruction — last: "Return only the SQL query. No explanation. No markdown fences."

No chain-of-thought. Small models produce verbose reasoning that corrupts SQL extraction.
Temperature 0.0 for deterministic output.

**Few-shot examples — actual POS domain, SQLite-valid, ISO dates:**

```python
FEW_SHOT_EXAMPLES: dict[QueryClass, str] = {

    QueryClass.SIMPLE: """
-- Q: How many transactions happened on Saturdays?
SELECT COUNT(DISTINCT ticket_number) AS transaction_count
FROM sales
WHERE week_day = 'Saturday';
""",

    QueryClass.AGGREGATION: """
-- Q: What is the most bought product on Fridays?
SELECT product_name,
       SUM(quantity) AS total_qty
FROM sales
WHERE week_day = 'Friday'
  AND total > 0
GROUP BY product_name
ORDER BY total_qty DESC
LIMIT 10;
""",

    QueryClass.TIME_FILTER: """
-- Q: What are the busiest hours on weekdays?
SELECT CAST(substr(hour, 1, 2) AS INTEGER) AS hour_of_day,
       COUNT(DISTINCT ticket_number) AS transactions
FROM sales
WHERE week_day NOT IN ('Saturday', 'Sunday')
GROUP BY hour_of_day
ORDER BY transactions DESC
LIMIT 10;
""",

    QueryClass.WINDOW: """
-- Q: What is the week-over-week revenue trend?
-- date column is ISO YYYY-MM-DD (normalized at ingestion). Use strftime() directly.
WITH weekly AS (
    SELECT strftime('%Y-W%W', date) AS week,
           SUM(total) AS weekly_revenue
    FROM sales
    WHERE total > 0
    GROUP BY week
)
SELECT week,
       weekly_revenue,
       weekly_revenue - LAG(weekly_revenue) OVER (ORDER BY week) AS wow_change
FROM weekly
ORDER BY week;
""",
}
```

> **Correction from v7:** Window few-shot example previously used a broken substr()
> formula for date conversion. Now uses `strftime('%Y-W%W', date)` directly, which is
> correct because the date column is ISO after ingestion normalization.

**`extract_sql` — rule-based, no LLM call:**

```python
import re

def extract_sql(response: str) -> str:
    # 1. Strip markdown fences
    response = re.sub(r"```sql|```", "", response).strip()
    # 2. Find first SELECT/WITH statement
    match = re.search(r"\b(SELECT|WITH)\b", response, re.IGNORECASE)
    if match:
        sql = response[match.start():]
        # 3. Truncate at first semicolon (inclusive)
        if ";" in sql:
            sql = sql[:sql.index(";") + 1]
        return sql.strip()
    # 4. No valid SQL found — return raw, caller handles via try_execute
    return response
```

---

### 5.6 SQLExecutor — ReAct Loop

Replaces a fixed syntactic retry. The difference is qualitative: the agent **observes the result** before deciding to accept or refine. This catches semantic failures — 0 rows, implausible cardinality, wrong result shape — that syntax-only retry never touches.

> **Correction from v7:** `decide_action` used a fragile string sentinel
> (`"Accept." in observation`). Any refactor of `observe_result` could silently break
> the loop into infinite refinement. Replaced with a structured `ObservationResult`
> enum.

```python
from enum import Enum
from dataclasses import dataclass

class Action(Enum):
    ACCEPT = "accept"
    REFINE = "refine"

@dataclass
class ObservationResult:
    action: Action
    message: str

@dataclass
class ExecutionResult:
    success: bool
    data: list[dict] | None = None
    columns: list[str] | None = None
    sql: str = ""
    steps_taken: int = 0
    failure_reason: str | None = None

def execute_react(
    self,
    sql: str,
    question: str,
    linked_schema: str,
    max_steps: int = 4,
) -> ExecutionResult:
    for step in range(max_steps):
        result = self._try_execute(sql)

        if not result.success:
            obs = ObservationResult(
                action=Action.REFINE,
                message=f"SQL error: {result.error}",
            )
        else:
            obs = self._observe_result(question, sql, result)

        self._log_step(step, sql, obs)

        if obs.action == Action.ACCEPT:
            return ExecutionResult(
                success=True,
                data=result.data,
                columns=result.columns,
                sql=sql,
                steps_taken=step + 1,
            )

        # Refinement: linked_schema passed explicitly — SQLGenerator is stateless.
        sql = self.sql_generator.refine(sql, obs.message, linked_schema)

    # Loop exhaustion — all steps consumed without accept.
    return ExecutionResult(
        success=False,
        sql=sql,
        steps_taken=max_steps,
        failure_reason="max steps reached without successful result",
    )

def _observe_result(self, question: str, sql: str, result) -> ObservationResult:
    """Rule-based semantic observation. No LLM call."""
    row_count = len(result.data)

    if row_count == 0:
        return ObservationResult(
            action=Action.REFINE,
            message=(
                "Query returned 0 rows. Possible causes: "
                "filter value mismatch (check product_name or week_day spelling), "
                "overly restrictive date range, or incorrect column reference."
            ),
        )

    if row_count > 10_000:
        return ObservationResult(
            action=Action.REFINE,
            message=(
                f"Query returned {row_count} rows. Likely missing WHERE clause "
                "or GROUP BY for an aggregation query."
            ),
        )

    scalar_indicators = ["total", "average", "how many", "count", "sum", "most", "top"]
    expects_scalar = any(w in question.lower() for w in scalar_indicators)
    if expects_scalar and row_count > 50:
        return ObservationResult(
            action=Action.REFINE,
            message=(
                f"Question implies aggregated result but got {row_count} rows. "
                "May be missing GROUP BY, ORDER BY + LIMIT, or aggregation function."
            ),
        )

    return ObservationResult(action=Action.ACCEPT, message="Result shape matches question intent.")
```

**`build_refinement_prompt` — fully specified:**

> **Correction from v7:** This function was referenced but not designed.
> It is the load-bearing function in the ReAct loop — the entire semantic value
> of self-correction depends on what context the LLM receives.

```python
def build_refinement_prompt(
    original_sql: str,
    observation: str,
    schema: str,
    question: str,
) -> str:
    return f"""You are correcting a SQL query that failed or produced a bad result.

Schema:
{schema}

Original question: {question}

Attempted SQL:
{original_sql}

Problem observed:
{observation}

Instructions:
- Fix only the specific problem described above.
- Keep all correct parts of the original query unchanged.
- Do not add columns, tables, or logic not needed to fix the stated problem.
- Common fixes for '0 rows': check WHERE clause values match actual data
  (week_day values: Monday/Tuesday/Wednesday/Thursday/Friday/Saturday/Sunday;
   product names are case-sensitive exact strings).
- Common fixes for 'too many rows': add GROUP BY, ORDER BY + LIMIT, or a WHERE filter.
- Common fixes for SQL errors: check column names against the schema above.

Return only the corrected SQL query. No explanation. No markdown fences."""
```

---

### 5.7 ResultSynthesizer

> **Correction from v7:** Synthesis was not guarded against execution failure.
> Calling the 32B model with an empty or null result set causes hallucinated narratives —
> confident natural-language output over data that doesn't exist. This inverts the
> "trustworthy" brand claim. Guard is now mandatory.

```python
def synthesize(
    self,
    question: str,
    result: ExecutionResult,
    interpretations: list[str],
) -> str | None:
    # MANDATORY GUARD: never synthesize over a failed execution.
    if not result.success or not result.data:
        return None  # caller handles: UI shows "Query could not be executed" message

    prompt = self._build_synthesis_prompt(
        question=question,
        data=result.data,
        sql=result.sql,
        interpretations_applied=interpretations,
        steps_taken=result.steps_taken,
    )
    response = self.llm_client.generate(
        prompt,
        model=self.synthesis_model,  # qwen3:32b
        temperature=0.3,             # slight temperature: narrative quality, not SQL correctness
    )
    return response

def _build_synthesis_prompt(
    self,
    question: str,
    data: list[dict],
    sql: str,
    interpretations_applied: list[str],
    steps_taken: int,
) -> str:
    # Truncate large result sets before injection.
    # Full list[dict] for 50+ rows = 1,500–3,000 tokens, causing attention degradation
    # on factual accuracy checks. Inject top 10 rows + summary stats.
    sample = data[:10]
    summary = {
        "total_rows": len(data),
        "columns": list(data[0].keys()) if data else [],
        "showing": f"first {len(sample)} of {len(data)} rows",
    }
    interp_text = (
        "\n".join(f"- {i}" for i in interpretations_applied)
        if interpretations_applied
        else "None"
    )

    return f"""You are a business analyst generating a concise insight from a query result.

Question asked: {question}

Interpretations applied (business rules used): 
{interp_text}

Result summary: {summary}
Result sample: {sample}

Write a 2–3 sentence analytical narrative that includes:
1. The concrete finding (specific numbers from the result)
2. One business implication or actionable observation
3. Any interpretation assumptions, stated explicitly

Be factual. Do not invent numbers not present in the result sample.
Write in plain language, as if briefing a store manager."""
```

---

### 5.8 LLMClient Abstraction

```python
class LLMClient:
    def __init__(self, backend: str = "ollama", model: str = "qwen2.5-coder:14b"):
        self.backend = backend   # "ollama" | "groq" | "together"
        self.model = model

    def generate(self, prompt: str, model: str | None = None, **kwargs) -> str:
        target_model = model or self.model
        if self.backend == "ollama":
            return self._ollama_generate(prompt, target_model, **kwargs)
        return self._litellm_generate(prompt, target_model, **kwargs)

    def _ollama_generate(self, prompt: str, model: str, **kwargs) -> str:
        import ollama
        response = ollama.generate(model=model, prompt=prompt, options=kwargs)
        return response["response"]

    def _litellm_generate(self, prompt: str, model: str, **kwargs) -> str:
        import litellm
        # Model string format per backend:
        # groq:     "groq/qwen3-32b"
        # together: "together_ai/Qwen/Qwen2.5-Coder-7B-Instruct"
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        return response.choices[0].message.content
```

---

### 5.9 Pipeline Orchestration

```python
@dataclass
class PipelineResult:
    question: str
    resolved_question: str
    interpretations: list[str]
    query_class: str
    sql: str
    execution: ExecutionResult
    narrative: str | None
    run_id: str
    total_latency_ms: int

class Pipeline:
    def run(self, question: str) -> PipelineResult:
        run_id = datetime.utcnow().isoformat()
        t0 = time.time()

        resolved = self.ambiguity_detector.detect_and_resolve(question, self.domain)
        linked_schema = self.schema_linker.link(resolved.resolved)
        query_class, cls_method = self.query_classifier.classify(resolved.resolved, self.llm_client)

        self._log(run_id, "classifier", {"class": query_class.value, "method": cls_method})

        sql = self.sql_generator.generate_sql(resolved, linked_schema, query_class, self.kpis, self.llm_client)
        execution = self.sql_executor.execute_react(sql, resolved.resolved, linked_schema)

        # Synthesis only on successful execution with non-empty results.
        narrative = None
        if execution.success and execution.data:
            narrative = self.result_synthesizer.synthesize(
                question=question,
                result=execution,
                interpretations=resolved.interpretations_applied,
            )

        return PipelineResult(
            question=question,
            resolved_question=resolved.resolved,
            interpretations=resolved.interpretations_applied,
            query_class=query_class.value,
            sql=execution.sql,
            execution=execution,
            narrative=narrative,
            run_id=run_id,
            total_latency_ms=int((time.time() - t0) * 1000),
        )
```

---

### 5.10 Logging Convention

Every stage logs a structured record:

```python
{
    "run_id": "2025-05-25T14:32:01",
    "stage": "sql_executor",
    "question": "...",
    "resolved_question": "...",
    "model": "qwen2.5-coder:14b",
    "step": 2,
    "sql_attempted": "SELECT ...",
    "observation_action": "refine",
    "observation_message": "Query returned 0 rows. ...",
    "latency_ms": 3200
}
```

Written to `logs/runs/{run_id}.jsonl`. All decisions in the ReAct loop are reconstructible from the log. Every refinement step, every action, every acceptance is captured — enables posterior analysis of failure modes.

---

## 6. Docker Configuration

### Ollama Container — Corrected Entrypoint

> **Correction from v7:** `sleep 5` is not a reliable health check. Replaced with
> a polling loop that confirms the Ollama API is accepting connections before pulling.
> Without this, ollama pull can fail silently on slower machines.

```bash
#!/bin/sh
# entrypoint.sh — runs inside ollama container

# Start ollama server in background
ollama serve &

# Poll until the API is ready — do not proceed until confirmed responsive.
echo "Waiting for Ollama API..."
until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
    sleep 2
done
echo "Ollama API ready."

# Pull models. Second pull is a no-op if volume is cached.
echo "Pulling SQL model..."
ollama pull qwen2.5-coder:14b

echo "Pulling synthesis model..."
ollama pull qwen3:32b

echo "Models ready. Ollama serving."
wait
```

### Ollama Healthcheck (docker-compose.yml)

The nlp service must not start until the ollama container is both running *and* has finished pulling models. This is implemented via a Docker healthcheck that polls a sentinel file written by the entrypoint after pulls complete:

```bash
# At end of entrypoint.sh, after both pulls succeed:
touch /tmp/models_ready

# Healthcheck polls for this file:
# healthcheck:
#   test: ["CMD", "test", "-f", "/tmp/models_ready"]
#   interval: 30s
#   timeout: 10s
#   retries: 60       # 60 × 30s = 30 min max wait — covers slow download + cold start
#   start_period: 60s
```

```yaml
# docker-compose.yml (key sections)
version: "3.9"

services:
  db:
    build: ./db
    ports: ["8001:8001"]
    volumes: ["./data.csv:/app/data.csv:ro"]
    networks: [nivii-net]
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8001/health"]
      interval: 10s
      retries: 5

  ollama:
    image: ollama/ollama
    volumes: ["ollama_cache:/root/.ollama"]
    entrypoint: ["/bin/sh", "/entrypoint.sh"]
    configs:
      - source: ollama_entrypoint
        target: /entrypoint.sh
        mode: 0755
    networks: [nivii-net]
    healthcheck:
      test: ["CMD", "test", "-f", "/tmp/models_ready"]
      interval: 30s
      timeout: 10s
      retries: 60
      start_period: 60s
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

  nlp:
    build: ./nlp
    ports: ["8002:8002"]
    networks: [nivii-net]
    depends_on:
      db:
        condition: service_healthy
      ollama:
        condition: service_healthy  # waits for models_ready sentinel
    environment:
      - DB_URL=http://db:8001
      - OLLAMA_URL=http://ollama:11434
      - SQL_MODEL=qwen2.5-coder:14b
      - SYNTHESIS_MODEL=qwen3:32b

  ui:
    build: ./ui
    ports: ["3000:3000"]
    networks: [nivii-net]
    depends_on:
      nlp:
        condition: service_started

volumes:
  ollama_cache:

networks:
  nivii-net:
    driver: bridge
```

---

## 7. Evaluation Harness

### Test Cases — Corrected for Actual Domain and 60-Day Data Window

> **Correction from v7:** Previous test cases were copied from a CRM/SaaS domain spec
> and never rewritten. "Revenue by segment in Q2", "Top 5 customers by deal value",
> and "Enterprise deals closed in under 30 days" are unanswerable against this dataset.
> All 12 cases below are verified answerable against the actual data.

| # | Question | Class | Expected SQL shape | Known answer |
|---|---|---|---|---|
| 1 | What is the most bought product on Fridays? | aggregation | GROUP BY product_name WHERE week_day='Friday' ORDER BY SUM(quantity) DESC | Alfajor Sin Azucar Suelto (850 units) |
| 2 | How many transactions happened on Saturdays? | simple | COUNT(DISTINCT ticket_number) WHERE week_day='Saturday' | verifiable |
| 3 | What are the busiest hours on weekdays? | time_filter | GROUP BY hour_of_day WHERE week_day NOT IN (...) ORDER BY transactions DESC | verifiable |
| 4 | What is the total revenue for October 2024? | aggregation | SUM(total) WHERE strftime('%Y-%m', date)='2024-10' AND total>0 | ~110,614,650 ARS |
| 5 | Which waiter generated the most revenue? | aggregation | GROUP BY waiter ORDER BY SUM(total) DESC | verifiable |
| 6 | What is the week-over-week revenue trend? | window | CTE with strftime week grouping + LAG() | verifiable |
| 7 | What are the top 5 products by revenue? | aggregation | GROUP BY product_name ORDER BY SUM(total) DESC LIMIT 5 | verifiable |
| 8 | How many transactions were there in November? | simple | COUNT(DISTINCT ticket_number) WHERE strftime('%Y-%m', date)='2024-11' | verifiable |
| 9 | What is the average ticket value per waiter? | aggregation | SUM(total) / COUNT(DISTINCT ticket_number) GROUP BY waiter | verifiable |
| 10 | Show me the most popular product (ambiguous — no day specified) | aggregation + ambiguity | triggers disambiguation rule → SUM(quantity) DESC | Alfajor Sin Azucar Suelto |
| 11 | What were the recent sales? (semantic trap — "recent") | time_filter + ambiguity | triggers disambiguation → WHERE date >= last 30 days | verifiable |
| 12 | Which products have the most returns? | aggregation | WHERE total < 0 GROUP BY product_name ORDER BY COUNT(*) DESC | verifiable |

### Two-Layer Evaluation

**Layer 1 — SQL structural check (runs in Phase 2, skip_judge=True):**
Validates that the generated SQL contains the expected clause pattern. Structural match, not exact match. Catches generation failures before running the judge.

```python
@dataclass
class TestCase:
    question: str
    expected_class: str
    expected_clauses: list[str]    # substrings that must appear in generated SQL
    forbidden_clauses: list[str]   # substrings that must NOT appear
    known_answer: str | None = None

def check_sql_structure(generated_sql: str, case: TestCase) -> dict:
    sql_lower = generated_sql.lower()
    passes = [c.lower() in sql_lower for c in case.expected_clauses]
    fails  = [c.lower() in sql_lower for c in case.forbidden_clauses]
    return {
        "pass": all(passes) and not any(fails),
        "expected_present": list(zip(case.expected_clauses, passes)),
        "forbidden_present": list(zip(case.forbidden_clauses, fails)),
    }
```

**Layer 2 — LLM-as-judge on synthesis (Phase 3, Ollama only):**

```python
def judge_synthesis(
    self,
    question: str,
    result_data: list[dict],
    narrative: str,
) -> JudgeScore:
    # Truncate to top 10 rows + summary stats.
    # Full result sets (50+ rows) inflate judge prompt token count, causing
    # attention degradation on factual accuracy checks.
    sample = result_data[:10]
    summary = {
        "total_rows": len(result_data),
        "columns": list(result_data[0].keys()) if result_data else [],
    }
    prompt = f"""Evaluate whether this narrative faithfully represents the query result.

Question: {question}
Result summary: {summary}
Result sample (first {len(sample)} rows): {sample}
Narrative: {narrative}

Score on two dimensions (1–5 each):
1. Factual accuracy: do all numbers in the narrative appear correctly in the result data?
2. Interpretation fidelity: does the framing match the direction and magnitude of the data?

Respond with JSON only:
{{"factual_accuracy": <int>, "interpretation_fidelity": <int>, "issues": "<str or null>"}}"""

    response = self.llm_client.generate(prompt, model=self.synthesis_model)
    return JudgeScore(**parse_json(response))

def run_eval(self, test_cases: list[TestCase], skip_judge: bool = False) -> EvalReport:
    results = []
    for case in test_cases:
        pipeline_result = self.pipeline.run(case.question)
        sql_score = self.check_sql_structure(pipeline_result.sql, case)
        judge_score = None
        if not skip_judge and pipeline_result.narrative:
            judge_score = self.judge_synthesis(
                case.question, pipeline_result.execution.data, pipeline_result.narrative
            )
        results.append({
            "question": case.question,
            "class": pipeline_result.query_class,
            "sql_pass": sql_score["pass"],
            "sql_detail": sql_score,
            "judge": judge_score,
            "latency_ms": pipeline_result.total_latency_ms,
            "steps_taken": pipeline_result.execution.steps_taken,
            "failure_reason": pipeline_result.execution.failure_reason,
        })
    return EvalReport(results=results)
```

**Eval as final-pass gate, not continuous regression.** On local hardware, a full eval run (12 cases × synthesis ~4 min × judge ~4 min) takes 90–120 minutes. Run once after the pipeline is complete, before writing the README. State this explicitly — prevents the evaluator from expecting CI-style coverage.

---

## 8. Build Order

### Hour 0–2: Infrastructure — Wire Before Writing Pipeline Code

- [ ] `docker-compose.yml` skeleton: four services, `nivii-net`, `ollama_cache` volume
- [ ] `ollama` service: entrypoint.sh with polling health check + `models_ready` sentinel
- [ ] **Confirm synthesis model name: `ollama pull qwen3:32b` — do not proceed without this verified**
- [ ] `db` service: FastAPI app, `load_csv_to_db()` on startup with ISO date normalization, `/execute` + `/schema` + `/health`
- [ ] Smoke test: `db` container starts, CSV loads, `GET /health` returns `row_count: 24212`

### Hour 2–6: NLP Service Core

- [ ] `LLMClient` with `groq` backend for Phase 1 iteration
- [ ] `SemanticLayer`: load YAML descriptor, `render_ddl()` returning the CREATE TABLE with comments
- [ ] `AmbiguityDetector`: triggers + corrected composition logic (against original, not cascading)
- [ ] `QueryClassifier`: keyword map + LLM fallback
- [ ] `SQLGenerator`: `build_sql_prompt()` + `extract_sql()`
- [ ] Manual end-to-end test: canonical question → clean SQL output with Groq backend

### Hour 6–10: ReAct Loop + Synthesis

- [ ] `build_refinement_prompt()` (fully specified above — implement exactly)
- [ ] `SQLExecutor.execute_react()` with `ObservationResult` enum (not string sentinel)
- [ ] `ResultSynthesizer.synthesize()` with `success` guard
- [ ] `Pipeline.run()` orchestration with structured logging
- [ ] `nlp` service FastAPI wrapper: `POST /query` returning full `PipelineResult`
- [ ] Test with 5 representative questions across query classes using Groq

### Hour 10–14: UI + Docker Polish

- [ ] `ui` service: single Jinja2 HTML page — NL input, NL answer (bold), SQL (collapsible), result table
- [ ] Show loading state during inference — critical for UX given latency
- [ ] Show interpretation notes when disambiguation rules fired
- [ ] Full `docker compose up` smoke test with Groq backend (fast iteration)
- [ ] Switch to Together.ai backend: Phase 2 validation, run eval with `skip_judge=True`

### Hour 14–20: Ollama Validation + Eval

- [ ] Switch to Ollama backend: `SQL_MODEL=qwen2.5-coder:14b`, `SYNTHESIS_MODEL=qwen3:32b`
- [ ] Test canonical question end-to-end on local Ollama — verify latency is acceptable
- [ ] Fix any prompt transfer issues (Ollama models may be more/less instruction-following than Groq)
- [ ] Run full eval harness (12 cases, `skip_judge=False`) — capture pass rate + failure mode distribution
- [ ] `docker compose down -v && docker compose up` — clean-state smoke test

### Hour 20–24: Hardening + README + Submission

- [ ] Error handling: empty results, model timeout, malformed SQL — all return clean UI error messages, never 500
- [ ] README: architecture decisions, Docker setup, scale-out, production delta, limitations
- [ ] README: state "~29 GB first-run download, subsequent runs use cached volume"
- [ ] README: state eval harness is a final-pass gate, not CI regression
- [ ] README: state CPU-only fallback configuration
- [ ] Git push — verify clone + `docker compose up` works from a clean directory

---

## 9. README Content Plan

### Architecture Decisions

Each decision stated as a tradeoff with explicit rationale:

| Decision | Why | Tradeoff |
|---|---|---|
| DIN-SQL stage decomposition | Token budget management: each stage gets short context, enables two-model strategy on local hardware | More code; each stage is a failure point |
| CREATE TABLE over natural language schema | Structural representation that forces correct column reference and type awareness | Slightly more verbose in prompt |
| Date normalization at ingestion (not in SQL) | Source dates are M/D/YYYY; fixed-position substr() fails for 48% of rows | Requires Python preprocessing step in db service |
| ReAct over fixed retry | Detects semantic failures (0 rows, wrong cardinality) that syntax retry misses | More complex; 2× latency per correction step |
| Rule-based AmbiguityDetector | Zero latency; LLM call here adds 20–30s before SQL generation starts | Coverage is finite; open-domain queries may not resolve |
| Keyword heuristic QueryClassifier | Fires for 60–70% of questions at near-zero cost | Heuristic can misclassify edge cases |
| SQLite over Postgres | Simplest possible db for demo scope; no infrastructure overhead | Not production-grade for concurrency or large data |
| Four containers over monolith | Each service independently scalable; clear separation of concerns | More orchestration complexity |
| Two-model strategy (14B SQL + 32B synthesis) | Task-matched: SQL generation needs code precision, synthesis needs narrative reasoning | 29 GB download; synthesis latency 2–5 min |
| Structural few-shot examples | Demonstrates expected SQL shape per class without overfitting to specific values | One example per class may not cover all variations |

### Limitations

- Local model SQL reliability on complex queries: small models can generate syntactically valid but semantically wrong SQL that passes observe_result checks. The ReAct loop catches the most common semantic failures but not all.
- Latency on CPU-only machines: see §4 for fallback configuration.
- Dataset scope: 60 days (Sep–Nov 2024); queries referencing annual periods will have partial results.
- AmbiguityDetector rule coverage is finite; novel question phrasings may not trigger.
- Eval harness is final-pass gate, not continuous regression.

### Scale-Out Section (required by brief)

**More tables / larger schema:** replace full schema injection in SchemaLinker with retrieval-augmented linking. Beyond ~15 tables, store table embeddings in ChromaDB or pgvector; SchemaLinker retrieves top-k relevant tables by cosine similarity to the question. The pipeline code does not change — only SchemaLinker's implementation swaps from `render_ddl()` to `retrieve_and_render(question)`.

**More data:** SQLite → PostgreSQL with read replicas. The `db` service interface (`POST /execute`) is unchanged. Swap the backend, add connection pooling, adjust the Compose file.

**High traffic on the frontend:** the `nlp` service is the bottleneck (model inference latency is 3–7 minutes per query on GPU). Scale horizontally with multiple `nlp` replicas behind a load balancer. Ollama supports concurrent request queuing. Add a Redis job queue between `ui` and `nlp` for async processing — UI submits job, polls for result — so the frontend does not block on inference. This makes the system feel responsive under concurrent load.

**Model quality at scale:** for high-stakes queries, CHASE-SQL candidate consistency: generate N=3 SQL candidates, execute all, select by result consistency (majority vote on output). Trades latency (3× generation cost) for quality. Applicable as an optional mode without changing the pipeline interface.

### Production Delta

What would need to change for a real Nivii deployment beyond this demo:

- Automated schema enrichment (profile new tables, generate descriptions, detect date format patterns)
- LLM-path AmbiguityDetector for open-domain queries
- Kubernetes per-client deployment (data never leaves client environment)
- Continuous evaluation pipeline (every prompt change triggers an eval run)
- Synthesis plausibility filter (sanity-check narrative numbers against result data before returning)
- CHASE-SQL candidate consistency for business-critical queries

---

## 10. Correction Log (v7 → Final)

| # | Finding | Change |
|---|---|---|
| C1 | Date format is M/D/YYYY not MM/DD/YYYY; substr() formula fails for 48.2% of rows | Normalize date to ISO at ingestion in db service; all SQL and few-shot examples updated to use strftime() on ISO column |
| C2 | Date range is 60 days not ~1 year | All references to "~1 year" replaced with "60 days (Sep 21 – Nov 20, 2024)"; dataset contract updated |
| C3 | Eval harness test cases were CRM/SaaS domain, not POS | All 12 test cases rewritten for actual POS domain and verified answerable against actual data |
| C4 | quantity is REAL not INTEGER (one row = 0.5) | DDL, YAML descriptor, and schema comments updated to REAL |
| C5 | Synthesis model "qwen3.5:27b" does not exist in Ollama | Replaced with `qwen3:32b`; fallback `qwen3:14b` documented for CPU-only |
| C6 | First-run download stated as ~9 GB; actual is ~29 GB (both models) | All documentation updated; README must warn ~29 GB |
| C7 | AmbiguityDetector sequential template composition produced malformed NL | Rewritten to collect all matching rules against original question, then compose once |
| C8 | `decide_action` used fragile string sentinel ("Accept." substring match) | Replaced with `ObservationResult` dataclass with `Action` enum |
| C9 | `build_refinement_prompt()` unspecified | Fully specified in §5.6 with explicit context about what the LLM needs to fix |
| C10 | ResultSynthesizer not guarded against execution failure | Mandatory `if not result.success` guard added in §5.7; returns None, caller handles |
| C11 | `sleep 5` in ollama entrypoint is not a reliable readiness check | Replaced with polling loop + `models_ready` sentinel file + Docker healthcheck |
| C12 | No CPU-only fallback path documented | CPU fallback configuration added in §4 with environment variable override |
