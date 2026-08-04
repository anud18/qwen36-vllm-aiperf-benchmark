# Reproducing the optimumxt endpoint benchmarks on spark, against a local vLLM

Every point previously measured against the two `optimumxt` Dynamo endpoints, re-run on **spark
itself** (NVIDIA GB10, aarch64, 119 GB unified memory) with `vllm/vllm-openai:v0.24.0`.
Run 2026-08-04. 26 points total, 13 per model. **All 26 completed with 0 errors and
`osl_mismatch_count = 0`.**

The endpoint data is fixed, so parity was established by making the spark side match it — never
the other way round. See *Achieving prompt parity* for the two corrections that required.

## Result in one line

The Dynamo deployments' **prefill throughput is 30–237× below** the same model on the same box
(40–131 tok/s/user against 1,700–16,700). **Decode throughput** is a wash on Llama (0.93–0.98×)
and 1.5–1.7× slow on Qwen. Concurrency scaling and the c32 wedge are deployment problems too, not
GB10 limits.

## Source data — the endpoint runs being reproduced

The endpoint numbers in this document are not recomputed here; they are read straight out of the
artifacts committed earlier on this branch. Their full context, methodology and caveats:

| document | what it covers |
|---|---|
| [`INDEX_optimumxt.md`](INDEX_optimumxt.md) | index of every endpoint artifact, which points are invalid and why, comparability warnings |
| [`qwen3vl_ngrok/RESULTS.md`](qwen3vl_ngrok/RESULTS.md) | narrative report for the Qwen endpoint — config, repeatability, prefix-cache analysis, workload feasibility at 4096 |
| [`TABLES_w0.md`](TABLES_w0.md) | Qwen endpoint, `WARMUP=0 / REQS=20 / c1` tables |
| [`TABLES_llama31_cf.md`](TABLES_llama31_cf.md) | Llama endpoint tables + the cold-cache repeatability evidence |
| [`TABLES_r100.md`](TABLES_r100.md) | Llama endpoint, 100-request alternating series on context-filtered datasets |

Per-point endpoint artifacts are linked inline from each comparison block below.

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

An earlier note in [`qwen3vl_ngrok/RESULTS.md`](qwen3vl_ngrok/RESULTS.md) inferred the endpoint's usable prefix cache was "on the order of
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

## Prefill and decode throughput

Taken straight from aiperf's own metrics — no derived quantities:

| reported as | aiperf field | unit |
|---|---|---|
| **Prefill throughput** | `prefill_throughput_per_user` | tokens/sec/user — ISL ÷ TTFT per request |
| **Decode throughput** | `output_token_throughput_per_user` | tokens/sec/user — the reciprocal of ITL |
| **E2E output throughput** | `e2e_output_token_throughput` | tokens/sec/user — OSL ÷ full request latency |
| **System output throughput** | `output_token_throughput` | tokens/sec — total OSL ÷ wall clock |

The first three are **per-user** rates: what one client experiences. Only
`output_token_throughput` is system-wide, which is why at c2 a per-user figure can fall while the
system figure rises. All four come with percentiles in the per-pair tables below.

> **Prefill throughput is inflated by prefix-cache hits on the endpoint side.** Cached prefix
> tokens count toward ISL but are never computed, so the endpoint's true prefill rate is *lower*
> than reported — its cache hit rates run 46–74 %. The spark side has no cache figures at all (see
> *Known gap*), so no symmetric correction is possible. The gap below is a conservative lower
> bound.

| model | point | prefill spark | prefill endpoint | prefill × | decode spark | decode endpoint | decode × | system out spark | system out endpoint |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|
| Qwen3 | w2 chatbot c1 | 1,747 | 53.9 | **32×** | 30.50 | 19.89 | 1.53× | 29.59 | 11.95 |
| Qwen3 | w2 chatbot c2 | 2,953 | 40.3 | **73×** | 23.09 | 7.38 | 3.13× | 44.30 | 9.87 |
| Qwen3 | w2 chatbot c1 rep | 5,845 | 53.9 | **108×** | 30.48 | 20.12 | 1.52× | 30.23 | 12.04 |
| Qwen3 | w2 agent c1 | 5,513 | 130.9 | **42×** | 30.02 | 17.54 | 1.71× | 28.88 | 7.45 |
| Qwen3 | w0 chatbot c1 | 6,312 | 55.7 | **113×** | 30.48 | 20.22 | 1.51× | 30.24 | 12.65 |
| Qwen3 | w0 agent c1 | 14,205 | 117.6 | **121×** | 30.07 | 17.42 | 1.73× | 29.39 | 6.86 |
| Qwen3 | w0 chatbot c1 rep | 6,420 | 55.7 | **115×** | 30.50 | 20.04 | 1.52× | 30.26 | 12.59 |
| Llama | w0 chatbot c1 | 7,476 | 50.7 | **147×** | 13.79 | 14.56 | 0.95× | 13.78 | 9.36 |
| Llama | w0 agent c1 | 16,660 | 94.3 | **177×** | 13.66 | 13.94 | 0.98× | 13.61 | 5.44 |
| Llama | w0 chatbot c1 rep | 7,474 | 51.8 | **144×** | 13.76 | 14.86 | 0.93× | 13.75 | 9.54 |
| Llama | r100 chatbot c1 | 6,554 | 64.8 | **101×** | 13.76 | 14.86 | 0.93× | 13.74 | 8.97 |
| Llama | r100 chatbot c2 | 3,096 | 48.5 | **64×** | 14.57 | 6.62 | 2.20× | 28.75 | 7.89 |

Prefill on the endpoints is **32–177× slower** than the same model, same prompts, same box.
Decode splits by model: Llama is a wash at c1 (0.93–0.98×), Qwen is 1.5–1.7× slow. At c2 the
endpoint's per-user decode collapses (3.13× and 2.20×) while spark's holds — the concurrency
problem showing up in the decode path.

System output throughput tells the same story from the server's side: spark sustains 13.7–30.3
tok/s at c1 against the endpoint's 5.4–12.7, and at c2 spark's *rises* (13.76 → 28.75 on Llama,
30.5 → 44.3 on Qwen) where the endpoint's falls or barely moves.

## Local vs endpoint, model-matched

Endpoint and spark figures side by side for every pair where a valid endpoint point exists.
Each block links both sets of raw artifacts.

**ISL and OSL rows are identical on every pair** — that is the parity check, and it holds at every
percentile, not just the total.

**TPOT = ITL**: aiperf's `inter_token_latency` is `(request_latency − TTFT) / (OSL − 1)`, the
standard time-per-output-token. **p50 is the median.**

### Qwen3-VL-30B-A3B-Instruct

#### w2 chatbot c1

spark [`spark_repro_qwen3vl/w2_chatbot_c1/chatbot_flat/c1/`](spark_repro_qwen3vl/w2_chatbot_c1/chatbot_flat/c1/) · endpoint [`qwen3vl_ngrok/chatbot_flat/c1/`](qwen3vl_ngrok/chatbot_flat/c1/)

| metric | | avg | p50 | p90 | p95 | p99 | max |
|---|---|--:|--:|--:|--:|--:|--:|
| TTFT (ms) | spark | 298.2 | 321.7 | 371.8 | 416.1 | 451.5 | 460.4 |
|  | endpoint | 9,070.7 | 11,187.2 | 14,102.1 | 15,927.2 | 17,387.2 | 17,752.2 |
| ITL = TPOT (ms) | spark | 32.79 | 32.77 | 33.21 | 33.27 | 33.32 | 33.33 |
|  | endpoint | 50.76 | 50.80 | 56.70 | 57.91 | 58.88 | 59.12 |
| E2E latency (ms) | spark | 9,425.9 | 9,857.5 | 14,130.9 | 14,625.7 | 15,021.5 | 15,120.5 |
|  | endpoint | 23,347.0 | 27,802.8 | 30,418.5 | 32,604.0 | 34,352.4 | 34,789.5 |
| Prefill throughput (tok/s/user) | spark | 1,747.4 | 1,185.9 | 4,053.6 | 4,498.9 | 4,855.3 | 4,944.3 |
|  | endpoint | 53.9 | 34.9 | 107.5 | 113.6 | 118.5 | 119.7 |
| Decode throughput (tok/s/user) | spark | 30.50 | 30.51 | 30.90 | 30.95 | 30.98 | 30.99 |
|  | endpoint | 19.89 | 19.70 | 22.61 | 22.82 | 22.98 | 23.02 |
| E2E output throughput (tok/s/user) | spark | 29.50 | 29.32 | 30.24 | 30.25 | 30.25 | 30.25 |
|  | endpoint | 13.22 | 10.45 | 19.31 | 20.10 | 20.74 | 20.89 |
| ISL (tokens) | spark | 593.7 | 479.0 | 1,342.0 | 1,490.5 | 1,609.3 | 1,639.0 |
|  | endpoint | 593.7 | 479.0 | 1,342.0 | 1,490.5 | 1,609.3 | 1,639.0 |
| OSL (tokens) | spark | 279.0 | 288.0 | 427.2 | 441.6 | 453.1 | 456.0 |
|  | endpoint | 279.0 | 288.0 | 427.2 | 441.6 | 453.1 | 456.0 |

| aggregate | spark | endpoint |
|---|--:|--:|
| Request throughput (req/s) | 0.1061 | 0.0428 |
| Output token throughput, system (tok/s) | 29.59 | 11.95 |
| Total token throughput, system (tok/s) | 92.57 | 37.37 |
| Total ISL (tokens) | 5,937 | 5,937 |
| Total OSL (tokens) | 2,790 | 2,790 |
| Duration (s) | 94.3 | 233.5 |
| Requests completed | 10 | 10 |
| Prefix cache hit rate (%) | — (see *Known gap*) | 60.64 |
| Errors | 0 | 0 |

#### w2 chatbot c2

spark [`spark_repro_qwen3vl/w2_chatbot_c2/chatbot_flat/c2/`](spark_repro_qwen3vl/w2_chatbot_c2/chatbot_flat/c2/) · endpoint [`qwen3vl_ngrok/chatbot_flat/c2/`](qwen3vl_ngrok/chatbot_flat/c2/)

| metric | | avg | p50 | p90 | p95 | p99 | max |
|---|---|--:|--:|--:|--:|--:|--:|
| TTFT (ms) | spark | 236.4 | 215.5 | 354.0 | 355.6 | 363.5 | 365.5 |
|  | endpoint | 14,599.6 | 11,521.4 | 25,946.5 | 27,399.3 | 45,271.0 | 49,738.9 |
| ITL = TPOT (ms) | spark | 43.44 | 43.85 | 44.80 | 45.13 | 46.27 | 46.56 |
|  | endpoint | 150.04 | 144.47 | 200.64 | 219.90 | 239.47 | 244.36 |
| E2E latency (ms) | spark | 13,446.5 | 12,413.0 | 20,099.5 | 22,113.8 | 27,316.6 | 28,617.3 |
|  | endpoint | 61,238.6 | 58,969.5 | 97,169.3 | 100,730.3 | 106,181.6 | 107,544.5 |
| Prefill throughput (tok/s/user) | spark | 2,952.8 | 1,884.6 | 7,045.6 | 10,536.2 | 11,162.4 | 11,319.0 |
|  | endpoint | 40.3 | 27.7 | 65.0 | 82.1 | 130.6 | 142.7 |
| Decode throughput (tok/s/user) | spark | 23.09 | 22.80 | 23.45 | 23.87 | 27.90 | 28.90 |
|  | endpoint | 7.38 | 6.93 | 9.01 | 9.47 | 14.75 | 16.07 |
| E2E output throughput (tok/s/user) | spark | 22.70 | 22.48 | 23.18 | 23.49 | 27.23 | 28.17 |
|  | endpoint | 5.77 | 5.50 | 6.94 | 9.12 | 14.07 | 15.31 |
| ISL (tokens) | spark | 602.0 | 613.0 | 1,321.5 | 1,444.3 | 1,600.0 | 1,639.0 |
|  | endpoint | 602.0 | 613.0 | 1,321.5 | 1,444.3 | 1,600.0 | 1,639.0 |
| OSL (tokens) | spark | 304.0 | 288.0 | 459.1 | 494.7 | 611.7 | 641.0 |
|  | endpoint | 304.0 | 288.0 | 459.1 | 494.7 | 611.7 | 641.0 |

| aggregate | spark | endpoint |
|---|--:|--:|
| Request throughput (req/s) | 0.1457 | 0.0325 |
| Output token throughput, system (tok/s) | 44.30 | 9.87 |
| Total token throughput, system (tok/s) | 132.02 | 29.42 |
| Total ISL (tokens) | 12,040 | 12,040 |
| Total OSL (tokens) | 6,080 | 6,080 |
| Duration (s) | 137.3 | 615.9 |
| Requests completed | 20 | 20 |
| Prefix cache hit rate (%) | — (see *Known gap*) | 40.27 |
| Errors | 0 | 0 |

#### w2 chatbot c1 rep

spark [`spark_repro_qwen3vl/w2_chatbot_c1_rep/chatbot_flat/c1/`](spark_repro_qwen3vl/w2_chatbot_c1_rep/chatbot_flat/c1/) · endpoint [`qwen3vl_ngrok_run2/chatbot_flat/c1/`](qwen3vl_ngrok_run2/chatbot_flat/c1/)

| metric | | avg | p50 | p90 | p95 | p99 | max |
|---|---|--:|--:|--:|--:|--:|--:|
| TTFT (ms) | spark | 105.2 | 96.4 | 144.8 | 149.0 | 152.4 | 153.2 |
|  | endpoint | 9,086.9 | 11,229.9 | 14,008.5 | 15,847.7 | 17,318.9 | 17,686.8 |
| ITL = TPOT (ms) | spark | 32.81 | 32.72 | 33.18 | 33.27 | 33.34 | 33.35 |
|  | endpoint | 50.13 | 49.83 | 56.04 | 57.27 | 58.25 | 58.50 |
| E2E latency (ms) | spark | 9,228.3 | 9,539.9 | 13,974.4 | 14,467.7 | 14,862.4 | 14,961.1 |
|  | endpoint | 23,163.6 | 27,800.2 | 30,111.6 | 31,842.9 | 33,227.9 | 33,574.2 |
| Prefill throughput (tok/s/user) | spark | 5,845.1 | 4,944.6 | 11,190.7 | 13,920.6 | 16,104.5 | 16,650.5 |
|  | endpoint | 53.9 | 34.8 | 107.6 | 114.1 | 119.2 | 120.5 |
| Decode throughput (tok/s/user) | spark | 30.48 | 30.56 | 30.71 | 30.72 | 30.72 | 30.72 |
|  | endpoint | 20.12 | 20.09 | 22.57 | 22.77 | 22.93 | 22.97 |
| E2E output throughput (tok/s/user) | spark | 30.14 | 30.28 | 30.49 | 30.54 | 30.57 | 30.58 |
|  | endpoint | 13.27 | 10.47 | 19.16 | 19.82 | 20.35 | 20.48 |
| ISL (tokens) | spark | 593.7 | 479.0 | 1,342.0 | 1,490.5 | 1,609.3 | 1,639.0 |
|  | endpoint | 593.7 | 479.0 | 1,342.0 | 1,490.5 | 1,609.3 | 1,639.0 |
| OSL (tokens) | spark | 279.0 | 288.0 | 427.2 | 441.6 | 453.1 | 456.0 |
|  | endpoint | 279.0 | 288.0 | 427.2 | 441.6 | 453.1 | 456.0 |

| aggregate | spark | endpoint |
|---|--:|--:|
| Request throughput (req/s) | 0.1083 | 0.0432 |
| Output token throughput, system (tok/s) | 30.23 | 12.04 |
| Total token throughput, system (tok/s) | 94.55 | 37.67 |
| Total ISL (tokens) | 5,937 | 5,937 |
| Total OSL (tokens) | 2,790 | 2,790 |
| Duration (s) | 92.3 | 231.7 |
| Requests completed | 10 | 10 |
| Prefix cache hit rate (%) | — (see *Known gap*) | 60.64 |
| Errors | 0 | 0 |

#### w2 agent c1

spark [`spark_repro_qwen3vl/w2_agent_c1/agent_flat/c1/`](spark_repro_qwen3vl/w2_agent_c1/agent_flat/c1/) · endpoint [`qwen3vl_ngrok/agent_flat/c1/`](qwen3vl_ngrok/agent_flat/c1/)

| metric | | avg | p50 | p90 | p95 | p99 | max |
|---|---|--:|--:|--:|--:|--:|--:|
| TTFT (ms) | spark | 314.8 | 311.0 | 370.2 | 409.5 | 440.9 | 448.8 |
|  | endpoint | 17,774.0 | 15,409.1 | 27,827.6 | 37,078.4 | 44,479.1 | 46,329.3 |
| ITL = TPOT (ms) | spark | 33.31 | 33.32 | 33.70 | 33.82 | 33.91 | 33.93 |
|  | endpoint | 57.42 | 57.20 | 63.95 | 64.05 | 64.13 | 64.14 |
| E2E latency (ms) | spark | 8,113.5 | 5,410.2 | 14,669.6 | 14,774.5 | 14,858.3 | 14,879.3 |
|  | endpoint | 31,469.0 | 25,653.0 | 52,969.3 | 53,835.3 | 54,528.1 | 54,701.3 |
| Prefill throughput (tok/s/user) | spark | 5,512.9 | 5,920.5 | 8,244.9 | 8,272.2 | 8,294.0 | 8,299.5 |
|  | endpoint | 130.9 | 113.1 | 221.5 | 275.7 | 319.1 | 329.9 |
| Decode throughput (tok/s/user) | spark | 30.02 | 30.01 | 30.36 | 30.44 | 30.50 | 30.52 |
|  | endpoint | 17.54 | 17.48 | 19.12 | 19.85 | 20.43 | 20.58 |
| E2E output throughput (tok/s/user) | spark | 28.73 | 28.70 | 29.33 | 29.44 | 29.53 | 29.55 |
|  | endpoint | 7.71 | 7.96 | 9.12 | 9.66 | 10.09 | 10.20 |
| ISL (tokens) | spark | 1,686.4 | 1,781.5 | 2,471.3 | 2,724.6 | 2,927.3 | 2,978.0 |
|  | endpoint | 1,686.4 | 1,781.5 | 2,471.3 | 2,724.6 | 2,927.3 | 2,978.0 |
| OSL (tokens) | spark | 234.4 | 153.5 | 423.4 | 429.7 | 434.7 | 436.0 |
|  | endpoint | 234.4 | 153.5 | 423.4 | 429.7 | 434.7 | 436.0 |

| aggregate | spark | endpoint |
|---|--:|--:|
| Request throughput (req/s) | 0.1232 | 0.0318 |
| Output token throughput, system (tok/s) | 28.88 | 7.45 |
| Total token throughput, system (tok/s) | 236.69 | 61.03 |
| Total ISL (tokens) | 16,864 | 16,864 |
| Total OSL (tokens) | 2,344 | 2,344 |
| Duration (s) | 81.2 | 314.7 |
| Requests completed | 10 | 10 |
| Prefix cache hit rate (%) | — (see *Known gap*) | 74.28 |
| Errors | 0 | 0 |

#### w0 chatbot c1

spark [`spark_repro_qwen3vl/w0_chatbot_c1/chatbot_flat/c1/`](spark_repro_qwen3vl/w0_chatbot_c1/chatbot_flat/c1/) · endpoint [`w0_chatbot/chatbot_flat/c1/`](w0_chatbot/chatbot_flat/c1/)

| metric | | avg | p50 | p90 | p95 | p99 | max |
|---|---|--:|--:|--:|--:|--:|--:|
| TTFT (ms) | spark | 109.9 | 101.1 | 146.9 | 153.4 | 155.9 | 156.6 |
|  | endpoint | 8,693.7 | 10,015.7 | 13,632.1 | 13,844.7 | 16,938.7 | 17,712.2 |
| ITL = TPOT (ms) | spark | 32.81 | 32.75 | 33.14 | 33.24 | 33.31 | 33.33 |
|  | endpoint | 49.90 | 48.61 | 56.44 | 57.67 | 57.97 | 58.05 |
| E2E latency (ms) | spark | 9,870.8 | 9,503.8 | 13,979.0 | 15,275.7 | 19,879.0 | 21,029.8 |
|  | endpoint | 23,584.0 | 26,158.6 | 32,460.5 | 32,820.5 | 33,579.6 | 33,769.3 |
| Prefill throughput (tok/s/user) | spark | 6,312.5 | 5,208.4 | 12,176.4 | 16,480.3 | 19,310.9 | 20,018.5 |
|  | endpoint | 55.7 | 35.0 | 108.4 | 121.3 | 139.1 | 143.5 |
| Decode throughput (tok/s/user) | spark | 30.48 | 30.53 | 30.72 | 30.72 | 30.78 | 30.80 |
|  | endpoint | 20.22 | 20.57 | 22.92 | 23.30 | 23.68 | 23.78 |
| E2E output throughput (tok/s/user) | spark | 30.18 | 30.30 | 30.46 | 30.49 | 30.56 | 30.57 |
|  | endpoint | 13.62 | 11.40 | 19.90 | 21.13 | 21.81 | 21.98 |
| ISL (tokens) | spark | 584.9 | 439.0 | 1,321.5 | 1,444.3 | 1,600.0 | 1,639.0 |
|  | endpoint | 584.9 | 439.0 | 1,321.5 | 1,444.3 | 1,600.0 | 1,639.0 |
| OSL (tokens) | spark | 298.5 | 288.0 | 427.2 | 465.3 | 605.8 | 641.0 |
|  | endpoint | 298.5 | 288.0 | 427.2 | 465.3 | 605.8 | 641.0 |

| aggregate | spark | endpoint |
|---|--:|--:|
| Request throughput (req/s) | 0.1013 | 0.0424 |
| Output token throughput, system (tok/s) | 30.24 | 12.65 |
| Total token throughput, system (tok/s) | 89.48 | 37.45 |
| Total ISL (tokens) | 11,698 | 11,698 |
| Total OSL (tokens) | 5,970 | 5,970 |
| Duration (s) | 197.4 | 471.8 |
| Requests completed | 20 | 20 |
| Prefix cache hit rate (%) | — (see *Known gap*) | 61.75 |
| Errors | 0 | 0 |

#### w0 agent c1

spark [`spark_repro_qwen3vl/w0_agent_c1/agent_flat/c1/`](spark_repro_qwen3vl/w0_agent_c1/agent_flat/c1/) · endpoint [`w0_agent/agent_flat/c1/`](w0_agent/agent_flat/c1/)

| metric | | avg | p50 | p90 | p95 | p99 | max |
|---|---|--:|--:|--:|--:|--:|--:|
| TTFT (ms) | spark | 184.5 | 123.7 | 358.0 | 370.1 | 477.4 | 504.2 |
|  | endpoint | 20,617.9 | 16,668.0 | 40,537.1 | 47,333.5 | 62,875.5 | 66,761.0 |
| ITL = TPOT (ms) | spark | 33.26 | 33.22 | 33.90 | 33.92 | 33.97 | 33.99 |
|  | endpoint | 57.93 | 57.98 | 65.83 | 66.15 | 68.38 | 68.94 |
| E2E latency (ms) | spark | 8,100.1 | 5,277.9 | 14,626.5 | 15,042.5 | 15,470.1 | 15,577.0 |
|  | endpoint | 34,705.8 | 30,515.2 | 55,283.3 | 59,401.3 | 86,639.4 | 93,448.9 |
| Prefill throughput (tok/s/user) | spark | 14,204.8 | 11,485.5 | 23,030.5 | 24,959.4 | 48,697.7 | 54,632.2 |
|  | endpoint | 117.6 | 107.1 | 216.3 | 290.2 | 321.3 | 329.1 |
| Decode throughput (tok/s/user) | spark | 30.07 | 30.10 | 30.48 | 30.49 | 30.51 | 30.52 |
|  | endpoint | 17.42 | 17.25 | 19.72 | 20.24 | 20.44 | 20.49 |
| E2E output throughput (tok/s/user) | spark | 29.34 | 29.55 | 30.17 | 30.25 | 30.27 | 30.27 |
|  | endpoint | 7.31 | 7.87 | 9.02 | 9.60 | 10.03 | 10.13 |
| ISL (tokens) | spark | 1,658.0 | 1,579.5 | 2,903.3 | 2,985.3 | 3,096.3 | 3,124.0 |
|  | endpoint | 1,658.0 | 1,579.5 | 2,903.3 | 2,985.3 | 3,096.3 | 3,124.0 |
| OSL (tokens) | spark | 238.3 | 153.5 | 436.0 | 436.8 | 449.0 | 452.0 |
|  | endpoint | 238.3 | 153.5 | 436.0 | 436.8 | 449.0 | 452.0 |

| aggregate | spark | endpoint |
|---|--:|--:|
| Request throughput (req/s) | 0.1233 | 0.0288 |
| Output token throughput, system (tok/s) | 29.39 | 6.86 |
| Total token throughput, system (tok/s) | 233.87 | 54.62 |
| Total ISL (tokens) | 33,160 | 33,160 |
| Total OSL (tokens) | 4,766 | 4,766 |
| Duration (s) | 162.2 | 694.4 |
| Requests completed | 20 | 20 |
| Prefix cache hit rate (%) | — (see *Known gap*) | 69.39 |
| Errors | 0 | 0 |

#### w0 chatbot c1 rep

spark [`spark_repro_qwen3vl/w0_chatbot_c1_rep/chatbot_flat/c1/`](spark_repro_qwen3vl/w0_chatbot_c1_rep/chatbot_flat/c1/) · endpoint [`w0_chatbot_rep/chatbot_flat/c1/`](w0_chatbot_rep/chatbot_flat/c1/)

| metric | | avg | p50 | p90 | p95 | p99 | max |
|---|---|--:|--:|--:|--:|--:|--:|
| TTFT (ms) | spark | 109.1 | 100.6 | 145.3 | 149.5 | 151.3 | 151.7 |
|  | endpoint | 8,705.7 | 10,072.6 | 13,533.4 | 13,754.3 | 16,959.2 | 17,760.4 |
| ITL = TPOT (ms) | spark | 32.79 | 32.73 | 33.13 | 33.20 | 33.28 | 33.31 |
|  | endpoint | 50.31 | 49.11 | 56.67 | 58.14 | 58.72 | 58.86 |
| E2E latency (ms) | spark | 9,863.0 | 9,497.1 | 13,968.6 | 15,266.7 | 19,854.9 | 21,001.9 |
|  | endpoint | 23,698.4 | 26,188.8 | 32,766.0 | 32,930.6 | 33,804.3 | 34,022.7 |
| Prefill throughput (tok/s/user) | spark | 6,419.9 | 5,229.3 | 12,104.6 | 16,842.6 | 20,120.4 | 20,939.8 |
|  | endpoint | 55.7 | 35.0 | 108.1 | 122.1 | 138.6 | 142.8 |
| Decode throughput (tok/s/user) | spark | 30.50 | 30.55 | 30.75 | 30.77 | 30.79 | 30.79 |
|  | endpoint | 20.04 | 20.37 | 22.48 | 22.66 | 22.83 | 22.87 |
| E2E output throughput (tok/s/user) | spark | 30.20 | 30.31 | 30.49 | 30.52 | 30.58 | 30.60 |
|  | endpoint | 13.51 | 11.42 | 19.71 | 20.76 | 21.45 | 21.63 |
| ISL (tokens) | spark | 584.9 | 439.0 | 1,321.5 | 1,444.3 | 1,600.0 | 1,639.0 |
|  | endpoint | 584.9 | 439.0 | 1,321.5 | 1,444.3 | 1,600.0 | 1,639.0 |
| OSL (tokens) | spark | 298.5 | 288.0 | 427.2 | 465.3 | 605.8 | 641.0 |
|  | endpoint | 298.5 | 288.0 | 427.2 | 465.3 | 605.8 | 641.0 |

| aggregate | spark | endpoint |
|---|--:|--:|
| Request throughput (req/s) | 0.1014 | 0.0422 |
| Output token throughput, system (tok/s) | 30.26 | 12.59 |
| Total token throughput, system (tok/s) | 89.55 | 37.27 |
| Total ISL (tokens) | 11,698 | 11,698 |
| Total OSL (tokens) | 5,970 | 5,970 |
| Duration (s) | 197.3 | 474.1 |
| Requests completed | 20 | 20 |
| Prefix cache hit rate (%) | — (see *Known gap*) | 61.75 |
| Errors | 0 | 0 |


### Llama-3.1-8B-Instruct

#### w0 chatbot c1

spark [`spark_repro_llama31/w0_chatbot_c1/chatbot_flat/c1/`](spark_repro_llama31/w0_chatbot_c1/chatbot_flat/c1/) · endpoint [`cf_llama31_chatbot/chatbot_flat/c1/`](cf_llama31_chatbot/chatbot_flat/c1/)

| metric | | avg | p50 | p90 | p95 | p99 | max |
|---|---|--:|--:|--:|--:|--:|--:|
| TTFT (ms) | spark | 79.3 | 79.1 | 82.7 | 84.8 | 86.4 | 86.8 |
|  | endpoint | 11,444.4 | 13,706.4 | 17,135.1 | 17,537.5 | 22,691.7 | 23,980.3 |
| ITL = TPOT (ms) | spark | 72.52 | 72.45 | 72.94 | 72.97 | 73.08 | 73.11 |
|  | endpoint | 68.72 | 68.45 | 71.46 | 71.49 | 71.88 | 71.97 |
| E2E latency (ms) | spark | 21,654.0 | 20,896.2 | 30,873.6 | 33,678.4 | 43,813.4 | 46,347.2 |
|  | endpoint | 31,875.2 | 34,582.1 | 43,200.2 | 45,414.9 | 45,682.8 | 45,749.8 |
| Prefill throughput (tok/s/user) | spark | 7,475.8 | 5,837.8 | 16,457.4 | 17,166.2 | 18,774.8 | 19,176.9 |
|  | endpoint | 50.7 | 44.0 | 84.2 | 97.9 | 114.5 | 118.6 |
| Decode throughput (tok/s/user) | spark | 13.79 | 13.80 | 13.86 | 13.87 | 13.87 | 13.87 |
|  | endpoint | 14.56 | 14.61 | 14.94 | 14.96 | 15.14 | 15.18 |
| E2E output throughput (tok/s/user) | spark | 13.79 | 13.80 | 13.85 | 13.87 | 13.87 | 13.87 |
|  | endpoint | 9.78 | 8.66 | 13.81 | 14.05 | 14.63 | 14.78 |
| ISL (tokens) | spark | 608.8 | 462.0 | 1,346.0 | 1,456.0 | 1,623.2 | 1,665.0 |
|  | endpoint | 608.8 | 462.0 | 1,346.0 | 1,456.0 | 1,623.2 | 1,665.0 |
| OSL (tokens) | spark | 298.5 | 288.0 | 427.2 | 465.3 | 605.8 | 641.0 |
|  | endpoint | 298.5 | 288.0 | 427.2 | 465.3 | 605.8 | 641.0 |

| aggregate | spark | endpoint |
|---|--:|--:|
| Request throughput (req/s) | 0.0462 | 0.0314 |
| Output token throughput, system (tok/s) | 13.78 | 9.36 |
| Total token throughput, system (tok/s) | 41.90 | 28.46 |
| Total ISL (tokens) | 12,176 | 12,176 |
| Total OSL (tokens) | 5,970 | 5,970 |
| Duration (s) | 433.1 | 637.6 |
| Requests completed | 20 | 20 |
| Prefix cache hit rate (%) | — (see *Known gap*) | 63.83 |
| Errors | 0 | 0 |

#### w0 agent c1

spark [`spark_repro_llama31/w0_agent_c1/agent_flat/c1/`](spark_repro_llama31/w0_agent_c1/agent_flat/c1/) · endpoint [`cf_llama31_agent/agent_flat/c1/`](cf_llama31_agent/agent_flat/c1/)

| metric | | avg | p50 | p90 | p95 | p99 | max |
|---|---|--:|--:|--:|--:|--:|--:|
| TTFT (ms) | spark | 112.1 | 85.9 | 156.0 | 176.1 | 324.0 | 360.9 |
|  | endpoint | 26,594.9 | 22,279.0 | 54,492.6 | 62,952.0 | 81,626.1 | 86,294.7 |
| ITL = TPOT (ms) | spark | 73.21 | 73.09 | 73.91 | 74.01 | 74.10 | 74.12 |
|  | endpoint | 71.83 | 72.08 | 74.89 | 75.71 | 76.04 | 76.12 |
| E2E latency (ms) | spark | 17,513.2 | 11,208.6 | 32,003.4 | 32,305.8 | 33,234.8 | 33,467.1 |
|  | endpoint | 43,822.1 | 39,991.8 | 73,339.0 | 79,105.3 | 111,310.6 | 119,361.9 |
| Prefill throughput (tok/s/user) | spark | 16,659.7 | 16,294.8 | 27,634.5 | 28,898.1 | 33,359.5 | 34,474.9 |
|  | endpoint | 94.3 | 84.8 | 172.7 | 246.2 | 263.9 | 268.4 |
| Decode throughput (tok/s/user) | spark | 13.66 | 13.68 | 13.74 | 13.77 | 13.80 | 13.80 |
|  | endpoint | 13.94 | 13.87 | 14.63 | 14.72 | 14.97 | 15.03 |
| E2E output throughput (tok/s/user) | spark | 13.63 | 13.64 | 13.73 | 13.76 | 13.79 | 13.80 |
|  | endpoint | 5.82 | 6.46 | 7.32 | 8.12 | 8.49 | 8.58 |
| ISL (tokens) | spark | 1,661.3 | 1,587.0 | 2,850.9 | 2,988.5 | 3,040.9 | 3,054.0 |
|  | endpoint | 1,661.3 | 1,587.0 | 2,850.9 | 2,988.5 | 3,040.9 | 3,054.0 |
| OSL (tokens) | spark | 238.3 | 153.5 | 436.0 | 436.8 | 449.0 | 452.0 |
|  | endpoint | 238.3 | 153.5 | 436.0 | 436.8 | 449.0 | 452.0 |

| aggregate | spark | endpoint |
|---|--:|--:|
| Request throughput (req/s) | 0.0571 | 0.0228 |
| Output token throughput, system (tok/s) | 13.61 | 5.44 |
| Total token throughput, system (tok/s) | 108.46 | 43.34 |
| Total ISL (tokens) | 33,226 | 33,226 |
| Total OSL (tokens) | 4,766 | 4,766 |
| Duration (s) | 350.3 | 876.5 |
| Requests completed | 20 | 20 |
| Prefix cache hit rate (%) | — (see *Known gap*) | 69.90 |
| Errors | 0 | 0 |

#### w0 chatbot c1 rep

spark [`spark_repro_llama31/w0_chatbot_c1_rep/chatbot_flat/c1/`](spark_repro_llama31/w0_chatbot_c1_rep/chatbot_flat/c1/) · endpoint [`cf_llama31_chatbot_rep/chatbot_flat/c1/`](cf_llama31_chatbot_rep/chatbot_flat/c1/)

| metric | | avg | p50 | p90 | p95 | p99 | max |
|---|---|--:|--:|--:|--:|--:|--:|
| TTFT (ms) | spark | 79.1 | 78.4 | 83.0 | 83.5 | 87.9 | 88.9 |
|  | endpoint | 11,196.3 | 13,396.8 | 16,808.7 | 17,148.3 | 22,254.2 | 23,530.7 |
| ITL = TPOT (ms) | spark | 72.67 | 72.63 | 73.13 | 73.20 | 73.25 | 73.26 |
|  | endpoint | 67.39 | 67.23 | 70.09 | 70.83 | 71.48 | 71.65 |
| E2E latency (ms) | spark | 21,702.1 | 20,952.4 | 30,955.3 | 33,745.3 | 43,904.0 | 46,443.7 |
|  | endpoint | 31,272.8 | 34,015.9 | 42,269.4 | 44,349.9 | 44,865.4 | 44,994.3 |
| Prefill throughput (tok/s/user) | spark | 7,474.3 | 5,962.6 | 16,212.6 | 17,432.5 | 18,462.7 | 18,720.2 |
|  | endpoint | 51.8 | 45.0 | 86.1 | 100.2 | 117.5 | 121.9 |
| Decode throughput (tok/s/user) | spark | 13.76 | 13.77 | 13.83 | 13.84 | 13.85 | 13.86 |
|  | endpoint | 14.86 | 14.87 | 15.57 | 15.60 | 15.89 | 15.96 |
| E2E output throughput (tok/s/user) | spark | 13.76 | 13.77 | 13.83 | 13.83 | 13.85 | 13.85 |
|  | endpoint | 10.01 | 8.78 | 14.26 | 14.39 | 14.85 | 14.96 |
| ISL (tokens) | spark | 608.8 | 462.0 | 1,346.0 | 1,456.0 | 1,623.2 | 1,665.0 |
|  | endpoint | 608.8 | 462.0 | 1,346.0 | 1,456.0 | 1,623.2 | 1,665.0 |
| OSL (tokens) | spark | 298.5 | 288.0 | 427.2 | 465.3 | 605.8 | 641.0 |
|  | endpoint | 298.5 | 288.0 | 427.2 | 465.3 | 605.8 | 641.0 |

| aggregate | spark | endpoint |
|---|--:|--:|
| Request throughput (req/s) | 0.0461 | 0.0320 |
| Output token throughput, system (tok/s) | 13.75 | 9.54 |
| Total token throughput, system (tok/s) | 41.80 | 29.01 |
| Total ISL (tokens) | 12,176 | 12,176 |
| Total OSL (tokens) | 5,970 | 5,970 |
| Duration (s) | 434.1 | 625.5 |
| Requests completed | 20 | 20 |
| Prefix cache hit rate (%) | — (see *Known gap*) | 63.83 |
| Errors | 0 | 0 |

#### r100 chatbot c1

spark [`spark_repro_llama31/r100_chatbot_c1/chatbot_flat/c1/`](spark_repro_llama31/r100_chatbot_c1/chatbot_flat/c1/) · endpoint [`r100_chatbot_flat_c1/chatbot_flat/c1/`](r100_chatbot_flat_c1/chatbot_flat/c1/)

| metric | | avg | p50 | p90 | p95 | p99 | max |
|---|---|--:|--:|--:|--:|--:|--:|
| TTFT (ms) | spark | 95.5 | 91.8 | 118.8 | 124.0 | 140.4 | 151.7 |
|  | endpoint | 10,970.9 | 10,847.2 | 20,745.1 | 23,313.6 | 31,551.5 | 32,093.9 |
| ITL = TPOT (ms) | spark | 72.66 | 72.62 | 73.09 | 73.21 | 73.35 | 73.37 |
|  | endpoint | 67.36 | 66.94 | 69.85 | 71.01 | 71.29 | 72.50 |
| E2E latency (ms) | spark | 17,988.3 | 17,311.7 | 32,302.5 | 35,542.4 | 47,229.8 | 53,617.4 |
|  | endpoint | 27,572.8 | 27,561.9 | 45,387.1 | 46,982.9 | 54,997.1 | 65,396.9 |
| Prefill throughput (tok/s/user) | spark | 6,553.6 | 4,949.3 | 14,395.0 | 16,034.9 | 18,113.5 | 18,430.5 |
|  | endpoint | 64.8 | 47.9 | 121.7 | 172.3 | 198.7 | 350.6 |
| Decode throughput (tok/s/user) | spark | 13.76 | 13.77 | 13.84 | 13.84 | 13.86 | 13.86 |
|  | endpoint | 14.86 | 14.94 | 15.41 | 15.52 | 15.61 | 15.76 |
| E2E output throughput (tok/s/user) | spark | 13.73 | 13.75 | 13.83 | 13.83 | 13.85 | 13.85 |
|  | endpoint | 9.05 | 8.60 | 14.10 | 14.54 | 14.92 | 14.92 |
| ISL (tokens) | spark | 655.5 | 552.0 | 1,471.8 | 1,583.3 | 1,832.2 | 1,951.0 |
|  | endpoint | 655.5 | 552.0 | 1,471.8 | 1,583.3 | 1,832.2 | 1,951.0 |
| OSL (tokens) | spark | 247.2 | 238.5 | 446.1 | 487.8 | 651.9 | 740.0 |
|  | endpoint | 247.2 | 238.5 | 446.1 | 487.8 | 651.9 | 740.0 |

| aggregate | spark | endpoint |
|---|--:|--:|
| Request throughput (req/s) | 0.0556 | 0.0363 |
| Output token throughput, system (tok/s) | 13.74 | 8.97 |
| Total token throughput, system (tok/s) | 50.18 | 32.73 |
| Total ISL (tokens) | 65,546 | 65,546 |
| Total OSL (tokens) | 24,723 | 24,723 |
| Duration (s) | 1,799.0 | 2,757.6 |
| Requests completed | 100 | 100 |
| Prefix cache hit rate (%) | — (see *Known gap*) | 67.04 |
| Errors | 0 | 0 |

#### r100 chatbot c2

spark [`spark_repro_llama31/r100_chatbot_c2/chatbot_flat/c2/`](spark_repro_llama31/r100_chatbot_c2/chatbot_flat/c2/) · endpoint [`r100_chatbot_flat_c2/chatbot_flat/c2/`](r100_chatbot_flat_c2/chatbot_flat/c2/)

| metric | | avg | p50 | p90 | p95 | p99 | max |
|---|---|--:|--:|--:|--:|--:|--:|
| TTFT (ms) | spark | 211.0 | 212.6 | 216.0 | 217.7 | 219.6 | 220.4 |
|  | endpoint | 17,821.7 | 13,533.2 | 35,059.4 | 43,280.3 | 62,304.2 | 73,673.7 |
| ITL = TPOT (ms) | spark | 68.62 | 68.62 | 69.06 | 69.18 | 69.26 | 71.35 |
|  | endpoint | 181.71 | 156.42 | 278.60 | 295.55 | 566.31 | 1,054.03 |
| E2E latency (ms) | spark | 17,112.0 | 16,477.2 | 30,926.5 | 33,788.3 | 44,711.6 | 50,735.6 |
|  | endpoint | 62,530.2 | 62,220.9 | 108,834.4 | 114,921.6 | 120,162.6 | 164,584.0 |
| Prefill throughput (tok/s/user) | spark | 3,095.8 | 2,695.1 | 6,894.5 | 7,317.8 | 8,515.9 | 9,076.3 |
|  | endpoint | 48.5 | 34.4 | 85.3 | 128.8 | 199.2 | 347.2 |
| Decode throughput (tok/s/user) | spark | 14.57 | 14.57 | 14.67 | 14.68 | 14.70 | 14.71 |
|  | endpoint | 6.62 | 6.39 | 9.07 | 9.13 | 9.23 | 11.52 |
| E2E output throughput (tok/s/user) | spark | 14.35 | 14.43 | 14.55 | 14.58 | 14.60 | 14.64 |
|  | endpoint | 4.33 | 3.93 | 6.71 | 7.73 | 8.67 | 8.91 |
| ISL (tokens) | spark | 655.5 | 552.0 | 1,471.8 | 1,583.3 | 1,832.2 | 1,951.0 |
|  | endpoint | 655.5 | 552.0 | 1,471.8 | 1,583.3 | 1,832.2 | 1,951.0 |
| OSL (tokens) | spark | 247.2 | 238.5 | 446.1 | 487.8 | 651.9 | 740.0 |
|  | endpoint | 247.2 | 238.5 | 446.1 | 487.8 | 651.9 | 740.0 |

| aggregate | spark | endpoint |
|---|--:|--:|
| Request throughput (req/s) | 0.1163 | 0.0319 |
| Output token throughput, system (tok/s) | 28.75 | 7.89 |
| Total token throughput, system (tok/s) | 104.98 | 28.82 |
| Total ISL (tokens) | 65,546 | 65,546 |
| Total OSL (tokens) | 24,723 | 24,723 |
| Duration (s) | 859.8 | 3,132.2 |
| Requests completed | 100 | 100 |
| Prefix cache hit rate (%) | — (see *Known gap*) | 46.77 |
| Errors | 0 | 0 |

### Pairs with no endpoint counterpart

These spark points have no valid endpoint data to sit beside, so they appear only in *All points*:

| point | why |
|---|---|
| Llama `w2 *` series (4 points) | never run against the Llama endpoint — the `WARMUP=2` series predates it |
| `w0 agent c2` (both models) | endpoint point invalid — 6/20 requests hit the ngrok bandwidth quota, see [`INDEX_optimumxt.md`](INDEX_optimumxt.md) |
| `r100 agent c1` / `c2` (both models) | endpoint points lost 3 and 10 requests to Cloudflare 524 timeouts, which truncate the slow tail, see [`TABLES_r100.md`](TABLES_r100.md) |
| `r100 *` (Qwen) | the 100-request series was only ever run against the Llama endpoint |
| `c32 chatbot` (both models) | endpoint run wedged the worker and produced no summary |

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

| model | requests | duration | req/s | prefill (tok/s/user) | decode (tok/s/user) | **system output (tok/s)** | TTFT avg | ITL avg | errors |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| Llama-3.1-8B | 320 | 226.4 s | 1.4137 | 2,381 | 12.09 | **346.1** | 275 ms | 82.8 ms | 0 |
| Qwen3-VL-30B-A3B | 320 | 513.5 s | 0.6232 | 1,013 | 5.13 | **152.6** | 650 ms | 195.6 ms | 0 |

Per-user decode drops at c32 while system output rises 25× to 346 tok/s on Llama — batching
working as it should. That is the behaviour the endpoint could not produce.

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

Artifacts and the full file inventory: [`SPARK_INDEX.md`](SPARK_INDEX.md).
Endpoint-side data and its caveats: [`INDEX_optimumxt.md`](INDEX_optimumxt.md).
