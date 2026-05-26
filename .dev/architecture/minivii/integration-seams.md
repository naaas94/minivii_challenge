Section:      integration-seams
Version:      1.0.0
Last updated: 2026-05-26

```
Seam:          UI → NLP service
Direction:     outbound (from ui container)
Protocol:      HTTP POST JSON
Auth:          none (internal Docker network)
Data sent:     {"question": "<user NL question>"}
Data received: PipelineResult JSON or {"error": "..."}
Error modes:   NLP unreachable (httpx exception → UI "Service unavailable"); NLP returns error envelope
Retry policy:  none (single attempt; 600s client timeout)
Owner module:  ui/main.py
```

```
Seam:          NLP → DB service
Direction:     outbound
Protocol:      HTTP POST JSON
Auth:          none (internal Docker network)
Data sent:     {"sql": "<generated SQL>"}
Data received: {columns, rows, row_count} or {error, sql}
Error modes:   HTTP errors, SQLite syntax/runtime errors in body, empty result sets (handled by ReAct observer)
Retry policy:  ReAct loop up to 4 steps with LLM refinement (not HTTP retry)
Owner module:  nlp/pipeline/sql_executor.py
```

```
Seam:          NLP → Ollama inference
Direction:     outbound
Protocol:      Ollama Python client (generate API)
Auth:          none (internal network; default client host)
Data sent:     prompt text, model name, temperature/options
Data received: generated text (SQL or narrative)
Error modes:   model not loaded, Ollama down, timeout, malformed model output
Retry policy:  none at LLMClient level; ReAct loop retries SQL generation only
Owner module:  nlp/pipeline/llm_client.py
```

```
Seam:          Ollama container bootstrap
Direction:     outbound (to Ollama registry)
Protocol:      ollama pull via entrypoint shell
Auth:          none
Data sent:     model pull requests (qwen2.5-coder:14b, qwen3:32b)
Data received: model weights (~29 GB first run)
Error modes:   pull failure, slow download, disk space
Retry policy:  compose healthcheck retries up to 60 times (30s interval)
Owner module:  ollama/entrypoint.sh
```

```
Seam:          DB service → CSV dataset
Direction:     inbound
Protocol:      Docker volume mount (read-only)
Auth:          none
Data sent:     none
Data received: data.csv (24,212 POS rows)
Error modes:   missing file at /app/data.csv → RuntimeError on startup
Retry policy:  none
Owner module:  db/main.py (lifespan), db/ingest.py
```

```
Seam:          DB service → SQLite file
Direction:     bidirectional
Protocol:      sqlite3 file at /app/sales.db
Auth:          none (local file)
Data sent:     INSERT on startup ingest; arbitrary SQL from /execute
Data received: query result sets
Error modes:   corrupt DB, locked file, SQL errors
Retry policy:  none
Owner module:  db/main.py, db/ingest.py
```

```
Seam:          NLP → filesystem (run logs)
Direction:     outbound
Protocol:      local JSONL append
Auth:          none
Data sent:     PipelineStageLogRecord lines to logs/runs/{run_id}.jsonl
Data received: none
Error modes:   disk full, permission errors
Retry policy:  none
Owner module:  nlp/pipeline/pipeline.py
```

```
Seam:          Eval harness → filesystem (eval reports)
Direction:     outbound
Protocol:      local JSON write
Auth:          none
Data sent:     EvalReport to logs/eval_{timestamp}.json
Data received: none
Error modes:   same as run logs
Retry policy:  none
Owner module:  nlp/eval/harness.py
```
