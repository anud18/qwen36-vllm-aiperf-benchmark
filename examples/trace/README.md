# Example — vLLM trace recording

A committed sample of the trace-recording feature (full docs: [`../../docs/TRACING.md`](../../docs/TRACING.md)).
Live traces normally land in the gitignored `traces/` dir; this folder keeps a small, readable
example checked in.

- **`sample_trace.jsonl`** — 4 real records captured by `scripts/trace_proxy.py` against the live
  vLLM server, one JSON object per request.
- **`record_sample.sh`** — reproduces `sample_trace.jsonl` (starts the proxy, sends the 4 requests,
  prints the summary). Needs vLLM serving on `:8000`.

```bash
examples/trace/record_sample.sh        # run from repo root
```

## What the 4 records show

| # | request | mode | what it demonstrates |
|---|---|---|---|
| 1 | `What is 2+2?` (thinking off) | chat, non-streaming | `usage` token counts from the response body |
| 2 | `Name three primary colors.` (thinking off) | chat, streaming | `ttft_ms` + token counts (proxy injects `include_usage`) |
| 3 | `What is 17*23? Think briefly…` (thinking on) | chat, streaming | **`reasoning`** captured separately from `output` |
| 4 | `The capital of France is` | `/v1/completions` | the `{"prompt": "..."}` input form (not `messages`) |

`scripts/trace_summary.py examples/trace/sample_trace.jsonl`:

```
ts                              in    out  ttft_ms    lat_ms  input -> output
--------------------------------------------------------------------------------------------------
2026-...T19:16:46.266110        25      2        -       360  What is 2+2? Answer with just the … -> 4
2026-...T19:16:46.637151        17     40       84       842  Name three primary colors. -> The three primary colors …
2026-...T19:16:47.484111        27    200       97      3954  What is 17*23? Think briefly, then… ->            (all 200 tokens went to reasoning)
2026-...T19:16:51.443722         5     20        -       830  The capital of France is -> a city with an ancient history …
--------------------------------------------------------------------------------------------------
requests=4  input_tokens=74  output_tokens=262  total_tokens=336
```

Each record carries: `ts`/`ts_epoch`, `endpoint`, `model`, `streamed`, `input` (full content),
`output` (full content), `reasoning`, `prompt_tokens`/`completion_tokens`/`total_tokens`,
`ttft_ms`, `latency_ms`, `status`. Record 3's `output` is empty because the model spent all 200
tokens in the reasoning phase — the chain-of-thought is preserved in `reasoning`.
