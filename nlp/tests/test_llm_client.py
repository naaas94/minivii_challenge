import os
from unittest.mock import MagicMock, patch

import pytest

from pipeline.llm_client import (
    CONTAINER_OLLAMA_URL,
    HOST_OLLAMA_URL,
    LLMClient,
    _ollama_client,
    resolve_ollama_url,
)


@pytest.fixture(autouse=True)
def clear_ollama_client_cache():
    _ollama_client.cache_clear()
    resolve_ollama_url.cache_clear()
    yield
    _ollama_client.cache_clear()
    resolve_ollama_url.cache_clear()


def test_ollama_generate_uses_client_with_ollama_url_host():
    os.environ["OLLAMA_URL"] = "http://ollama:11434"
    mock_client = MagicMock()
    mock_client.generate.return_value = {"response": "ok"}

    with patch("ollama.Client", return_value=mock_client) as mock_client_cls:
        client = LLMClient(backend="ollama")
        result = client.generate("hello")

    mock_client_cls.assert_called_once_with(host="http://ollama:11434")
    mock_client.generate.assert_called_once_with(model="qwen2.5-coder:14b", prompt="hello", options={})
    assert result == "ok"


def test_resolve_ollama_url_prefers_host_when_reachable():
    os.environ.pop("OLLAMA_URL", None)

    with patch("pipeline.llm_client._probe_ollama", side_effect=lambda url, timeout=2.0: url == HOST_OLLAMA_URL):
        assert resolve_ollama_url() == HOST_OLLAMA_URL


def test_resolve_ollama_url_falls_back_to_container_when_host_unreachable():
    os.environ.pop("OLLAMA_URL", None)

    with patch("pipeline.llm_client._probe_ollama", return_value=False):
        assert resolve_ollama_url() == CONTAINER_OLLAMA_URL


def test_ollama_generate_does_not_use_module_level_generate():
    os.environ["OLLAMA_URL"] = "http://ollama:11434"
    mock_client = MagicMock()
    mock_client.generate.return_value = {"response": "ok"}

    with patch("ollama.Client", return_value=mock_client):
        with patch("ollama.generate") as mock_module_generate:
            LLMClient(backend="ollama").generate("hello")

    mock_module_generate.assert_not_called()
