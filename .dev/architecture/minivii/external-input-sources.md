Section:      external-input-sources
Version:      1.0.0
Last updated: 2026-05-26

```
Source:               Challenge dataset (repo-root data.csv)
Format:               CSV (9 columns; date as M/D/YYYY)
Parser:               Python csv.DictReader + datetime.strptime (db/ingest.py)
Trust level:          partially trusted — fixed challenge dataset; malformed dates would break ingest (no automated guard; noted in T2 decision log)
Surfaces extracted:   All 9 CSV columns; derived ticket_prefix; ISO-normalized date
Surfaces NOT extracted: none (full row loaded)
Volume:               24,212 rows ingested once at db service startup
Sensitivity:          Business POS data (synthetic/demo scope); bad ingest prevents stack startup
Owner module:         db/ingest.py
```

```
Source:               End user via web form
Format:               HTML form field (plain text)
Parser:               FastAPI Form parameter (ui/main.py)
Trust level:          untrusted — arbitrary NL strings forwarded to NLP pipeline and LLM prompts
Surfaces extracted:   question string only
Surfaces NOT extracted: no HTML/JS execution in server template; no file uploads
Volume:               single question per request; 600s NLP timeout
Sensitivity:          Prompt injection into SQL/narrative models; SQL execution constrained to read-only patterns only by LLM behavior (no db-side restriction)
Owner module:         ui/main.py → nlp/main.py → nlp/pipeline/*
```

```
Source:               LLM model outputs (Ollama / optional LiteLLM backends)
Format:               Unstructured text (SQL snippets, JSON for eval judge, narrative prose)
Parser:               extract_sql regex (sql_generator/sql_executor); json.loads with regex fallback (eval harness judge)
Trust level:          untrusted — model-generated SQL executed against SQLite; narratives shown to user
Surfaces extracted:   SQL statements, narrative text, judge JSON scores
Surfaces NOT extracted: markdown fences stripped from SQL; synthesis truncates to first 10 rows of result
Volume:               1–4 SQL attempts per question; 1 synthesis call on success
Sensitivity:          Incorrect SQL can return wrong analytics; narrative may hallucinate if prompt guard fails
Owner module:         nlp/pipeline/llm_client.py and downstream consumers
```

```
Source:               domain.yaml semantic descriptor
Format:               YAML
Parser:               PyYAML safe_load (semantic_layer.py)
Trust level:          trusted — repo-controlled; shipped with application
Surfaces extracted:   Table/column metadata, KPIs, disambiguation rules
Surfaces NOT extracted: relationships (empty); no external schema fetch
Volume:               loaded once per SemanticLayer instance
Sensitivity:          Drift from db SCHEMA_DDL would mislead SQL generation
Owner module:         nlp/pipeline/semantic_layer.py
```
