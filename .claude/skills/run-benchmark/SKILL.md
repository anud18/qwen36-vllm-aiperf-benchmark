---
name: run-benchmark
description: Use when the user wants to run / re-run / resume the Qwen3.6-35B-A3B-FP8 vLLM benchmark in this repo (跑 benchmark) — bring up the vLLM server + Prometheus/Grafana, build the aiperf datasets, run the concurrency sweep over the 5 workloads, and summarize/plot the results.
---

# Run the Qwen3.6 vLLM benchmark (GB10 / aarch64)

Full config rationale lives in `RUNBOOK.md`; dataset conversion in `FORMAT.md` / `DATASETS.md`.
This skill is the operational path: what to run, in what order, and what to check.

## 0. Preconditions

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
Termination: chatbot/rag/toolagent `--request-count 160`; agent/coding `--benchmark-duration 300
--benchmark-grace-period 300`.

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
| `RC_TLIM` | 1200 | hard wall-clock cap per request-count point |
| `WEDGE_S` / `MAX_TRIES` | 120 / 3 | wedge watchdog |
| `VLLM_IMAGE` | `ghcr.io/spark-arena/dgx-vllm-eugr-nightly-tf5:20260614` | arm64 nightly, vLLM 0.22.1 |

Reasoning is OFF everywhere except **coding** (`enable_thinking=false`, per-line for file datasets,
`--extra-inputs` for chatbot/toolagent). Changing that changes the workload definition — flag it.

## Not this benchmark

`scripts/serve_nvfp4.sh` / `run_nvfp4.sh` / `summarize_nvfp4.py` are the separate **NVFP4
cross-hardware** track (Spark / 5090 / H100, see `RESULTS_nvfp4.md`), and
`scripts/build_flat_traces.py` / `double_flat_run.sh` the flat-trace track (`FLAT_TRACES.md`).
Don't mix their scripts or result dirs into a v6 run.
