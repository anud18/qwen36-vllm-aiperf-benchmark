#!/usr/bin/env bash
# Reproduce examples/trace/sample_litellm_trace.json: call vLLM through LiteLLM
# with the logging callback, then pretty-print the JSONL to the committed sample.
# Requires vLLM already serving on :8000 (scripts/serve_vllm.sh); record 2 needs
# the server started with --enable-auto-tool-choice --tool-call-parser hermes.
set -euo pipefail
cd "$(dirname "$0")/../.."            # repo root
LIVE=traces/litellm_trace.jsonl      # client writes JSONL here (gitignored)
OUT=examples/trace/sample_litellm_trace.json  # pretty-printed committed sample
VENV=.venv-litellm

[ -x "$VENV/bin/python" ] || { python3 -m venv "$VENV"; "$VENV/bin/pip" install -q litellm; }
mkdir -p traces
TRACE_FILE="$LIVE" "$VENV/bin/python" scripts/litellm_client.py

# convert the live JSONL to a pretty-printed JSON array (committed, more readable)
python3 -c "import json; recs=[json.loads(l) for l in open('$LIVE') if l.strip()]; json.dump(recs, open('$OUT','w'), indent=2, ensure_ascii=False); open('$OUT','a').write('\n')"
echo ">>> recorded $(python3 -c "import json;print(len(json.load(open('$OUT'))))") records to $OUT"
