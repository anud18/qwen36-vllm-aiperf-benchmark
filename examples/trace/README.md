# Example — LiteLLM trace recording

A committed sample of the LiteLLM trace/cost logging (full docs:
[`../../docs/OBSERVABILITY.md`](../../docs/OBSERVABILITY.md)). Live traces land in the gitignored
`traces/` dir as **JSONL** (one object per line); the file here is the same data **pretty-printed as
JSON** for readability.

- **`sample_litellm_trace.json`** — 2 real records from `scripts/litellm_client.py`: a plain chat
  turn and a tool call. Each carries input/output content, token counts, **`cost_usd`**, and latency.
- **`record_litellm_sample.sh`** — regenerates the sample (runs the client, pretty-prints the JSONL).
  Needs vLLM serving on `:8000` (`scripts/serve_vllm.sh`) with tools enabled for record 2
  (`--enable-auto-tool-choice --tool-call-parser hermes`).

```bash
examples/trace/record_litellm_sample.sh        # run from repo root
```

## What the 2 records show

| # | request | what it demonstrates |
|---|---|---|
| 1 | `Name three primary colors.` | `usage` token counts + LiteLLM `cost_usd` for a plain chat turn |
| 2 | `Weather in Tokyo? Use the tool.` | `tool_calls` `[{name, arguments}]` captured; `output` is `null` |

Each record is `{ts, model, input, output, tool_calls, prompt_tokens, completion_tokens,
total_tokens, cost_usd, latency_ms}` — see the field table in
[`../../docs/OBSERVABILITY.md`](../../docs/OBSERVABILITY.md). Record 2's `output` is `null` because
the model answered with a tool call instead of text; the call is preserved in `tool_calls`.
