#!/usr/bin/env bash
# Re-run rag/coding/agent with NO output cap and thinking ON (uncapped datasets).
# Lets the model generate to natural EOS so we see real output lengths.
# Results -> results/uncapped/<wl>/
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

MODEL="${SERVED_NAME:-qwen3.6}"
URL="${URL:-http://localhost:8000}"
TOKENIZER="${TOKENIZER:-Qwen/Qwen3.6-35B-A3B-FP8}"
HF_DIR="${HF_DIR:-/home/howard/.cache/huggingface}"
IMG="${AIPERF_IMAGE:-aiperf:local}"
DATA=datasets/aiperf
BUDGET="${BUDGET:-900}"

run() {  # wl dtype file sizeflag conc
  local wl=$1 dtype=$2 file=$3 sizeflag=$4 conc=$5
  local adir="results/uncapped/$wl"
  mkdir -p "$adir"
  local cname="aiperf-unc-$wl"
  echo "==== $wl (no cap, thinking ON, conc=$conc, budget=${BUDGET:-none}) $(date +%T) ===="
  docker rm -f "$cname" >/dev/null 2>&1 || true
  # BUDGET=0 (or empty) -> no timeout, run to natural completion
  local TO=(); [ "${BUDGET:-0}" -gt 0 ] 2>/dev/null && TO=(timeout -k 30 "$BUDGET")
  "${TO[@]}" docker run --rm --name "$cname" --network host \
    -v "${HF_DIR}:/hf" -e HF_HOME=/hf -e HF_HUB_OFFLINE=1 \
    -v "${ROOT}:/work" -w /work "$IMG" profile \
    --model "$MODEL" --url "$URL" --endpoint-type chat --streaming \
    --tokenizer "$TOKENIZER" --artifact-dir "$adir" --random-seed 42 \
    --input-file "$DATA/$file" --custom-dataset-type "$dtype" \
    --concurrency "$conc" $sizeflag > "$adir/run.log" 2>&1
  local rc=$?
  docker rm -f "$cname" >/dev/null 2>&1 || true
  [ $rc -eq 124 -o $rc -eq 137 ] && echo "  [$wl] TIMEOUT (partial)"
  grep -E "Benchmark Duration" "$adir/run.log" | tail -1 || true
}

SEL="${*:-rag agent coding}"
case " $SEL " in *" rag "*)    run rag    single_turn rag_singleturn_uncapped.jsonl  "--request-count 24"     8 ;; esac
case " $SEL " in *" agent "*)  run agent  multi_turn  agent_multiturn_uncapped.jsonl "--conversation-num 12"  8 ;; esac
case " $SEL " in *" coding "*) run coding multi_turn  coding_multiturn_uncapped.jsonl "--conversation-num 8"  4 ;; esac
echo "==== UNCAPPED DONE $(date +%T) ===="
