#!/usr/bin/env bash
# Reproduce every point measured against the optimumxt Dynamo endpoints, against a
# local vLLM on spark. Assumes scripts/serve_optimumxt_repro.sh is already up for
# the matching MODEL_KEY.
#
#   MODEL_KEY=llama31 bash scripts/run_optimumxt_repro.sh
#
# REMOTE=1 on purpose. The endpoint runs could not reset the prefix cache or read
# vLLM's /metrics, so neither does this, otherwise the workloads would differ.
# A local server could do better -- see RESET=1 below for that variant -- but the
# result would no longer be comparable with the endpoint numbers.
set -uo pipefail
cd "$(dirname "$0")/.."

MODEL_KEY="${MODEL_KEY:?set MODEL_KEY=llama31|qwen3vl}"
case "$MODEL_KEY" in
  llama31) SERVED="Llama-3.1-8B-Instruct-optimumxt"
           TOK="NousResearch/Meta-Llama-3.1-8B-Instruct"
           FILTERED="datasets/aiperf/le4096" ;;
  qwen3vl) SERVED="Qwen3-VL-30B-A3B-Instruct-optimumxt"
           TOK="Qwen/Qwen3-VL-30B-A3B-Instruct"
           FILTERED="datasets/aiperf/le4096_qwen3vl" ;;
  *) echo "!!! unknown MODEL_KEY=$MODEL_KEY"; exit 2 ;;
esac

URL="${URL:-http://localhost:8000}"
BASE="${OUTROOT:-results/nvfp4/spark_repro_$MODEL_KEY}"
export REMOTE="${REMOTE:-1}" NODE="spark_repro_$MODEL_KEY" SERVED_NAME="$SERVED" \
       URL TOKENIZER="$TOK" RC_TLIM="${RC_TLIM:-9000}"

run() {  # label workload point reqs warmup [data_dir]
  local label=$1 wl=$2 pt=$3 reqs=$4 wu=$5 dd=${6:-datasets/aiperf}
  echo "### $label  $wl $pt reqs=$reqs warmup=$wu  start $(date '+%F %T')"
  WARMUP="$wu" REQS="$reqs" POINTS="$pt" DATA_DIR="$dd" \
    OUTBASE="$BASE/$label" bash scripts/run_nvfp4.sh "$wl"
  echo "### $label  end $(date '+%F %T')"
}

echo "======== repro $MODEL_KEY start $(date '+%F %T') ========"

# S1 -- the original WARMUP=2 series (ngrok, Qwen3-VL)
run w2_chatbot_c1      chatbot_flat c1  10 2
run w2_chatbot_c2      chatbot_flat c2  20 2
run w2_chatbot_c1_rep  chatbot_flat c1  10 2
run w2_agent_c1        agent_flat   c1  10 2

# S2 -- the WARMUP=0, 20-request series
run w0_chatbot_c1      chatbot_flat c1  20 0
run w0_agent_c1        agent_flat   c1  20 0
run w0_chatbot_c1_rep  chatbot_flat c1  20 0
run w0_agent_c2        agent_flat   c2  20 0

# S3 -- the 100-request series, alternating, on context-filtered datasets
run r100_chatbot_c1    chatbot_flat c1 100 0 "$FILTERED"
run r100_agent_c1      agent_flat   c1 100 0 "$FILTERED"
run r100_chatbot_c2    chatbot_flat c2 100 0 "$FILTERED"
run r100_agent_c2      agent_flat   c2 100 0 "$FILTERED"

# S4 -- the c32 point that wedged the Dynamo worker
run c32_chatbot        chatbot_flat c32 320 16

echo "======== repro $MODEL_KEY DONE $(date '+%F %T') ========"
