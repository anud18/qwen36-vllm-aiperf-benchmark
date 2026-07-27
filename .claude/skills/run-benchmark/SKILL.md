---
name: run-benchmark
description: Use when the user wants to run / re-run / resume a vLLM benchmark in this repo (跑 benchmark) — the v6 Qwen3.6-35B-A3B-FP8 sweep or the flat-trace sweep, against a local server or a managed cloud endpoint. Brings up vLLM + Prometheus/Grafana, builds the aiperf datasets, runs the concurrency sweep, and summarizes/plots the results.
---

# Run the Qwen3.6 vLLM benchmark (GB10 / aarch64)

Full config rationale lives in `RUNBOOK.md`; dataset conversion in `FORMAT.md` / `DATASETS.md`.
This skill is the operational path: what to run, in what order, and what to check.

## 0. Ask the user before running anything

These four choices change the run and cannot be inferred. Ask them together (AskUserQuestion),
then state the resolved config back before launching. Skip a question only if the user already
answered it in their request.

| choice | options | consequence |
|---|---|---|
| **track** | v6 Qwen3.6 local (§2) / flat traces (§6) | different scripts, datasets and result dirs — never mix |
| **endpoint** | local self-hosted vLLM / managed cloud gateway | cloud needs `REMOTE=1` + `API_KEY`, and loses `/metrics`, prefix-hit and the wedge watchdog |
| **requests per point** | v6: `REQ_COUNT` (default 160) · flat: `REQS` (default 96, dataset allows ≤ 320) | more requests = longer per point; the dataset must hold `warmup + requests` entries |
| **OSL** (flat track only) | follow the trace exactly / let the model stop naturally | the shipped flat files already pin it (`ignore_eos` in-data); "natural" means rebuilding without `--force-osl`. Exact OSL also needs a vLLM you control — a gateway drops the parameter |

Defaults if the user says "just run it": v6 track, local, `REQ_COUNT=160`. On the flat track the
shipped datasets pin OSL to the trace — only rebuild if the user asks for natural stopping.

**Request count vs dataset size.** aiperf consumes entries in file order — a point uses
`entries[warmup : warmup + requests]`, verified. So any request count ≤ dataset size is
deterministic and reproducible, but a smaller count is a *prefix subset*, weighted toward the
first turns of few sessions: coding's first 16 entries average OSL 40 against 584 for the whole
file. Runs with different request counts are different workloads, not coarse/fine versions of
one. If `warmup + requests` exceeds the file, aiperf wraps around and replays early entries,
inflating prefix-cache hits — rebuild the dataset larger instead (§6).

| dataset | entries | max requests (warmup 16) |
|---|--:|--:|
| `nvfp4_{chatbot,agent,coding}_flat.jsonl` | 384 | 320 |
| `final_rag.jsonl` | 500 | 484 |
| `final_toolagent.jsonl` | 320 | 304 |
| chatbot (`--public-dataset sharegpt`) | — | unbounded |

## 0b. Preconditions

```bash
nvidia-smi                              # GB10 visible, no stray EngineCore holding memory
docker images | grep -E 'aiperf|vllm'   # need aiperf:local
ls datasets/aiperf/final_*.jsonl        # need the 4 file-based datasets
```

- Missing `aiperf:local` → `docker build -t aiperf:local -f scripts/aiperf.Dockerfile scripts/`
  (`scripts/setup_aiperf.sh` is the host-venv alternative; the run scripts use the container).
- Missing datasets → `python3 scripts/build_final.py` (needs the HF cache; chatbot uses aiperf's
  built-in `--public-dataset sharegpt`, so it has no file).

## 1. Monitoring (optional but recommended)

```bash
cd monitoring && docker compose up -d && cd ..   # Prometheus :9090, Grafana :3000
```

Prometheus scrapes vLLM `/metrics` at `host.docker.internal:8000`. Grafana is pinned to **11.6.5**
— do not bump it, 13.x breaks the file-provisioned vLLM dashboard.

## 2. Run the sweep

`scripts/run_final.sh` restarts the vLLM server before **each** workload itself — do not start
`serve_vllm.sh` by hand first, it would just be killed and replaced.

```bash
GPU_UTIL=0.85 MAX_NUM_SEQS=32 MAX_MODEL_LEN=248320 MAX_NUM_BATCHED_TOKENS=248320 \
  bash scripts/run_final.sh
```

These four env vars are the **v6 config** and are inherited by `serve_vllm.sh`. Omitting them
silently falls back to the util-0.5 / 64k baseline, which is a different experiment.
Run it with `run_in_background: true` — a full pass is several hours.

Subset / single workload (same env prefix):

```bash
bash scripts/run_final.sh rag coding     # default: chatbot rag toolagent agent coding
```

Sweep shape: chatbot, rag → `4 8 16 32`; toolagent, agent, coding → `4 8 16`.
Termination: chatbot/rag/toolagent `--request-count $REQ_COUNT` (default 160); agent/coding
`--benchmark-duration 300 --benchmark-grace-period 300`.

## 3. Expectations while it runs

- **Server startup is ~11 min per restart** (the 248320 compile range takes ~120 s to load from the
  AOT cache, plus weights + cudagraph). 5 workloads → budget ~1 h of pure restart overhead.
  `serve_vllm.sh` waits up to 1500 s for `/health`; a shorter wait causes every workload to be skipped.
- **Resume is built in**: a point with a non-empty `results/final/<wl>/c<N>/profile_export_aiperf.json`
  is skipped. Killing and re-running the same command continues where it stopped — that is the
  normal recovery, do not wipe `results/final/` to "start clean" unless the user asks.
- **Engine wedge**: vLLM V1 EngineCore intermittently pins requests with prompt+gen throughput at 0
  while `running>0`. The script watchdogs `/metrics` every 15 s, kills after `WEDGE_S` (120 s) of no
  token movement, restarts the server and retries the point up to `MAX_TRIES` (3). Repeated
  `!!! wedge` lines for one point are a known failure mode, not a script bug.
- Watch: `tail -f results/final/<wl>/c<N>/run.log`, server log `results/final/<wl>.serve.log`,
  live state `curl -s localhost:8000/metrics | grep -E 'num_requests_(running|waiting)'`.

## 4. Outputs

Per `(workload, concurrency)` under `results/final/<wl>/c<N>/`:
- `profile_export_aiperf.json` — aiperf summary (existence = point complete)
- `prefix.json` — prefix-cache hit delta for that point, from `vllm:prefix_cache_hits_total` /
  `vllm:prefix_cache_queries_total` sampled before/after; `{"failed":true,...}` if the point gave up
- `run.log` — aiperf stdout

```bash
python3 scripts/summarize_final.py      # tables incl. prefix-hit
python3 scripts/plot_pareto.py          # Pareto curves
```

## 5. Knobs worth knowing

| env | default | effect |
|---|---|---|
| `GPU_UTIL` | 0.5 in the script | **set 0.85** for v6 — 0.6 OOMs with the 248320 batch budget |
| `MAX_NUM_BATCHED_TOKENS` | unset | the main v6 lever: 248320 batches all prefills in one step (rag c16: TTFT −35%, req/s +24%) |
| `WARMUP` / `WARMUP_CODING` | 32 / 8 | coding is reasoning-ON and long; 32 warmups there eat the time budget |
| `DURATION` / `GRACE` | 300 / 300 | duration-based points (agent, coding) |
| `REQ_COUNT` | 160 | requests per point for chatbot/rag/toolagent; at 320 raise `RC_TLIM` to ≥1800 (toolagent c4 needs ~1200 s) and note toolagent's dataset is exactly 320 lines |
| `RC_TLIM` | 1200 | hard wall-clock cap per request-count point |
| `WEDGE_S` / `MAX_TRIES` | 120 / 3 | wedge watchdog |
| `VLLM_IMAGE` | `ghcr.io/spark-arena/dgx-vllm-eugr-nightly-tf5:20260614` | arm64 nightly, vLLM 0.22.1 |

Reasoning is OFF everywhere except **coding** (`enable_thinking=false`, per-line for file datasets,
`--extra-inputs` for chatbot/toolagent). Changing that changes the workload definition — flag it.

## 6. Flat-trace track (`run_nvfp4.sh`) — the other benchmark

Separate scripts, datasets and result dirs from §2. Use it when the point is comparing
*machines or endpoints* on identical input tokens. Full guide: `FLAT_TRACES.md`.

`nvfp4_{chatbot,agent,coding}_flat.jsonl` are 384-entry `mooncake_trace` **`messages` mode**
files: every conversation turn is one independent request carrying its real history, so ISL is
fixed by the file. `rag` (`single_turn`) and `toolagent` (lengths-declared trace) are already
flat and need no variant.

```bash
# local self-hosted vLLM
NODE=spark REQS=320 POINTS="c2 c8 c32" bash scripts/run_nvfp4.sh chatbot_flat agent_flat coding_flat

# managed cloud gateway (NCHC GLM-5.2)
API_KEY=... REMOTE=1 NODE=glm52 REQS=320 SERVED_NAME=GLM-5.2 \
  URL=https://inner-medusa.genai.nchc.org.tw TOKENIZER=zai-org/GLM-5.2-FP8 \
  OUTBASE=results/nvfp4/glm52 POINTS="c2 c8 c32" \
  bash scripts/run_nvfp4.sh chatbot_flat agent_flat coding_flat rag toolagent
```

| env | default | effect |
|---|---|---|
| `REQS` | 96 | requests per point; ≤ 320 with the 384-entry files |
| `REMOTE` | 0 | 1 = endpoint we don't own: no server restart, no `/reset_prefix_cache`, no `/metrics` watchdog (tlimit only), `prefix.json` marked unavailable |
| `API_KEY` | unset | passed to aiperf as `--api-key` |
| `POINTS` | `c2 c4 c8 c16 c32 r0.8 r1.0 r1.2` | `c<N>` closed-loop, `r<R>` poisson open-loop, `fixed` replays trace timestamps |
| `RC_TLIM` / `RATE_TLIM` | 5400 / 7200 | hard caps, sized for `REQS=320` with OSL pinned (that window decodes 3.2-5.0x the tokens of the old 96 window; Spark coding_flat c2 took 577 s at 96). Lower them for small `REQS` |
| `WARMUP` | 16 | also consumed from the front of the file — changing it shifts which entries are profiled |

**OSL mode.** The shipped files carry `ignore_eos` (built with `--force-osl`), so on a vLLM you
control the measured OSL equals `output_length` exactly — verified through aiperf: chatbot
279.5/54/641, agent 195.6/80/452, coding 39.9/13/156, identical to declared. `temperature 0` /
`seed 42` are pinned in-data too. Two catches: a managed gateway may silently drop `ignore_eos`
(the NCHC one does, along with `min_tokens`), leaving `output_length` as a cap only — those
numbers are not comparable with self-hosted ones; and with OSL forced, the cap becomes real
decode work (93/384 coding turns generate a full 2,048 tokens each, so coding runs heavier).
To rebuild without it, drop `--force-osl`:

```bash
python3 scripts/build_flat_text_traces.py chatbot --n-entries 384 --osl-cap 2048 --force-osl
API_KEY=... python3 scripts/build_flat_text_traces.py agent coding \
  --n-entries 384 --osl-cap 2048 --force-osl --model GLM-5.2 \
  --url https://inner-medusa.genai.nchc.org.tw
```

`--osl-cap` sets both the canonical-generation `max_tokens` and the `output_length` ceiling;
changing it means **deleting `datasets/aiperf/canonical/*_replies.jsonl` first**, or previously
clipped replies survive from the cache. Rebuilding changes the dataset — say so, and don't mix
the new numbers with results measured against an older build (`datasets/aiperf/archive_*`).

## Not this benchmark

`scripts/build_flat_traces.py` (v1 synthetic, lengths + hash_ids) is superseded by
`build_flat_text_traces.py`; `double_flat_run.sh` is the H100 reproducibility double-run.
Don't mix §2 and §6 scripts or result dirs in one run.
