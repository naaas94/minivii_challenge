import os
from functools import lru_cache


@lru_cache(maxsize=1)
def _ollama_client():
    import ollama

    return ollama.Client(host=os.environ["OLLAMA_URL"])


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
