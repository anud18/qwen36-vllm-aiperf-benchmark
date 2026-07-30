# Result tables — `Llama-3.1-8B-Instruct-optimumxt`, 100 requests, c1 and c2

Endpoint `https://arena-iii-chains-rings.trycloudflare.com` → NVIDIA Dynamo,
worker `192.168.8.51:42471`, `device_type=cuda`, context **4096**.
Flat-trace track, `REMOTE=1`, **`WARMUP=0`**, **`REQS=100`**, trace slice `[0:100]` of the
filtered datasets. OSL pinned to the trace via in-data `ignore_eos`. aiperf 0.10.0.
Run 2026-07-30 03:23 → 07:45.

Points were run **alternating workloads** as requested — chatbot c1 → agent c1 → chatbot c2 →
agent c2 — so no round is preceded by the same workload.

> Alternating is not actually required on this deployment. The cold-cache repeat documented in
> `TABLES_llama31_cf.md` showed cross-round prefix-cache carryover is zero: a restarted worker
> with a provably empty KV cache reported the identical cache-read total. Alternating costs
> nothing, so it was done as asked, but it does not change the numbers.

## Filtered datasets

Entries whose `ISL + OSL` exceeds the 4096 context cap were removed, tokenising with the Llama 3.1
tokenizer. Written to `datasets/aiperf/le4096/` by `scripts/filter_le4096.py`; the originals are
untouched, and the run picked them up via `DATA_DIR`.

Only the agent file is committed — `chatbot_flat` lost nothing, so its filtered copy is
byte-identical to `datasets/aiperf/nvfp4_chatbot_flat.jsonl`. Regenerate it with:

```bash
python3 scripts/filter_le4096.py --tokenizer NousResearch/Meta-Llama-3.1-8B-Instruct
```

Filtering is tokenizer-dependent — rerun it before benchmarking a different model.

| dataset | kept | dropped | first 100 entries: ISL sum / avg / max | ISL+OSL max |
|---|--:|--:|---|--:|
| `nvfp4_chatbot_flat.jsonl` | 384 / 384 | 0 | 63,046 / 630.5 / 1,926 | 2,197 |
| `nvfp4_agent_flat.jsonl` | 279 / 384 | **105** | 160,941 / 1,609.4 / 3,807 | 3,987 |

> **Filtered `agent_flat` is a new workload.** Dropping 105 long entries shifts the composition
> toward shorter prompts. Do not compare these agent numbers with the unfiltered `agent_flat` runs
> in `TABLES_w0.md` or `TABLES_llama31_cf.md`. `chatbot_flat` lost nothing, so it remains the same
> workload at a larger request count.

## Validity

| point | completed | errors |
|---|--:|---|
| `chatbot_flat` c1 | **100 / 100** | none |
| `chatbot_flat` c2 | **100 / 100** | none |
| `agent_flat` c1 | 97 / 100 | 3 × HTTP 524 |
| `agent_flat` c2 | 90 / 100 | 10 × HTTP 524 |

`osl_mismatch_count = 0` on all four points — output-length control held throughout.

**The 524s bias the agent numbers optimistically, and not by 3 % / 10 %.** HTTP 524 is
Cloudflare's origin-response timeout (~100 s on a free quick tunnel). It does not drop requests at
random: it drops precisely the *slowest* ones. Every agent latency figure below is therefore a
distribution with its right tail cut off — the true avg, p90, p95 and p99 are all higher than
shown, and `max` is capped near the tunnel's limit rather than by the server. The two chatbot
points are unaffected and are the only fully trustworthy rows here.

## Distribution metrics

**TPOT = ITL** — aiperf's `inter_token_latency` is `(request_latency − TTFT) / (OSL − 1)`, the
standard time-per-output-token. One row, both labels. **p50 is the median.**

| workload | point | metric | avg | p50 (median) | p90 | p95 | p99 | min | max | std |
|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|
| `chatbot_flat` | c1 | TTFT (ms) | 10,970.88 | 10,847.18 | 20,745.14 | 23,313.58 | 31,551.52 | 538.55 | 32,093.94 | 7,607.81 |
| `chatbot_flat` | c2 | TTFT (ms) | 17,821.75 | 13,533.17 | 35,059.38 | 43,280.31 | 62,304.22 | 556.12 | 73,673.68 | 15,373.04 |
| `agent_flat` | c1 | TTFT (ms) | 23,615.90 | 16,205.08 | 49,218.56 | 71,024.09 | 111,973.84 | 3,129.86 | 114,246.44 | 21,021.59 |
| `agent_flat` | c2 | TTFT (ms) | 45,671.64 | 36,831.28 | 94,558.53 | 113,410.14 | 120,419.13 | 3,143.20 | 124,727.75 | 31,156.01 |
| `chatbot_flat` | c1 | ITL = TPOT (ms) | 67.36 | 66.94 | 69.85 | 71.01 | 71.29 | 63.46 | 72.50 | 1.94 |
| `chatbot_flat` | c2 | ITL = TPOT (ms) | 181.71 | 156.42 | 278.60 | 295.55 | 566.31 | 86.78 | 1,054.03 | 115.35 |
| `agent_flat` | c1 | ITL = TPOT (ms) | 70.03 | 69.67 | 73.68 | 74.18 | 74.99 | 65.02 | 75.45 | 2.35 |
| `agent_flat` | c2 | ITL = TPOT (ms) | 333.43 | 261.24 | 510.17 | 736.99 | 1,449.74 | 109.12 | 2,606.46 | 315.64 |
| `chatbot_flat` | c1 | E2E request latency (ms) | 27,572.77 | 27,561.93 | 45,387.10 | 46,982.88 | 54,997.10 | 3,386.96 | 65,396.94 | 12,837.09 |
| `chatbot_flat` | c2 | E2E request latency (ms) | 62,530.21 | 62,220.89 | 108,834.38 | 114,921.58 | 120,162.59 | 5,192.12 | 164,584.04 | 33,860.38 |
| `agent_flat` | c1 | E2E request latency (ms) | 38,451.12 | 30,749.06 | 72,552.07 | 88,281.03 | 116,602.65 | 13,619.28 | 120,922.17 | 24,059.89 |
| `agent_flat` | c2 | E2E request latency (ms) | 107,986.32 | 102,804.32 | 173,008.25 | 208,571.18 | 243,722.11 | 11,034.19 | 248,798.37 | 54,486.78 |
| `chatbot_flat` | c1 | ISL (tokens) | 655.5 | 552.0 | 1,471.8 | 1,583.3 | 1,832.2 | 40.0 | 1,951.0 | 534.4 |
| `chatbot_flat` | c2 | ISL (tokens) | 655.5 | 552.0 | 1,471.8 | 1,583.3 | 1,832.2 | 40.0 | 1,951.0 | 534.4 |
| `agent_flat` | c1 | ISL (tokens) | 1,601.1 | 1,448.0 | 2,733.4 | 2,904.2 | 3,092.0 | 406.0 | 3,309.0 | 749.6 |
| `agent_flat` | c2 | ISL (tokens) | 1,562.1 | 1,444.0 | 2,600.8 | 2,852.8 | 3,089.7 | 406.0 | 3,309.0 | 711.4 |
| `chatbot_flat` | c1 | OSL (tokens) | 247.2 | 238.5 | 446.1 | 487.8 | 651.9 | 10.0 | 740.0 | 147.9 |
| `chatbot_flat` | c2 | OSL (tokens) | 247.2 | 238.5 | 446.1 | 487.8 | 651.9 | 10.0 | 740.0 | 147.9 |
| `agent_flat` | c1 | OSL (tokens) | 212.3 | 171.0 | 395.4 | 436.0 | 525.0 | 33.0 | 669.0 | 123.8 |
| `agent_flat` | c2 | OSL (tokens) | 215.6 | 179.0 | 414.4 | 436.0 | 540.0 | 33.0 | 669.0 | 124.0 |
| `chatbot_flat` | c1 | Per-user output throughput (tok/s) | 14.86 | 14.94 | 15.41 | 15.52 | 15.61 | 13.79 | 15.76 | 0.42 |
| `chatbot_flat` | c2 | Per-user output throughput (tok/s) | 6.62 | 6.39 | 9.07 | 9.13 | 9.23 | 0.95 | 11.52 | 2.31 |
| `agent_flat` | c1 | Per-user output throughput (tok/s) | 14.30 | 14.35 | 14.89 | 15.06 | 15.20 | 13.25 | 15.38 | 0.48 |
| `agent_flat` | c2 | Per-user output throughput (tok/s) | 4.49 | 3.83 | 8.83 | 8.99 | 9.07 | 0.38 | 9.16 | 2.57 |

## Aggregate metrics

| metric | `chatbot_flat` c1 | `chatbot_flat` c2 | `agent_flat` c1 | `agent_flat` c2 |
|---|--:|--:|--:|--:|
| Request throughput (req/s) | 0.0363 | 0.0319 | 0.0236 | 0.0158 |
| Output token throughput (tok/s) | 8.97 | 7.89 | 5.02 | 3.30 |
| Total token throughput (tok/s) | 32.73 | 28.82 | 42.85 | 27.21 |
| E2E output token throughput (tok/s) | 9.05 | 4.33 | 6.06 | 2.14 |
| Total ISL (tokens) | 65,546 | 65,546 | 155,303 | 135,900 |
| Total OSL (tokens) | 24,723 | 24,723 | 20,589 | 18,759 |
| Prefix cache hit rate (%) | 67.04 | 46.77 | 72.32 | 47.82 |
| Cache-read tokens | 43,941 | 30,653 | 112,316 | 64,988 |
| Benchmark duration (s) | 2,757.64 | 3,132.16 | 4,105.14 | 5,683.69 |
| Requests completed | 100 / 100 | 100 / 100 | 97 / 100 | 90 / 100 |
| OSL mismatches | 0 | 0 | 0 | 0 |

## c1 → c2 scaling

`chatbot_flat` is the clean comparison: identical 100 requests, zero errors on both points.

| metric | c1 | c2 | Δ |
|---|--:|--:|--:|
| request throughput (req/s) | 0.0363 | 0.0319 | **−12.1 %** |
| output token throughput (tok/s) | 8.97 | 7.89 | −12.0 % |
| E2E output token throughput (tok/s) | 9.05 | 4.33 | −52.2 % |
| TTFT avg (ms) | 10,970.88 | 17,821.75 | +62.4 % |
| ITL = TPOT avg (ms) | 67.36 | 181.71 | **+169.7 %** |
| E2E latency avg (ms) | 27,572.77 | 62,530.21 | +126.8 % |
| per-user output throughput (tok/s) | 14.86 | 6.62 | −55.5 % |
| duration (s) | 2,757.64 | 3,132.16 | +13.6 % |

**Doubling concurrency again reduces aggregate throughput and takes longer in wall clock.** Total
work is fixed at 100 requests, so c2 should finish sooner if concurrency helped at all; it finished
13.6 % later. This reproduces at 100 requests what the 20-request runs showed, and the ITL blow-up
(+170 %) is the mechanism: the two in-flight requests are not batched, they interleave and starve
each other. `agent_flat` shows the same shape more severely (ITL 70.03 → 333.43 ms), though its
numbers are truncated by the 524s.

## Prefix cache

| point | prompt tokens | cache-read tokens | hit rate |
|---|--:|--:|--:|
| `chatbot_flat` c1 | 65,546 | 43,941 | 67.04 % |
| `chatbot_flat` c2 | 65,546 | 30,653 | 46.77 % |
| `agent_flat` c1 | 155,303 | 112,316 | 72.32 % |
| `agent_flat` c2 | 135,900 | 64,988 | 47.82 % |

Identical ISL totals for the two chatbot points but very different hit rates (67.04 % vs 46.77 %)
— the same effect seen at 20 requests. At c2 two sessions are in flight simultaneously, so a
turn often starts before the earlier turn of its own session has finished writing its blocks, and
the prefix that would have been reused is not there yet. Concurrency reduces achievable cache
reuse for this workload shape; it is not a measurement artefact.

## Effective prefill rate

Computed against *uncached* tokens only. Chatbot rows only — agent's TTFT is truncated by the
tunnel timeouts.

| point | ISL avg | cache hit rate | uncached tokens | TTFT avg | effective prefill |
|---|--:|--:|--:|--:|--:|
| `chatbot_flat` c1 | 655.5 | 67.04 % | ≈216.1 | 10.97 s | **19.7 tok/s** |
| `chatbot_flat` c2 | 655.5 | 46.77 % | ≈348.9 | 17.82 s | **19.6 tok/s** |

Still ≈19–20 tok/s, unchanged from the 20-request runs and matching the other Llama points. Note
the two rows agree despite very different cache hit rates — which is what makes the uncached-token
normalisation the right way to read this metric.

## Reproduce

```bash
cd ~/benchmark
R100='REMOTE=1 NODE=llama31_cf SERVED_NAME=Llama-3.1-8B-Instruct-optimumxt
      URL=https://arena-iii-chains-rings.trycloudflare.com
      TOKENIZER=NousResearch/Meta-Llama-3.1-8B-Instruct
      DATA_DIR=datasets/aiperf/le4096
      WARMUP=0 RC_TLIM=9000 REQS=100'
for step in "chatbot_flat c1" "agent_flat c1" "chatbot_flat c2" "agent_flat c2"; do
  set -- $step
  env $R100 POINTS="$2" OUTBASE="results/nvfp4/r100_$1_$2" bash scripts/run_nvfp4.sh "$1"
done
```

`WARMUP=0` requires the `scripts/run_nvfp4.sh` fix that omits `--warmup-request-count` entirely.

Artifacts: `results/nvfp4/r100_{chatbot_flat,agent_flat}_{c1,c2}/`, log `results/nvfp4/r100_run.log`.
Filtered datasets: `datasets/aiperf/le4096/`.
