#!/usr/bin/env bash
# Run an aiperf benchmark against the local vLLM server for one workload.
# Usage: scripts/run_bench.sh <chatbot|coding|rag|agent|toolagent> [concurrency] [request-count]
set -euo pipefail
cd "$(dirname "$0")/.."

WL="${1:?workload: chatbot|coding|rag|agent|toolagent}"
CONC="${2:-32}"
REQ="${3:-200}"

MODEL="${SERVED_NAME:-qwen3.6}"
URL="${URL:-http://localhost:8000}"
TOKENIZER="${TOKENIZER:-Qwen/Qwen3.6-35B-A3B-FP8}"
DATA=datasets/aiperf
export HF_HOME="${HF_HOME:-/home/howard/.cache/huggingface}"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"

. .venv/bin/activate

COMMON=(--model "$MODEL" --url "$URL" --endpoint-type chat --streaming
        --tokenizer "$TOKENIZER" --artifact-dir "results/$WL" --random-seed 42)

case "$WL" in
  chatbot)
    set -- "${COMMON[@]}" --public-dataset sharegpt \
        --concurrency "$CONC" --request-count "$REQ" ;;
  coding)
    set -- "${COMMON[@]}" --input-file "$DATA/coding_multiturn.jsonl" \
        --custom-dataset-type multi_turn --concurrency "$CONC" ;;
  rag)
    set -- "${COMMON[@]}" --input-file "$DATA/rag_singleturn.jsonl" \
        --custom-dataset-type single_turn --concurrency "$CONC" --request-count "$REQ" ;;
  agent)
    set -- "${COMMON[@]}" --input-file "$DATA/agent_multiturn.jsonl" \
        --custom-dataset-type multi_turn --concurrency "$CONC" ;;
  toolagent)
    set -- "${COMMON[@]}" --input-file "$DATA/toolagent_mooncake.jsonl" \
        --custom-dataset-type mooncake_trace --concurrency "$CONC" ;;
  *) echo "unknown workload: $WL"; exit 1 ;;
esac

echo ">>> aiperf profile $*"
aiperf profile "$@"
echo ">>> results in results/$WL/"
