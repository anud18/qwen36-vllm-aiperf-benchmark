#!/usr/bin/env python3
"""LiteLLM demo: call vLLM through the LiteLLM SDK with a logging callback.

LiteLLM is a gateway/SDK with a unified API across providers; its distinguishing
feature for observability is built-in **cost** computation and pluggable logging
callbacks. Here a CustomLogger records each call (input/output content, tool
calls, tokens, cost, latency) as one JSON line per request. vLLM's qwen3.6 isn't
in LiteLLM's price map, so we register a price so response_cost is non-zero.

Env: TRACE_FILE (default traces/litellm_trace.jsonl), VLLM_BASE (default
http://localhost:8000/v1). See docs/OBSERVABILITY.md.

Run: .venv-litellm/bin/python scripts/litellm_client.py
"""
import os, json, datetime
import litellm
from litellm.integrations.custom_logger import CustomLogger

TRACE_FILE = os.environ.get("TRACE_FILE", "traces/litellm_trace.jsonl")
BASE = os.environ.get("VLLM_BASE", "http://localhost:8000/v1")
os.makedirs(os.path.dirname(TRACE_FILE) or ".", exist_ok=True)
open(TRACE_FILE, "w").close()

# register a price for the local model so LiteLLM computes a cost ($/token, demo values)
litellm.register_model({"qwen3.6": {
    "input_cost_per_token": 0.10e-6, "output_cost_per_token": 0.40e-6,
    "litellm_provider": "openai", "mode": "chat"}})


class Recorder(CustomLogger):
    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        usage = getattr(response_obj, "usage", None)
        msg = response_obj["choices"][0]["message"]
        tcs = msg.get("tool_calls") or []
        rec = {
            "ts": start_time.astimezone(datetime.timezone.utc).isoformat(),
            "model": kwargs.get("model"),
            "input": kwargs.get("messages"),
            "output": msg.get("content"),
            "tool_calls": [{"name": t["function"]["name"], "arguments": t["function"]["arguments"]}
                           for t in tcs] or None,
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
            "cost_usd": kwargs.get("response_cost"),
            "latency_ms": round((end_time - start_time).total_seconds() * 1000, 1),
        }
        with open(TRACE_FILE, "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


litellm.callbacks = [Recorder()]
common = dict(api_base=BASE, api_key="dummy",
              extra_body={"chat_template_kwargs": {"enable_thinking": False}})

r = litellm.completion(model="openai/qwen3.6", max_tokens=40,
                       messages=[{"role": "user", "content": "Name three primary colors."}], **common)
print("chat:", r.choices[0].message.content[:55], "| cost $", r._hidden_params.get("response_cost"))

r = litellm.completion(model="openai/qwen3.6", max_tokens=120,
                       messages=[{"role": "user", "content": "Weather in Tokyo? Use the tool."}],
                       tools=[{"type": "function", "function": {"name": "get_weather",
                               "parameters": {"type": "object", "properties": {"location": {"type": "string"}}}}}],
                       tool_choice="auto", **common)
tc = r.choices[0].message.tool_calls
print("tool:", tc[0].function.name if tc else None, "| cost $", r._hidden_params.get("response_cost"))
print(">>> recorded to", TRACE_FILE)
