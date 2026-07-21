#!/usr/bin/env bash
# Serve nvidia/Qwen3.6-35B-A3B-NVFP4 for the NVFP4 cross-hardware benchmark.
# Runs ON the machine being measured. NODE=spark|5090 picks image + memory knobs;
# everything else is unified across the two machines (see RUNBOOK).
set -euo pipefail

NODE="${NODE:?set NODE=spark|5090|5080|h100}"
DEF_OFFLOAD=0   # GB of weights to spill to CPU RAM (only when VRAM < weights)
case "$NODE" in
  spark) DEF_IMAGE="vllm/vllm-openai:v0.24.0";             DEF_UTIL=0.5; DEF_BT=32768 ;;
  5090)  DEF_IMAGE="vllm/vllm-openai:v0.24.0-x86_64-cu129"; DEF_UTIL=0.9; DEF_BT=8192 ;;
  # RTX 5080 = 16 GB VRAM < 20.4 GiB weights -> CPU-offload the overflow (driver 580 = cu130 OK)
  5080)  DEF_IMAGE="vllm/vllm-openai:v0.24.0";             DEF_UTIL=0.9; DEF_BT=8192; DEF_OFFLOAD=12 ;;
  # H100 PCIe 80 GB: weights fit natively, no offload; sm_90 still Marlin weight-only FP4 (driver 610 = cu130)
  h100)  DEF_IMAGE="vllm/vllm-openai:v0.24.0";             DEF_UTIL=0.9; DEF_BT=32768 ;;
  *) echo "!!! unknown NODE=$NODE (want spark|5090|5080)"; exit 2 ;;
esac

IMAGE="${VLLM_IMAGE:-$DEF_IMAGE}"
# SERVE_MODEL wins over MODEL: run_nvfp4.sh reassigns MODEL to the *served* name
# (the id aiperf sends), and it stays exported, so it can't carry the HF repo id here.
MODEL="${SERVE_MODEL:-${MODEL:-nvidia/Qwen3.6-35B-A3B-NVFP4}}"
SERVED="${SERVED_NAME:-qwen3.6-nvfp4}"
PORT="${PORT:-8000}"
MAXLEN="${MAX_MODEL_LEN:-131072}"
GPU_UTIL="${GPU_UTIL:-$DEF_UTIL}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-32}"
BT="${MAX_NUM_BATCHED_TOKENS:-$DEF_BT}"
OFFLOAD="${CPU_OFFLOAD_GB:-$DEF_OFFLOAD}"
HF_DIR="${HF_DIR:-$HOME/.cache/huggingface}"
VLLM_CACHE="${VLLM_CACHE:-$HOME/.cache/vllm}"
NAME="${CONTAINER_NAME:-vllm-nvfp4}"
WAIT_S="${WAIT_S:-1200}"
mkdir -p "$VLLM_CACHE"

OFFLOAD_ARG=""; [ "${OFFLOAD:-0}" -gt 0 ] && OFFLOAD_ARG="--cpu-offload-gb $OFFLOAD"
echo ">>> node=$NODE image=$IMAGE model=$MODEL served=$SERVED"
echo ">>> max_len=$MAXLEN util=$GPU_UTIL max_seqs=$MAX_NUM_SEQS batched_tokens=$BT cpu_offload_gb=$OFFLOAD"
docker rm -f "$NAME" >/dev/null 2>&1 || true
# kill any stray vLLM EngineCore still holding GPU memory from a previous container
spid=$(nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader 2>/dev/null | awk -F', ' '/EngineCore|vllm/{print $1}')
if [ -n "$spid" ]; then echo ">>> killing stray vLLM pid(s): $spid"; kill -9 $spid 2>/dev/null || true; sleep 4; fi

docker run -d --name "$NAME" \
  --gpus all --ipc=host \
  --add-host host.docker.internal:host-gateway \
  --entrypoint vllm \
  -p "${PORT}:8000" \
  -v "${HF_DIR}:/root/.cache/huggingface" \
  -v "${VLLM_CACHE}:/root/.cache/vllm" \
  -e HF_HUB_OFFLINE=1 \
  -e VLLM_SERVER_DEV_MODE=1 \
  ${DOCKER_ENV_ARGS:-} \
  "$IMAGE" \
  serve "$MODEL" \
  --served-model-name "$SERVED" \
  --port 8000 \
  --max-model-len "$MAXLEN" \
  --gpu-memory-utilization "$GPU_UTIL" \
  --max-num-seqs "$MAX_NUM_SEQS" \
  --max-num-batched-tokens "$BT" \
  --enable-prefix-caching \
  --reasoning-parser qwen3 \
  --trust-remote-code \
  ${OFFLOAD_ARG} \
  ${EXTRA_ARGS:-}

echo ">>> container started: $NAME; waiting for /health (up to ${WAIT_S}s)"
for i in $(seq 1 $((WAIT_S / 5))); do
  if curl -fsS "http://localhost:${PORT}/health" >/dev/null 2>&1; then
    echo ">>> READY after ~$((i*5))s"
    curl -s "http://localhost:${PORT}/v1/models" | head -c 400; echo
    exit 0
  fi
  if ! docker ps --filter "name=${NAME}" --format '{{.Names}}' | grep -q "$NAME"; then
    echo "!!! container exited early; last logs:"; docker logs --tail 60 "$NAME"; exit 1
  fi
  sleep 5
done
echo "!!! not ready after ${WAIT_S}s; logs:"; docker logs --tail 60 "$NAME"; exit 1
