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
Regenerate with `python3 scripts/summarize.py --sweep`. Counts kept modest so even
concurrency 4 finishes within budget: chatbot 40 req · rag 80 req · coding 10 conv ·
agent 12 conv · toolagent 40 req (output capped 128).

**chatbot** (ShareGPT, thinking on)
| metric | c4 | c8 | c16 | c32 |
|---|--:|--:|--:|--:|
| ISL (tok) | 486 | 439 | 192 | 73 |
| OSL (tok) | 262 | 261 | 244 | 241 |
| TTFT (ms) | 242 | 358 | 880 | 1,080 |
| ITL (ms) | 34.7 | 54.0 | 72.4 | 98.6 |
| Out tok/s | 109 | 132 | 162 | **195** |
| Req/s | 0.42 | 0.51 | 0.67 | 0.81 |

**coding** (codex traces, multi-turn, thinking off — high prefix-cache)
| metric | c4 | c8 | c16 | c32 |
|---|--:|--:|--:|--:|
| ISL (tok) | 25,883 | 25,938 | 25,857 | 25,857 |
| OSL (tok) | 177 | 202 | 188 | 165 |
| TTFT (ms) | 2,899 | 2,542 | 2,920 | 3,382 |
| ITL (ms) | 73.4 | 106.3 | 154.7 | 157.6 |
| Out tok/s | 44.2 | 56.2 | 52.8 | 49.8 |
| Req/s | 0.25 | 0.28 | 0.28 | 0.30 |

→ ISL ≈ 26k (50 KB shared preamble accumulated across turns) but TTFT stays ~3 s
instead of the ~25 s a cold 26k-token prefill costs — **prefix caching is doing its job.**

**rag** (MultiHopRAG, single-turn, thinking off — long input, ~3-token answers)
| metric | c4 | c8 | c16 | c32 |
|---|--:|--:|--:|--:|
| ISL (tok) | 6,958 | 6,958 | 6,958 | 6,958 |
| OSL (tok) | 2.7 | 2.6 | 2.5 | 3.4 |
| TTFT (ms) | 5,128 | 820 | 1,453 | 3,155 |
| Req/s | 0.68 | **5.87** | 6.50 | 6.25 |

→ Prefill-bound (OSL≈3); throughput is best read as req/s. c4 is cold-cache; c8+ pipeline
the 7k-token prefills and req/s jumps ~9x.

**agent** (ATBench-Claw, multi-turn, thinking on)
| metric | c4 | c8 | c16 | c32 |
|---|--:|--:|--:|--:|
| ISL (tok) | 2,390 | 2,390 | 2,388 | 2,390 |
| OSL (tok) | 197 | 197 | 196 | 197 |
| TTFT (ms) | 506 | 673 | 1,027 | 1,063 |
| ITL (ms) | 36.4 | 52.1 | 74.1 | 71.3 |
| Out tok/s | 101 | 124 | 144 | **147** |
| Req/s | 0.52 | 0.63 | 0.73 | 0.75 |

**toolagent** (Mooncake FAST25 trace, length+hash_id replay, thinking on)
| metric | c4 | c8 | c16 | c32 |
|---|--:|--:|--:|--:|
| ISL (tok) | 9,920 | 9,920 | 9,920 | 9,920 |
| OSL (tok) | 79 | 79 | 79 | 79 |
| TTFT (ms) | 4,445 | 657 | 1,300 | 2,986 |
| ITL (ms) | 93.7 | 78.8 | 121.4 | 208.7 |
| Out tok/s | 27.7 | 100.7 | 122.5 | **152** |
| Req/s | 0.35 | 1.27 | 1.54 | 1.91 |

→ Mooncake traces carry per-request `timestamp`s, which makes aiperf auto-select
**fixed-schedule** mode (concurrency ignored, all 2000 entries replayed). To run a real
concurrency sweep we strip timestamps and cap output (`datasets/aiperf/toolagent_concurrency.jsonl`).
Use the original `toolagent_mooncake.jsonl` with `--fixed-schedule` for trace-faithful replay.

### Cross-workload takeaways
- **Decode-bound** workloads (chatbot, agent, toolagent): aggregate tok/s scales with
  concurrency (chatbot 109→195, agent 101→147, toolagent 28→152). Per-user ITL grows
  ~35→100 ms — single-stream decode on GB10 for this 35B-A3B MoE is ~10-30 tok/s/user.
- **Prefill-bound** workloads (rag, coding): latency dominated by input. Prefix caching
  keeps coding's 26k-token context cheap; RAG throughput is best measured in req/s.
- **c4 cold-cache artifact**: the first level of rag/toolagent shows inflated TTFT before
  the prefix cache warms; c8+ is representative.

> Operational note: a prior fixed-schedule toolagent run left ~2000 in-flight requests on
> the server (vLLM keeps generating after the client disconnects), saturating the GPU and
> stalling later runs. Restarting the server cleared it. The sweep script now uses
> `timeout -k` (SIGKILL) and bounded request counts to avoid this.

## Reproduce
```bash
scripts/serve_vllm.sh                 # start vLLM (waits for /health)
python3 scripts/build_datasets.py     # raw datasets -> datasets/aiperf/*.jsonl
scripts/run_bench.sh <workload> [conc] [req]   # single run
scripts/run_sweep.sh                  # concurrency 4,8,16,32 for all workloads
python3 scripts/summarize.py          # pass-1 table
python3 scripts/summarize.py --sweep  # sweep tables
```

## Pass 3 — uncapped output + thinking ON (real generation lengths)

To check whether the tiny OSL in Pass 1/2 was an artifact of capping, we re-ran with
**no `output_length` cap and thinking left ON** (`build_datasets.py --uncapped` → only a
`text` field; no `max_completion_tokens`, no `enable_thinking:false`). Model generates to
natural EOS. Runs use no time budget (`BUDGET=0`). Datasets are small here because the
generations are huge: rag 24 req · agent 12 conv (53 turns) · coding 8 conv (32 turns).

Reference answer lengths in the raw data (Qwen3.6 tokenizer): **RAG answers are genuinely
tiny** — median **1** token, mean 2.0, 53% are yes/no. Agent assistant turns median 57 / mean
112 tokens. So the short capped OSL was faithful; the model is simply terse when thinking is off.

Comparison at matching concurrency (capped = Pass-2 sweep; uncapped = thinking on, no cap):

| workload (conc) | mode | OSL avg | OSL max | ISL | TTFT ms | ITL ms | ReqLat ms | out tok/s |
|---|---|--:|--:|--:|--:|--:|--:|--:|
| RAG (c8)    | capped   | 3   | 34     | 6,958  | 820   | 225  | 1,112   | 15  |
| RAG (c8)    | **uncapped** | **1,263** | 2,991  | 6,718  | 3,663 | 63 | **81,619** | 114 |
| Agent (c8)  | capped   | 197 | 512    | 2,390  | 673   | 52   | 10,399  | 124 |
| Agent (c8)  | **uncapped** | **1,995** | 9,588  | 5,831  | 648   | 50 | **98,657** | 117 |
| Coding (c4) | capped   | 177 | 512    | 25,883 | 2,899 | 73   | 14,549  | 44  |
| Coding (c4) | **uncapped** | **7,163** | **50,911** | 28,312 | 3,490 | 43 | **314,881** | 85 |

**Findings**
- Removing the cap + enabling thinking blows up output length ~400× for RAG (3→1,263),
  10× for agent (197→1,995), 40× for coding (177→7,163, with a single turn hitting **50,911**
  tokens). The whole coding run took **42 min**; per-request latency averaged **315 s**.
- **ITL is unchanged** (~50–65 ms/token) — per-token decode speed is the same; what explodes is
  the *number* of tokens (the reasoning trace), so end-to-end latency scales with OSL.
- The ISL that aiperf *reports* grows on later turns (agent 2,390→5,831; coding 25,883→28,312)
  because aiperf tokenizes the history it assembled, which includes the model's reasoning.
  **But this is an aiperf measurement artifact, not real prefill growth**: Qwen3.6's chat
  template strips each historical assistant turn's `<think>…</think>` block before prefill
  (verified: 666 reasoning tokens in history add +0 to vLLM's `prompt_tokens`). Since the
  uncapped turns finish naturally (they contain `</think>`), the model does NOT re-attend to
  prior reasoning — only the final answer carries forward. Reasoning leaks into history only
  if a turn is truncated mid-thinking by `max_tokens` (no `</think>` to split on), or if served
  without the chat template's reasoning handling / a `--reasoning-parser`.
- Confirms the Pass-1/2 short OSL was **not** a capping artifact for RAG — the dataset answers
  really are 1–2 tokens; thinking-on just prepends a long chain-of-thought before that answer.

Reproduce: `python3 scripts/build_datasets.py --uncapped --only rag coding agent …` then
`BUDGET=0 scripts/run_uncapped.sh`. Results in `results/uncapped/<wl>/`.
