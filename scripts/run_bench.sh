#!/usr/bin/env bash
# Run an aiperf benchmark (in the aiperf:local container) against the local vLLM
# server for one workload.
# Usage: scripts/run_bench.sh <chatbot|coding|rag|agent|toolagent> [concurrency] [request-count]
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

WL="${1:?workload: chatbot|coding|rag|agent|toolagent}"
CONC="${2:-32}"
REQ="${3:-200}"

MODEL="${SERVED_NAME:-qwen3.6}"
URL="${URL:-http://localhost:8000}"
TOKENIZER="${TOKENIZER:-Qwen/Qwen3.6-35B-A3B-FP8}"
HF_DIR="${HF_DIR:-/home/howard/.cache/huggingface}"
IMG="${AIPERF_IMAGE:-aiperf:local}"
DATA=datasets/aiperf

COMMON=(--model "$MODEL" --url "$URL" --endpoint-type chat --streaming
        --tokenizer "$TOKENIZER" --artifact-dir "results/$WL" --random-seed 42)

case "$WL" in
  chatbot)   ARGS=("${COMMON[@]}" --public-dataset sharegpt --concurrency "$CONC" --request-count "$REQ") ;;
  coding)    ARGS=("${COMMON[@]}" --input-file "$DATA/coding_multiturn.jsonl"   --custom-dataset-type multi_turn   --concurrency "$CONC") ;;
  rag)       ARGS=("${COMMON[@]}" --input-file "$DATA/rag_singleturn.jsonl"     --custom-dataset-type single_turn  --concurrency "$CONC" --request-count "$REQ") ;;
  agent)     ARGS=("${COMMON[@]}" --input-file "$DATA/agent_multiturn.jsonl"    --custom-dataset-type multi_turn   --concurrency "$CONC") ;;
  toolagent) ARGS=("${COMMON[@]}" --input-file "$DATA/toolagent_mooncake.jsonl" --custom-dataset-type mooncake_trace --concurrency "$CONC") ;;
  *) echo "unknown workload: $WL"; exit 1 ;;
esac

echo ">>> [$WL] aiperf profile ${ARGS[*]}"
docker run --rm --network host \
  -v "${HF_DIR}:/hf" -e HF_HOME=/hf -e HF_HUB_OFFLINE=1 \
  -v "${ROOT}:/work" -w /work \
  "$IMG" profile "${ARGS[@]}"
echo ">>> results in results/$WL/"
