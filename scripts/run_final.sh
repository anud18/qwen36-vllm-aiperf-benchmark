#!/usr/bin/env bash
# v5 final benchmark.
#  - restarts the vLLM server before EACH workload (clean cache, no cross-workload leak)
#  - records prefix-cache hit rate per (workload, concurrency) from /metrics
#  - reasoning ON only for coding; coding/agent use --benchmark-duration, others --request-count
#  - server: nightly image + mounted vLLM compile cache + reasoning-parser qwen3 (see serve_vllm.sh)
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

MODEL="${SERVED_NAME:-qwen3.6}"
URL="${URL:-http://localhost:8000}"
TOKENIZER="${TOKENIZER:-Qwen/Qwen3.6-35B-A3B-FP8}"
HF_DIR="${HF_DIR:-/home/howard/.cache/huggingface}"
IMG="${AIPERF_IMAGE:-aiperf:local}"
DATA=datasets/aiperf
WARMUP="${WARMUP:-32}"
DURATION="${DURATION:-300}"
GRACE="${GRACE:-300}"
THINKOFF='{"chat_template_kwargs":{"enable_thinking":false}}'

prefix_metrics() {  # echo "hits queries"
  curl -s "${URL}/metrics" 2>/dev/null | awk '
    $1 ~ /^vllm:prefix_cache_hits_total/    {h=$2}
    $1 ~ /^vllm:prefix_cache_queries_total/ {q=$2}
    END{printf "%d %d", (h==""?0:h), (q==""?0:q)}'
}

restart_server() {
  local log=$1
  echo "==== [restart vLLM] $(date +%T) ===="
  REASONING_PARSER=qwen3 GPU_UTIL="${GPU_UTIL:-0.5}" bash scripts/serve_vllm.sh >"$log" 2>&1
  grep -q "READY" "$log" || { echo "   !!! server not ready"; tail -6 "$log"; return 1; }
}

run_point() {  # workload concurrency dtype file  extra-term-args...
  local wl=$1 c=$2 dtype=$3 file=$4; shift 4
  local adir="results/final/$wl/c$c"; mkdir -p "$adir"
  local cname="aiperf-$wl-c$c"; docker rm -f "$cname" >/dev/null 2>&1 || true
  local b a; b=$(prefix_metrics)
  echo "   [aiperf] $wl c=$c $* $(date +%T)"
  local args=(--model "$MODEL" --url "$URL" --endpoint-type chat --streaming
              --tokenizer "$TOKENIZER" --artifact-dir "$adir" --random-seed 42
              --concurrency "$c" --warmup-request-count "$WARMUP" "$@")
  if [ "$wl" = chatbot ]; then args+=(--public-dataset sharegpt --extra-inputs "$THINKOFF")
  elif [ "$wl" = toolagent ]; then args+=(--input-file "$file" --custom-dataset-type "$dtype" --extra-inputs "$THINKOFF")
  else args+=(--input-file "$file" --custom-dataset-type "$dtype"); fi
  docker run --rm --name "$cname" --network host \
    -v "${HF_DIR}:/hf" -e HF_HOME=/hf -e HF_HUB_OFFLINE=1 \
    -v "${ROOT}:/work" -w /work "$IMG" profile "${args[@]}" >"$adir/run.log" 2>&1
  docker rm -f "$cname" >/dev/null 2>&1 || true
  a=$(prefix_metrics)
  awk -v b="$b" -v a="$a" -v wl="$wl" -v c="$c" 'BEGIN{
    split(b,B," "); split(a,A," "); dh=A[1]-B[1]; dq=A[2]-B[2];
    r=(dq>0)?dh/dq*100:0;
    printf "   [prefix-hit] %s c=%s: hits=%d queries=%d rate=%.1f%%\n", wl, c, dh, dq, r;
    printf "{\"hits\":%d,\"queries\":%d,\"hit_rate\":%.4f}\n", dh, dq, (dq>0?dh/dq:0) > "results/final/" wl "/c" c "/prefix.json"
  }'
}

workload() {  # name "levels" dtype file term-args...
  local wl=$1 levels=$2 dtype=$3 file=$4; shift 4
  mkdir -p "results/final/$wl"
  restart_server "results/final/${wl}.serve.log" || return
  for c in $levels; do run_point "$wl" "$c" "$dtype" "$file" "$@"; done
}

SEL="${*:-chatbot rag toolagent agent coding}"
for wl in $SEL; do
  case $wl in
    chatbot)   workload chatbot   "4 8 16 32" public         ""                          --request-count 160 ;;
    rag)       workload rag       "4 8 16 32" single_turn    "$DATA/final_rag.jsonl"      --request-count 160 ;;
    toolagent) workload toolagent "4 8 16"    mooncake_trace "$DATA/final_toolagent.jsonl" --request-count 160 ;;
    agent)     workload agent     "4 8 16"    multi_turn     "$DATA/final_agent.jsonl"    --benchmark-duration "$DURATION" --benchmark-grace-period "$GRACE" ;;
    coding)    workload coding    "4 8 16"    multi_turn     "$DATA/final_coding.jsonl"   --benchmark-duration "$DURATION" --benchmark-grace-period "$GRACE" ;;
  esac
done
echo "================ RUN_FINAL DONE $(date +%T) ================"
