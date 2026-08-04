# Output file index — `optimumxt` endpoint benchmarks, 2026-07-29

Every artifact produced while benchmarking the two `optimumxt` deployments on
`192.168.8.51` (NVIDIA Dynamo, context 4096). All paths are relative to
`~/benchmark/results/nvfp4/`.

Two models were measured on the same physical box through two different tunnels:

| # | model | tunnel | status |
|---|---|---|---|
| A | `Qwen3-VL-30B-A3B-Instruct-optimumxt` | ngrok — `poppy-zero-ritzy.ngrok-free.dev` | **dead**, monthly bandwidth quota exhausted (`ERR_NGROK_725`) |
| B | `Llama-3.1-8B-Instruct-optimumxt` | Cloudflare — `athens-move-ted-convertible.trycloudflare.com` | **dead** — trycloudflare quick tunnels are ephemeral, DNS record gone |
| B′ | `Llama-3.1-8B-Instruct-optimumxt` | Cloudflare — `arena-iii-chains-rings.trycloudflare.com` | same model and box, worker restarted (port 38103 → 42471) |


> **Reproduced locally.** Every point here was re-run on spark against a local vLLM at the same
> 4096 context, with ISL matched exactly. See [`SPARK_REPRO.md`](SPARK_REPRO.md) — the endpoint's
> prefill turns out to be 30–237× slower than the same model on the same box.

## Reports (start here)

| file | contents |
|---|---|
| [`qwen3vl_ngrok/RESULTS.md`](qwen3vl_ngrok/RESULTS.md) | Full narrative report for model A — config, methodology caveats, all points, repeatability, prefix-cache analysis, prefill diagnosis, workload feasibility at 4096 context |
| [`TABLES_w0.md`](TABLES_w0.md) | Result tables for the `WARMUP=0 / REQS=20 / c1` series on model A (TTFT, ITL=TPOT, E2E, ISL, OSL, req/s, token throughput; avg / p50 / p90 / p95 / p99 / min / max / std) |
| [`TABLES_llama31_cf.md`](TABLES_llama31_cf.md) | Same tables for model B, plus the cross-model comparison at identical settings |
| [`TABLES_r100.md`](TABLES_r100.md) | 100-request series on model B — chatbot and agent at c1 and c2, run alternating, on context-filtered datasets |
| [`SPARK_REPRO.md`](SPARK_REPRO.md) | Local reproduction of all these points on spark against vLLM, with endpoint and spark figures side by side |
| `INDEX_optimumxt.md` | This file |
| [`DATASETS_optimumxt.md`](DATASETS_optimumxt.md) | Dataset description — format, real content, session structure, ISL/OSL per tokenizer and slice, prefix-cache rate theory vs measured |
| [`SPARK_INDEX.md`](SPARK_INDEX.md) | Index of the spark reproduction artifacts — all 26 local points, scripts and datasets |

Metric formulas for every aiperf field, verified against the raw per-request records:
[`SPARK_REPRO.md` § Metric definitions](SPARK_REPRO.md#metric-definitions).

Dataset contents, ISL/OSL distributions and prefix-cache characteristics:
[`DATASETS_optimumxt.md`](DATASETS_optimumxt.md).

## Benchmark points

Every point directory contains the same ten files — see *Artifact layout* below.

### Model A — Qwen3-VL-30B-A3B via ngrok

| point directory | workload | conc. | reqs | warmup | slice | duration | valid |
|---|---|--:|--:|--:|---|--:|---|
| [`qwen3vl_ngrok/chatbot_flat/c1/`](qwen3vl_ngrok/chatbot_flat/c1/) | chatbot_flat | 1 | 10 | 2 | `[2:12]` | 233.5 s | ✅ |
| [`qwen3vl_ngrok/chatbot_flat/c2/`](qwen3vl_ngrok/chatbot_flat/c2/) | chatbot_flat | 2 | 20 | 2 | `[2:22]` | 615.9 s | ✅ |
| [`qwen3vl_ngrok_run2/chatbot_flat/c1/`](qwen3vl_ngrok_run2/chatbot_flat/c1/) | chatbot_flat | 1 | 10 | 2 | `[2:12]` | 231.7 s | ✅ repeat of the above, 90 min later |
| [`qwen3vl_ngrok/agent_flat/c1/`](qwen3vl_ngrok/agent_flat/c1/) | agent_flat | 1 | 10 | 2 | `[2:12]` | 314.7 s | ✅ |
| [`w0_chatbot/chatbot_flat/c1/`](w0_chatbot/chatbot_flat/c1/) | chatbot_flat | 1 | 20 | **0** | `[0:20]` | 471.8 s | ✅ |
| [`w0_agent/agent_flat/c1/`](w0_agent/agent_flat/c1/) | agent_flat | 1 | 20 | **0** | `[0:20]` | 694.4 s | ✅ |
| [`w0_chatbot_rep/chatbot_flat/c1/`](w0_chatbot_rep/chatbot_flat/c1/) | chatbot_flat | 1 | 20 | **0** | `[0:20]` | 474.1 s | ✅ cache-carryover probe |
| [`w0_agent/agent_flat/c2/`](w0_agent/agent_flat/c2/) | agent_flat | 2 | 20 | **0** | `[0:20]` | 646.0 s | ❌ **INVALID** — 6/20 requests got ngrok 403 `ERR_NGROK_725` |
| [`qwen3vl_ngrok/chatbot_flat/c32/`](qwen3vl_ngrok/chatbot_flat/c32/) | chatbot_flat | 32 | 320 | 16 | `[16:336]` | — | ❌ **INVALID** — worker wedged, run aborted, no summary produced |

### Model B — Llama-3.1-8B via Cloudflare

| point directory | workload | conc. | reqs | warmup | slice | duration | valid |
|---|---|--:|--:|--:|---|--:|---|
| [`cf_llama31_chatbot/chatbot_flat/c1/`](cf_llama31_chatbot/chatbot_flat/c1/) | chatbot_flat | 1 | 20 | **0** | `[0:20]` | 637.6 s | ✅ |
| [`cf_llama31_agent/agent_flat/c1/`](cf_llama31_agent/agent_flat/c1/) | agent_flat | 1 | 20 | **0** | `[0:20]` | 876.5 s | ✅ |
| [`cf_llama31_chatbot_rep/chatbot_flat/c1/`](cf_llama31_chatbot_rep/chatbot_flat/c1/) | chatbot_flat | 1 | 20 | **0** | `[0:20]` | 625.5 s | ✅ repeat, cold cache after worker restart |

### Model B′ — Llama-3.1-8B, 100 requests, filtered datasets

Run alternating (chatbot c1 → agent c1 → chatbot c2 → agent c2) on 2026-07-30 03:23–07:45,
against `datasets/aiperf/le4096/` — entries over the 4096 cap removed.

| point directory | workload | conc. | reqs | warmup | slice | duration | valid |
|---|---|--:|--:|--:|---|--:|---|
| [`r100_chatbot_flat_c1/`](r100_chatbot_flat_c1/) | chatbot_flat | 1 | 100 | **0** | `[0:100]` | 2,757.6 s | ✅ 100/100 |
| [`r100_agent_flat_c1/`](r100_agent_flat_c1/) | agent_flat | 1 | 100 | **0** | `[0:100]` | 4,105.1 s | ⚠️ 97/100 — 3 × Cloudflare 524 |
| [`r100_chatbot_flat_c2/`](r100_chatbot_flat_c2/) | chatbot_flat | 2 | 100 | **0** | `[0:100]` | 3,132.2 s | ✅ 100/100 |
| [`r100_agent_flat_c2/`](r100_agent_flat_c2/) | agent_flat | 2 | 100 | **0** | `[0:100]` | 5,683.7 s | ⚠️ 90/100 — 10 × Cloudflare 524 |

The 524s are the tunnel's ~100 s origin timeout. They drop the *slowest* requests, so the agent
latency distributions are truncated on the right and read optimistically — the true avg and upper
percentiles are higher than reported. Both chatbot points are clean.

## Driver logs

| file | what it covers |
|---|---|
| [`qwen3vl_ngrok_run.log`](qwen3vl_ngrok_run.log) | first `c32` attempt — the run that wedged the worker |
| [`qwen3vl_ngrok_c1c2.log`](qwen3vl_ngrok_c1c2.log) | recovery watcher + `c1` (10 reqs) and `c2` (20 reqs) |
| [`qwen3vl_ngrok_run2.log`](qwen3vl_ngrok_run2.log) | `c1` repeat for reproducibility |
| [`qwen3vl_ngrok_agent.log`](qwen3vl_ngrok_agent.log) | `agent_flat` `c1`, 10 requests |
| [`w0_run.log`](w0_run.log) | the three `WARMUP=0` points, with Dynamo `cached_tokens` sampled around each |
| [`w0_agent_c2.log`](w0_agent_c2.log) | `agent_flat` `c2` — the point killed by the ngrok quota |
| [`cf_llama31_run.log`](cf_llama31_run.log) | both Cloudflare / Llama points |
| [`cf_llama31_chatbot_rep.log`](cf_llama31_chatbot_rep.log) | `chatbot_flat` c1 repeat on the second tunnel, cold cache |
| [`r100_run.log`](r100_run.log) | the four alternating 100-request points, with per-point start/end timestamps |

## Artifact layout

Each point directory holds:

| file | contents |
|---|---|
| `profile_export_aiperf.json` | aiperf summary — every metric with avg/percentiles. **Its existence marks the point complete**; the run script skips points that already have it |
| `profile_export_aiperf.csv` | same summary, CSV |
| `profile_export.jsonl` | **per-request records** — one line per request with TTFT, ITL, latency, ISL, OSL, `usage_prompt_cache_read_tokens`, timestamps, worker id |
| `inputs.json` | the exact payloads aiperf sent, in order |
| [`run.log`](run.log) | aiperf stdout, including phase transitions and any HTTP errors |
| `logs/aiperf.log` | aiperf's internal debug log |
| `meta.json` | node, workload, point, start/end epoch, request count, warmup, attempt number, `remote: true` |
| `prefix.json` | `{"unavailable": true}` on every point — the run script reads vLLM's `vllm:prefix_cache_*` counters, which Dynamo does not expose. **Use `overall_usage_prompt_cache_read_pct` from the aiperf summary instead** |
| `server_metrics_export.{json,csv}` | server-side metrics aiperf scraped |
| `gpu_telemetry_export.jsonl` | GPU telemetry, only present on the aborted `c32` point |

The aborted `c32` directory has no `profile_export_aiperf.json`, `meta.json` or
`prefix.json` — the run never reached a summary.

## Datasets consumed

Unmodified from the repo; no dataset was rebuilt during this work.

| file | entries | used by |
|---|--:|---|
| `datasets/aiperf/nvfp4_chatbot_flat.jsonl` | 384 | all `chatbot_flat` points |
| `datasets/aiperf/nvfp4_agent_flat.jsonl` | 384 | all `agent_flat` points |

Both are `mooncake_trace` **`messages` mode** files carrying in-data `ignore_eos`,
`temperature 0`, `seed 42`. OSL is pinned to the trace; both endpoints honour it —
`osl_mismatch_count = 0` on every valid point.

`coding_flat`, `rag` and `toolagent` were **never run**: their prompts exceed the 4096 context
cap (see the feasibility table in `qwen3vl_ngrok/RESULTS.md`).

For the 100-request series, `scripts/filter_le4096.py` produced context-filtered copies in
`datasets/aiperf/le4096/`: `agent_flat` kept 279/384 entries (105 dropped), `chatbot_flat` kept
all 384. Both files are committed — the chatbot copy is byte-identical to the original, but must
be present for `DATA_DIR=datasets/aiperf/le4096` to resolve. Filtering is tokenizer-dependent, so
it must be regenerated for a different model.

## Code changes

`scripts/filter_le4096.py` — new. Drops flat-trace entries whose `ISL + OSL` exceeds a context
limit, so a small-context endpoint stops returning HTTP 400 mid-run. Output feeds the runner via
`DATA_DIR`.

`scripts/run_nvfp4.sh` line ~101 — `WARMUP=0` now omits `--warmup-request-count` entirely
instead of passing `0`, which aiperf rejects (`greater_than 0` validation). Without this fix
every `WARMUP=0` point fails in ~15 s with no requests sent. Behaviour for `WARMUP>0` is
unchanged.

## Comparability warnings

1. **Do not mix with the `spark` / `5090` / `h100` flat runs.** Those used `WARMUP=16` and reset
   the prefix cache before every point. Nothing here does — `REMOTE=1` means no
   `/reset_prefix_cache`, and warmup was 2 or 0.
2. **The three warmup settings are three different workloads.** `WARMUP=16`, `WARMUP=2` and
   `WARMUP=0` profile different slices of the trace (`[16:...]`, `[2:...]`, `[0:...]`), not
   coarse and fine versions of one.
3. **Model A vs model B is not a tunnel A/B.** The tunnel and the model changed together.
   Isolating the tunnel's latency contribution still requires a `localhost` run on the box.
4. **Filtered `agent_flat` is a different workload from unfiltered `agent_flat`.** Removing the
   105 over-cap entries shifts the length distribution; the 100-request agent numbers are not
   comparable with the 10- and 20-request ones. `chatbot_flat` lost no entries and stays
   comparable across all request counts.
5. **`total_token_throughput` ranks workloads misleadingly** when prefix-cache hit rates differ —
   `agent_flat` tops it while having the worst request throughput, because ~70 % of its prompt
   tokens are cache hits.
