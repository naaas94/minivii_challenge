import logging
import os
import urllib.error
import urllib.request
from functools import lru_cache

logger = logging.getLogger(__name__)

HOST_OLLAMA_URL = "http://host.docker.internal:11434"
CONTAINER_OLLAMA_URL = "http://ollama:11434"


def _probe_ollama(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/api/tags", timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


@lru_cache(maxsize=1)
def resolve_ollama_url() -> str:
    """Pick Ollama backend: explicit OLLAMA_URL, else host, else container."""
    explicit = os.environ.get("OLLAMA_URL")
    if explicit:
        logger.info("Using Ollama at %s (OLLAMA_URL)", explicit)
        return explicit

    host_url = os.environ.get("OLLAMA_HOST_URL", HOST_OLLAMA_URL)
    fallback_url = os.environ.get("OLLAMA_FALLBACK_URL", CONTAINER_OLLAMA_URL)

    if _probe_ollama(host_url):
        logger.info("Using host Ollama at %s", host_url)
        return host_url

    logger.warning(
        "Host Ollama unreachable at %s; falling back to %s",
        host_url,
        fallback_url,
    )
    return fallback_url


@lru_cache(maxsize=1)
def _ollama_client():
    import ollama

    return ollama.Client(host=resolve_ollama_url())


class LLMClient:
    def __init__(self, backend: str = "ollama", model: str = "qwen2.5-coder:14b"):
        if backend not in {"ollama", "groq", "together"}:
            raise ValueError(f"Unsupported backend: {backend}")
        self.backend = backend
        self.model = model

    def generate(self, prompt: str, model: str | None = None, **kwargs) -> str:
        target_model = model or self.model
        if self.backend == "ollama":
            return self._ollama_generate(prompt, target_model, **kwargs)
        return self._litellm_generate(prompt, target_model, **kwargs)

    def _ollama_generate(self, prompt: str, model: str, **kwargs) -> str:
        options = {k: v for k, v in kwargs.items() if k != "model"}
        response = _ollama_client().generate(model=model, prompt=prompt, options=options)
        return response["response"]

    def _litellm_generate(self, prompt: str, model: str, **kwargs) -> str:
        import litellm

        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        return response.choices[0].message.content
