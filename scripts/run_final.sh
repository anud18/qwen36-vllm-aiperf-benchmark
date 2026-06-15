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

run_point() {  # workload concurrency dtype file tlimit  extra-term-args...
  local wl=$1 c=$2 dtype=$3 file=$4 tlim=$5; shift 5
  local adir="results/final/$wl/c$c"; mkdir -p "$adir"
  # resume: skip a point that already has a non-empty summary
  if [ -s "$adir/profile_export_aiperf.json" ]; then
    echo "   [skip] $wl c=$c already complete"; return 0
  fi
  local cname="aiperf-$wl-c$c"
  local attempt rc tries="${MAX_TRIES:-3}"
  for attempt in $(seq 1 "$tries"); do
    docker rm -f "$cname" >/dev/null 2>&1 || true
    rm -f "$adir/profile_export_aiperf.json"
    local b a; b=$(prefix_metrics)
    echo "   [aiperf] $wl c=$c (try $attempt, tlimit=${tlim}s) $* $(date +%T)"
    local args=(--model "$MODEL" --url "$URL" --endpoint-type chat --streaming
                --tokenizer "$TOKENIZER" --artifact-dir "$adir" --random-seed 42
                --concurrency "$c" --warmup-request-count "$WARMUP" "$@")
    if [ "$wl" = chatbot ]; then args+=(--public-dataset sharegpt --extra-inputs "$THINKOFF")
    elif [ "$wl" = toolagent ]; then args+=(--input-file "$file" --custom-dataset-type "$dtype" --extra-inputs "$THINKOFF")
    else args+=(--input-file "$file" --custom-dataset-type "$dtype"); fi
    # Launch aiperf in the background and actively watchdog the engine. The
    # intermittent vLLM V1 EngineCore deadlock pins requests with BOTH prompt and
    # generation throughput at 0 while running>0, and the streaming client then
    # blocks forever. Detect no-token-movement for WEDGE_S and kill in ~2 min
    # instead of waiting out the full tlimit (which stays as a hard backstop).
    docker run --rm --name "$cname" --network host \
      -v "${HF_DIR}:/hf" -e HF_HOME=/hf -e HF_HUB_OFFLINE=1 \
      -v "${ROOT}:/work" -w /work "$IMG" profile "${args[@]}" >"$adir/run.log" 2>&1 &
    local dpid=$! start=$SECONDS frozen=0 lastg="" lastp="" wedged=0 g p r
    while kill -0 "$dpid" 2>/dev/null; do
      sleep 15
      read g p r < <(curl -s -m3 "${URL}/metrics" 2>/dev/null | awk '
        /^vllm:generation_tokens_total/{g=$2} /^vllm:prompt_tokens_total/{p=$2} /^vllm:num_requests_running/{r=$2}
        END{printf "%s %s %s", g+0, p+0, r+0}')
      if awk "BEGIN{exit !(${r:-0}>0)}" && [ "$g" = "$lastg" ] && [ "$p" = "$lastp" ]; then
        frozen=$((frozen+15)); else frozen=0; fi
      lastg="$g"; lastp="$p"
      if [ "$frozen" -ge "${WEDGE_S:-120}" ]; then
        echo "   !!! wedge: running=$r, no prompt/gen movement ${frozen}s — killing $(date +%T)"; wedged=1; break; fi
      if [ $((SECONDS-start)) -ge "$tlim" ]; then
        echo "   !!! hard tlimit ${tlim}s exceeded — killing $(date +%T)"; wedged=1; break; fi
    done
    if [ "$wedged" = 1 ]; then
      docker rm -f "$cname" >/dev/null 2>&1 || true
      kill -9 "$dpid" 2>/dev/null || true; wait "$dpid" 2>/dev/null; rc=137
    else
      wait "$dpid"; rc=$?
    fi
    docker rm -f "$cname" >/dev/null 2>&1 || true
    if [ -s "$adir/profile_export_aiperf.json" ]; then
      a=$(prefix_metrics)
      awk -v b="$b" -v a="$a" -v wl="$wl" -v c="$c" 'BEGIN{
        split(b,B," "); split(a,A," "); dh=A[1]-B[1]; dq=A[2]-B[2];
        r=(dq>0)?dh/dq*100:0;
        printf "   [prefix-hit] %s c=%s: hits=%d queries=%d rate=%.1f%%\n", wl, c, dh, dq, r;
        printf "{\"hits\":%d,\"queries\":%d,\"hit_rate\":%.4f}\n", dh, dq, (dq>0?dh/dq:0) > "results/final/" wl "/c" c "/prefix.json"
      }'
      return 0
    fi
    echo "   !!! $wl c=$c FAILED (rc=$rc${rc:+ }$([ "$rc" = 137 ] && echo '=timeout/KILL'), no summary) — likely engine wedge"
    # the wedged engine is dead for all future points; always restart before continuing
    restart_server "results/final/${wl}.serve.log" || { echo "   !!! restart failed; abandoning $wl c=$c"; return 1; }
  done
  echo "   !!! $wl c=$c failed $tries times; recording failure, moving on"
  echo '{"failed":true,"hits":0,"queries":0,"hit_rate":0}' > "$adir/prefix.json"
  return 1
}

workload() {  # name "levels" dtype file tlimit term-args...
  local wl=$1 levels=$2 dtype=$3 file=$4 tlim=$5; shift 5
  mkdir -p "results/final/$wl"
  restart_server "results/final/${wl}.serve.log" || return
  for c in $levels; do run_point "$wl" "$c" "$dtype" "$file" "$tlim" "$@"; done
}

RC_TLIM="${RC_TLIM:-1200}"                 # hard cap for --request-count points
DUR_TLIM=$((DURATION + GRACE + 600))       # hard cap for --benchmark-duration points
SEL="${*:-chatbot rag toolagent agent coding}"
for wl in $SEL; do
  case $wl in
    chatbot)   workload chatbot   "4 8 16 32" public         ""                          "$RC_TLIM"  --request-count 160 ;;
    rag)       workload rag       "4 8 16 32" single_turn    "$DATA/final_rag.jsonl"      "$RC_TLIM"  --request-count 160 ;;
    toolagent) workload toolagent "4 8 16"    mooncake_trace "$DATA/final_toolagent.jsonl" "$RC_TLIM" --request-count 160 ;;
    agent)     workload agent     "4 8 16"    multi_turn     "$DATA/final_agent.jsonl"    "$DUR_TLIM" --benchmark-duration "$DURATION" --benchmark-grace-period "$GRACE" ;;
    coding)    workload coding    "4 8 16"    multi_turn     "$DATA/final_coding.jsonl"   "$DUR_TLIM" --benchmark-duration "$DURATION" --benchmark-grace-period "$GRACE" ;;
  esac
done
echo "================ RUN_FINAL DONE $(date +%T) ================"
