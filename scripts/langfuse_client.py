#!/usr/bin/env python3
"""Langfuse demo: trace vLLM calls into a self-hosted Langfuse (UI + API).

Uses Langfuse's drop-in OpenAI wrapper (`from langfuse.openai import openai`),
which records each call as a Langfuse generation with input/output content,
token usage, model, and latency — viewable at the Langfuse UI and queryable via
its API. Reads LANGFUSE_HOST / LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY from env
(see monitoring/langfuse/.env).

Run:
  set -a; . monitoring/langfuse/.env; set +a
  LANGFUSE_HOST=http://localhost:3001 \
  LANGFUSE_PUBLIC_KEY=$LANGFUSE_INIT_PROJECT_PUBLIC_KEY \
  LANGFUSE_SECRET_KEY=$LANGFUSE_INIT_PROJECT_SECRET_KEY \
  .venv-langfuse/bin/python scripts/langfuse_client.py
"""
import os
from langfuse.openai import openai          # instrumented OpenAI client
from langfuse import get_client

BASE = os.environ.get("VLLM_BASE", "http://localhost:8000/v1")
client = openai.OpenAI(base_url=BASE, api_key="dummy")
THINK_OFF = {"chat_template_kwargs": {"enable_thinking": False}}

r = client.chat.completions.create(
    model="qwen3.6", max_completion_tokens=40,
    messages=[{"role": "user", "content": "Name three primary colors."}],
    extra_body=THINK_OFF, name="primary-colors")
print("chat   :", r.choices[0].message.content[:60], "| usage:", r.usage.total_tokens)

r = client.chat.completions.create(
    model="qwen3.6", max_completion_tokens=120,
    messages=[{"role": "user", "content": "What is the weather in Tokyo? Use the tool."}],
    tools=[{"type": "function", "function": {"name": "get_weather",
            "parameters": {"type": "object", "properties": {"location": {"type": "string"}}}}}],
    tool_choice="auto", extra_body=THINK_OFF, name="weather-tool")
tc = r.choices[0].message.tool_calls
print("tool   :", tc[0].function.name, tc[0].function.arguments if tc else None)

get_client().flush()   # push traces to Langfuse before exit
print(">>> flushed traces to Langfuse")
