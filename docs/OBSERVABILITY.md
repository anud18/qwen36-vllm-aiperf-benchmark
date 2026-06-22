# LLM observability options for the vLLM benchmark

Four ways to capture what the model is doing, from black-box to fully instrumented. They are
complementary; pick by what you need (content vs timing, client vs server, file vs UI).

| approach | captures content? | captures timing | where | extra hop | backend |
|---|---|---|---|---|---|
| **Proxy** (`scripts/trace_proxy.py`) | ✅ full in/out/reasoning/tool_calls | client-side TTFT/latency | between client & vLLM | yes (+1 hop) | JSONL file |
| **vLLM OTLP** (`--otlp-traces-endpoint`) | ❌ tokens only | ✅ server-internal (queue/prefill/decode/e2e) | inside vLLM | no | OTel collector → file |
| **OpenLLMetry** (`scripts/openllmetry_client.py`) | ✅ in/out messages + tool_calls | client span; **joins** vLLM server span | OpenAI client | no | OTLP → collector / Langfuse |
| **Langfuse** | ✅ (via OpenLLMetry/SDK) | ✅ (spans) | client + ingest | no | self-hosted UI |

All four are documented here; the proxy has its own deep-dive in [`TRACING.md`](TRACING.md).

## 1. Proxy — content, any client

Transparent logging proxy; records every request to JSONL. Best for capturing real traffic
(incl. content) with no code changes. See [`TRACING.md`](TRACING.md). Caveat: adds a network hop,
so don't use it for headline latency numbers.

## 2. vLLM native OTLP — server-internal timing

vLLM's own OpenTelemetry spans (`gen_ai.*`): token counts + `time_in_queue`,
`time_in_model_prefill`, `time_in_model_decode`, `e2e` — no content, no extra hop. Enable with
`--otlp-traces-endpoint grpc://host.docker.internal:4317` and the OTel collector in `monitoring/`.
Read with `scripts/otel_span_summary.py`. See the "Native vLLM OTLP tracing" section of
[`TRACING.md`](TRACING.md).

## 3. OpenLLMetry — client instrumentation (content + timing in one trace)

[OpenLLMetry](https://github.com/traceloop/openllmetry) (Traceloop) instruments the OpenAI client.
It captures prompt/completion **content**, tokens, and tool calls as OTel spans — and because it
propagates W3C trace context, **its client span and vLLM's server span land in the same trace**, so
you get content (client) + prefill/decode/e2e timing (server) joined automatically.

```bash
# collector + vLLM-with-OTLP already running (see TRACING.md)
python3 -m venv .venv-openllmetry && .venv-openllmetry/bin/pip install -q \
  openai opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc opentelemetry-instrumentation-openai
.venv-openllmetry/bin/python scripts/openllmetry_client.py     # sends instrumented calls to vLLM
python3 scripts/openllmetry_summary.py traces/vllm_spans.jsonl # content + tokens (+ join id)
```

What it records (newer gen_ai semconv): `gen_ai.input.messages` / `gen_ai.output.messages` (full
content), `gen_ai.usage.input_tokens` / `output_tokens`, `gen_ai.response.id` (== vLLM
`gen_ai.request.id`, the join key), tool calls, finish reasons.

Verified — one trace, both spans:

```
traceId 6a837b41776b563c..
  CLIENT (OpenLLMetry): "Name three primary colors."   out_tok=40        ← content
  SERVER (vLLM)       : prefill 71 ms  decode 773 ms  e2e 849 ms          ← server timing
```

> Note: this build uses `opentelemetry-instrumentation-openai` ≥ the new gen_ai conventions, so
> content is in `gen_ai.input.messages` / `output.messages` (not the older `gen_ai.prompt.N.content`).

## When to use which

- **Debugging / content capture / dataset capture** → proxy (any client) or OpenLLMetry (Python client).
- **Authoritative perf timing** → vLLM OTLP (zero hop, server-internal).
- **Both content + timing, correlated** → OpenLLMetry (it joins to the vLLM span).
- **A searchable UI, evals, cost tracking** → Langfuse (below).
