# Qwen3-VL-30B-A3B-Instruct-optimumxt — flat-trace smoke run

Flat-trace track (`scripts/run_nvfp4.sh` §6), remote managed endpoint.
Run date **2026-07-29**. aiperf 0.10.0, schema 1.3.


> **Metric formulas** — every aiperf field used here, verified against the raw per-request
> records: [`SPARK_REPRO.md` § Metric definitions](../SPARK_REPRO.md#metric-definitions).

> **Reproduced locally.** Every point here was re-run on spark against a local vLLM at the same
> 4096 context, with ISL matched exactly. See [`SPARK_REPRO.md`](../SPARK_REPRO.md) — the endpoint's
> prefill turns out to be 30–237× slower than the same model on the same box.

## Run configuration

| | |
|---|---|
| endpoint | `https://poppy-zero-ritzy.ngrok-free.dev` (ngrok tunnel → NVIDIA Dynamo frontend) |
| served model | `Qwen3-VL-30B-A3B-Instruct-optimumxt` |
| worker | `192.168.8.51:38843`, `device_type=cuda`, single instance |
| context length | **4096** tokens (`dynamo_frontend_model_context_length`) |
| KV block size | 16 tokens (`dynamo_frontend_model_kv_cache_block_size`) |
| datasets | `nvfp4_chatbot_flat.jsonl`, `nvfp4_agent_flat.jsonl` — 384-entry `mooncake_trace`, `messages` mode |
| OSL control | in-data `ignore_eos` + `min_tokens` (built with `--force-osl`), `temperature=0`, `seed=42` |
| ISL source | `--use-server-token-count` (server-reported usage, not client tokenizer) |
| tokenizer | `Qwen/Qwen3-VL-30B-A3B-Instruct` |
| mode | `REMOTE=1` — no server restart, **no `/reset_prefix_cache` between points** |
| warmup | **2** (script default is 16 — lowered for this smoke run) |
| `NODE` / `OUTBASE` | `qwen3vl_ngrok` / `results/nvfp4/qwen3vl_ngrok` |

> **Not comparable with the spark / 5090 / h100 flat runs.** Those used `WARMUP=16` and a cold
> prefix cache per point. Here warmup is 2 (so different dataset entries are profiled) and the
> cache is warm across points. Treat these numbers as a liveness/sanity check, not as a
> cross-machine data point.

## Points

| point | concurrency | requests | dataset entries | wall clock | started | artifacts |
|---|--:|--:|---|--:|---|---|
| `c1` | 1 | 10 | `[2:12]` | 233.5 s | 05:55:10 | `qwen3vl_ngrok/` |
| `c2` | 2 | 20 | `[2:22]` | 615.9 s | 06:00:02 | `qwen3vl_ngrok/` |
| `c1` (repeat) | 1 | 10 | `[2:12]` | 231.7 s | 07:27:52 | `qwen3vl_ngrok_run2/` |
| `agent_flat` `c1` | 1 | 10 | `[2:12]` | 314.7 s | 08:28:47 | `qwen3vl_ngrok/agent_flat/` |
| `chatbot_flat` `c1` no-warmup | 1 | 20 | `[0:20]` | 471.8 s | 17:03:47 | `w0_chatbot/` |
| `agent_flat` `c1` no-warmup | 1 | 20 | `[0:20]` | 694.4 s | 17:11:48 | `w0_agent/` |
| `chatbot_flat` `c1` no-warmup (repeat) | 1 | 20 | `[0:20]` | 474.1 s | 17:23:34 | `w0_chatbot_rep/` |

Errors: **0** on all points. No cancellations, no retries.

`c1` was run twice with identical parameters, ~90 minutes apart, to check reproducibility — see
*Repeatability* below. Unless stated otherwise, `c1` figures in this document are from run 1.

## Headline results

| metric | unit | **c1** | **c2** | Δ |
|---|---|--:|--:|--:|
| request throughput | req/s | **0.0428** | **0.0325** | **−24.2 %** |
| output token throughput | tok/s | 11.95 | 9.87 | −17.4 % |
| total token throughput | tok/s | 37.37 | 29.42 | −21.3 % |
| e2e output token throughput | tok/s | 13.22 | 5.77 | −56.4 % |
| TTFT avg | ms | 9,070.7 | 14,599.6 | +61.0 % |
| ITL avg | ms | 50.8 | 150.0 | +195.6 % |
| request latency avg | ms | 23,347.0 | 61,238.7 | +162.3 % |
| output tok/s per user | tok/s | 19.89 | 7.38 | −62.9 % |
| prefill tok/s per user | tok/s | 53.94 | 40.31 | −25.3 % |

**Throughput went *down* when concurrency doubled.** Two concurrent requests already contend to
the point of producing less aggregate work than one. See *Observations*.

## Sequence lengths

### Input sequence length (tokens, server-reported)

| point | avg | min | p25 | p50 | p75 | p90 | p95 | p99 | max | std | total |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| c1 | 593.70 | 24 | 108.25 | 479.00 | 921.25 | 1342.00 | 1490.50 | 1609.30 | 1639 | 542.59 | 5,937 |
| c2 | 602.00 | 13 | 67.00 | 613.00 | 1002.00 | 1321.50 | 1444.25 | 1600.05 | 1639 | 515.34 | 12,040 |

### Output sequence length (tokens)

| point | avg | min | p25 | p50 | p75 | p90 | p95 | p99 | max | std | total |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| c1 | 279.00 | 73 | 208.00 | 288.00 | 312.00 | 427.20 | 441.60 | 453.12 | 456 | 106.85 | 2,790 |
| c2 | 304.00 | 73 | 231.25 | 288.00 | 341.50 | 459.10 | 494.70 | 611.74 | 641 | 122.49 | 6,080 |

### OSL fidelity — measured vs. trace-declared

The endpoint honours `ignore_eos` / `min_tokens`, so measured OSL reproduces the trace exactly.

| point | declared mean / min / max | measured mean / min / max | mismatched requests | diff |
|---|---|---|--:|--:|
| c1 | 279.0 / 73 / 456 | **279.0 / 73 / 456** | 0 / 10 | 0.00 % |
| c2 | 304.0 / 73 / 641 | **304.0 / 73 / 641** | 0 / 20 | 0.00 % |

`osl_mismatch_count = 0`, `osl_mismatch_diff_pct = 0.0` on both points. Output length control is
verified working against this endpoint.

c1 and c2 differ in OSL because they consume different slices of the trace (`[2:12]` vs `[2:22]`),
not because the endpoint behaved differently.

## Latency detail (ms)

### Time to first token

| point | avg | min | p25 | p50 | p75 | p90 | p95 | p99 | max | std |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| c1 | 9,070.67 | 861.21 | 3,673.23 | 11,187.22 | 12,758.39 | 14,102.10 | 15,927.16 | 17,387.20 | 17,752.21 | 5,617.04 |
| c2 | 14,599.61 | 696.34 | 2,396.08 | 11,521.43 | 25,097.79 | 25,946.48 | 27,399.34 | 45,270.96 | 49,738.87 | 12,408.28 |

### Inter-token latency

| point | avg | min | p25 | p50 | p75 | p90 | p95 | p99 | max | std |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| c1 | 50.76 | 43.44 | 46.87 | 50.80 | 54.72 | 56.70 | 57.91 | 58.88 | 59.12 | 5.03 |
| c2 | 150.04 | 62.23 | 114.44 | 144.47 | 191.10 | 200.64 | 219.90 | 239.47 | 244.36 | 45.48 |

### Request latency (end to end)

| point | avg | min | p25 | p50 | p75 | p90 | p95 | p99 | max | std |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| c1 | 23,347.00 | 4,093.78 | 19,838.06 | 27,802.76 | 29,575.56 | 30,418.50 | 32,604.01 | 34,352.41 | 34,789.52 | 9,433.87 |
| c2 | 61,238.65 | 10,867.94 | 40,093.68 | 58,969.53 | 83,252.00 | 97,169.34 | 100,730.31 | 106,181.63 | 107,544.45 | 28,482.68 |

### Time to second token

| point | avg | min | p50 | p90 | p95 | p99 | max | std |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| c1 | 82.60 | 36.89 | 46.24 | 106.53 | 244.51 | 354.90 | 382.50 | 100.57 |
| c2 | **1,975.14** | 93.60 | 134.62 | 167.57 | 2,010.11 | 29,896.52 | 36,868.12 | 8,005.02 |

c2's p99 time-to-second-token of ~30 s indicates requests stalling immediately after their first
token — consistent with scheduler preemption rather than steady batched decode.

## Prefix cache

Server-reported, per point (`usage.prompt_tokens_details.cached_tokens`). `REMOTE=1` means the
cache was **not** reset between points, so c2 inherits whatever c1 left warm.

| point | prompt tokens | cache-read tokens | hit rate |
|---|--:|--:|--:|
| c1 | 5,937 | 3,600 | **60.64 %** |
| c2 | 12,040 | 4,848 | **40.27 %** |

`prefix.json` in each point directory is marked `{"unavailable": true}` — the run script only
understands vLLM's `vllm:prefix_cache_*` counters, not Dynamo's. The numbers above come from
aiperf's `overall_usage_prompt_cache_read_pct` instead.

## Repeatability — `c1` run twice, 90 minutes apart

Identical invocation (`REQS=10 WARMUP=2 POINTS=c1`), same trace slice `[2:12]`.
Run 1 started 05:55:10, run 2 started 07:27:52. No cache reset in between; unrelated traffic
(including one unique 3,862-token probe) hit the endpoint during the gap.

| metric | run 1 | run 2 | Δ |
|---|--:|--:|--:|
| benchmark duration (s) | 233.50 | 231.66 | −0.8 % |
| request throughput (req/s) | 0.042827 | 0.043157 | +0.8 % |
| output token throughput (tok/s) | 11.95 | 12.04 | +0.8 % |
| total token throughput (tok/s) | 37.37 | 37.67 | +0.8 % |
| TTFT avg (ms) | 9,070.67 | 9,086.89 | +0.2 % |
| TTFT p50 (ms) | 11,187.22 | 11,229.85 | +0.4 % |
| TTFT max (ms) | 17,752.21 | 17,686.77 | −0.4 % |
| ITL avg (ms) | 50.76 | 50.13 | −1.3 % |
| ITL p50 (ms) | 50.80 | 49.83 | −1.9 % |
| request latency avg (ms) | 23,347.00 | 23,163.59 | −0.8 % |
| request latency max (ms) | 34,789.52 | 33,574.20 | −3.5 % |
| output tok/s per user | 19.89 | 20.12 | +1.1 % |
| prefill tok/s per user | 53.94 | 53.88 | −0.1 % |
| time to second token avg (ms) | 82.60 | 43.35 | **−47.5 %** |
| time to second token p99 (ms) | 354.90 | 70.11 | **−80.2 %** |
| **total ISL / OSL (tokens)** | 5,937 / 2,790 | **5,937 / 2,790** | **0.0 %** |
| **prefix cache read (tokens)** | 3,600 | **3,600** | **0.0 %** |
| **prefix cache hit rate** | 60.64 % | **60.64 %** | **0.0 %** |
| `osl_mismatch_count` | 0 | 0 | — |

ISL and OSL are bit-identical across every percentile — the trace replay and the endpoint's
output-length control are fully deterministic. Latency metrics land within ±1.3 %.

**Cross-run prefix cache carryover is zero.** Cache-read tokens are exactly 3,600 in both runs,
so all cache hits originate *within* a run (later turns of a session hitting earlier turns'
prefixes); nothing survived from run 1 into run 2. This is evidence against cross-round
contamination — but weak evidence: 90 minutes elapsed and a unique 3,862-token prompt was sent in
between, either of which could have evicted the blocks. It says nothing about two rounds run
back to back.

The one metric that moved is time-to-second-token: run 1 had a few requests stall briefly after
their first token, run 2 had none. At n=10 this is not conclusive, but it points the same
direction as the c2 preemption behaviour.

## `agent_flat` — c1, 10 requests

Same point shape as `chatbot_flat` c1 (concurrency 1, 10 requests, warmup 2, trace slice `[2:12]`),
so the two are directly comparable and isolate the effect of prompt size. Run 16:28:47, 314.7 s,
0 errors. Dataset `nvfp4_agent_flat.jsonl`; all 12 consumed entries fit under the 4096 cap
(largest ISL+OSL = 3,400).

| metric | `chatbot_flat` c1 | `agent_flat` c1 |
|---|--:|--:|
| ISL avg / total (tokens) | 593.70 / 5,937 | **1,686.40 / 16,864** |
| OSL avg / total (tokens) | 279.00 / 2,790 | 234.40 / 2,344 |
| prefix cache hit rate | 60.64 % | **74.28 %** (12,527 tok) |
| TTFT avg (ms) | 9,070.67 | **17,774.00** |
| ITL avg (ms) | 50.76 | 57.42 |
| request latency avg (ms) | 23,347.00 | 31,468.99 |
| request throughput (req/s) | 0.0428 | 0.0318 |
| output token throughput (tok/s) | 11.95 | 7.45 |
| total token throughput (tok/s) | 37.37 | **61.03** |
| output tok/s per user | 19.89 | 17.54 |
| time to second token avg (ms) | 82.60 | 43.34 |
| benchmark duration (s) | 233.50 | 314.73 |
| `osl_mismatch_count` | 0 | 0 |

### Sequence lengths

| metric | avg | min | p50 | p90 | p99 | max | std |
|---|--:|--:|--:|--:|--:|--:|--:|
| input sequence length | 1,686.40 | 462 | 1,781.50 | 2,471.30 | 2,927.33 | 2,978 | 699.79 |
| output sequence length | 234.40 | 114 | 153.50 | 423.40 | 434.74 | 436 | 130.35 |

Measured OSL total (2,344) equals the trace-declared total for entries `[2:12]` exactly.

### Latency

| metric | avg | min | p50 | p90 | p99 | max | std |
|---|--:|--:|--:|--:|--:|--:|--:|
| time to first token (ms) | 17,774.00 | 6,174.13 | 15,409.15 | 27,827.55 | 44,479.09 | 46,329.26 | 11,270.58 |
| inter-token latency (ms) | 57.42 | 48.60 | 57.20 | 63.95 | 64.13 | 64.14 | 4.75 |
| request latency (ms) | 31,468.99 | 12,672.27 | 25,653.05 | 52,969.29 | 54,528.11 | 54,701.31 | 15,951.76 |
| time to second token (ms) | 43.34 | 9.29 | 44.35 | 62.43 | 80.05 | 82.00 | 21.46 |
| output tok/s per user | 17.54 | 15.59 | 17.48 | 19.12 | 20.43 | 20.58 | 1.50 |
| prefill tok/s per user | 130.88 | 26.40 | 113.12 | 221.53 | 319.09 | 329.92 | 87.42 |

Note `prefill_throughput_per_user` is computed by aiperf as raw ISL ÷ TTFT, so prefix-cache hits
inflate it. It is not the machine's real prefill rate — see below.

`agent_flat` posts the highest *total* token throughput of any point here (61.03 tok/s) purely
because 74 % of its prompt tokens are cache hits and cost almost nothing. Its *request*
throughput is the worst (0.0318 req/s). Reading total token throughput alone would invert the
ranking.

Unlike c2, `agent_flat` c1 shows no post-first-token stalls (time-to-second-token max 82 ms),
confirming the c2 stall behaviour is triggered by concurrency, not by prompt size.

## Prefill cost — corrected

An earlier revision of this document called prefill "superlinearly slow", comparing raw ISL
against TTFT. That was wrong: it ignored prefix-cache hits, which mean most of the declared ISL
is never actually computed. Recomputing against *uncached* tokens only:

| sample | ISL | cache hit rate | uncached tokens | TTFT | **effective prefill rate** |
|---|--:|--:|--:|--:|--:|
| `chatbot_flat` c1 | 593.7 | 60.64 % | ≈233.6 | 9.07 s | **25.8 tok/s** |
| `agent_flat` c1 | 1,686.4 | 74.28 % | ≈433.7 | 17.77 s | **24.4 tok/s** |
| single 3,862-token probe | 3,862 | ~0 % | 3,859 | 186.6 s | **20.7 tok/s** |

Across an order of magnitude in prompt size the effective rate stays in a 21–26 tok/s band.
Prefill scales linearly in uncached tokens; the rate itself is simply very low. This is a
cleaner diagnosis than "some size threshold triggers a pathological path" — the whole prefill
path is slow.

## No-warmup runs (`WARMUP=0`, `REQS=20`, c1) — cache-contamination check

Three points run back to back at 17:03–17:31, concurrency 1, 20 requests, **no warmup phase**
(trace slice `[0:20]`). The third point repeats the first verbatim, with an entire `agent_flat`
run in between, to test whether one round's prefix cache contaminates the next.

| metric | chatbot #1 | agent | **chatbot #2 (repeat)** |
|---|--:|--:|--:|
| ISL total (tokens) | 11,698 | 33,160 | **11,698** |
| OSL total (tokens) | 5,970 | 4,766 | **5,970** |
| ISL avg / p50 / max | 584.90 / 439.00 / 1,639 | 1,658.00 / 1,579.50 / 3,124 | 584.90 / 439.00 / 1,639 |
| OSL avg / p50 / max | 298.50 / 288.00 / 641 | 238.30 / 153.50 / 452 | 298.50 / 288.00 / 641 |
| **cache-read tokens** | **7,224** | 23,010 | **7,224** |
| **cache hit rate** | **61.75 %** | 69.39 % | **61.75 %** |
| TTFT avg / p50 / p99 (ms) | 8,693.71 / 10,015.69 / 16,938.74 | 20,617.85 / 16,668.00 / 62,875.49 | 8,705.66 / 10,072.60 / 16,959.16 |
| ITL avg / p99 (ms) | 49.90 / 57.97 | 57.93 / 68.38 | 50.31 / 58.72 |
| request latency avg / p99 (ms) | 23,583.99 / 33,579.58 | 34,705.85 / 86,639.42 | 23,698.45 / 33,804.26 |
| output tok/s per user | 20.22 | 17.42 | 20.04 |
| request throughput (req/s) | 0.0424 | 0.0288 | 0.0422 |
| output token throughput (tok/s) | 12.65 | 6.86 | 12.59 |
| total token throughput (tok/s) | 37.45 | 54.62 | 37.27 |
| duration (s) | 471.83 | 694.41 | 474.11 |
| errors | 0 | 0 | 0 |
| `osl_mismatch_count` | 0 | 0 | 0 |

### Cross-round prefix cache carryover: none measurable

chatbot #1 and chatbot #2 report **identical cache-read tokens (7,224) and identical hit rate
(61.75 %)**, despite a full `agent_flat` run consuming 33,160 prompt tokens in between. TTFT avg
differs by 0.14 %, duration by 0.48 %.

Dynamo's Prometheus counters, sampled around each point, agree exactly with aiperf's per-request
`usage.prompt_tokens_details.cached_tokens`:

| stage | Δ cached tokens | Δ input tokens |
|---|--:|--:|
| chatbot #1 | +7,224 | +11,698 |
| agent | +23,010 | +33,160 |
| chatbot #2 | **+7,224** | **+11,698** |

Two independent measurement paths, same numbers.

**Interpretation.** The 61.75 % hit rate is entirely *intra-run* — later turns of a session hitting
the prefixes of earlier turns of the same session. That is part of the workload definition for a
`messages`-mode flat trace, not contamination. Nothing carries over between rounds. Together with
the earlier `c1` repeat 90 minutes apart (3,600 cache-read tokens both times), rounds on this
endpoint are effectively independent and **no cache flush is needed between them**.

**Side inference on KV cache capacity.** The `agent_flat` round introduced roughly 10,150 tokens
of previously unseen prefix, and that was enough to evict chatbot's blocks completely. Under a
plain LRU policy that puts the usable prefix cache on the order of ten thousand tokens — small.
This is an inference, not a measurement: an idle TTL on cached blocks, or a scoping limit in
Dynamo's prefix sharing, would produce the same observation. Confirming it requires the worker's
startup log.

`agent_flat` at 20 requests reaches TTFT p99 62,875 ms / max 66,761 ms, up from 44,479 / 46,329 at
10 requests, as ISL max rises from 2,978 to 3,124 — close to the 4096 ceiling. The slow prefill
path dominates increasingly as prompts grow.

Artifacts: `results/nvfp4/w0_chatbot/`, `results/nvfp4/w0_agent/`, `results/nvfp4/w0_chatbot_rep/`,
log `results/nvfp4/w0_run.log`.

## Observations

1. **Negative concurrency scaling.** c1 → c2 doubles offered load and aggregate throughput drops
   24 %. ITL nearly triples (50.8 → 150.0 ms). Two in-flight requests are not being batched
   productively.
2. **Prefill is linear but uniformly slow — ≈25 tok/s on uncached tokens.** Measured across three
   samples spanning an order of magnitude in prompt size (see *Prefill cost* below). This is one
   to two orders of magnitude below what a 3B-activated MoE on CUDA should do, and it dominates
   every latency number in this document.
3. **Decode is slow even unloaded.** c1 ITL 50.8 ms ≈ 19.7 tok/s per user, low for a 30B-A3B MoE
   (≈3B activated) on CUDA.
4. **The endpoint wedges under load.** An earlier `c32` attempt (warmup 16 concurrent) left the
   worker accepting requests at the frontend but emitting zero tokens for ~25 minutes; it
   recovered on its own at 13:54 local. `dynamo_frontend_requests_total{status="success"}` stayed
   frozen throughout while `error_type="cancelled"` climbed.
5. **Context is capped at 4096**, which is a serving-config limit, not a model limit —
   Qwen3-VL-30B-A3B-Instruct supports far more. This blocks 4 of the 5 flat workloads.

## Workload feasibility at 4096 context

Token counts measured with a Qwen3-family tokenizer over the shipped datasets.

| workload | n | ISL max | ISL p50 | OSL max | ISL+OSL max | entries over 4096 |
|---|--:|--:|--:|--:|--:|--:|
| `chatbot_flat` | 384 | 2,112 | 522 | 870 | **2,431** | **0 / 384** ✅ |
| `agent_flat` | 384 | 13,004 | 2,261 | 1,381 | 13,232 | 107 / 384 |
| `coding_flat` | 384 | 89,391 | 28,853 | 2,048 | 89,431 | 384 / 384 |
| `rag` | 500 | 31,427 | 4,975 | 2,048 | 33,475 | 500 / 500 |
| `toolagent` | 320 | 120,633 | 6,513 | 929 | 121,213 | 228 / 320 |

Required `--max-model-len` to unlock each: 16k → `agent_flat`; 40k → `rag`; 96k → `coding_flat`;
**128k → all five**.

## Reproduce

```bash
cd ~/benchmark
COMMON='REMOTE=1 NODE=qwen3vl_ngrok SERVED_NAME=Qwen3-VL-30B-A3B-Instruct-optimumxt
        URL=https://poppy-zero-ritzy.ngrok-free.dev
        TOKENIZER=Qwen/Qwen3-VL-30B-A3B-Instruct
        OUTBASE=results/nvfp4/qwen3vl_ngrok WARMUP=2 RC_TLIM=900'

env $COMMON REQS=10 POINTS="c1" bash scripts/run_nvfp4.sh chatbot_flat
env $COMMON REQS=20 POINTS="c2" bash scripts/run_nvfp4.sh chatbot_flat

# repeat run — needs a fresh OUTBASE, else the script skips points that already
# have a non-empty profile_export_aiperf.json
env $COMMON REQS=10 POINTS="c1" OUTBASE=results/nvfp4/qwen3vl_ngrok_run2 \
  bash scripts/run_nvfp4.sh chatbot_flat

# agent_flat — needs a larger tlimit, its ISL is 2.8x chatbot's
env $COMMON REQS=10 POINTS="c1" RC_TLIM=1800 bash scripts/run_nvfp4.sh agent_flat

# no-warmup, 20 requests. WARMUP=0 requires the scripts/run_nvfp4.sh fix that omits
# --warmup-request-count entirely; aiperf rejects the flag with value 0.
W0='REMOTE=1 NODE=qwen3vl_ngrok SERVED_NAME=Qwen3-VL-30B-A3B-Instruct-optimumxt
    URL=https://poppy-zero-ritzy.ngrok-free.dev
    TOKENIZER=Qwen/Qwen3-VL-30B-A3B-Instruct
    WARMUP=0 RC_TLIM=2700 REQS=20 POINTS=c1'
env $W0 OUTBASE=results/nvfp4/w0_chatbot     bash scripts/run_nvfp4.sh chatbot_flat
env $W0 OUTBASE=results/nvfp4/w0_agent       bash scripts/run_nvfp4.sh agent_flat
env $W0 OUTBASE=results/nvfp4/w0_chatbot_rep bash scripts/run_nvfp4.sh chatbot_flat
```

Raw artifacts:
- `results/nvfp4/qwen3vl_ngrok/chatbot_flat/{c1,c2}/profile_export_aiperf.json`
- `results/nvfp4/qwen3vl_ngrok_run2/chatbot_flat/c1/profile_export_aiperf.json`
- `results/nvfp4/qwen3vl_ngrok/agent_flat/c1/profile_export_aiperf.json`
