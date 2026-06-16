# v6 — dataset → request mapping & executed counts

How each workload's data becomes LLM requests in the v6 run, and exactly how many requests each
point executed. For the full three-layer raw→converted→payload walkthrough of every dataset, see
the repo-root [`FORMAT.md`](../FORMAT.md) (and Chinese [`FORMAT.zh-TW.md`](../FORMAT.zh-TW.md)).

## Splitting rule

- **single_turn / mooncake_trace**: 1 JSONL line → **1 request**.
- **multi_turn**: 1 session line → **one request per turn** (a 6-turn session = 6 requests, sent in
  order with accumulated history; the assistant turns in history are the model's *own* prior
  replies, never the dataset's gpt text).
- How much runs is bounded by `--request-count` (fixed total) or `--benchmark-duration` (time-boxed
  → count is whatever completed in the window, so it grows with concurrency).

## v6 datasets

| Workload | aiperf dataset-type | v6 file | reasoning | output cap |
|---|---|---|---|---|
| chatbot | public (`--public-dataset sharegpt`) | ShareGPT built-in | off (`--extra-inputs`) | 5000 |
| coding | `multi_turn` | `datasets/aiperf/final_coding.jsonl` (100 conv / 600 turns) | **ON** | 5000 |
| rag | `single_turn` | `datasets/aiperf/final_rag.jsonl` (500) | off (in data) | 5000 |
| agent | `multi_turn` | `datasets/aiperf/final_agent.jsonl` (200 conv / 887 turns) | off (in data) | 5000 |
| toolagent | `mooncake_trace` | `datasets/aiperf/final_toolagent.jsonl` (200, timestamps stripped) | off (`--extra-inputs`) | trace len |

## Executed request counts (the authoritative numbers)

Verified from each point's `results/final/<wl>/c<level>/profile_export_aiperf.csv` `Request Count`.

| Workload | termination | executed requests — c4 / c8 / c16 / c32 |
|---|---|--:|
| Chatbot | `--request-count 160` | 160 / 160 / 160 / 160 |
| RAG | `--request-count 160` | 160 / 160 / 160 / 160 |
| Toolagent | `--request-count 160` | 160 / 160 / 160 / — |
| Agent | `--benchmark-duration 300 --grace 300` | 54 / 25 / 121 / — |
| Coding | `--benchmark-duration 300 --grace 300` | 10 / 18 / 31 / — |

- **Reasoning** is OFF for all v6 workloads except **coding** (ON) — that, plus coding's 20–24k-token
  inputs, is why so few coding requests complete inside the 300 s window.
- **Warmup** (separate from the counts above): 32 requests/point, **except coding = 8** — 32
  reasoning-ON warmup requests at low concurrency took ~18 min and never finished in time.
- Duration-mode counts are **not** monotonic in concurrency (agent c8=25 < c4=54): each session's
  turns run sequentially, so which conversations are mid-flight when the 300 s window closes varies;
  longer outputs in flight at that moment mean fewer completed requests.
