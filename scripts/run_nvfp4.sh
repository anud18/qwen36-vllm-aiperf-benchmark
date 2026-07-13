#!/usr/bin/env bash
# NVFP4 cross-hardware sweep driver. Runs ON the machine being measured
# (aiperf client co-located with the server, per methodology decision).
#
#   NODE=spark bash scripts/run_nvfp4.sh [workloads...]      # default: all 5
#
# Per workload: restart the vLLM server, then run every point in POINTS
# (c<N> = closed-loop concurrency, r<R> = open-loop poisson request-rate).
# Before EVERY point: POST /reset_prefix_cache (cold prefix cache per point).
# Reasoning/thinking is OFF for all workloads (chatbot/toolagent/coding via
# --extra-inputs; rag/agent carry it in-data). OSL capped at 2048 in nvfp4_*.jsonl.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

NODE="${NODE:?set NODE=spark|5090}"
MODEL="${SERVED_NAME:-qwen3.6-nvfp4}"
URL="${URL:-http://localhost:8000}"
TOKENIZER="${TOKENIZER:-nvidia/Qwen3.6-35B-A3B-NVFP4}"
HF_DIR="${HF_DIR:-$HOME/.cache/huggingface}"
IMG="${AIPERF_IMAGE:-aiperf:local}"
DATA="${DATA_DIR:-datasets/aiperf}"
REQS="${REQS:-96}"
WARMUP="${WARMUP:-16}"
WARMUP_CODING="${WARMUP_CODING:-8}"
POINTS="${POINTS:-c2 c4 c8 c16 c32 r0.8 r1.0 r1.2}"
RC_TLIM="${RC_TLIM:-2700}"       # hard cap, concurrency points
RATE_TLIM="${RATE_TLIM:-3600}"   # hard cap, rate points (saturation drain can be long)
WEDGE_S="${WEDGE_S:-120}"
THINKOFF='{"chat_template_kwargs":{"enable_thinking":false}}'
OUTBASE="${OUTBASE:-results/nvfp4/$NODE}"
RESTART_PER_WL="${RESTART_PER_WL:-1}"   # 0 = reuse running server (smoke)
VLLM_CNAME="${VLLM_CNAME:-vllm-nvfp4}"  # server container name (prefix on shared boxes)
CPREFIX="${CPREFIX:-aiperf}"            # aiperf client container-name prefix

prefix_metrics() {  # echo "hits queries"
  curl -s "${URL}/metrics" 2>/dev/null | awk '
    $1 ~ /^vllm:prefix_cache_hits_total/    {h=$2}
    $1 ~ /^vllm:prefix_cache_queries_total/ {q=$2}
    END{printf "%d %d", (h==""?0:h), (q==""?0:q)}'
}

reset_kv() {  # returns http code of POST /reset_prefix_cache
  curl -s -m 30 -X POST -o /dev/null -w '%{http_code}' "${URL}/reset_prefix_cache" 2>/dev/null
}

restart_server() {
  local log=$1
  echo "==== [restart vLLM] $(date +%T) ===="
  NODE="$NODE" bash scripts/serve_nvfp4.sh >"$log" 2>&1
  grep -q "READY" "$log" || { echo "   !!! server not ready"; tail -8 "$log"; return 1; }
  docker inspect "$VLLM_CNAME" --format '{{json .Config.Cmd}}' > "$OUTBASE/server_cmd.json" 2>/dev/null || true
}

run_point() {  # workload point dtype file  extra-args...
  local wl=$1 pt=$2 dtype=$3 file=$4; shift 4
  local adir="$OUTBASE/$wl/$pt"; mkdir -p "$adir"
  if [ -s "$adir/profile_export_aiperf.json" ]; then
    echo "   [skip] $wl $pt already complete"; return 0
  fi

  local loadargs=() tlim tries
  case "$pt" in
    c*) loadargs=(--concurrency "${pt#c}"); tlim=$RC_TLIM; tries="${MAX_TRIES:-3}" ;;
    r*) loadargs=(--request-rate "${pt#r}" --arrival-pattern poisson); tlim=$RATE_TLIM; tries="${MAX_TRIES:-2}" ;;
    fixed) loadargs=(--fixed-schedule); tlim=$RATE_TLIM; tries="${MAX_TRIES:-2}" ;;  # replay trace timestamps; all entries
    *) echo "   !!! bad point $pt"; return 1 ;;
  esac
  local wu="$WARMUP"; [ "$wl" = coding ] && wu="$WARMUP_CODING"

  local cname="${CPREFIX}-$wl-$pt" attempt rc
  for attempt in $(seq 1 "$tries"); do
    docker rm -f "$cname" >/dev/null 2>&1 || true
    rm -f "$adir/profile_export_aiperf.json"

    # cold prefix cache for every point
    local rkc; rkc=$(reset_kv)
    [ "$rkc" = 200 ] || echo "   !!! reset_prefix_cache HTTP $rkc (continuing)"

    local b a t0 t1; b=$(prefix_metrics); t0=$(date +%s)
    echo "   [aiperf] $wl $pt (try $attempt, warmup=$wu, reqs=$REQS, tlimit=${tlim}s) $(date +%T)"
    local args=(--model "$MODEL" --url "$URL" --endpoint-type chat --streaming
                --tokenizer "$TOKENIZER" --artifact-dir "$adir" --random-seed 42)
    if [ "$pt" = fixed ]; then
      # fixed-schedule: replay ALL entries at trace timing; no request-count/warmup
      args+=("${loadargs[@]}")
    else
      args+=(--request-count "$REQS" --warmup-request-count "$wu" "${loadargs[@]}")
    fi
    if [ "$wl" = chatbot ]; then args+=(--public-dataset sharegpt --extra-inputs "$THINKOFF")
    elif [ "$wl" = toolagent ]; then args+=(--input-file "$file" --custom-dataset-type "$dtype" --extra-inputs "$THINKOFF")
    elif [ "$wl" = coding ]; then args+=(--input-file "$file" --custom-dataset-type "$dtype" --extra-inputs "$THINKOFF")
    elif [ "$wl" = chatbot_flat ] || [ "$wl" = agent_flat ] || [ "$wl" = coding_flat ]; then
      # text-mode flat traces (`messages` entries): aiperf can't tokenize raw
      # messages client-side, so ISL comes from server usage (entries carry
      # stream_options.include_usage; thinking-off is in-data too)
      args+=(--input-file "$file" --custom-dataset-type "$dtype" --use-server-token-count)
    else args+=(--input-file "$file" --custom-dataset-type "$dtype"); fi

    # background aiperf + wedge watchdog (engine deadlock: running>0 but no token movement)
    docker run --rm --name "$cname" --network host \
      -v "${HF_DIR}:/hf" -e HF_HOME=/hf \
      -e AIPERF_DATASET_CONFIGURATION_TIMEOUT="${AIPERF_DS_TIMEOUT:-900}" \
      -e AIPERF_SERVICE_PROFILE_CONFIGURE_TIMEOUT="${AIPERF_DS_TIMEOUT:-900}" \
      -v "${ROOT}:/work" -w /work "$IMG" profile "${args[@]}" >"$adir/run.log" 2>&1 &
    local dpid=$! start=$SECONDS frozen=0 lastg="" lastp="" wedged=0 timedout=0 g p r
    while kill -0 "$dpid" 2>/dev/null; do
      sleep 15
      read g p r < <(curl -s -m3 "${URL}/metrics" 2>/dev/null | awk '
        /^vllm:generation_tokens_total/{g=$2} /^vllm:prompt_tokens_total/{p=$2} /^vllm:num_requests_running/{r=$2}
        END{printf "%s %s %s", g+0, p+0, r+0}')
      if awk "BEGIN{exit !(${r:-0}>0)}" && [ "$g" = "$lastg" ] && [ "$p" = "$lastp" ]; then
        frozen=$((frozen+15)); else frozen=0; fi
      lastg="$g"; lastp="$p"
      if [ "$frozen" -ge "$WEDGE_S" ]; then
        echo "   !!! wedge: running=$r, no token movement ${frozen}s — killing $(date +%T)"; wedged=1; break; fi
      if [ $((SECONDS-start)) -ge "$tlim" ]; then
        echo "   !!! hard tlimit ${tlim}s exceeded — killing $(date +%T)"; timedout=1; break; fi
    done
    if [ "$wedged" = 1 ] || [ "$timedout" = 1 ]; then
      docker rm -f "$cname" >/dev/null 2>&1 || true
      kill -9 "$dpid" 2>/dev/null || true; wait "$dpid" 2>/dev/null; rc=137
    else
      wait "$dpid"; rc=$?
    fi
    docker rm -f "$cname" >/dev/null 2>&1 || true
    t1=$(date +%s)

    if [ -s "$adir/profile_export_aiperf.json" ]; then
      a=$(prefix_metrics)
      awk -v b="$b" -v a="$a" -v wl="$wl" -v pt="$pt" -v out="$adir/prefix.json" 'BEGIN{
        split(b,B," "); split(a,A," "); dh=A[1]-B[1]; dq=A[2]-B[2];
        printf "   [prefix-hit] %s %s: hits=%d queries=%d rate=%.1f%%\n", wl, pt, dh, dq, (dq>0?dh/dq*100:0);
        printf "{\"hits\":%d,\"queries\":%d,\"hit_rate\":%.4f}\n", dh, dq, (dq>0?dh/dq:0) > out
      }'
      printf '{"node":"%s","wl":"%s","point":"%s","start":%d,"end":%d,"reqs":%s,"warmup":%s,"try":%d}\n' \
        "$NODE" "$wl" "$pt" "$t0" "$t1" "$REQS" "$wu" "$attempt" > "$adir/meta.json"
      return 0
    fi

    echo "   !!! $wl $pt FAILED (rc=$rc, wedged=$wedged, timedout=$timedout, no summary)"
    if [ "$timedout" = 1 ] && [ "$wedged" = 0 ]; then
      # deterministic overload (point slower than tlimit) — retrying won't change it.
      # Still restart: killing the client leaves the server queue full of in-flight
      # requests that would contaminate the next point.
      echo "   !!! tlimit overload — recording failure, not retrying"
      restart_server "$OUTBASE/${wl}.serve.log" || echo "   !!! restart after overload failed"
      break
    fi
    # engine wedge or client crash: server state is suspect; restart before retry
    restart_server "$OUTBASE/${wl}.serve.log" || { echo "   !!! restart failed; abandoning $wl $pt"; return 1; }
  done
  echo '{"failed":true,"hits":0,"queries":0,"hit_rate":0}' > "$adir/prefix.json"
  printf '{"node":"%s","wl":"%s","point":"%s","failed":true}\n' "$NODE" "$wl" "$pt" > "$adir/meta.json"
  return 1
}

workload() {  # name dtype file
  local wl=$1 dtype=$2 file=$3
  mkdir -p "$OUTBASE/$wl"
  if [ "$RESTART_PER_WL" = 1 ]; then
    restart_server "$OUTBASE/${wl}.serve.log" || { echo "!!! serve failed for $wl — skipping"; return 1; }
  fi
  for pt in $POINTS; do run_point "$wl" "$pt" "$dtype" "$file"; done
}

echo "================ RUN_NVFP4 node=$NODE start $(date '+%F %T') ================"
mkdir -p "$OUTBASE"
SEL="${*:-chatbot rag toolagent agent coding}"
for wl in $SEL; do
  case $wl in
    chatbot)   workload chatbot   public         "" ;;
    rag)       workload rag       single_turn    "$DATA/nvfp4_rag.jsonl" ;;
    toolagent) workload toolagent mooncake_trace "$DATA/final_toolagent.jsonl" ;;
    toolagent_ts) workload toolagent_ts mooncake_trace "$DATA/nvfp4_toolagent_ts.jsonl" ;;
    agent)     workload agent     multi_turn     "$DATA/nvfp4_agent.jsonl" ;;
    coding)    workload coding    multi_turn     "$DATA/nvfp4_coding.jsonl" ;;
    # flattened multi-turn -> mooncake_trace: machine-independent ISL (see build_flat_traces.py)
    chatbot_flat) workload chatbot_flat mooncake_trace "$DATA/nvfp4_chatbot_flat.jsonl" ;;
    agent_flat)   workload agent_flat   mooncake_trace "$DATA/nvfp4_agent_flat.jsonl" ;;
    coding_flat)  workload coding_flat  mooncake_trace "$DATA/nvfp4_coding_flat.jsonl" ;;
    *) echo "!!! unknown workload $wl" ;;
  esac
done
if [ "${STOP_AFTER:-1}" = 1 ]; then
  echo ">>> stopping vLLM server"; docker rm -f "$VLLM_CNAME" >/dev/null 2>&1 || true
fi
echo "================ RUN_NVFP4 node=$NODE DONE $(date '+%F %T') ================"
