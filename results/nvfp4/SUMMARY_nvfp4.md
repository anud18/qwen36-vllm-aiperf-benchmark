# NVFP4 cross-hardware benchmark — GB10 Spark vs RTX 5090

`nvidia/Qwen3.6-35B-A3B-NVFP4` on vLLM **v0.24.0**, 2026-07-03.
80/80 points completed (2 machines × 5 workloads × [c2 c4 c8 c16 c32 + r0.8 r1.0 r1.2]), 96 requests/point,
reasoning/thinking **OFF** everywhere, OSL cap 2048, prefix cache **reset before every point**,
server restarted between workloads, aiperf client co-located on each machine. Total wall clock ≈ 4.5 h
(both sweeps ran in parallel; Spark 11:49–16:21 incl. mop-up, 5090 12:05–14:03).

## Configuration

| | Spark (GB10, DGX Spark) | RTX 5090 (mypda) |
|---|---|---|
| image | `vllm/vllm-openai:v0.24.0` (cu130) | `vllm/vllm-openai:v0.24.0-x86_64-cu129` (driver 575 can't run cu130) |
| `--gpu-memory-utilization` | 0.5 (of 128 GB unified) | 0.9 (of 32 GB) |
| `--max-num-batched-tokens` | 32768 | 8192 |
| `--max-model-len` / `--max-num-seqs` | 131072 / 32 | 131072 / 32 |
| resulting KV cache | **1,216,668 tokens** | **263,144 tokens** (4.6× smaller) |
| FP4 kernel | **Marlin weight-only** (no native FP4 on sm_121) | **Marlin weight-only** (same on sm_120) |
| weights in VRAM | 20.4 GiB | 20.4 GiB |

Neither GPU has native FP4 tensor-core support in this build — both fall back to Marlin
weight-only FP4, so the comparison is apples-to-apples on kernel path.

## Headline results (closed loop)

| metric @ c32 | chatbot | rag | toolagent | agent | coding |
|---|---|---|---|---|---|
| Req/s — spark | 1.7 | 1.1 | 0.5 | 0.8 | 0.2 |
| Req/s — 5090 | **6.7 (3.9×)** | **4.3 (3.9×)** | **1.7 (3.4×)** | **3.2 (4.0×)** | **0.6 (3.0×)** |
| TTFT avg — spark | 369 ms | 19.8 s | 15.3 s | 2.3 s | 15.3 s |
| TTFT avg — 5090 | 169 ms | 5.7 s | 9.0 s | 0.5 s | 27.2 s ← KV thrash | 
| Out tok/s — spark | 352 | 4.5 | 100 | 328 | 141 |
| Out tok/s — 5090 | 1414 | 18.5 | 345 | 1343 | 396 |

Single-user decode (c2, tok/s/user): **5090 ≈ 170–178 vs Spark ≈ 44–57** (≈3.2×).

## Open loop (poisson, 0.8 / 1.0 / 1.2 req/s)

- **5090 absorbs all three rates on every workload** (delivered = offered; TTFT p99 stays
  ~0.1–1 s on chatbot/rag/agent/toolagent; coding saturates too — delivered 0.5–0.7 req/s).
- **Spark saturates on 3 of 5 workloads**: toolagent capacity ≈0.5 req/s → offered 0.8–1.2
  yields TTFT 19–37 s; coding capacity ≈0.2 req/s → TTFT 58–96 s; rag holds 0.8/1.0 but at
  r1.2 (capacity ≈1.1) TTFT balloons to ~12 s. chatbot/agent hold all rates with moderate queueing.
- 這組 rate 剛好夾住 Spark 的容量點，曲線清楚呈現「哪台在哪個 rate 崩」。

## KV-capacity story (the most interesting contrast)

The 5090's 263K-token KV is the bottleneck on long-context workloads; the GB10's 1.2M-token
KV never was (max usage 53%):

- **coding on 5090**: prefix-hit collapses 72.7% (c2) → 40.2% (c4) → **0.1% (c8+)**, KV pinned
  98–100%, and prefix-cache queries explode from 3M to **306M tokens/point** (~100× recompute
  amplification from preempt-evict-recompute loops). Spark keeps 53–73% hit across c2–c32,
  queries flat at ~3M.
- **toolagent on 5090**: same pattern from c16 (heavy-tailed 120K inputs; queries 1M → 34.5M).
- Despite the thrash, the 5090's raw compute still delivers ~3× Spark's throughput — it
  brute-forces the recompute. Spark's unified memory buys cache stability, not speed, at
  these batch sizes.
- On small-context workloads (chatbot/agent) both machines' hit-rates and request streams are
  **identical** (same seed 42 → same hits/queries), confirming clean comparability.

## Add-on: fixed-schedule Mooncake replay (`toolagent_ts`)

Same 320 requests as the toolagent sweep, but replayed at the trace's **original
timestamps** (60 s arrival window, avg 5.33 req/s, bursty) via aiperf `--fixed-schedule` —
a production-burst absorption test. Offered load is ~10× Spark's toolagent capacity (0.5 req/s)
and ~3× the 5090's (1.7 req/s):

| fixed replay | delivered req/s | TTFT avg | ITL avg | out tok/s | prefix-hit | KV max | avg waiting |
|---|--:|--:|--:|--:|--:|--:|--:|
| Spark | 0.5 | **314.8 s** | 432 ms | 87 | 24.4% | 55% | 135 reqs |
| 5090 | 1.5 | **86.5 s** | 59 ms | 292 | 0.9% (96M-token thrash) | 100% | 117 reqs |

Both machines queue the burst (it exceeds both capacities), but the 5090 drains it 3.6×
faster (≈3.5 min vs ≈11 min) at 7× lower ITL — even while its 263K-token KV thrashes at 100%
(96M prefix queries vs Spark's 3M). Spark's big KV keeps the cache warm (24.4% hit) but the
Marlin-FP4 compute floor caps its drain rate. Datasets: `datasets/aiperf/nvfp4_toolagent_ts.jsonl`
(timestamps kept); results in `results/nvfp4/{spark,5090}/toolagent_ts/fixed/`.

## Incidents (all auto-recovered; full logs kept)

1. **5090 IPv6 egress dead** → docker pull failed; fixed by pulling amd64 images on Spark and
   shipping via `docker save | ssh docker load`; model rsync'd over LAN.
2. **Coolify's periodic docker cleanup pruned our images** on the 5090 (disk 96%) mid-prep;
   fixed by `pin-aiperf`/`pin-vllm` sleeper containers (left running for future runs).
3. `/reset_prefix_cache` is dev-gated in v0.24.0 → `VLLM_SERVER_DEV_MODE=1` added to serve.
4. **EngineCore silent-stall wedge still exists in v0.24.0**: Spark agent r0.8 stalled twice
   (running≈20, zero token movement, no exception; same signature as the v6 nightly). The
   watchdog killed+restarted; a post-sweep mop-up pass completed the point on first retry.
   One transient aiperf `ClientOSError` right after a restart (toolagent c2 try 1) also
   recovered on retry.

## Files

- `results/nvfp4/{spark,5090}/<wl>/<pt>/` — aiperf artifacts + `prefix.json` + `meta.json` + `prom.json`
- `results/nvfp4/SUMMARY_tables.md` — full per-point metric tables (both nodes + comparison)
- `results/nvfp4/nvfp4_{throughput,ttft,rate_ttft,kv_recompute}.png` — comparison plots
- `results/nvfp4/prom_snapshot/20260703T082146Z-*/` — Prometheus TSDB snapshot (both nodes, full run)
- `results/nvfp4/{spark,5090}_run.log`, `{spark,5090}_server_persist.log` — driver + server logs
- Harness: `scripts/{serve,run}_nvfp4.sh`, `scripts/build_nvfp4_datasets.py`,
  `scripts/{collect_prom,summarize,plot}_nvfp4.py`

## Reproduce

```bash
python3 scripts/build_nvfp4_datasets.py                # OSL-2048 dataset copies
cd monitoring && docker compose up -d && cd ..         # Prometheus(:9090)+Grafana(:3000), both nodes scraped
NODE=spark nohup bash scripts/run_nvfp4.sh &           # on the Spark
NODE=5090  nohup bash scripts/run_nvfp4.sh &           # on the 5090 (~/bench-nvfp4 mirror)
python3 scripts/collect_prom_nvfp4.py && python3 scripts/summarize_nvfp4.py --md
.venv-plot/bin/python3 scripts/plot_nvfp4.py
```
