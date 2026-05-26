#!/bin/sh
ollama serve &

echo "Waiting for Ollama API..."
until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
    sleep 2
done
echo "Ollama API ready."

echo "Pulling SQL model..."
ollama pull "${SQL_MODEL:-qwen2.5-coder:14b}" || exit 1

echo "Pulling synthesis model..."
ollama pull "${SYNTHESIS_MODEL:-qwen3:32b}" || exit 1

touch /tmp/models_ready
echo "Models ready. Ollama serving."
wait
