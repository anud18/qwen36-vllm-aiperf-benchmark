#!/usr/bin/env bash
# Reproduce examples/trace/sample_trace.jsonl: start the trace proxy, send a few
# varied requests through it, then print the summary.
# Requires vLLM already serving on :8000 (scripts/serve_vllm.sh).
set -euo pipefail
cd "$(dirname "$0")/../.."          # repo root
LIVE=traces/_sample.jsonl           # proxy writes JSONL here (gitignored)
OUT=examples/trace/sample_trace.json  # pretty-printed committed sample
PORT="${TRACE_PORT:-8001}"
U="http://localhost:${PORT}"

command -v fuser >/dev/null && fuser -k "${PORT}/tcp" 2>/dev/null || true
sleep 1
mkdir -p traces
TRACE_PORT="$PORT" TRACE_FILE="$LIVE" scripts/run_trace_proxy.sh >/tmp/sample_proxy.log 2>&1 &
trap 'command -v fuser >/dev/null && fuser -k "${PORT}/tcp" 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do curl -fsS -m2 "${U}/health" >/dev/null 2>&1 && break; sleep 1; done
: > "$LIVE"

J='Content-Type: application/json'
# 1) non-streaming chat, thinking off
curl -s -m60 "${U}/v1/chat/completions" -H "$J" -d '{"model":"qwen3.6","stream":false,"max_completion_tokens":30,"messages":[{"role":"user","content":"What is 2+2? Answer with just the number."}],"chat_template_kwargs":{"enable_thinking":false}}' >/dev/null
# 2) streaming chat, thinking off
curl -s -N -m60 "${U}/v1/chat/completions" -H "$J" -d '{"model":"qwen3.6","stream":true,"max_completion_tokens":40,"messages":[{"role":"user","content":"Name three primary colors."}],"chat_template_kwargs":{"enable_thinking":false}}' >/dev/null
# 3) streaming chat, thinking ON (reasoning captured separately)
curl -s -N -m90 "${U}/v1/chat/completions" -H "$J" -d '{"model":"qwen3.6","stream":true,"max_completion_tokens":200,"messages":[{"role":"user","content":"What is 17*23? Think briefly, then give the answer."}]}' >/dev/null
# 4) non-chat completions (shows the "prompt" input form)
curl -s -m60 "${U}/v1/completions" -H "$J" -d '{"model":"qwen3.6","stream":false,"max_tokens":20,"prompt":"The capital of France is"}' >/dev/null
# 5) tool call (needs the server started with --enable-auto-tool-choice --tool-call-parser hermes)
curl -s -m60 "${U}/v1/chat/completions" -H "$J" -d '{"model":"qwen3.6","stream":false,"max_completion_tokens":120,"messages":[{"role":"user","content":"What is the weather in Tokyo? Use the get_weather tool."}],"tools":[{"type":"function","function":{"name":"get_weather","description":"Get current weather for a city","parameters":{"type":"object","properties":{"location":{"type":"string"}},"required":["location"]}}}],"tool_choice":"auto","chat_template_kwargs":{"enable_thinking":false}}' >/dev/null || true

sleep 1
# convert the live JSONL to a pretty-printed JSON array (more readable, committed)
python3 -c "import json,sys; recs=[json.loads(l) for l in open('$LIVE') if l.strip()]; json.dump(recs, open('$OUT','w'), indent=2, ensure_ascii=False); open('$OUT','a').write('\n')"
echo ">>> recorded $(python3 -c "import json;print(len(json.load(open('$OUT'))))") records to $OUT"
python3 scripts/trace_summary.py "$OUT"
