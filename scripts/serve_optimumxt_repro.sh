#!/usr/bin/env bash
# Serve the models measured on the optimumxt Dynamo endpoints, locally on spark,
# so their numbers can be reproduced against a vLLM we control.
#
#   MODEL_KEY=llama31 bash scripts/serve_optimumxt_repro.sh
#   MODEL_KEY=qwen3vl bash scripts/serve_optimumxt_repro.sh
#
# Deliberately NOT scripts/serve_nvfp4.sh: that one hardcodes --reasoning-parser
# qwen3, which is wrong for Llama (the Dynamo endpoint returned reasoning_content
# null, i.e. no reasoning parsing) and would alter the measured output.
#
# max-model-len defaults to 4096 to match the endpoints' cap. That is the whole
# point of the comparison -- do not raise it without saying so in the results.
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL_KEY="${MODEL_KEY:?set MODEL_KEY=llama31|qwen3vl}"
case "$MODEL_KEY" in
  # dense 8B; weights ~16 GB, so a modest util still leaves a large KV cache.
  #
  # --chat-template is REQUIRED for parity. The NousResearch mirror ships a
  # 348-char template with no system block, while the Dynamo endpoint applied
  # Meta's official one -- worth exactly 25 tokens per request, verified against
  # the endpoint's per-request records (every one of 20 off by 25, ISL sum
  # 11,676 vs 12,176). With the template below the counts match exactly.
  llama31) DEF_MODEL="NousResearch/Meta-Llama-3.1-8B-Instruct"
           DEF_SERVED="Llama-3.1-8B-Instruct-optimumxt"
           DEF_UTIL=0.60
           DEF_EXTRA="--chat-template /work/scripts/chat_templates/llama31_dynamo.jinja" ;;
  # MoE, ~3B activated; weights ~60 GB of the 119 GB unified memory
  qwen3vl) DEF_MODEL="Qwen/Qwen3-VL-30B-A3B-Instruct"
           DEF_SERVED="Qwen3-VL-30B-A3B-Instruct-optimumxt"
           DEF_UTIL=0.88; DEF_EXTRA="--limit-mm-per-prompt {\"image\":0,\"video\":0}" ;;
  *) echo "!!! unknown MODEL_KEY=$MODEL_KEY (want llama31|qwen3vl)"; exit 2 ;;
esac

IMAGE="${VLLM_IMAGE:-vllm/vllm-openai:v0.24.0}"
MODEL="${MODEL:-$DEF_MODEL}"
SERVED="${SERVED_NAME:-$DEF_SERVED}"
PORT="${PORT:-8000}"
MAXLEN="${MAX_MODEL_LEN:-4096}"
GPU_UTIL="${GPU_UTIL:-$DEF_UTIL}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-32}"
BT="${MAX_NUM_BATCHED_TOKENS:-32768}"
HF_DIR="${HF_DIR:-$HOME/.cache/huggingface}"
VLLM_CACHE="${VLLM_CACHE:-$HOME/.cache/vllm}"
NAME="${CONTAINER_NAME:-vllm-repro}"
WAIT_S="${WAIT_S:-1800}"
mkdir -p "$VLLM_CACHE"

echo ">>> key=$MODEL_KEY image=$IMAGE model=$MODEL served=$SERVED"
echo ">>> max_len=$MAXLEN util=$GPU_UTIL max_seqs=$MAX_NUM_SEQS batched_tokens=$BT"
docker rm -f "$NAME" >/dev/null 2>&1 || true
# a previous container's EngineCore can survive and keep holding GPU memory
spid=$(nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader 2>/dev/null \
        | awk -F', ' '/EngineCore|vllm/{print $1}')
if [ -n "$spid" ]; then echo ">>> killing stray vLLM pid(s): $spid"; kill -9 $spid 2>/dev/null || true; sleep 4; fi

docker run -d --name "$NAME" \
  --gpus all --ipc=host \
  --add-host host.docker.internal:host-gateway \
  --entrypoint vllm \
  -p "${PORT}:8000" \
  -v "${HF_DIR}:/root/.cache/huggingface" \
  -v "${VLLM_CACHE}:/root/.cache/vllm" \
  -v "$(pwd):/work:ro" \
  -e HF_HUB_OFFLINE=1 \
  -e VLLM_SERVER_DEV_MODE=1 \
  "$IMAGE" \
  serve "$MODEL" \
  --served-model-name "$SERVED" \
  --port 8000 \
  --max-model-len "$MAXLEN" \
  --gpu-memory-utilization "$GPU_UTIL" \
  --max-num-seqs "$MAX_NUM_SEQS" \
  --max-num-batched-tokens "$BT" \
  --enable-prefix-caching \
  --trust-remote-code \
  ${EXTRA_ARGS:-$DEF_EXTRA}

echo ">>> container started: $NAME; waiting for /health (up to ${WAIT_S}s)"
for i in $(seq 1 $((WAIT_S / 5))); do
  if curl -fsS "http://localhost:${PORT}/health" >/dev/null 2>&1; then
    echo ">>> READY after ~$((i*5))s"
    curl -s "http://localhost:${PORT}/v1/models" | head -c 400; echo
    # KV cache capacity, the number the Dynamo endpoints would never tell us
    docker logs "$NAME" 2>&1 | grep -iE 'GPU KV cache size|Maximum concurrency' | tail -2
    exit 0
  fi
  if ! docker ps --filter "name=${NAME}" --format '{{.Names}}' | grep -q "$NAME"; then
    echo "!!! container exited early; last logs:"; docker logs --tail 60 "$NAME"; exit 1
  fi
  sleep 5
done
echo "!!! not ready after ${WAIT_S}s; logs:"; docker logs --tail 60 "$NAME"; exit 1
