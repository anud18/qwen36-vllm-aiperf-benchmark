#!/usr/bin/env bash
# Serve Qwen/Qwen3.6-35B-A3B-FP8 with vLLM in Docker on GB10 (aarch64).
# Usage: scripts/serve_vllm.sh [IMAGE]
#   IMAGE defaults to vllm/vllm-openai:latest; fallback: nvcr.io/nvidia/vllm:26.05.post1-py3
set -euo pipefail

IMAGE="${1:-${VLLM_IMAGE:-ghcr.io/spark-arena/dgx-vllm-eugr-nightly-tf5:20260614}}"
MODEL="${MODEL:-Qwen/Qwen3.6-35B-A3B-FP8}"
SERVED="${SERVED_NAME:-qwen3.6}"
PORT="${PORT:-8000}"
MAXLEN="${MAX_MODEL_LEN:-65536}"
GPU_UTIL="${GPU_UTIL:-0.50}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-}"
MAX_NUM_BATCHED_TOKENS="${MAX_NUM_BATCHED_TOKENS:-}"
HF_DIR="${HF_DIR:-/home/howard/.cache/huggingface}"
VLLM_CACHE="${VLLM_CACHE:-/home/howard/.cache/vllm}"
NAME="${CONTAINER_NAME:-vllm-qwen36}"
mkdir -p "$VLLM_CACHE"

echo ">>> image=$IMAGE model=$MODEL served=$SERVED port=$PORT max_len=$MAXLEN"
docker rm -f "$NAME" >/dev/null 2>&1 || true

docker run -d --name "$NAME" \
  --gpus all --ipc=host \
  --add-host host.docker.internal:host-gateway \
  --entrypoint vllm \
  -p "${PORT}:8000" \
  -v "${HF_DIR}:/root/.cache/huggingface" \
  -v "${VLLM_CACHE}:/root/.cache/vllm" \
  -e HF_HUB_OFFLINE=1 \
  -e VLLM_USE_V1=1 \
  "$IMAGE" \
  serve "$MODEL" \
  --served-model-name "$SERVED" \
  --port 8000 \
  --max-model-len "$MAXLEN" \
  --gpu-memory-utilization "$GPU_UTIL" \
  ${MAX_NUM_SEQS:+--max-num-seqs $MAX_NUM_SEQS} \
  ${MAX_NUM_BATCHED_TOKENS:+--max-num-batched-tokens $MAX_NUM_BATCHED_TOKENS} \
  --enable-prefix-caching \
  --trust-remote-code \
  ${REASONING_PARSER:+--reasoning-parser $REASONING_PARSER} \
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
