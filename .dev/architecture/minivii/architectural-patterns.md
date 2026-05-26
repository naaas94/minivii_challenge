Section:      architectural-patterns
Version:      1.1.0
Last updated: 2026-05-26

```
Pattern:      Four-container Compose layout
Description:  Stack runs as db, ollama, nlp, ui on bridge network nivii-net with frozen ports 8001/8002/3000/11434; nlp depends_on healthy db+ollama, ui depends_on started nlp
Falsifier:    rg "services:|nivii-net|8001|8002|3000|11434" docker-compose.yml — missing service, wrong port, or broken depends_on chain
```

```
Pattern:      Date normalization at ingest
Description:  CSV dates parsed as %m/%d/%Y in db/ingest.py and stored ISO YYYY-MM-DD; SQL prompts and few-shots use strftime() on date, not substr() conversion
Falsifier:    rg "strptime|'%Y-%m-%d'" db/ingest.py; pytest nlp/tests/test_sql_generator.py -k strftime; eval harness case 6 forbids substr(
```

```
Pattern:      Full schema injection (demo scope)
Description:  SchemaLinker.link() ignores question and returns SemanticLayer.render_ddl(); no retrieval, embeddings, or HTTP fetch to db /schema from NLP
Falsifier:    rg "del question" nlp/pipeline/schema_linker.py; absence of ChromaDB/pgvector/httpx call to /schema in nlp/pipeline/
```

```
Pattern:      ReAct SQL executor with rule-based observer
Description:  SQLExecutor.execute_react uses max_steps=4 default; _observe_result applies row-count heuristics without LLM; refinement calls LLM at temperature=0.0
Falsifier:    pytest nlp/tests/test_sql_executor.py -k "max_steps|observe_result"; rg "max_steps|Action.REFINE" nlp/pipeline/sql_executor.py
```

```
Pattern:      Rule-based AmbiguityDetector (non-cascading)
Description:  Ambiguity triggers matched against original question only; qualifiers composed once into resolved string
Falsifier:    pytest nlp/tests/test_ambiguity_detector.py -k cascade; rg "fired_axes" nlp/pipeline/ambiguity_detector.py
```

```
Pattern:      Keyword-heuristic QueryClassifier with LLM fallback
Description:  KEYWORD_CLASS_MAP checked first returning method "heuristic"; unmatched questions fall through to _llm_classify
Falsifier:    rg '"heuristic"|_llm_classify' nlp/pipeline/query_classifier.py
```

```
Pattern:      JSONL stage logging
Description:  Pipeline._log appends structured records to logs/runs/{run_id}.jsonl with stage, latency_ms, sql_attempted, and observation fields
Falsifier:    rg "json.dumps|logs/runs" nlp/pipeline/pipeline.py; inspect log file after a pipeline run
```

```
Pattern:      NLP /query HTTP 200 error envelope
Description:  nlp/main.py returns JSONResponse(status_code=200) for both success (PipelineResult dict) and handled exceptions ({"error": str})
Falsifier:    rg "status_code=200" nlp/main.py; ui/main.py checks "error" in JSON body not HTTP status from nlp
```

```
Pattern:      db /execute error envelope (not HTTP error for SQL failures)
Description:  db/main.py returns {"error", "sql"} in response body with HTTP 200 on sqlite3.Error; nlp sql_executor parses error from JSON
Falsifier:    rg '"error"' db/main.py execute handler; pytest nlp/tests/test_sql_executor.py -k parses_db_error
```

```
Pattern:      Synthesis guard on successful execution with data
Description:  pipeline.py calls ResultSynthesizer only inside if execution.success and execution.data
Falsifier:    pytest nlp/tests/test_result_synthesizer.py -k synthesize_guard
```

```
Pattern:      Temperature split by stage
Description:  SQL generation, refinement, and classification use temperature=0.0; narrative synthesis uses temperature=0.3
Falsifier:    rg "temperature=" nlp/pipeline/; pytest nlp/tests/test_result_synthesizer.py -k temperature_point_three
```

```
Pattern:      data.csv volume-mounted not baked into image
Description:  docker-compose.yml bind-mounts ./data.csv read-only; db/Dockerfile does not COPY data.csv
Falsifier:    rg "data.csv" docker-compose.yml db/Dockerfile — volume in compose, no COPY in Dockerfile
```

```
Pattern:      Ollama readiness sentinel
Description:  ollama/entrypoint.sh polls API with curl, pulls models, then touch /tmp/models_ready; compose healthcheck tests -f that file
Falsifier:    rg "models_ready|curl.*11434" ollama/entrypoint.sh docker-compose.yml
```
