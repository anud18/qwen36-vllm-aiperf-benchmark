# Benchmark results — Qwen/Qwen3.6-35B-A3B-FP8 on vLLM (GB10 / aarch64)

## Setup
- **Hardware**: NVIDIA GB10 (Grace-Blackwell, sm_121), 128 GB unified memory, aarch64.
- **Server**: `vllm/vllm-openai:latest` (vLLM 0.22.1) in Docker. Arch resolved as
  `Qwen3_5MoeForConditionalGeneration` (MoE 256 experts/8 active, hybrid
  linear+full attention, multimodal), FP8 (e4m3), TP=1.
  Flags: `--max-model-len 65536 --gpu-memory-utilization 0.90 --enable-prefix-caching`.
  KV cache ≈ 63.7 GiB → ~3.0M tokens, max concurrency ~46x @ 64k ctx.
- **Client**: NVIDIA `aiperf` 0.10.0 (`aiperf:local` container, `--endpoint-type chat --streaming`).
- **Model note**: Qwen3.6 is a reasoning model (emits chain-of-thought by default).
  For the explicitly *short-output* workloads (coding, RAG) we disable it via
  `chat_template_kwargs.enable_thinking=false`; chatbot/agent/toolagent use the
  default (thinking on).

## Workloads → aiperf format
| Workload | Source | aiperf dataset-type | Shape |
|---|---|---|---|
| Chatbot | ShareGPT (built-in `--public-dataset sharegpt`) | public | balanced multi-turn chat |
| Coding | `Inferact/codex_swebenchpro_traces` | `multi_turn` | long shared prefix, short output (high prefix-cache hit) |
| RAG | `yixuantt/MultiHopRAG` (+corpus) | `single_turn` | long input (retrieved docs), very short answer |
| Agent (multi-turn) | `AI45Research/ATBench-Claw` | `multi_turn` | growing tool-context conversations |
| Agent/tool (trace) | `kvcache-ai/Mooncake` FAST25 `toolagent_trace.jsonl` | `mooncake_trace` | length+hash_id replay, prefix reuse |

## Pass 1 — single operating point
chatbot: conc 16 / 100 req · rag: conc 32 / 300 req · coding & agent: conc 8 (multi_turn, 10 conversations default) · toolagent: conc 32 (timed out, see notes)

| metric | chatbot | coding | rag | agent |
|---|--:|--:|--:|--:|
| ISL avg (tok) | 494 | 13,386 | 6,374 | 1,130 |
| OSL avg (tok) | 233 | 162 | 2.7 | 147 |
| TTFT avg (ms) | 1,042 | 12,587 | 36,280 | 1,066 |
| TTFT p99 (ms) | 4,120 | 27,764 | 50,231 | 2,072 |
| ITL avg (ms) | 80.6 | 130.6 | 264.2 | 53.4 |
| Req latency avg (ms) | 19,704 | 30,923 | 36,756 | 6,187 |
| Output throughput (tok/s) | 174.3 | 38.5 | 2.3 | 86.2 |
| Request throughput (req/s) | 0.75 | 0.24 | 0.83 | 0.59 |

**Reading it**
- **Coding** shows the long-input/short-output profile (ISL 13k, OSL 162); TTFT is
  prefill-dominated (~12.6 s for a 13k-token first turn).
- **RAG** is the extreme prefill-bound case: OSL ≈ 3 tokens (factual answers), so the
  benchmark is essentially TTFT/prefill throughput. TTFT is high here because conc 32
  queues many 6k-token prefills — the concurrency sweep (Pass 2) shows how TTFT scales.
- **Chatbot/agent** are decode-balanced (thinking on), low TTFT, higher tok/s.
- **toolagent** (Pass 1) timed out at conc 32 with 500 reasoning-length requests; re-run
  with bounded counts in the sweep.

## Pass 2 — concurrency sweep (4, 8, 16, 32)
See `python3 scripts/summarize.py --sweep` (filled in after the sweep completes).
Per-workload counts kept modest so even concurrency 4 completes within budget:
chatbot 40 req · rag 80 req · coding 10 conv · agent 12 conv · toolagent 40 req.

## Reproduce
```bash
scripts/serve_vllm.sh                 # start vLLM (waits for /health)
python3 scripts/build_datasets.py     # raw datasets -> datasets/aiperf/*.jsonl
scripts/run_bench.sh <workload> [conc] [req]   # single run
scripts/run_sweep.sh                  # concurrency 4,8,16,32 for all workloads
python3 scripts/summarize.py          # pass-1 table
python3 scripts/summarize.py --sweep  # sweep tables
```
