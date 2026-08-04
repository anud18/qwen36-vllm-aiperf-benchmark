# Result tables — `Llama-3.1-8B-Instruct-optimumxt` via Cloudflare Tunnel

Endpoint `https://athens-move-ted-convertible.trycloudflare.com` → NVIDIA Dynamo,
worker `192.168.8.51:38103`, `device_type=cuda`, context **4096**.
Flat-trace track, `REMOTE=1`, **`WARMUP=0`**, `REQS=20`, concurrency 1, trace slice `[0:20]`.
OSL pinned to the trace via in-data `ignore_eos`. aiperf 0.10.0. Run 2026-07-29 18:46–19:12.

Settings are identical to the `w0` series in `TABLES_w0.md`.

> **Different model — not a tunnel A/B.** The earlier runs measured
> `Qwen3-VL-30B-A3B-Instruct-optimumxt`; this endpoint serves
> `Llama-3.1-8B-Instruct-optimumxt` (dense 8B). Same physical box, same Dynamo, same context cap,
> but swapping ngrok → Cloudflare *and* the model at once means these numbers cannot isolate the
> tunnel's contribution. That still requires a `localhost` run on the machine itself.

> **ISL differs from the Qwen runs by design.** Llama 3.1 tokenises the same trace entries
> differently (total ISL 12,176 vs 11,698 for chatbot, +4.1 %). OSL totals are identical
> (5,970 / 4,766) because the trace pins them.

**TPOT = ITL** — aiperf's `inter_token_latency` is `(request_latency − TTFT) / (OSL − 1)`, the
standard time-per-output-token. Shown as one row. **p50 is the median.**

Validity: all points completed **20 / 20** requests, **0 errors**, `osl_mismatch_count = 0`.

`chatbot_flat` c1 was run a second time on 2026-07-30 02:26 through a fresh tunnel
(`arena-iii-chains-rings.trycloudflare.com`) **after the worker was restarted** — the Dynamo
instance moved from port 38103 to 42471, so its KV cache started empty. See *Repeatability*.


> **Reproduced locally.** Every point here was re-run on spark against a local vLLM at the same
> 4096 context, with ISL matched exactly. See [`SPARK_REPRO.md`](SPARK_REPRO.md) — the endpoint's
> prefill turns out to be 30–237× slower than the same model on the same box.

## Distribution metrics

| workload | point | metric | avg | p50 (median) | p90 | p95 | p99 | min | max | std |
|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|
| `chatbot_flat` | c1 | TTFT (ms) | 11,444.39 | 13,706.37 | 17,135.06 | 17,537.52 | 22,691.72 | 528.93 | 23,980.27 | 6,822.04 |
| `chatbot_flat` | c1 | ITL = TPOT (ms) | 68.72 | 68.45 | 71.46 | 71.49 | 71.88 | 65.88 | 71.97 | 1.73 |
| `chatbot_flat` | c1 | E2E request latency (ms) | 31,875.21 | 34,582.14 | 43,200.22 | 45,414.89 | 45,682.79 | 6,019.84 | 45,749.76 | 10,433.27 |
| `chatbot_flat` | c1 | ISL (tokens) | 608.8 | 462.0 | 1,346.0 | 1,456.0 | 1,623.2 | 40.0 | 1,665.0 | 514.6 |
| `chatbot_flat` | c1 | OSL (tokens) | 298.5 | 288.0 | 427.2 | 465.3 | 605.8 | 73.0 | 641.0 | 113.9 |
| `chatbot_flat` | c1 | Per-user output throughput (tok/s) | 14.56 | 14.61 | 14.94 | 14.96 | 15.14 | 13.89 | 15.18 | 0.36 |
| `agent_flat` | c1 | TTFT (ms) | 26,594.87 | 22,279.00 | 54,492.60 | 62,951.99 | 81,626.15 | 7,553.17 | 86,294.69 | 19,730.87 |
| `agent_flat` | c1 | ITL = TPOT (ms) | 71.83 | 72.08 | 74.89 | 75.71 | 76.04 | 66.53 | 76.12 | 2.59 |
| `agent_flat` | c1 | E2E request latency (ms) | 43,822.14 | 39,991.84 | 73,338.99 | 79,105.26 | 111,310.56 | 13,789.11 | 119,361.88 | 25,779.99 |
| `agent_flat` | c1 | ISL (tokens) | 1,661.3 | 1,587.0 | 2,850.9 | 2,988.5 | 3,040.9 | 491.0 | 3,054.0 | 738.6 |
| `agent_flat` | c1 | OSL (tokens) | 238.3 | 153.5 | 436.0 | 436.8 | 449.0 | 80.0 | 452.0 | 130.4 |
| `agent_flat` | c1 | Per-user output throughput (tok/s) | 13.94 | 13.87 | 14.63 | 14.72 | 14.97 | 13.14 | 15.03 | 0.51 |

## Aggregate metrics

| metric | `chatbot_flat` c1 | `agent_flat` c1 |
|---|--:|--:|
| Request throughput (req/s) | 0.0314 | 0.0228 |
| Output token throughput (tok/s) | 9.36 | 5.44 |
| Total token throughput (tok/s) | 28.46 | 43.34 |
| E2E output token throughput (tok/s) | 9.78 | 5.82 |
| Total ISL (tokens) | 12,176 | 33,226 |
| Total OSL (tokens) | 5,970 | 4,766 |
| Prefix cache hit rate (%) | 63.83 | 69.90 |
| Cache-read tokens | 7,772 | 23,224 |
| Benchmark duration (s) | 637.56 | 876.51 |
| Requests completed | 20 / 20 | 20 / 20 |
| Errors | 0 | 0 |
| OSL mismatches | 0 | 0 |

## Repeatability — `chatbot_flat` c1 twice, worker restarted in between

Identical invocation. Run 1 at 18:46 on the original tunnel; run 2 at 02:26 the next day on a new
tunnel, after the Dynamo worker had been restarted (port 38103 → 42471, new instance id), so run 2
provably began with a **cold KV cache**.

| metric | run 1 (18:46) | run 2 (02:26, cold cache) | Δ |
|---|--:|--:|--:|
| benchmark duration (s) | 637.56 | 625.51 | −1.9 % |
| TTFT avg / p50 / p90 (ms) | 11,444.39 / 13,706.37 / 17,135.06 | 11,196.31 / 13,396.80 / 16,808.69 | −2.2 / −2.3 / −1.9 % |
| ITL = TPOT avg / p50 (ms) | 68.72 / 68.45 | 67.39 / 67.23 | −1.9 / −1.8 % |
| E2E latency avg / p50 (ms) | 31,875.21 / 34,582.14 | 31,272.78 / 34,015.90 | −1.9 / −1.6 % |
| request throughput (req/s) | 0.0314 | 0.0320 | +1.9 % |
| output token throughput (tok/s) | 9.36 | 9.54 | +1.9 % |
| output tok/s per user avg | 14.56 | 14.86 | +2.0 % |
| **total ISL / OSL (tokens)** | 12,176 / 5,970 | **12,176 / 5,970** | **0.0 %** |
| **cache-read tokens** | 7,772 | **7,772** | **0.0 %** |
| **cache hit rate** | 63.83 % | **63.83 %** | **0.0 %** |

ISL and OSL match on every percentile; latency metrics are uniformly ~2 % faster, within noise.

**This is the decisive evidence on cross-round cache carryover.** Run 2 started on a restarted
worker whose KV cache was necessarily empty, and still reported *exactly* the same 7,772
cache-read tokens. The 63.83 % hit rate is therefore entirely intra-run — later turns of a session
hitting earlier turns of the same session — with zero contribution from anything cached earlier.
The equivalent Qwen observation (`c1` twice, 7,224 both times) was consistent with this but could
also be explained by eviction during the 90-minute gap; a cold start cannot.

Practical consequence: **rounds on this deployment are independent and need no cache flush between
them.**

## Cross-model comparison, same settings

Both columns are `WARMUP=0`, `REQS=20`, c1, trace slice `[0:20]`, same physical box.
Model and tunnel both changed — read as two deployments, not as a controlled experiment.

| metric | Qwen3-VL-30B-A3B (ngrok) | **Llama-3.1-8B (Cloudflare)** | Δ |
|---|--:|--:|--:|
| **chatbot_flat** | | | |
| TTFT avg (ms) | 8,693.71 | 11,444.39 | +31.6 % |
| ITL = TPOT avg (ms) | 49.90 | 68.72 | +37.7 % |
| E2E latency avg (ms) | 23,583.99 | 31,875.21 | +35.2 % |
| request throughput (req/s) | 0.0424 | 0.0314 | −25.9 % |
| output token throughput (tok/s) | 12.65 | 9.36 | −26.0 % |
| prefix cache hit rate (%) | 61.75 | 63.83 | +2.1 pt |
| duration (s) | 471.83 | 637.56 | +35.1 % |
| **agent_flat** | | | |
| TTFT avg (ms) | 20,617.85 | 26,594.87 | +29.0 % |
| ITL = TPOT avg (ms) | 57.93 | 71.83 | +24.0 % |
| E2E latency avg (ms) | 34,705.85 | 43,822.14 | +26.3 % |
| request throughput (req/s) | 0.0288 | 0.0228 | −20.8 % |
| output token throughput (tok/s) | 6.86 | 5.44 | −20.7 % |
| prefix cache hit rate (%) | 69.39 | 69.90 | +0.5 pt |
| duration (s) | 694.41 | 876.51 | +26.2 % |

The dense 8B is uniformly **20–38 % slower** than the 30B-A3B MoE on the same hardware. That is
not absurd — the MoE activates roughly 3B parameters per token against the 8B's full 8B — but
both are far below what this class of hardware should deliver.

### Effective prefill rate

Computed against *uncached* tokens only (raw ISL ÷ TTFT is inflated by prefix-cache hits):

| sample | ISL avg | cache hit rate | uncached tokens | TTFT avg | effective prefill |
|---|--:|--:|--:|--:|--:|
| `chatbot_flat` | 608.8 | 63.83 % | ≈220.2 | 11.44 s | **19.2 tok/s** |
| `agent_flat` | 1,661.3 | 69.90 % | ≈500.1 | 26.59 s | **18.8 tok/s** |

Same pattern as the Qwen deployment: linear in uncached tokens, rate pinned at a very low
constant — ≈19 tok/s here versus ≈25 tok/s for Qwen. The prefill path, not the model, is the
bottleneck on this box.

Decode is more *consistent* on Llama though: ITL std 1.73 ms (chatbot) against 4.71 ms for Qwen,
with a p99/min spread of only 71.88 / 65.88 ms.

## Note on Dynamo metrics

`dynamo_frontend_cached_tokens_sum` sampled through the Cloudflare tunnel stayed frozen at
`73387 / 127547` across both runs, even though aiperf recorded 7,772 and 23,224 cache-read tokens.
The Cloudflare edge is most likely caching the `GET /metrics` response. The per-request figures
in this document come from aiperf's own `usage.prompt_tokens_details.cached_tokens`, which is
unaffected; the Dynamo counters were not used here.

## Reproduce

```bash
cd ~/benchmark
CF='REMOTE=1 NODE=llama31_cf SERVED_NAME=Llama-3.1-8B-Instruct-optimumxt
    URL=https://athens-move-ted-convertible.trycloudflare.com
    TOKENIZER=NousResearch/Meta-Llama-3.1-8B-Instruct
    WARMUP=0 RC_TLIM=2700 REQS=20 POINTS=c1'
env $CF OUTBASE=results/nvfp4/cf_llama31_chatbot bash scripts/run_nvfp4.sh chatbot_flat
env $CF OUTBASE=results/nvfp4/cf_llama31_agent   bash scripts/run_nvfp4.sh agent_flat
```

`meta-llama/Llama-3.1-8B-Instruct` is gated on HF and cannot be fetched;
`NousResearch/Meta-Llama-3.1-8B-Instruct` is an ungated mirror carrying the identical tokenizer
(vocab 128,000, verified encoding).

`WARMUP=0` requires the `scripts/run_nvfp4.sh` fix that omits `--warmup-request-count` entirely —
aiperf rejects the flag with value 0.

Artifacts: `results/nvfp4/cf_llama31_chatbot/`, `results/nvfp4/cf_llama31_agent/`,
log `results/nvfp4/cf_llama31_run.log`.
