# Runbook — Qwen3.6-35B-A3B-FP8 vLLM benchmark (v6 final config)

Reproducible setup for benchmarking `Qwen/Qwen3.6-35B-A3B-FP8` on vLLM (GB10 / aarch64)
with NVIDIA aiperf, live Prometheus + Grafana, and per-workload prefix-cache-hit recording.

## 1. Hardware / platform
- **NVIDIA GB10** (DGX Spark, Grace-Blackwell, sm_121, aarch64), 128 GB unified memory, CUDA 13.
- Model `qwen3_5_moe`: MoE 256 experts / 8 active, hybrid linear+full attention, multimodal VL,
  FP8 (e4m3), native 256K context (262144), ~37 GB. HF cache `/home/howard/.cache/huggingface`.

## 2. vLLM server (`scripts/serve_vllm.sh`)
- **Image**: `ghcr.io/spark-arena/dgx-vllm-eugr-nightly-tf5:20260614` (vLLM 0.22.1 nightly, arm64).
  Entrypoint is the NVIDIA wrapper, so the script overrides `--entrypoint vllm` and runs `serve <model>`.
- **Mounts**: HF cache (`/root/.cache/huggingface`) + **vLLM compile cache** (`/root/.cache/vllm`,
  persistent → torch.compile/AOT graphs loaded from cache, ~10 s instead of ~33 s on restart).
- **v6 flags** (env-overridable):

| flag | value | why |
|---|---|---|
| `--gpu-memory-utilization` | **0.85** | needed to fit the 248320 batch-token budget (0.6 OOM'd: no KV room) |
| `--max-model-len` | **248320** | (= vocab size) long context headroom |
| `--max-num-batched-tokens` | **248320** | big prefill batch → many prefills in one step → less queueing/waiting |
| `--max-num-seqs` | **32** | cap running batch to 32 sequences (matches max concurrency) |
| `--reasoning-parser` | **qwen3** | separates `reasoning_content` from `content`; keeps multi-turn history clean for coding |
| `--enable-prefix-caching` | on | prefix reuse (and we measure its hit rate) |

Resulting KV cache ≈ 1.3M tokens; max concurrency 5.27x @ 248K (≈218x @ 6K).

Launch:
```bash
REASONING_PARSER=qwen3 GPU_UTIL=0.85 MAX_NUM_SEQS=32 \
MAX_MODEL_LEN=248320 MAX_NUM_BATCHED_TOKENS=248320 \
bash scripts/serve_vllm.sh
```

## 3. Monitoring (`monitoring/`)
- **Prometheus** (`:9090`) scrapes vLLM `/metrics` at `host.docker.internal:8000`.
- **Grafana** (`:3000`, anonymous viewer) pinned to **11.6.5** (13.x's new provisioning breaks
  file-provisioned dashboards). Official vLLM dashboard from
  `vllm-project/vllm/examples/observability/prometheus_grafana/grafana.json`, datasource bound via
  fixed uid `prometheus`. Start: `cd monitoring && docker compose up -d`.

## 4. Client (aiperf)
- `aiperf:local` container (built from `scripts/aiperf.Dockerfile`, aiperf 0.10.0), run with
  `--network host`, `--endpoint-type chat --streaming`, tokenizer `Qwen/Qwen3.6-35B-A3B-FP8`.

## 5. Datasets (`scripts/build_final.py` → `datasets/aiperf/final_*.jsonl`)

| Workload | source | aiperf type | reasoning | output max | pool |
|---|---|---|---|---|---|
| chatbot | ShareGPT (built-in `--public-dataset sharegpt`) | public | **off** (`--extra-inputs`) | 5000 | ~250k |
| coding | `Inferact/codex_swebenchpro_traces` | multi_turn | **ON** | 5000 | 100 conv / 600 turns |
| rag | `yixuantt/MultiHopRAG` (+corpus) | single_turn | off (in data) | 5000 | 500 |
| agent | `AI45Research/ATBench-Claw` | multi_turn | off (in data) | 5000 | 200 conv / 887 turns |
| toolagent | `kvcache-ai/Mooncake` FAST25 trace | mooncake_trace | off (`--extra-inputs`) | trace len | 200 (timestamps stripped) |

- reasoning OFF = `extra.chat_template_kwargs.enable_thinking=false` (per-line for file datasets,
  `--extra-inputs '{"chat_template_kwargs":{"enable_thinking":false}}'` for the public/mooncake ones).
- Only **coding** keeps reasoning ON; the parser keeps its history clean.

## 6. Run methodology (`scripts/run_final.sh`)
- **Restart the vLLM server before each workload** (clean cache, no cross-workload leak / backlog).
- **Warmup** 32 requests per point (fills the pipe → measured window is steady-state, removes the
  cold-cache c4 artifact).
- **Termination**:
  - chatbot / rag / toolagent → `--request-count 160`
  - coding / agent → `--benchmark-duration 300 --benchmark-grace-period 300` (time-boxed)
- **Concurrency sweep**: chatbot, rag → `4 8 16 32`; toolagent, agent, coding → `4 8 16` (no 32).
- **Prefix-cache hit** recorded per (workload, concurrency) from `/metrics`
  (`vllm:prefix_cache_hits_total` / `vllm:prefix_cache_queries_total`, before/after delta) →
  `results/final/<wl>/c<level>/prefix.json`.

Run everything:
```bash
GPU_UTIL=0.85 MAX_NUM_SEQS=32 MAX_MODEL_LEN=248320 MAX_NUM_BATCHED_TOKENS=248320 \
bash scripts/run_final.sh
```
Summaries: `python3 scripts/summarize_final.py` · Pareto: `python3 scripts/plot_pareto.py`.

## 7. Key finding so far — `max-num-batched-tokens` vs the "waiting" queue
On rag c16, going from the default batch budget (~8k) to **248320** (at util 0.85):

| metric | default (util 0.5) | bt=248320 (util 0.85) | Δ |
|---|--:|--:|--:|
| TTFT avg | 19,599 ms | 12,732 ms | **−35%** |
| TTFT p99 | 29,124 ms | 19,061 ms | −35% |
| Req/s | 0.75 | 0.93 | **+24%** |

Live: **running reached 16, waiting = 0** — all 16 rag prefills (16×6.3k ≈ 101k < 248320) batch in
one step instead of being chunked/queued. The cost: the 248320-token activation budget needs more
memory (0.6 util OOM'd → use 0.85).

## Reproduce (full)
```bash
cd monitoring && docker compose up -d && cd ..      # Prometheus :9090 + Grafana :3000
python3 scripts/build_final.py                       # build datasets/aiperf/final_*.jsonl
GPU_UTIL=0.85 MAX_NUM_SEQS=32 MAX_MODEL_LEN=248320 MAX_NUM_BATCHED_TOKENS=248320 \
  bash scripts/run_final.sh                          # restarts server per workload, records prefix-hit
python3 scripts/summarize_final.py                   # tables (incl. prefix-hit)
python3 scripts/plot_pareto.py                       # Pareto curves
```
Earlier passes (util-0.5 baseline, capped/uncapped explorations) are in `RESULTS.md`,
`results/final_u0.5/`, and `SUMMARY_u0.5.txt`.
