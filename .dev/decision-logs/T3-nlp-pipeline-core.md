# T3 — NLP Pipeline Core

**Plan:** minivii-build · **Subtask:** T3 · **Date:** 2026-05-26

## Chosen approach

- Implemented six upstream modules under `nlp/pipeline/` as module-level functions and thin classes, matching spec §5.2–§5.5 and the T3 packet verbatim snippets.
- `SemanticLayer.render_ddl()` builds CREATE TABLE + KPI comment blocks from `domain.yaml` column metadata and fixed header/sample lines aligned with spec §5.2.
- `SchemaLinker.link()` returns full DDL via `SemanticLayer.render_ddl()`; the `question` argument is ignored for forward-compatible retrieval.
- `AmbiguityDetector` collects all trigger matches against the **original** question, then composes qualifiers once (no cascade).
- `QueryClassifier` uses keyword heuristics first, then `_llm_classify` via `LLMClient.generate(..., temperature=0.0)`.
- `SQLGenerator` uses `FEW_SHOT_EXAMPLES` keyed by all four `QueryClass` members; WINDOW example uses `strftime('%Y-W%W', date)` per correction C1.
- `LLMClient` supports `ollama`, `groq`, and `together` backends per spec §5.8.

## Alternatives rejected

- **LLM-based AmbiguityDetector:** Rejected per spec — adds 20–30s latency before SQL generation; rule-based path is sufficient for demo scope.
- **Retrieval-augmented SchemaLinker (ChromaDB/embeddings):** Rejected at T3 scope — single-table domain uses full schema injection; retrieval is a documented production enhancement only.
- **Sequential rule application on partially resolved text:** Rejected — v7 bug produced malformed NL; non-cascading composition against the original question is required.

## Assumptions made

- Docker/nlp container `WORKDIR` is `/app` with `pipeline` as the top-level import package (T1 layout); tests run with `cd nlp && pytest`.
- `litellm` and `ollama` are already listed in `nlp/requirements.txt` (T1); no new dependencies added.
- `log_interpretation` from spec §5.3 is deferred to T4 logging integration — not required in T3 packet outputs.

## Items deferred

- **Live LLM path validation:** Unit tests mock or avoid LLM calls; end-to-end classifier/generator wiring is validated in T6 eval harness.
- **Structured JSONL logging for ambiguity interpretations:** T4 owns pipeline-stage logging per plan §2 Logging contract.
