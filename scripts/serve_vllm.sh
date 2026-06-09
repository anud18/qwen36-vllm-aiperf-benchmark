#!/usr/bin/env bash
# Serve Qwen/Qwen3.6-35B-A3B-FP8 with vLLM in Docker on GB10 (aarch64).
# Usage: scripts/serve_vllm.sh [IMAGE]
#   IMAGE defaults to vllm/vllm-openai:latest; fallback: nvcr.io/nvidia/vllm:26.05.post1-py3
set -euo pipefail

IMAGE="${1:-${VLLM_IMAGE:-vllm/vllm-openai:latest}}"
MODEL="${MODEL:-Qwen/Qwen3.6-35B-A3B-FP8}"
SERVED="${SERVED_NAME:-qwen3.6}"
PORT="${PORT:-8000}"
MAXLEN="${MAX_MODEL_LEN:-65536}"
GPU_UTIL="${GPU_UTIL:-0.90}"
HF_DIR="${HF_DIR:-/home/howard/.cache/huggingface}"
NAME="${CONTAINER_NAME:-vllm-qwen36}"

echo ">>> image=$IMAGE model=$MODEL served=$SERVED port=$PORT max_len=$MAXLEN"
docker rm -f "$NAME" >/dev/null 2>&1 || true

docker run -d --name "$NAME" \
  --gpus all --ipc=host \
  -p "${PORT}:8000" \
  -v "${HF_DIR}:/root/.cache/huggingface" \
  -e HF_HUB_OFFLINE=1 \
  -e VLLM_USE_V1=1 \
  "$IMAGE" \
  --model "$MODEL" \
  --served-model-name "$SERVED" \
  --port 8000 \
  --max-model-len "$MAXLEN" \
  --gpu-memory-utilization "$GPU_UTIL" \
  --enable-prefix-caching \
  --trust-remote-code \
  ${EXTRA_ARGS:-}

echo ">>> container started: $NAME"
echo ">>> follow logs: docker logs -f $NAME"
echo ">>> waiting for /health ..."
for i in $(seq 1 120); do
  if curl -fsS "http://localhost:${PORT}/health" >/dev/null 2>&1; then
    echo ">>> READY after ~$((i*5))s"
    curl -s "http://localhost:${PORT}/v1/models" | head -c 400; echo
    exit 0
  fi
  if ! docker ps --filter "name=${NAME}" --format '{{.Names}}' | grep -q "$NAME"; then
    echo "!!! container exited early; last logs:"; docker logs --tail 40 "$NAME"; exit 1
  fi
  sleep 5
done
echo "!!! not ready after 600s; logs:"; docker logs --tail 60 "$NAME"; exit 1
