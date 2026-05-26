Section:      open-questions
Version:      1.1.0
Last updated: 2026-05-26

```
Question:     Should OLLAMA_URL be mapped to OLLAMA_HOST (or passed as Client host) in LLMClient for Compose correctness?
Impact:       nlp/main.py, nlp/pipeline/llm_client.py, docker-compose.yml, README env table
Closes when:  LLMClient reads host from OLLAMA_URL or compose sets OLLAMA_HOST; verified with docker compose up + successful /query LLM path
```

```
Question:     Is curl required in db Dockerfile for compose healthcheck, or should healthcheck use Python/stdlib?
Impact:       db/Dockerfile, docker-compose.yml, stack bring-up (nlp depends_on db healthy)
Closes when:  db reaches service_healthy on clean docker compose up without manual intervention
```

```
Question:     Should db /execute restrict SQL to read-only (SELECT/WITH) for NL-derived queries?
Impact:       db/main.py, security posture for prompt-injection surface
Closes when:  Explicit allow/deny policy implemented or accepted as demo-scope risk with documented rationale
```

```
Question:     How should CPU fallback (7b/8b env overrides) stay consistent with ollama/entrypoint.sh hardcoded 14b/32b pulls?
Impact:       ollama/entrypoint.sh, docker-compose.yml, README CPU fallback section
Closes when:  Entrypoint reads model names from env, or README documents that CPU fallback requires entrypoint edit, or parameterized compose profile exists
```

```
Question:     Should dual DDL (db SCHEMA_DDL vs domain.yaml render_ddl) be unified or is accepted debt sufficient for submission?
Impact:       db/main.py, nlp/schema/domain.yaml, nlp/pipeline/semantic_layer.py
Closes when:  Single source of truth chosen, or explicit "accepted debt" recorded in README/architecture with no /schema consumer dependency
Note:         Reclassified from blocker to maintainability debt — NLP runtime path uses YAML only; drift affects /schema endpoint and manual sync
```

## Resolved for demo scope (removed as open forks)

- **Schema retrieval vs full injection:** Resolved — demo uses full injection via `SchemaLinker.link()` ignoring question; retrieval (`retrieve_and_render`) documented as README scale-out future work only (README.md § scale-out item 1).
