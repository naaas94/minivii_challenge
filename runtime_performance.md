# Runtime performance

How Mini Nivii picks an Ollama backend, and what that means for wall-clock time.

## How inference routing works

When the app needs the LLM, it picks where to send the request:

1. **You set `OLLAMA_URL`** — that wins (manual override).
2. **Ollama is running on your machine** (outside Docker) — the app uses that. This is the fast path: your GPU on Windows, Metal on Mac.
3. **Otherwise** — the app uses the Ollama container in Docker. That works everywhere, but on Windows and Mac it usually runs on CPU only, which is much slower.

You still run `docker compose up` as before. The Ollama container stays in the stack so the app works even if you haven't installed Ollama on your machine; it also pulls models on first run when you're on the container path.

Check which path is in use:

```bash
curl http://localhost:8002/health
# host Ollama:  "ollama_url": "http://host.docker.internal:11434"
# container:    "ollama_url": "http://ollama:11434"
```

Set `OLLAMA_URL` yourself if you want to force one or the other.

---

## Why this matters

The Linux Ollama container does **not** get GPU access from Docker Desktop on Windows or Mac by default. Without host routing, inference runs on **CPU only** inside the container — multi-hour eval runs, roughly 15–20 min per query.

Install Ollama on your machine (Windows app, Mac via Homebrew or the desktop app) to use CUDA or Metal. That is what this routing change prefers automatically.

---

## Measured runs (`nlp/logs`)

Same models throughout: `qwen2.5-coder:14b` and `qwen3:32b`.

| Log | Ollama location | Time |
|-----|-----------------|------|
| `eval_20260527T034521Z.json` — 12-case eval with judge | Docker container | ~101 min logged · ~3 h wall clock |
| `eval_20260526T204618Z.json` — 12-case eval, no judge | Docker container | ~12 min total |
| `runs/2026-05-27*.jsonl` — May 27 eval (container, CPU) | Docker container | ~7–24 min per case |

Judge calls add extra time on top of pipeline latency and are not included in `latency_ms` inside the eval JSON.

Install Ollama on your machine before `docker compose up` to avoid the container CPU path. A single UI query on accelerated hardware is typically **~3–7 min**; a full 12-case eval with judge is typically **~90–120 min** (see README).

---

## Mac usage

- Install Ollama on the Mac (`brew install ollama` or the desktop app) and pull the two models.
- Run `docker compose up`. The app checks for Ollama on your Mac automatically.
- Apple Silicon uses Metal, not NVIDIA CUDA. The Linux Ollama container cannot use Metal — use Ollama on the Mac itself.
- If Ollama is not installed on the Mac, the Docker container still works, but expect the slower CPU timings in the table above.

---

## Linux and Windows usage

| OS | Use this for speed | If that is not available |
|----|--------------------|---------------------------|
| **Windows** | Ollama desktop app (GPU) | Docker Ollama container (CPU) |
| **Mac (Apple Silicon)** | Ollama on the Mac (Metal) | Docker Ollama container (CPU) |
| **Linux + NVIDIA** | Ollama on the host (GPU) | Docker Ollama container (CPU) |

Host and container keep **separate model caches**. If you switch between them, pull the models on whichever Ollama instance you are using.

---

## CPU-only machines

If you have no GPU or Metal acceleration, see [README.md](README.md) for smaller fallback models. The routing change above still applies; latency will remain high with the default 14b + 32b pair on CPU.
