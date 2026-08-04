# Reproducing the optimumxt endpoint benchmarks on spark, against a local vLLM

Every point previously measured against the two `optimumxt` Dynamo endpoints, re-run on **spark
itself** (NVIDIA GB10, aarch64, 119 GB unified memory) with `vllm/vllm-openai:v0.24.0`.
Run 2026-08-04. 26 points total, 13 per model. **All 26 completed with 0 errors and
`osl_mismatch_count = 0`.**

The endpoint data is fixed, so parity was established by making the spark side match it — never
the other way round. See *Achieving prompt parity* for the two corrections that required.

## Result in one line

The Dynamo deployments' **prefill is broken by 30–237×**. Decode is close to local on Llama and
~1.5× slow on Qwen. Concurrency scaling and the c32 wedge are deployment problems too, not GB10
limits.

## Setup

| | |
|---|---|
| hardware | NVIDIA GB10, aarch64, 119 GB unified memory, 1.3 TB free |
| image | `vllm/vllm-openai:v0.24.0` |
| serve script | `scripts/serve_optimumxt_repro.sh` |
| run driver | `scripts/run_optimumxt_repro.sh` |
| max-model-len | **4096**, matching the endpoints' cap |
| prefix caching | enabled |
| mode | `REMOTE=1` — no `/reset_prefix_cache`, no `/metrics` sampling, matching how the endpoint runs were done |

`scripts/serve_nvfp4.sh` was deliberately not reused: it hardcodes `--reasoning-parser qwen3`,
which is wrong for Llama (the Dynamo endpoint returned `reasoning_content: null`) and would alter
the measured output.

### KV cache capacity — the number the endpoints never exposed

| model | GPU KV cache | max concurrency @ 4096 |
|---|--:|--:|
| Llama-3.1-8B (util 0.60) | 426,496 tokens | 104.1× |
| Qwen3-VL-30B-A3B (util 0.88) | 479,504 tokens | 117.1× |

An earlier note in `RESULTS.md` inferred the endpoint's usable prefix cache was "on the order of
ten thousand tokens" from its eviction behaviour. Whatever the endpoint was doing, it was not a
hardware limit — the same box gives ~430–480 k tokens.

## Achieving prompt parity

ISL is the server-reported `prompt_tokens`, so it only matches when the model, the tokenizer *and*
the chat template all match. Two problems had to be fixed before any comparison was meaningful.

**1. A wrong-model comparison.** An initial table put local Llama next to the *Qwen* endpoint and
explained the ISL gap as "tokenizer difference". True but useless — those columns are not
comparable at all. Every comparison in this document is model-matched.

**2. Llama's chat template was missing its system block.** The `NousResearch` mirror ships a
348-character template with no system block; the Dynamo endpoint applied Meta's official one.
Worth **exactly 25 tokens per request** — verified against the endpoint's per-request records,
where all 20 requests were off by exactly 25 and the ISL sum was 11,676 against the endpoint's
12,176.

Fixed with `scripts/chat_templates/llama31_dynamo.jinja`, passed via `--chat-template`. Verified
three ways:

- against the endpoint's per-request records: all 20 diffs = 0, ISL sum 12,176 = 12,176
- against Meta's official template (via the `unsloth` mirror): token-identical across 150 chatbot
  + 150 agent entries, all diffs 0
- against the live server: entry 0 returns `prompt_tokens = 69`, matching the endpoint's 69

Qwen needed no change — its template matched out of the box (`tokenizer_config.json` and
`chat_template.json` are identical, and `enable_thinking` does not affect token counts).

The aiperf client tokenizer was already identical between endpoint and spark runs
(`NousResearch/Meta-Llama-3.1-8B-Instruct`, `Qwen/Qwen3-VL-30B-A3B-Instruct`). It does not affect
ISL anyway — these datasets run with `--use-server-token-count`.

**Result: ISL matches exactly on every model-matched pair below.**

## Local vs endpoint, model-matched

`x` columns are how many times *slower the endpoint* is. `=` marks exact ISL parity.

### Qwen3-VL-30B-A3B

| point | ISL local | ISL endpoint | TTFT local | TTFT endpoint | TTFT ×| ITL local | ITL endpoint | ITL × | dur local | dur endpoint |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| w2 chatbot c1 | 5,937 | = 5,937 | 298 | 9,071 | **30×** | 32.8 | 50.8 | 1.55× | 94 s | 233 s |
| w2 chatbot c2 | 12,040 | = 12,040 | 236 | 14,600 | **62×** | 43.4 | 150.0 | 3.45× | 137 s | 616 s |
| w2 chatbot c1 rep | 5,937 | = 5,937 | 105 | 9,087 | **86×** | 32.8 | 50.1 | 1.53× | 92 s | 232 s |
| w2 agent c1 | 16,864 | = 16,864 | 315 | 17,774 | **56×** | 33.3 | 57.4 | 1.72× | 81 s | 315 s |
| w0 chatbot c1 | 11,698 | = 11,698 | 110 | 8,694 | **79×** | 32.8 | 49.9 | 1.52× | 197 s | 472 s |
| w0 agent c1 | 33,160 | = 33,160 | 185 | 20,618 | **112×** | 33.3 | 57.9 | 1.74× | 162 s | 694 s |
| w0 chatbot c1 rep | 11,698 | = 11,698 | 109 | 8,706 | **80×** | 32.8 | 50.3 | 1.53× | 197 s | 474 s |

### Llama-3.1-8B

| point | ISL local | ISL endpoint | TTFT local | TTFT endpoint | TTFT × | ITL local | ITL endpoint | ITL × | dur local | dur endpoint |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| w0 chatbot c1 | 12,176 | = 12,176 | 79 | 11,444 | **144×** | 72.5 | 68.7 | 0.95× | 433 s | 638 s |
| w0 agent c1 | 33,226 | = 33,226 | 112 | 26,595 | **237×** | 73.2 | 71.8 | 0.98× | 350 s | 877 s |
| w0 chatbot c1 rep | 12,176 | = 12,176 | 79 | 11,196 | **142×** | 72.7 | 67.4 | 0.93× | 434 s | 626 s |
| r100 chatbot c1 | 65,546 | = 65,546 | 96 | 10,971 | **115×** | 72.7 | 67.4 | 0.93× | 1,799 s | 2,758 s |
| r100 chatbot c2 | 65,546 | = 65,546 | 211 | 17,822 | **84×** | 68.6 | 181.7 | 2.65× | 860 s | 3,132 s |

All latencies in ms.

## What this settles

**Prefill on both Dynamo deployments is broken.** 30–237× slower than the same model, same prompts,
same hardware, on stock vLLM. The earlier estimate of ~19–25 tok/s effective prefill was right in
direction and, if anything, understated: local prefills ~600 tokens in 79–110 ms.

**Decode is a different story per model, and an earlier claim here was too broad.** A previous
note said "prefill is broken, decode is normal". That holds for **Llama only** — local ITL is 72.5
vs the endpoint's 68.7 ms, i.e. local is marginally *slower*. For **Qwen the endpoint's decode is
also ~1.5× slow** (50.8 vs 32.8 ms). So: prefill catastrophic on both; decode fine on Llama,
degraded on Qwen.

**GB10 decode speed itself is real and model-dependent.** Locally, Qwen3-VL-30B-A3B decodes at
32.8 ms ITL (30.5 tok/s per user) against Llama-8B's 72.5 ms (13.8 tok/s) — the MoE's ~3B activated
parameters beating a dense 8B, as expected. Neither is a bug.

**Concurrency scaling is positive locally, negative on the endpoint.**

| model | point | c1 duration | c2 duration | speedup |
|---|---|--:|--:|--:|
| Qwen3-VL | r100 chatbot | 829.2 s | 551.8 s | **1.50×** |
| Qwen3-VL | r100 agent | 766.8 s | 508.5 s | **1.51×** |
| Qwen3-VL | w0 agent | 162.2 s | 109.0 s | **1.49×** |
| Llama-3.1-8B | r100 chatbot | 1,799.0 s | 859.8 s | **2.09×** |
| Llama-3.1-8B | r100 agent | 1,642.4 s | 784.4 s | **2.09×** |
| Llama-3.1-8B | w0 agent | 350.3 s | 168.1 s | **2.08×** |

The endpoint got **13.6 % slower** going c1 → c2 on the same workload. Local gets 1.5–2.1× faster.
Llama scales nearly ideally; Qwen's 1.5× is lower because its decode is already fast enough that
the fixed per-step cost dominates sooner.

**The c32 point that wedged the Dynamo worker runs fine locally.** That point left the endpoint
accepting requests and emitting zero tokens for ~25 minutes, and never produced a summary.

| model | requests | duration | req/s | output tok/s | TTFT avg | ITL avg | errors |
|---|--:|--:|--:|--:|--:|--:|--:|
| Llama-3.1-8B | 320 | 226.4 s | 1.4137 | 346.1 | 275 ms | 82.8 ms | 0 |
| Qwen3-VL-30B-A3B | 320 | 513.5 s | 0.6232 | 152.6 | 650 ms | 195.6 ms | 0 |

At concurrency 32 the box sustains 346 output tok/s on Llama — against 9.4 tok/s from the endpoint
at c1. The hardware was never the constraint.

## All points

13 per model, all valid. `dur` in seconds.

| point | reqs | conc. | warmup | Qwen ISL / OSL | Qwen dur | Llama ISL / OSL | Llama dur |
|---|--:|--:|--:|---|--:|---|--:|
| w2 chatbot c1 | 10 | 1 | 2 | 5,937 / 2,790 | 94.3 | 6,199 / 2,790 | 202.7 |
| w2 chatbot c2 | 20 | 2 | 2 | 12,040 / 6,080 | 137.3 | 12,518 / 6,080 | 216.4 |
| w2 chatbot c1 rep | 10 | 1 | 2 | 5,937 / 2,790 | 92.3 | 6,199 / 2,790 | 202.5 |
| w2 agent c1 | 10 | 1 | 2 | 16,864 / 2,344 | 81.2 | 16,967 / 2,344 | 172.3 |
| w0 chatbot c1 | 20 | 1 | 0 | 11,698 / 5,970 | 197.4 | 12,176 / 5,970 | 433.1 |
| w0 agent c1 | 20 | 1 | 0 | 33,160 / 4,766 | 162.2 | 33,226 / 4,766 | 350.3 |
| w0 chatbot c1 rep | 20 | 1 | 0 | 11,698 / 5,970 | 197.3 | 12,176 / 5,970 | 434.1 |
| w0 agent c2 | 20 | 2 | 0 | 33,160 / 4,766 | 109.0 | 33,226 / 4,766 | 168.1 |
| r100 chatbot c1 | 100 | 1 | 0 | 63,251 / 24,723 | 829.2 | 65,546 / 24,723 | 1,799.0 |
| r100 agent c1 | 100 | 1 | 0 | 161,083 / 22,411 | 766.8 | 163,441 / 22,348 | 1,642.4 |
| r100 chatbot c2 | 100 | 2 | 0 | 63,251 / 24,723 | 551.8 | 65,546 / 24,723 | 859.8 |
| r100 agent c2 | 100 | 2 | 0 | 161,083 / 22,411 | 508.5 | 163,441 / 22,348 | 784.4 |
| c32 chatbot | 320 | 32 | 16 | 206,916 / 78,337 | 513.5 | 212,802 / 78,337 | 226.4 |

Qwen and Llama ISL differ from each other by design — different tokenizers over the same text.
Each matches *its own* endpoint exactly, which is what parity requires.

The `r100` agent rows also differ in composition: context filtering is tokenizer-dependent, so
`filter_le4096.py` keeps 279/384 entries under Llama and 277/384 under Qwen. The two models'
`r100 agent` points are therefore not identical workloads to each other, though each matches its
own endpoint counterpart where one exists.

## Known gap

`REMOTE=1` was chosen so the workloads match the endpoint runs, which could not reset the prefix
cache or read `/metrics`. The cost is that **prefix cache hit rates are missing from these local
runs** — vLLM's OpenAI API returns `prompt_tokens_details: null`, so aiperf has no per-request
cache figure, and `REMOTE=1` stops the runner reading vLLM's `vllm:prefix_cache_*` counters.
`prefix.json` is `{"unavailable": true}` on all 26 points.

Re-running with `REMOTE=0 RESTART_PER_WL=0` would collect them and reset the cache per point — but
that is a different workload from the endpoint runs and the numbers would not be comparable.

## Reproduce

```bash
cd ~/benchmark

# Llama-3.1-8B
MODEL_KEY=llama31 bash scripts/serve_optimumxt_repro.sh
MODEL_KEY=llama31 bash scripts/run_optimumxt_repro.sh

# Qwen3-VL-30B-A3B -- regenerate the filtered datasets for its tokenizer first
docker run --rm --entrypoint python -v $PWD:/w -w /w \
  -v $HOME/.cache/huggingface:/root/.cache/huggingface aiperf:local \
  scripts/filter_le4096.py --tokenizer Qwen/Qwen3-VL-30B-A3B-Instruct \
  --out datasets/aiperf/le4096_qwen3vl
MODEL_KEY=qwen3vl bash scripts/serve_optimumxt_repro.sh
MODEL_KEY=qwen3vl bash scripts/run_optimumxt_repro.sh
```

Weights: `NousResearch/Meta-Llama-3.1-8B-Instruct` (15 GB; the official `meta-llama` repo is gated)
and `Qwen/Qwen3-VL-30B-A3B-Instruct` (58 GB).

Artifacts: `results/nvfp4/spark_repro_{llama31,qwen3vl}/`, logs
`results/nvfp4/spark_repro_{llama31,qwen3vl}.log`.
Endpoint-side data and its caveats: `results/nvfp4/INDEX_optimumxt.md`.
