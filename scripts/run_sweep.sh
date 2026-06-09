#!/usr/bin/env bash
# Concurrency sweep: run each workload at concurrency 4,8,16,32.
# Results: results/sweep/<workload>/c<level>/profile_export_aiperf.csv
# Usage: scripts/run_sweep.sh [workload ...]   (default: all five)
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

LEVELS="${LEVELS:-4 8 16 32}"
BUDGET="${BUDGET:-420}"
MODEL="${SERVED_NAME:-qwen3.6}"
URL="${URL:-http://localhost:8000}"
TOKENIZER="${TOKENIZER:-Qwen/Qwen3.6-35B-A3B-FP8}"
HF_DIR="${HF_DIR:-/home/howard/.cache/huggingface}"
IMG="${AIPERF_IMAGE:-aiperf:local}"
DATA=datasets/aiperf

# per-workload sizing (kept modest: 4 levels x 5 workloads = 20 runs)
declare -A SIZE=( [chatbot]="--request-count 40" [rag]="--request-count 80"
  [coding]="--conversation-num 10" [agent]="--conversation-num 12"
  [toolagent]="--request-count 40" )
declare -A SRC=( [coding]="multi_turn $DATA/coding_multiturn.jsonl"
  [rag]="single_turn $DATA/rag_singleturn.jsonl"
  [agent]="multi_turn $DATA/agent_multiturn.jsonl"
  [toolagent]="mooncake_trace $DATA/toolagent_mooncake.jsonl" )

run_one() {  # workload concurrency
  local wl=$1 c=$2 adir="results/sweep/$wl/c$c"
  mkdir -p "$adir"
  local args=(--model "$MODEL" --url "$URL" --endpoint-type chat --streaming
              --tokenizer "$TOKENIZER" --artifact-dir "$adir" --random-seed 42
              --concurrency "$c" ${SIZE[$wl]})
  if [ "$wl" = "chatbot" ]; then
    args+=(--public-dataset sharegpt)
  else
    read -r dtype dfile <<<"${SRC[$wl]}"
    args+=(--input-file "$dfile" --custom-dataset-type "$dtype")
  fi
  local cname="aiperf-${wl}-c${c}"
  echo "---- $wl c=$c $(date +%T) ----"
  docker rm -f "$cname" >/dev/null 2>&1 || true
  timeout "$BUDGET" docker run --rm --name "$cname" --network host \
    -v "${HF_DIR}:/hf" -e HF_HOME=/hf -e HF_HUB_OFFLINE=1 \
    -v "${ROOT}:/work" -w /work "$IMG" profile "${args[@]}" \
    > "$adir/run.log" 2>&1
  local rc=$?
  # timeout SIGTERMs the docker CLI but not the container; force-remove it
  docker rm -f "$cname" >/dev/null 2>&1 || true
  [ $rc -eq 124 ] && echo "  [$wl c=$c] TIMEOUT (partial)"
  grep -E "Benchmark Duration" "$adir/run.log" | tail -1 || echo "  (no duration; see $adir/run.log)"
}

WLS=("${@:-chatbot coding rag agent toolagent}")
# shellcheck disable=SC2068
for wl in ${WLS[@]}; do
  for c in $LEVELS; do run_one "$wl" "$c"; done
done
echo "================ SWEEP DONE $(date +%T) ================"
