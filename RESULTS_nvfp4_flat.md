# Results — NVFP4 flat traces: GB10 Spark vs RTX 5090 vs H100 PCIe

Companion to [RESULTS_nvfp4.md](RESULTS_nvfp4.md), restricted to the **flat-trace**
workloads (`chatbot_flat`, `agent_flat`, `coding_flat`) where input tokens are fixed in
the file, so every machine serves a **bit-identical ISL at every point** — the confound the
multi-turn originals can't avoid (emergent turn depth depends on machine speed). Same
engine (`nvidia/Qwen3.6-35B-A3B-NVFP4`, vLLM v0.24.0, TP=1, prefix cache reset per point,
96 req/point, reasoning OFF, OSL cap 2048) and the same three configs as the main run — see
[RESULTS_nvfp4.md § Configuration](RESULTS_nvfp4.md#configuration) for KV sizes
(Spark 1.22M / 5090 263K / H100 2.23M tokens).

The concurrency grid (c2–c32) is now **complete for all three machines** — Spark's
`coding_flat` (2026-07-18) and the H100's c4/c16 (2026-07-18) closed the last gaps. Raw
per-point tables: [`results/nvfp4/SUMMARY_tables.md`](results/nvfp4/SUMMARY_tables.md);
full aiperf tables: [`results/nvfp4/AIPERF_TABLES.md`](results/nvfp4/AIPERF_TABLES.md).

## ⚠️ Version caveat — read before comparing across machines

Two generations of flat trace exist and they are **not** interchangeable:

| | build script | prompt text | measured ISL (chatbot / agent / coding) | chatbot hit |
|---|---|---|---|---|
| **v1** | `build_flat_traces.py` | synthetic (declared lengths + hash blocks) | 620 / 3,041 / 29,869 | ~1.5% |
| **v2** | `build_flat_text_traces.py` | original conversation text (`messages`) | 654 / 2,977 / 29,646 | ~22–25% |

Which version each curve is measured against (5090 is unreachable from here, so it can't be
re-run to v2):

| workload | Spark | 5090 | H100 |
|---|---|---|---|
| chatbot_flat | v1 | v1 | **v2** |
| agent_flat | v1 | v1 | **v2** |
| coding_flat | **v2** (2026-07-18) | v1 | **v2** |

Consequences for the tables below:

- **coding_flat is the clean one** — Spark and H100 are both v2 (ISL 29,646 to the token);
  only the 5090 is v1 (29,869, ~0.7% longer). Treat Spark↔H100 coding_flat as directly
  comparable.
- **chatbot_flat / agent_flat mix versions.** The H100's higher chatbot prefix-hit (22–25%
  vs Spark/5090's 1.5%) is a **v1→v2 artifact, not a hardware difference** — v1's 512-token
  hash blocks understate real chat prefix sharing. Compare H100 chatbot/agent_flat curves to
  each other and to its own multi-turn originals, not head-to-head against Spark/5090 hit rates.
- Throughput/latency on chatbot/agent_flat are within a few % of the multi-turn originals on
  every machine (the flat rewrite preserves load), so those *rate* comparisons still hold;
  it is the *prefix-hit* column that the version split distorts.

Full-v2 parity needs a 5090 re-run (`NODE=5090 bash scripts/run_nvfp4.sh chatbot_flat
agent_flat coding_flat` — the datasets are already v2, no rebuild) plus Spark chatbot/agent_flat.

## Closed loop — Req/s (c2 → c32)

| workload | Spark | 5090 | H100 | H100 vs 5090 @c32 |
|---|---|---|---|--:|
| chatbot_flat | 0.5 / 0.8 / 1.1 / 1.4 / 1.7 | 1.5 / 2.5 / 3.7 / 4.9 / 6.5 | 1.4 / 2.3 / 3.5 / 4.9 / 6.4 | ≈ tie |
| agent_flat | 0.2 / 0.4 / 0.5 / 0.6 / 0.7 | 0.7 / 1.3 / 1.8 / 2.5 / 3.1 | 0.9 / 1.4 / 2.3 / 3.0 / 3.7 | **1.2×** |
| coding_flat | 0.2 / 0.2 / 0.2 / 0.2 / 0.2 | 0.5 / 0.9 / 1.0 / 0.9 / 0.9 | 0.6 / 0.8 / 1.2 / 1.4 / 1.4 | **1.5×** |

![flat-throughput](results/nvfp4/nvfp4_flat_throughput.png)

The decode-bound workloads (chatbot/agent_flat) put H100 and the 5090 in a near-tie — no KV
pressure to relieve, same Marlin weight-only FP4 kernel, so raw decode dominates and both run
~4× Spark. **coding_flat is where the KV cache decides it**: the 5090 peaks at c8 (0.97 req/s)
and then *regresses* to 0.91 at c32 as its 263K-token KV thrashes, while the H100 climbs
monotonically to 1.4 — a 1.5× lead built entirely on cache headroom (see below). Spark holds
hit but is compute-bound at ~0.2 req/s throughout.

## Closed loop — TTFT avg, ms (c2 → c32)

| workload | Spark | 5090 | H100 |
|---|---|---|---|
| chatbot_flat | 170 / 192 / 243 / 468 / 1,291 | 113 / 117 / 144 / 193 / 330 | 82 / 88 / 98 / 127 / 248 |
| agent_flat | 359 / 399 / 521 / 954 / 2,813 | 186 / 208 / 237 / 336 / 642 | 122 / 131 / 143 / 217 / 564 |
| coding_flat | 1,795 / 2,192 / 3,004 / 6,539 / 15,063 | 576 / 786 / 911 / **4,950 / 17,184** | 426 / 571 / 715 / 1,404 / 2,942 |

![flat-ttft](results/nvfp4/nvfp4_flat_ttft.png)

The 5090's coding_flat TTFT blows out 0.9 s → 17.2 s at c16/c32 (the thrash) — the H100 stays
at 2.9 s on the same point (5.8× lower). H100 leads TTFT on every flat point; on chatbot/agent
its edge is queueing headroom rather than KV.

## Closed loop — ITL avg, ms (c2 → c32)

| workload | Spark | 5090 | H100 |
|---|---|---|---|
| chatbot_flat | 18 / 23 / 32 / 47 / 69 | 6 / 7 / 9 / 13 / 18 | 6 / 7 / 9 / 12 / 17 |
| agent_flat | 18 / 24 / 35 / 53 / 88 | 6 / 7 / 9 / 13 / 20 | 6 / 7 / 10 / 13 / 18 |
| coding_flat | 27 / 51 / 83 / 198 / 617 | 8 / 11 / 19 / 33 / 39 | 7 / 10 / 19 / 41 / 101 |

The two datacenter-class cards are near-identical on the decode-bound flats (≤20 ms). On
coding_flat the 5090's ITL actually looks *better* than the H100 at c32 (39 vs 101 ms) — an
artifact of the thrash: the 5090 admits far fewer concurrent decodes (most requests are stuck
in prefill/queue), so the few that reach decode see a light batch. Spark decode is compute-bound
and degrades steeply (coding_flat 0.6 s/token at c32).

## Closed loop — E2E request latency avg, s (c2 → c32)

| workload | Spark | 5090 | H100 |
|---|---|---|---|
| chatbot_flat | 4.1 / 5.1 / 7.3 / 10.5 / 16.0 | 1.3 / 1.6 / 2.1 / 3.0 / 4.2 | 1.5 / 1.7 / 2.2 / 3.0 / 4.1 |
| agent_flat | 8.2 / 10.4 / 15.2 / 23.8 / 35.7 | 2.7 / 3.0 / 4.1 / 5.7 / 8.4 | 2.2 / 2.9 / 3.4 / 4.9 / 6.8 |
| coding_flat | 12.0 / 20.1 / 34.9 / 63.6 / 103.1 | 3.7 / 4.6 / 8.0 / 15.3 / 28.8 | 3.2 / 4.6 / 6.3 / 9.5 / 17.2 |

H100 coding_flat E2E at c32 is **1.7× lower than the 5090** (17.2 vs 28.8 s) and **6× lower
than Spark** — the KV-headroom compounding of the throughput and TTFT wins.

## Prefix-cache hit — the KV-headroom story

| workload | Spark | 5090 | H100 |
|---|---|---|---|
| chatbot_flat | 1.5 / 1.5 / 1.5 / 1.5 / 3.0 | 1.5 / 1.5 / 1.5 / 1.5 / 1.5 | 22 / 23 / 23 / 24 / 25 |
| agent_flat | 42 / 42 / 43 / 42 / 42 | 43 / 43 / 43 / 43 / 44 | 56 / 56 / 57 / 56 / 54 |
| coding_flat | 74 / 73 / 72 / 71 / 69 | 71 / 71 / 71 / **40 / 43** | 74 / 71 / 72 / 71 / 68 |

![kv](results/nvfp4/nvfp4_kv_recompute.png)

- **coding_flat is the payoff.** Both large-KV machines (Spark 1.22M, H100 2.23M) hold hit at
  ~68–74% flat across the whole sweep; the 5090's 263K KV **collapses from 71% to 40% at c16**
  and never recovers — exactly where its throughput regressed and TTFT blew out. This
  reproduces the multi-turn coding thrash deterministically (real multi-turn coding fell all
  the way to 0.1%; flat order keeps a parent turn's blocks hot when its child arrives, so the
  flat variant is a *milder, upper-bound* version of the same failure).
- **chatbot/agent_flat show no thrash on any machine** — short/mid context fits every KV. The
  H100's higher absolute numbers here are the **v2 real-text effect** (see the caveat), not
  headroom: with real conversation text the 512-token blocks actually fill and share, so v2
  hit (~24% / ~56%) sits above v1's (~1.5% / ~43%). Spark & 5090 chatbot_flat pinned at 1.5%
  is v1's block-granularity artifact — chat turns rarely fill a 512-token block.

## Flat vs original multi-turn

![flat-vs-orig](results/nvfp4/nvfp4_flat_vs_orig.png)

chatbot/agent_flat track their multi-turn originals within a few % on all three machines, so
they are drop-in comparable. coding_flat runs ~1.5–2× hotter than real multi-turn coding
(trace order keeps parent blocks cache-hot; real interleaving evicts them) — read it as an
**upper bound** on cache benefit, not a replacement. Output-token throughput @c32 tells the
same story as Req/s: chatbot_flat 368 / 1,361 / 1,490 tok/s (Spark / 5090 / H100); agent_flat
293 / 1,334 / 1,353; coding_flat 85 / 355 / **504**.

## Open loop (partial)

Poisson rate points (r0.8/1.0/1.2) exist only for **Spark (chatbot/agent_flat)** and **the
5090 (all three)** — the H100 flat sweep and Spark's new coding_flat were concurrency-only, so
there is no clean 3-way open-loop table. From what's measured (full numbers in
[SUMMARY_tables.md](results/nvfp4/SUMMARY_tables.md)): both machines deliver the offered
0.8/1.0/1.2 on chatbot_flat; agent_flat saturates Spark at ≈0.6 req/s (TTFT 1.5 → 5.9 s) while
the 5090 absorbs all rates (TTFT ~190 ms); coding_flat on the 5090 caps at ≈0.9 req/s. The
Spark agent r0.8 EngineCore wedge seen in the main run did **not** reproduce on agent_flat.

## Takeaways

1. **coding_flat cleanly isolates the KV-capacity win.** With ISL fixed at 29,646 tokens, the
   only variable is cache: H100 leads the 5090 **1.5× throughput / 1.7× E2E / 5.8× TTFT** at
   c32, entirely because its 2.23M KV never thrashes where the 5090's 263K does. Spark shares
   the no-thrash property but is compute-bound.
2. **Decode-bound flats (chatbot/agent) are a hardware tie** between the two datacenter cards
   and ~4× Spark — no KV pressure, identical FP4 kernel.
3. **Mind the version split.** coding_flat Spark↔H100 is a true v2 apples-to-apples comparison;
   chatbot/agent_flat cross-machine *hit rates* are not, until the 5090 and Spark chatbot/agent
   are re-run on v2.

## Reproduce (flat only)

```bash
# datasets are already v2 (messages mode); rebuild only if regenerating:
python3 scripts/build_flat_text_traces.py chatbot                         # no server needed
python3 scripts/build_flat_text_traces.py agent coding --url http://localhost:8000

# per machine (aiperf co-located with the server):
NODE=spark POINTS="c2 c4 c8 c16 c32" bash scripts/run_nvfp4.sh chatbot_flat agent_flat coding_flat
NODE=5090  bash scripts/run_nvfp4.sh chatbot_flat agent_flat coding_flat
# H100 (shared box, container-name prefixes + user-dir caches):
NODE=h100 VLLM_CNAME=an-hao-vllm-nvfp4 CONTAINER_NAME=an-hao-vllm-nvfp4 CPREFIX=an-hao-aiperf \
  HF_DIR=$HOME/900g/an-hao/hf VLLM_CACHE=$HOME/900g/an-hao/vllm-cache \
  POINTS="c2 c4 c8 c16 c32" bash scripts/run_nvfp4.sh chatbot_flat agent_flat coding_flat

python3 scripts/summarize_nvfp4.py --md > results/nvfp4/SUMMARY_tables.md
.venv-plot/bin/python3 scripts/plot_nvfp4.py
```
