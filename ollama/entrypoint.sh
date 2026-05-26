#!/bin/sh
ollama serve &

echo "Waiting for Ollama API..."
until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
    sleep 2
done
echo "Ollama API ready."

echo "Pulling SQL model..."
ollama pull qwen2.5-coder:14b

echo "Pulling synthesis model..."
ollama pull qwen3:32b

touch /tmp/models_ready
echo "Models ready. Ollama serving."
wait
