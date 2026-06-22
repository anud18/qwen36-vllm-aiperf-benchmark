#!/usr/bin/env python3
"""OpenLLMetry (Traceloop) demo: instrument the OpenAI client calling vLLM.

Unlike the proxy (network hop) or vLLM's server spans (timing, no content),
OpenLLMetry instruments the *client* and captures BOTH prompt/completion
**content** and token usage as OTel spans — exported here to the same OTel
collector (traces/vllm_spans.jsonl). If trace context propagates over the wire,
the client span and vLLM's server span share one trace.

Run (collector on :4317, vLLM on :8000):
  .venv-openllmetry/bin/python scripts/openllmetry_client.py
"""
import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
from openai import OpenAI

os.environ.setdefault("TRACELOOP_TRACE_CONTENT", "true")  # capture prompt/completion text
ENDPOINT = os.environ.get("OTLP_ENDPOINT", "localhost:4317")
BASE = os.environ.get("VLLM_BASE", "http://localhost:8000/v1")

provider = TracerProvider(resource=Resource.create({"service.name": "openllmetry-client"}))
provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint=ENDPOINT, insecure=True)))
trace.set_tracer_provider(provider)
OpenAIInstrumentor().instrument(tracer_provider=provider)

client = OpenAI(base_url=BASE, api_key="dummy")
THINK_OFF = {"chat_template_kwargs": {"enable_thinking": False}}

# 1) non-streaming chat
r = client.chat.completions.create(
    model="qwen3.6", max_completion_tokens=40,
    messages=[{"role": "user", "content": "Name three primary colors."}],
    extra_body=THINK_OFF)
print("non-stream:", r.choices[0].message.content[:60], "| usage:", r.usage.total_tokens)

# 2) streaming chat
stream = client.chat.completions.create(
    model="qwen3.6", max_completion_tokens=50, stream=True,
    messages=[{"role": "user", "content": "In one sentence, what is vLLM?"}],
    extra_body=THINK_OFF)
buf = "".join(c.choices[0].delta.content or "" for c in stream if c.choices)
print("stream    :", buf[:60])

# 3) tool call
r = client.chat.completions.create(
    model="qwen3.6", max_completion_tokens=120,
    messages=[{"role": "user", "content": "What is the weather in Tokyo? Use the tool."}],
    tools=[{"type": "function", "function": {"name": "get_weather",
            "parameters": {"type": "object", "properties": {"location": {"type": "string"}}}}}],
    tool_choice="auto", extra_body=THINK_OFF)
tc = r.choices[0].message.tool_calls
print("tool      :", tc[0].function.name, tc[0].function.arguments if tc else None)

provider.shutdown()  # flush spans to the collector
print(">>> spans exported to", ENDPOINT)
