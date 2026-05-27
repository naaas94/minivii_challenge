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
- **Confirmed** — same SQL answers as primary dev workstation when the SQL stage completes; nothing changed in the cloned repo
- **Verdict** — portability yes; performance / full-default parity no on this hardware

---

## Goal

Verify that Mini Nivii runs from a clean checkout on a weaker machine than the primary dev PC, and document what is portable vs. hardware-bound.

---

## How the check was run

### Baseline (default README path)

```bash
# data.csv at repo root (not committed)
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
```

This matches the README [CPU-Only Fallback](README.md#cpu-only-fallback) intent without editing the repo.

---

## Hardware on this laptop

| Resource | Observed |
|----------|----------|
| System RAM | ~14 GB total |
| Docker memory limit | ~10.7 GiB per container |
| GPU | None (Ollama `inference compute: CPU`) |
| Disk (Ollama cache) | ~29 GB volume after first pull (14b + 32b) |

**Implication:** Default models (`qwen2.5-coder:14b` ~9 GB + `qwen3:32b` ~20 GB) exceed available RAM for a full SQL → synthesis path on this host.

---

## Strategies (hardware-bound, no repo edits)

| Limitation | Strategy |
|------------|----------|
| 32B synthesis OOM (~20 GiB needed, ~13 GiB visible) | README fallback pair via `docker compose run -e` |
| 14B SQL on CPU ~8–9 min/query vs ~1–2 min on GPU PC | Accept slower inference; do not change committed default models |
| Shell env before `compose up` ignored by hardcoded `environment:` | Use `compose run --no-deps -e ...` for fallback runs |
| UI `nlp` service still on 14b/32b | SQL may complete; synthesis may OOM — use `compose run -e` for full e2e proof on low RAM |

---

## Results

### Stack portability (`docker compose up`)

| Check | Result |
|-------|--------|
| All 4 containers start | Pass |
| Health | `db` healthy (24,212 rows); `ollama` healthy |
| UI | HTTP 200 at `http://localhost:3001` |
| NLP unit tests (in container) | 34/34 pass |
| Ollama models | `qwen2.5-coder:14b`, `qwen3:32b` present |

### Default models (14b + 32b, via UI / running `nlp` service)

Representative runs: SQL stage ~8–9 min (CPU), execution pass, synthesis fails with Ollama `model requires more system memory (20.0 GiB) than is available (13.0 GiB)`.

**Confirmed:** Same pipeline logic and same SQL row answers as the primary workstation when SQL completes; synthesis blocked by RAM, not by clone-specific code.

### Fallback models (7b + 8b, `compose run -e`)

| Field | Value |
|-------|-------|
| Question | `what is the most sold product` |
| SQL result | Alfajor Sin Azucar Suelto, **4,566** units |
| Narrative | Generated |
| Wall time | **~15.7 min** (CPU) |

---

## Verdict

| Dimension | Verdict |
|-----------|---------|
| **Portability** (orchestration, services, data) | **Achieved** — identical compose stack on a 2nd Windows machine |
| **Reproducibility** (logic + answers) | **Achieved** when models fit in memory and inference finishes |
| **Performance parity** | **Not achieved** — CPU-only; default-model full e2e blocked by RAM on this host |
| **Product parity (default models, this laptop)** | **Partial** — SQL yes; synthesis needs fallback models via `compose run -e` |

A reviewer can stand up the full stack from a clean checkout. Low-RAM CPU hardware needs the documented fallback models (see README), not changes to committed configuration.
