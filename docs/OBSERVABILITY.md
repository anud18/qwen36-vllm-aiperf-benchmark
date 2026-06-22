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

## 4. Langfuse — self-hosted UI + API

[Langfuse](https://langfuse.com) is an LLM-observability **platform**: it stores traces with full
content, token usage, latency, and cost in a searchable UI, plus evals/datasets. Self-hosted here
(Postgres + ClickHouse + Redis + MinIO + web/worker) under `monitoring/langfuse/`.

```bash
cp monitoring/langfuse/.env.example monitoring/langfuse/.env   # fill in keys / secrets
cd monitoring/langfuse && docker compose up -d && cd ../..      # UI at http://localhost:3001
# instrument vLLM calls with Langfuse's OpenAI wrapper and send traces:
set -a; . monitoring/langfuse/.env; set +a
LANGFUSE_HOST=http://localhost:3001 \
  LANGFUSE_PUBLIC_KEY=$LANGFUSE_INIT_PROJECT_PUBLIC_KEY \
  LANGFUSE_SECRET_KEY=$LANGFUSE_INIT_PROJECT_SECRET_KEY \
  .venv-langfuse/bin/python scripts/langfuse_client.py
```

- Web UI on **:3001** (Grafana keeps :3000; MinIO console remapped to 127.0.0.1:9190 to avoid
  Prometheus :9090). The project + API keys are bootstrapped headlessly via `LANGFUSE_INIT_*` in
  `.env` (no manual signup); the real `.env` is gitignored, `.env.example` is the template.
- `scripts/langfuse_client.py` uses the drop-in wrapper `from langfuse.openai import openai`, so
  each call becomes a Langfuse **generation** with input/output content, model, token usage, latency.

Verified via the public API (`GET /api/public/traces`):

```
trace primary-colors  →  GENERATION  model=qwen3.6
  input : [{"role":"user","content":"Name three primary colors."}]
  output: {"role":"assistant","content":"The three primary colors …"}
  usage : input=17 output=40 total=57   latency=0.868s
```

Tool calls are captured too (the `weather-tool` trace records the `get_weather` call). Langfuse can
also ingest **OTLP** directly (point an OpenLLMetry/OTel exporter at
`http://localhost:3001/api/public/otel/v1/traces` with basic auth) if you prefer instrumentation
over the SDK wrapper.

> Heaviest option (6 containers) but the only one with a real UI, search, evals, and cost tracking.

## When to use which

- **Debugging / content capture / dataset capture** → proxy (any client) or OpenLLMetry (Python client).
- **Authoritative perf timing** → vLLM OTLP (zero hop, server-internal).
- **Both content + timing, correlated** → OpenLLMetry (it joins to the vLLM span).
- **A searchable UI, evals, cost tracking** → Langfuse (below).
