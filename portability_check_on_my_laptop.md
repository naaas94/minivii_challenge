# Portability check on my laptop

**Date:** 2026-05-27  
**Machine:** 2nd clean Windows 10 host (fresh clone + `data.csv` only)  
**Repo state:** Unmodified from pulled clone — no edits to `docker-compose.yml`, service code, or default model config.

---

## TL;DR

- **How** — default `docker compose up` vs `docker compose run -e` fallback (no compose edits)
- **Hardware** — ~14 GB RAM, CPU-only, Docker ~10.7 GiB limit
- **Strategies** — smaller models via `-e`, cached Ollama volume, accepting slower CPU inference
- **Results** — stack/UI/tests pass; default 14b/32b partial (SQL ok, synthesis OOM); full e2e with 7b/8b in ~15.7 min
- **Confirmed** — same answers as primary PC `dev_log.yaml`; nothing changed in the cloned repo
- **Verdict** — portability yes; performance / full-default parity no on this hardware

---

## Goal

Verify that Mini Nivii runs from a clean checkout on a weaker machine than the primary dev PC, and document what is portable vs. what is hardware-bound.

---

## How the check was run

### Baseline (default README path)

```bash
# data.csv placed at repo root (not committed)
docker compose up
# UI: http://localhost:3001
```

No compose overrides, no code changes, no custom `.env` file.

### Supplementary-model path (RAM-limited fallback, config unchanged)

Default `environment:` values in `docker-compose.yml` are hardcoded; shell `$env:SQL_MODEL=...` on `docker compose up` does **not** override them. One-off runs use `docker compose run -e`:

```powershell
docker compose exec ollama ollama pull qwen2.5-coder:7b
docker compose exec ollama ollama pull qwen3:8b

docker compose run --rm --no-deps `
  -e DB_URL=http://db:8001 `
  -e OLLAMA_URL=http://ollama:11434 `
  -e SQL_MODEL=qwen2.5-coder:7b `
  -e SYNTHESIS_MODEL=qwen3:8b `
  nlp python -m eval.harness --skip-judge
# (or any Pipeline.run() invocation — the -e flags are what matter)
```

This matches the README [CPU-Only Fallback](README.md#cpu-only-fallback) intent without editing the repo.

---

## Hardware on this laptop

| Resource | Observed |
|----------|----------|
| System RAM | ~14 GB total |
| Docker memory limit | ~10.7 GiB per container |
| GPU | None (`total_vram=0`, Ollama `inference compute: CPU`) |
| Disk (Ollama cache) | ~29 GB volume after first pull (14b + 32b) |

**Implication:** Default models (`qwen2.5-coder:14b` ~9 GB + `qwen3:32b` ~20 GB) exceed available RAM for a full SQL → synthesis path on this host.

---

## Strategies adopted (because of hardware)

| Limitation | Strategy | Config file changed? |
|------------|----------|----------------------|
| 32B synthesis model cannot load (~20 GiB needed, ~13 GiB visible) | Use README fallback pair via `docker compose run -e` | No |
| 14B SQL on CPU ~8–9 min/query vs ~1–2 min on GPU PC | Accept slower inference; do not swap default compose models | No |
| Shell env before `docker compose up` ignored by hardcoded compose `environment:` | Use `docker compose run --no-deps -e ...` for fallback runs | No |
| First-run model download ~29 GB | Rely on `ollama_cache` Docker volume; subsequent starts reuse cache | No |
| UI service still points at default `nlp` (14b/32b) | Document that interactive UI on this laptop completes SQL but may fail at synthesis; use `compose run` for full e2e proof | No |

---

## Results

### Stack portability (default `docker compose up`)

| Check | Result |
|-------|--------|
| All 4 containers start | Pass (`db`, `ollama`, `nlp`, `ui`) |
| Health | `db` healthy (24,212 rows); `ollama` healthy (models cached) |
| UI | HTTP 200 at `http://localhost:3001` |
| NLP unit tests (in container) | 34/34 pass (excluding host-only README contract test) |
| Ollama models present | `qwen2.5-coder:14b`, `qwen3:32b` (+ fallback pulls added to same volume) |

### Default-model pipeline (14b + 32b, via UI / running `nlp` service)

Partial runs logged in `nlp` container at `logs/runs/`:

| Query | SQL stage | Execution | Synthesis |
|-------|-----------|-----------|-----------|
| Most bought product on Fridays | ~9 min (CPU) | Pass — Alfajor Sin Azucar Suelto, **850** | Fail — `qwen3:32b` OOM |
| Transactions on Saturdays | ~8.4 min | Pass — **1721** transactions | Fail — same OOM |
| Busiest hours on weekdays | Started | Incomplete | — |

Ollama log (representative):

```text
model requires more system memory (20.0 GiB) than is available (13.0 GiB)
POST /api/generate → 500
```

**Confirmed:** Same pipeline logic and same SQL answers as the primary PC when the SQL stage completes; synthesis blocked by RAM, not by code differences.

### Fallback-model full e2e (`compose run -e`, 7b + 8b)

| Field | Value |
|-------|-------|
| Question | `what is the most sold product` |
| Models | `qwen2.5-coder:7b` + `qwen3:8b` |
| Query class | `aggregation` |
| SQL result | Alfajor Sin Azucar Suelto, **4,566** units |
| Narrative | Generated (full paragraph) |
| Wall time | **~15.7 min** (942 s) |
| PC reference (GPU, dev_log) | Same product/quantity; ~7 min e2e with 14b/32b |

---

## What was confirmed on this end

1. **Reproducible bring-up** — clone, add `data.csv`, `docker compose up`; no local patches required.
2. **Same data contract** — 24,212 rows, schema and ingest behavior match README.
3. **Same analytical outcomes** — SQL and row results align with primary PC dev_log when inference completes.
4. **Same failure modes** — classifier quirks (e.g. Friday → `time_filter`) and RAM ceiling on 32B are environmental, not clone-specific.
5. **Fallback path works without repo edits** — README CPU model pair via `docker compose run -e` delivers full SQL + narrative on this hardware.
6. **Nothing in the pulled clone was modified** to achieve the above; only runtime commands and ephemeral Ollama pulls (`7b`, `8b`) on top of the default cached models.

---

## Rationale / verdict

| Dimension | Verdict |
|-----------|---------|
| **Portability** (orchestration, services, data) | **Achieved** — identical compose stack runs on a 2nd Windows machine. |
| **Reproducibility** (logic + answers) | **Achieved** when models fit in memory and inference finishes. |
| **Performance parity** | **Not achieved** — CPU-only, ~5× slower SQL vs GPU PC; full default e2e blocked by RAM. |
| **Product parity on this laptop (default models)** | **Partial** — SQL path yes; synthesis no without fallback models. |

The project meets its portability goal for the challenge: a reviewer can stand up the full stack from a clean checkout. Full interactive use on low-RAM CPU hardware requires the documented fallback models via `docker compose run -e`, not changes to the committed configuration.

---

## Artifacts inspected

- Docker logs: `db`, `nlp`, `ui`, `ollama`
- Pipeline JSONL: `nlp` container `logs/runs/2026-05-27*.jsonl`
- Primary PC comparison: `dev_log.yaml`, README eval table
