Section:      data-contract-registry
Version:      1.0.0
Last updated: 2026-05-26

```
Contract:       QueryRequest
Module:         nlp/main.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        Inbound NL question from UI or API caller
Fields:
  - question: str — raw natural-language question
Validators:     none (empty string allowed)
Consumers:      nlp/pipeline/pipeline.py
Last changed:   2026-05-26
```

```
Contract:       PipelineResult (API wire shape via dataclasses.asdict)
Module:         nlp/pipeline/pipeline.py
Serialization:  dataclass → JSON
Version:        unversioned — tracked by git blame
Purpose:        Full pipeline output returned by POST /query
Fields:
  - question: str — original question
  - resolved_question: str — after ambiguity resolution
  - interpretations: list[str] — applied disambiguation rules
  - query_class: str — QueryClass enum value
  - sql: str — final executed SQL
  - execution: ExecutionResult — nested dict (success, data, columns, sql, steps_taken, failure_reason)
  - narrative: str | null — LLM synthesis when execution succeeded with data
  - run_id: str — ISO UTC timestamp string
  - total_latency_ms: int — end-to-end pipeline latency
Validators:     none at API boundary; synthesis skipped unless execution.success and execution.data
Consumers:      ui/templates/index.html, nlp/eval/harness.py
Last changed:   2026-05-26
```

```
Contract:       PipelineErrorEnvelope
Module:         nlp/main.py
Serialization:  JSON object
Version:        unversioned — tracked by git blame
Purpose:        Graceful failure response (always HTTP 200 per T4 contract)
Fields:
  - error: str — exception message string
Validators:     none
Consumers:      ui/main.py
Last changed:   2026-05-26
```

```
Contract:       ExecuteRequest
Module:         db/main.py
Serialization:  Pydantic model
Version:        unversioned — tracked by git blame
Purpose:        Raw SQL passed to SQLite executor
Fields:
  - sql: str — SQL statement(s) to execute
Validators:     none at API boundary; SQLite errors returned in response body
Consumers:      nlp/pipeline/sql_executor.py
Last changed:   2026-05-26
```

```
Contract:       ExecuteSuccessResponse
Module:         db/main.py
Serialization:  JSON object
Version:        unversioned — tracked by git blame
Purpose:        Tabular query result from db service
Fields:
  - columns: list[str] — result column names
  - rows: list[list] — row values (JSON-serializable)
  - row_count: int — len(rows)
Validators:     none
Consumers:      nlp/pipeline/sql_executor.py
Last changed:   2026-05-26
```

```
Contract:       ExecuteErrorResponse
Module:         db/main.py
Serialization:  JSON object
Version:        unversioned — tracked by git blame
Purpose:        SQLite execution failure (HTTP 200 with error payload)
Fields:
  - error: str — sqlite3 error message
  - sql: str — echoed attempted SQL
Validators:     none
Consumers:      nlp/pipeline/sql_executor.py
Last changed:   2026-05-26
```

```
Contract:       ExecutionResult
Module:         nlp/pipeline/sql_executor.py
Serialization:  dataclass
Version:        unversioned — tracked by git blame
Purpose:        Internal + wire-nested result of ReAct SQL execution loop
Fields:
  - success: bool
  - data: list[dict] | null — row dicts keyed by column name
  - columns: list[str] | null
  - sql: str — current/final SQL
  - steps_taken: int — ReAct iterations used
  - failure_reason: str | null
Validators:     accept observation requires success and non-error payload
Consumers:      pipeline.py, result_synthesizer.py, eval/harness.py
Last changed:   2026-05-26
```

```
Contract:       ResolvedQuestion
Module:         nlp/pipeline/ambiguity_detector.py
Serialization:  dataclass
Version:        unversioned — tracked by git blame
Purpose:        Ambiguity detection output feeding classifier and SQL generator
Fields:
  - original: str
  - resolved: str — may append qualifier suffix after em dash
  - interpretations_applied: list[str]
Validators:     rules matched against original question only (non-cascading)
Consumers:      sql_generator.py, pipeline.py, result_synthesizer.py
Last changed:   2026-05-26
```

```
Contract:       DomainDescriptor (domain.yaml)
Module:         nlp/schema/domain.yaml
Serialization:  YAML (PyYAML safe_load)
Version:        unversioned — tracked by git blame; T1 kill criterion locks content to spec §5.2
Purpose:        Semantic layer: table/column metadata, KPIs, disambiguation rules
Fields:
  - domain: str
  - tables.sales: object — columns (type, description), sample_values, date_range
  - relationships: list — empty (single table)
  - kpis: list — name, definition, optional note
  - disambiguation_rules: list — when, apply, note, state_in_output
Validators:     AmbiguityDetector matches rule.when strings via AMBIGUITY_TRIGGERS axis keys
Consumers:      semantic_layer.py, ambiguity_detector.py (via descriptor dict), tests
Last changed:   2026-05-26
```

```
Contract:       PipelineStageLogRecord
Module:         nlp/pipeline/pipeline.py
Serialization:  JSON Lines (one JSON object per line)
Version:        unversioned — tracked by git blame
Purpose:        Per-stage observability under logs/runs/{run_id}.jsonl
Fields:
  - run_id, stage, question, resolved_question: str
  - model: str | null
  - step: int | null
  - sql_attempted, observation_action, observation_message: str | null
  - latency_ms: int
  - extra keys merged when present (e.g. class, method, success, steps_taken)
Validators:     none
Consumers:      operators, eval/debug workflows
Last changed:   2026-05-26
```

```
Contract:       EvalReport
Module:         nlp/eval/harness.py
Serialization:  dataclass → JSON file (logs/eval_{timestamp}.json)
Version:        unversioned — tracked by git blame
Purpose:        Batch eval output for final-pass gate
Fields:
  - results: list[dict] — per-case question, class, sql_pass, sql_detail, judge, latency_ms, steps_taken, failure_reason, or error
Validators:     structural SQL check uses case-insensitive substring matching
Consumers:      README-documented manual eval workflow
Last changed:   2026-05-26
```

```
Contract:       SalesRow (ingested)
Module:         db/ingest.py
Serialization:  SQLite row (10 columns)
Version:        unversioned — tracked by git blame
Purpose:        Normalized POS line item stored in sales table
Fields:
  - date: TEXT — ISO YYYY-MM-DD (converted from CSV M/D/YYYY)
  - week_day, hour, ticket_number, ticket_prefix, waiter, product_name: TEXT
  - quantity: REAL
  - unitary_price, total: INTEGER
Validators:     datetime.strptime('%m/%d/%Y') on ingest; ticket_prefix derived from ticket_number split
Consumers:      all SQL queries via db /execute
Last changed:   2026-05-26
```
