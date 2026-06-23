# Example — vLLM trace recording

A committed sample of the trace-recording feature (full docs: [`../../docs/TRACING.md`](../../docs/TRACING.md)).
Live traces normally land in the gitignored `traces/` dir; this folder keeps a small, readable
example checked in.

- **`sample_trace.jsonl`** — 5 real records captured by `scripts/trace_proxy.py` (content trace).
- **`sample_vllm_spans.jsonl`** — native vLLM **OTLP** spans (server-internal timing), as written by
  the OTel collector; read with `scripts/otel_span_summary.py`.
- **`sample_openllmetry_spans.jsonl`** — **OpenLLMetry** client spans (content + tokens + tool calls);
  read with `scripts/openllmetry_summary.py`.
- **`sample_langfuse_trace.json`** — one **Langfuse** trace exported from its API (content + usage +
  latency). See [`../../docs/OBSERVABILITY.md`](../../docs/OBSERVABILITY.md) for all four tools.
- **`record_sample.sh`** — reproduces `sample_trace.jsonl` (starts the proxy, sends the requests,
  prints the summary). Needs vLLM serving on `:8000` (record 5 needs `--enable-auto-tool-choice
  --tool-call-parser hermes`).

```bash
examples/trace/record_sample.sh        # run from repo root
```

## What the 5 records show (content trace)

| # | request | mode | what it demonstrates |
|---|---|---|---|
| 1 | `What is 2+2?` (thinking off) | chat, non-streaming | `usage` token counts from the response body |
| 2 | `Name three primary colors.` (thinking off) | chat, streaming | `ttft_ms` + token counts (proxy injects `include_usage`) |
| 3 | `What is 17*23? Think briefly…` (thinking on) | chat, streaming | **`reasoning`** captured separately from `output` |
| 4 | `The capital of France is` | `/v1/completions` | the `{"prompt": "..."}` input form (not `messages`) |
| 5 | `Weather in Tokyo? Use the tool.` | chat + tools | **`tool_calls`** `[{id, name, arguments}]` captured |

## OTLP spans + the join

`sample_vllm_spans.jsonl` is vLLM's own tracing output — token counts plus server-internal
latencies (`time_in_queue`, `time_in_model_prefill`, `time_in_model_decode`, `e2e`) the proxy can't
see. `scripts/otel_span_summary.py examples/trace/sample_vllm_spans.jsonl`:

```
request_id                               in    out  queue_ms   ttft_ms    e2e_ms
chatcmpl-a6242eaa46e8c33c                25      2         0        87       108
chatcmpl-a72fd3cf04d3e3bf                17     40         0        73       844
```

The content record's `response_id` equals the span's `gen_ai.request.id`, so the two files **join**:
content/tokens from the proxy, prefill/decode/queue timing from OTLP. See
[`../../docs/TRACING.md`](../../docs/TRACING.md).

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
