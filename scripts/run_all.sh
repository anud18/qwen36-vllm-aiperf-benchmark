#!/usr/bin/env bash
# Run all five workloads sequentially, each with a time budget. Logs to results/<wl>.run.log
set -uo pipefail
cd "$(dirname "$0")/.."
BUDGET="${BUDGET:-420}"   # seconds per workload

run() {  # name conc req
  local wl=$1 conc=$2 req=${3:-}
  echo "================ $wl (conc=$conc req=$req) $(date +%T) ================"
  timeout "$BUDGET" bash scripts/run_bench.sh "$wl" "$conc" "$req" > "results/${wl}.run.log" 2>&1
  local rc=$?
  if [ $rc -eq 124 ]; then echo "[$wl] TIMEOUT after ${BUDGET}s (partial)"; fi
  grep -E "Benchmark Duration|CSV Export" "results/${wl}.run.log" | tail -2 || true
}

run chatbot   16 100
run rag        32 300
run coding      8 80
run agent       8 120
run toolagent  32 500
echo "================ ALL DONE $(date +%T) ================"
