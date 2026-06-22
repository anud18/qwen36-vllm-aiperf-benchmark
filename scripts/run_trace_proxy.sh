#!/usr/bin/env bash
# Start the vLLM trace-logging proxy (scripts/trace_proxy.py).
#  - sits in front of the vLLM OpenAI server and records every chat/completions
#    call (input + output content, token counts, timestamps) to a JSONL file.
#  - point your client at the proxy port instead of vLLM.
#
# Usage:
#   scripts/run_trace_proxy.sh                 # :8001 -> localhost:8000, traces/vllm_trace.jsonl
#   TRACE_PORT=8001 VLLM_UPSTREAM=http://localhost:8000 \
#     TRACE_FILE=traces/run1.jsonl scripts/run_trace_proxy.sh
set -euo pipefail
cd "$(dirname "$0")/.."

VENV="${TRACE_VENV:-.venv-trace}"
if [ ! -x "$VENV/bin/python" ]; then
  echo ">>> creating $VENV and installing aiohttp"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --upgrade pip aiohttp
fi

export VLLM_UPSTREAM="${VLLM_UPSTREAM:-http://localhost:8000}"
export TRACE_PORT="${TRACE_PORT:-8001}"
export TRACE_FILE="${TRACE_FILE:-traces/vllm_trace.jsonl}"
exec "$VENV/bin/python" scripts/trace_proxy.py
