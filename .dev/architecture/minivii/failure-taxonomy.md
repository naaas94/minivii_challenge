Section:      failure-taxonomy
Version:      1.1.0
Last updated: 2026-05-26

Taxonomy version: 1.1.0
Last updated:     2026-05-26

## Layer framework

```
L0  Input integrity   — failures attributable to input data before any processing begins
L2  Model behavior    — failures in model output relative to the prompt
L3  Output validation — failures in structural or semantic validity of output
L5  Infrastructure    — failures in external systems or environment
```

## Cause classes

```
L0.malformed_csv_date
Description:  Unguarded datetime.strptime('%m/%d/%Y') in db/ingest.py crashes startup on bad date strings
Evidence:     CHANGELOG.MD T2 deferral; no unit test for malformed dates
```

```
L0.missing_dataset_file
Description:  data.csv absent at /app/data.csv causes db lifespan RuntimeError before ingest
Evidence:     db/main.py lifespan guard; compose volume mount required
```

```
L3.ambiguity_axis_mismatch
Description:  AMBIGUITY_TRIGGERS axis strings diverge from domain.yaml disambiguation_rules.when — rule lookup returns None and trigger is silently skipped
Evidence:     ambiguity_detector.lookup_disambiguation_rule; coupling surface confirmed in code review 2026-05-26
```

```
L2.sql_generation_wrong_metric
Description:  Generated SQL uses wrong aggregation (e.g. sum(total) when quantity expected) — caught by eval forbidden_clauses
Evidence:     nlp/eval/harness.py TEST_CASES with forbidden_clauses; structural check only
```

```
L3.sql_structure_eval_failure
Description:  Generated SQL missing expected_clauses or containing forbidden_clauses per eval harness substring rules
Evidence:     check_sql_structure in nlp/eval/harness.py
```

```
L3.react_max_steps_exhausted
Description:  SQLExecutor ReAct loop reaches max_steps=4 without observer accept — failure_reason "max steps reached without successful result"
Evidence:     nlp/pipeline/sql_executor.py execute_react; test_execute_react_default_max_steps_is_four
```

```
L5.db_unreachable
Description:  httpx failure calling db POST /execute — failure_reason contains "db unreachable"
Evidence:     test_try_execute_db_unreachable_returns_failure in nlp/tests/test_sql_executor.py
```

```
L5.ollama_host_misconfigured
Description:  LLMClient uses ollama SDK default host (OLLAMA_HOST env, default localhost:11434); compose sets OLLAMA_URL which SDK does not read — NLP container cannot reach ollama service in Compose unless OLLAMA_HOST set separately
Evidence:     nlp/pipeline/llm_client.py _ollama_generate; ollama Python SDK BaseClient reads os.getenv('OLLAMA_HOST'); docker-compose.yml sets OLLAMA_URL only; static code review 2026-05-26 (runtime stack not exercised in architecture run)
```

```
L5.ollama_model_not_ready
Description:  Models not pulled or sentinel /tmp/models_ready absent — nlp blocked by depends_on ollama service_healthy
Evidence:     ollama/entrypoint.sh; docker-compose.yml healthcheck
```

```
L5.db_healthcheck_curl_missing
Description:  db compose healthcheck invokes curl but db/Dockerfile (python:3.11-slim) does not install curl — service_healthy may never pass, blocking nlp depends_on
Evidence:     docker-compose.yml; db/Dockerfile; T2 decision log; CHANGELOG.MD cross-task flag
```

```
L2.narrative_hallucination
Description:  Synthesis narrative cites numbers not present in result sample despite prompt guard — no runtime plausibility filter; eval judge_synthesis is the gate
Evidence:     result_synthesizer prompt text; README production delta; eval harness judge path
```

```
L3.schema_ddl_drift
Description:  db/main.py hardcoded SCHEMA_DDL diverges from SemanticLayer.render_ddl() sourced from domain.yaml — affects /schema consumers and maintainability; NLP path uses YAML-rendered DDL only
Evidence:     dual sources in db/main.py and nlp/pipeline/semantic_layer.py; NLP does not call GET /schema
```

```
L3.unrestricted_sql_execution
Description:  db POST /execute runs arbitrary SQL via conn.execute with no SELECT/WITH guard — mutating statements possible if LLM emits them
Evidence:     db/main.py execute handler; no read-only enforcement in code review 2026-05-26
```

```
L5.entrypoint_model_env_drift
Description:  ollama/entrypoint.sh hard-pulls qwen2.5-coder:14b and qwen3:32b while README CPU fallback overrides SQL_MODEL/SYNTHESIS_MODEL env without changing entrypoint pulls
Evidence:     ollama/entrypoint.sh; README CPU fallback; docker-compose.yml env block
```
