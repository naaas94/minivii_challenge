Section:      known-coupling-surfaces
Version:      1.1.0
Last updated: 2026-05-26

```
Surface:      Ambiguity axis strings (AMBIGUITY_TRIGGERS values ↔ domain.yaml disambiguation_rules.when)
Shared by:    nlp/pipeline/ambiguity_detector.py ↔ nlp/schema/domain.yaml
Failure mode: Trigger fires but no rule applied — ambiguous NL passes through unchanged
Confirmed:    yes — source: ambiguity_detector.py and domain.yaml
```

```
Surface:      SQLite column set and semantics
Shared by:    db/ingest.py CREATE TABLE ↔ domain.yaml columns ↔ db/main.py SCHEMA_DDL ↔ SemanticLayer.render_ddl()
Failure mode: SQL runs against ingest schema but LLM prompts describe wrong column semantics or missing ticket_prefix
Confirmed:    yes — source: ingest.py, domain.yaml, dual DDL paths
```

```
Surface:      POST /execute JSON response shape
Shared by:    db/main.py ↔ sql_executor._try_execute
Failure mode: Parser breaks if shape deviates from {columns, rows, row_count} or {error, sql}
Confirmed:    yes — source: db/main.py and sql_executor.py; test_try_execute_parses_db_error
```

```
Surface:      PipelineResult field names
Shared by:    nlp/pipeline/pipeline.py PipelineResult ↔ ui/templates/index.html
Failure mode: Template renders empty sections if narrative, query_class, execution.steps_taken, execution.data, or interpretations renamed
Confirmed:    yes — source: index.html Jinja bindings audited 2026-05-26
```

```
Surface:      QueryClass enum values ↔ FEW_SHOT_EXAMPLES ↔ eval expected_class
Shared by:    query_classifier.py ↔ sql_generator.py ↔ eval/harness.py TEST_CASES
Failure mode: KeyError at generation or false eval failures
Confirmed:    yes — source: QueryClass members and harness TEST_CASES
```

```
Surface:      Eval clause vocabulary (substring SQL checks)
Shared by:    nlp/eval/harness.py TEST_CASES expected_clauses / forbidden_clauses
Failure mode: Brittle pass/fail on formatting differences; intentional final-pass gate behavior
Confirmed:    yes — source: check_sql_structure implementation
```

```
Surface:      Docker service hostnames and ports
Shared by:    docker-compose.yml ↔ nlp/main.py (DB_URL, OLLAMA_URL) ↔ ui/main.py (NLP_URL) ↔ sql_executor httpx
Failure mode: DNS/connection failures if names or ports drift
Confirmed:    yes — source: compose and service defaults
```

```
Surface:      Model name triple (compose env ↔ entrypoint pulls ↔ nlp defaults ↔ README CPU fallback)
Shared by:    docker-compose.yml ↔ ollama/entrypoint.sh ↔ nlp/main.py ↔ README.md
Failure mode: Env names one model set, entrypoint pulls another; CPU fallback changes env but not entrypoint
Confirmed:    yes — source: entrypoint.sh hardcoded pulls vs README override docs
```

```
Surface:      OLLAMA_URL (documented) ↔ OLLAMA_HOST (SDK consumed)
Shared by:    docker-compose.yml / README / nlp/main.py health ↔ ollama Python SDK BaseClient
Failure mode: OLLAMA_URL set in compose but inference uses SDK default localhost unless OLLAMA_HOST set
Confirmed:    yes — source: llm_client.py; ollama SDK _client.py reads os.getenv('OLLAMA_HOST'); static review 2026-05-26
```

```
Surface:      CSV path and date format contract
Shared by:    compose volume ./data.csv:/app/data.csv:ro ↔ db CSV_PATH constant ↔ ingest %m/%d/%Y parser
Failure mode: Wrong mount path or date format crashes ingest or loads wrong data
Confirmed:    yes — source: docker-compose.yml and ingest.py
```

```
Surface:      ticket_prefix derivation
Shared by:    db/ingest.py r['ticket_number'].split()[0]
Failure mode: Unexpected ticket_number format yields wrong or empty prefix
Confirmed:    yes — source: ingest.py line 28
```

```
Surface:      Log path conventions
Shared by:    pipeline.py logs/runs/{run_id}.jsonl ↔ eval harness logs/eval_{timestamp}.json ↔ .gitignore logs/
Failure mode: Log writes fail or artifacts committed if paths or gitignore drift
Confirmed:    yes — source: pipeline.py, harness.py, .gitignore
```

```
Surface:      README contract strings
Shared by:    README.md ↔ nlp/tests/test_readme_contract.py
Failure mode: Submission doc regressions break T7 kill-criteria tests (~29 GB, 60-day range, eval command, 10 architecture decisions)
Confirmed:    yes — source: test_readme_contract.py
```

```
Surface:      /tmp/models_ready sentinel
Shared by:    ollama/entrypoint.sh ↔ docker-compose.yml ollama healthcheck
Failure mode: Renaming breaks depends_on service_healthy for nlp
Confirmed:    yes — source: entrypoint.sh and compose
```

```
Surface:      week_day / product_name literal values in prompts and observation messages
Shared by:    domain.yaml sample_values ↔ sql_generator FEW_SHOT_EXAMPLES ↔ sql_executor _observe_result hints
Failure mode: ReAct refinement hints reference wrong spellings; false 0-row refinements
Confirmed:    yes — source: shared string literals across pipeline modules
```

```
Surface:      Sales table DDL semantics (SCHEMA_DDL vs render_ddl) — accepted submission debt
Shared by:    db/main.py SCHEMA_DDL constant ↔ nlp/pipeline/semantic_layer.py from domain.yaml
Failure mode: External /schema consumers see different DDL than LLM prompts; maintainability drift
Confirmed:    yes — intentional T2 simplification; no sync test; NLP never calls /schema
```

```
Surface:      Healthcheck curl dependency (db service)
Shared by:    docker-compose.yml db healthcheck ↔ python:3.11-slim db/Dockerfile (no curl)
Failure mode: db never healthy → nlp startup blocked
Confirmed:    yes — source: T2 decision log, CHANGELOG, Dockerfile audit 2026-05-26
```
