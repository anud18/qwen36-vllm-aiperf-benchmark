# Qwen3.6-35B-A3B-FP8 vLLM benchmark (GB10 / aarch64)

Serve Qwen/Qwen3.6-35B-A3B-FP8 on vLLM in Docker, benchmark with NVIDIA aiperf.

Workloads: chatbot (ShareGPT), coding (codex_swebenchpro_traces), RAG (MultiHopRAG), agent (ATBench-Claw), toolagent (Mooncake trace).

Docs:

- **DATASETS.md** — original dataset sources + measured input/output/turn characteristics per workload
- **FORMAT.md** (中文版: **FORMAT.zh-TW.md**) — exactly how each dataset is converted and sent to the LLM
- **RUNBOOK.md** — v6 server/client config and run methodology
- **RESULTS.md** — benchmark numbers
- `slides/` — architecture & workloads slide deck
