# Results — NVFP4 cross-hardware: GB10 Spark vs RTX 5090

`nvidia/Qwen3.6-35B-A3B-NVFP4` on vLLM **v0.24.0**, 2026-07-03. **82 points**:
2 machines × 5 workloads × (concurrency 2/4/8/16/32 closed-loop + 0.8/1.0/1.2 req/s
poisson open-loop) + a fixed-schedule Mooncake replay on both. 96 requests/point,
reasoning/thinking OFF, OSL cap 2048, prefix cache reset before every point, server
restarted between workloads, aiperf 0.10 client co-located on each machine.
Full methodology + incident log: [`results/nvfp4/SUMMARY_nvfp4.md`](results/nvfp4/SUMMARY_nvfp4.md);
raw per-point tables: [`results/nvfp4/SUMMARY_tables.md`](results/nvfp4/SUMMARY_tables.md);
per-run Grafana windows: [`results/nvfp4/GRAFANA_LINKS.md`](results/nvfp4/GRAFANA_LINKS.md).

## Configuration

| | Spark (GB10, 128 GB unified) | RTX 5090 (32 GB) |
|---|---|---|
| image | `vllm/vllm-openai:v0.24.0` (cu130) | `v0.24.0-x86_64-cu129` (driver 575) |
| gpu-mem-util / batched-tokens | 0.5 / 32768 | 0.9 / 8192 |
| max-model-len / max-num-seqs | 131072 / 32 | 131072 / 32 |
| **KV cache** | **1,216,668 tokens** | **263,144 tokens (4.6× smaller)** |
| FP4 kernel | Marlin weight-only (sm_121 — no native FP4) | Marlin weight-only (sm_120 — same) |

Same kernel path on both sides ⇒ clean comparison. Weights: 20.4 GiB each.

## Closed loop — Req/s (c2 → c32)

| workload | spark c2/c4/c8/c16/c32 | 5090 c2/c4/c8/c16/c32 | 5090 @c32 |
|---|---|---|--:|
| chatbot | 0.5 / 0.8 / 1.0 / 1.4 / 1.7 | 1.5 / 2.6 / 3.4 / 5.2 / 6.7 | **3.9×** |
| rag | 1.1 / 1.1 / 1.1 / 1.1 / 1.1 | 3.2 / 3.7 / 4.2 / 4.3 / 4.3 | **3.9×** |
| toolagent | 0.3 / 0.4 / 0.5 / 0.5 / 0.5 | 1.1 / 1.4 / 1.7 / 1.8 / 1.7 | **3.4×** |
| agent | 0.2 / 0.3 / 0.4 / 0.5 / 0.8 | 0.8 / 1.1 / 1.8 / 2.2 / 3.2 | **4.0×** |
| coding | 0.1 / 0.2 / 0.1 / 0.2 / 0.2 | 0.4 / 0.4 / 0.4 / 0.5 / 0.6 | **3.0×** |

![throughput](results/nvfp4/nvfp4_throughput.png)

## Closed loop — TTFT avg, ms (c2 → c32)

| workload | spark | 5090 |
|---|---|---|
| chatbot | 147 / 153 / 188 / 236 / 369 | 101 / 107 / 118 / 119 / 169 |
| rag | 1,643 / 2,484 / 4,351 / 8,787 / 19,812 | 512 / 765 / 1,246 / 2,730 / 5,713 |
| toolagent | 1,328 / 1,501 / 2,473 / 5,937 / 15,254 | 440 / 472 / 573 / 1,854 / 8,973 |
| agent | 295 / 333 / 489 / 748 / 2,305 | 154 / 169 / 197 / 230 / 498 |
| coding | 1,640 / 1,903 / 3,315 / 5,968 / 15,280 | 541 / 1,098 / 4,829 / 13,435 / 27,217 ← KV thrash |

![ttft](results/nvfp4/nvfp4_ttft.png)

Single-user decode (c2): **5090 ≈ 157–178 tok/s/user vs Spark ≈ 30–57** (≈3.2×).
Output throughput @c32: chatbot 1,414 vs 352 tok/s; agent 1,343 vs 328; coding 396 vs 141.

## Open loop — delivered req/s (offered 0.8 / 1.0 / 1.2) and TTFT avg

| workload | spark delivered | spark TTFT (ms) | 5090 delivered | 5090 TTFT (ms) |
|---|---|---|---|---|
| chatbot | 0.8 / 0.9 / 1.0 | 174 / 185 / 199 | 0.8 / 1.0 / 1.2 | 97 / 104 / 97 |
| rag | 0.8 / 1.0 / 1.1 | 2,678 / 5,192 / 11,786 | 0.8 / 1.0 / 1.2 | 425 / 439 / 473 |
| toolagent | **0.5 / 0.5 / 0.5 (saturated)** | 19,175 / 29,841 / 37,280 | 0.8 / 1.0 / 1.2 | 840 / 943 / 1,054 |
| agent | 0.6 / 0.7 / 0.6 | 481 / 2,024 / 7,148 | 0.8 / 1.0 / 1.2 | 161 / 165 / 172 |
| coding | **0.2 / 0.2 / 0.2 (saturated)** | 57,958 / 75,344 / 95,813 | 0.5 / 0.7 / 0.6 | 18,295 / 15,424 / 30,621 |

The 0.8/1.0/1.2 band brackets Spark's capacity: it holds chatbot/agent, saturates on
toolagent (cap ≈0.5) and coding (≈0.2), and tips over on rag at 1.2 (cap ≈1.1). The 5090
absorbs every rate except coding.

![rate-ttft](results/nvfp4/nvfp4_rate_ttft.png)

## Fixed-schedule Mooncake replay (320 reqs, original timestamps, 60 s window ≈ 5.33 req/s)

| | delivered | TTFT avg | ITL avg | out tok/s | prefix-hit | KV max | drain time |
|---|--:|--:|--:|--:|--:|--:|--:|
| Spark | 0.5 req/s | 314.8 s | 432 ms | 87 | 24.4% | 55% | ≈11 min |
| 5090 | 1.5 req/s | 86.5 s | 59 ms | 292 | 0.9% | 100% | ≈3.5 min |

Both queue the burst (over both capacities); the 5090 drains 3.6× faster at 7× lower ITL
even while its KV thrashes (96M prefix-query tokens vs Spark's 3M).

## KV-capacity story

- **5090 (263K-token KV)** thrashes on long-context workloads: coding prefix-hit collapses
  72.7% → 40.2% → 0.1% by c8 with KV pinned 98–100% and prefix queries exploding 3M → 306M
  tokens/point (preempt-evict-recompute); toolagent shows the same from c16 (1M → 34.5M).
  Raw compute still keeps it ~3× ahead of Spark.
- **Spark (1.22M-token KV)** never saturates (max 55%): coding holds 53–73% hit across the
  whole sweep, queries stay flat. Cache stability doesn't close the compute gap.
- Small-context workloads (chatbot/agent): identical request streams on both machines
  (seed 42) produced identical hit/query counts — comparability check passed.

![kv](results/nvfp4/nvfp4_kv_recompute.png)

## Operational notes

- `/reset_prefix_cache` needs `VLLM_SERVER_DEV_MODE=1` in v0.24.0.
- vLLM v0.24.0 still has the **EngineCore silent-stall wedge** (running>0, zero token
  movement, no exception): reproduced twice on Spark agent r0.8 (~20 concurrent); the
  watchdog + post-sweep mop-up recovered it. One transient aiperf `ClientOSError` right
  after a server restart also auto-recovered.
- 5090 box: IPv6 egress dead (ship images from Spark via `docker save | ssh docker load`),
  Coolify periodically prunes unused images (`pin-vllm`/`pin-aiperf` sleeper containers
  left running as protection), no CUDA-13 images on driver 575.
- Prometheus scrapes both nodes with a `node` label; the vLLM dashboard splits series by
  node, and every point is tagged as a Grafana region annotation (tag `nvfp4`).

## Reproduce

```bash
python3 scripts/build_nvfp4_datasets.py
cd monitoring && docker compose up -d && cd ..
NODE=spark nohup bash scripts/run_nvfp4.sh &                    # on the Spark
NODE=5090  nohup bash scripts/run_nvfp4.sh &                    # on the 5090 (~/bench-nvfp4 mirror)
NODE=spark POINTS=fixed bash scripts/run_nvfp4.sh toolagent_ts  # timestamped replay
python3 scripts/collect_prom_nvfp4.py && python3 scripts/summarize_nvfp4.py --md
.venv-plot/bin/python3 scripts/plot_nvfp4.py
python3 scripts/annotate_grafana_nvfp4.py                       # tag runs in Grafana
```
