# Result tables — `WARMUP=0`, `REQS=20`, concurrency 1

Endpoint `https://poppy-zero-ritzy.ngrok-free.dev` → `Qwen3-VL-30B-A3B-Instruct-optimumxt`
(NVIDIA Dynamo, context 4096). Flat-trace track, `REMOTE=1`, no warmup phase, trace slice
`[0:20]`, OSL pinned to the trace via in-data `ignore_eos`. aiperf 0.10.0. 2026-07-29.

**TPOT and ITL are the same quantity here.** aiperf's `inter_token_latency` is
`(request_latency − TTFT) / (OSL − 1)`, which is the standard time-per-output-token definition —
verified against a raw record: `(57,609.37 − 39,895.55) / (332 − 1) = 53.516 ms`, matching the
reported value exactly. They are shown as one row rather than duplicated.

**p50 is the median** — one column, both labels.

## Distribution metrics

| workload | point | metric | avg | p50 (median) | p90 | p95 | p99 | min | max | std |
|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|
| `chatbot_flat` | c1 | TTFT (ms) | 8,693.71 | 10,015.69 | 13,632.09 | 13,844.69 | 16,938.74 | 510.26 | 17,712.25 | 5,169.81 |
| `chatbot_flat` | c1 | ITL = TPOT (ms) | 49.90 | 48.61 | 56.44 | 57.67 | 57.97 | 42.06 | 58.05 | 4.71 |
| `chatbot_flat` | c1 | E2E request latency (ms) | 23,583.99 | 26,158.60 | 32,460.52 | 32,820.54 | 33,579.58 | 3,928.62 | 33,769.34 | 8,135.74 |
| `chatbot_flat` | c1 | ISL (tokens) | 584.9 | 439.0 | 1,321.5 | 1,444.3 | 1,600.0 | 13.0 | 1,639.0 | 516.8 |
| `chatbot_flat` | c1 | OSL (tokens) | 298.5 | 288.0 | 427.2 | 465.3 | 605.8 | 73.0 | 641.0 | 113.9 |
| `chatbot_flat` | c1 | Per-user output throughput (tok/s) | 20.22 | 20.57 | 22.92 | 23.30 | 23.68 | 17.23 | 23.78 | 1.91 |
| `chatbot_flat` | c1 (repeat) | TTFT (ms) | 8,705.66 | 10,072.60 | 13,533.36 | 13,754.29 | 16,959.16 | 487.49 | 17,760.38 | 5,185.11 |
| `chatbot_flat` | c1 (repeat) | ITL = TPOT (ms) | 50.31 | 49.11 | 56.67 | 58.14 | 58.72 | 43.72 | 58.86 | 4.63 |
| `chatbot_flat` | c1 (repeat) | E2E request latency (ms) | 23,698.45 | 26,188.78 | 32,766.01 | 32,930.60 | 33,804.26 | 4,091.47 | 34,022.67 | 8,156.42 |
| `chatbot_flat` | c1 (repeat) | ISL (tokens) | 584.9 | 439.0 | 1,321.5 | 1,444.3 | 1,600.0 | 13.0 | 1,639.0 | 516.8 |
| `chatbot_flat` | c1 (repeat) | OSL (tokens) | 298.5 | 288.0 | 427.2 | 465.3 | 605.8 | 73.0 | 641.0 | 113.9 |
| `chatbot_flat` | c1 (repeat) | Per-user output throughput (tok/s) | 20.04 | 20.37 | 22.48 | 22.66 | 22.83 | 16.99 | 22.87 | 1.81 |
| `agent_flat` | c1 | TTFT (ms) | 20,617.85 | 16,668.00 | 40,537.10 | 47,333.55 | 62,875.49 | 6,189.55 | 66,760.97 | 15,051.28 |
| `agent_flat` | c1 | ITL = TPOT (ms) | 57.93 | 57.98 | 65.83 | 66.15 | 68.38 | 48.80 | 68.94 | 5.52 |
| `agent_flat` | c1 | E2E request latency (ms) | 34,705.85 | 30,515.25 | 55,283.25 | 59,401.35 | 86,639.42 | 10,296.84 | 93,448.94 | 20,284.31 |
| `agent_flat` | c1 | ISL (tokens) | 1,658.0 | 1,579.5 | 2,903.3 | 2,985.3 | 3,096.3 | 462.0 | 3,124.0 | 760.8 |
| `agent_flat` | c1 | OSL (tokens) | 238.3 | 153.5 | 436.0 | 436.8 | 449.0 | 80.0 | 452.0 | 130.4 |
| `agent_flat` | c1 | Per-user output throughput (tok/s) | 17.42 | 17.25 | 19.72 | 20.24 | 20.44 | 14.50 | 20.49 | 1.65 |

## Aggregate metrics

Throughput and totals are single values per point — aiperf does not produce percentiles for them.

| metric | `chatbot_flat` c1 | `chatbot_flat` c1 (repeat) | `agent_flat` c1 |
|---|--:|--:|--:|
| Request throughput (req/s) | 0.0424 | 0.0422 | 0.0288 |
| Output token throughput (tok/s) | 12.65 | 12.59 | 6.86 |
| Total token throughput (tok/s) | 37.45 | 37.27 | 54.62 |
| E2E output token throughput (tok/s) | 13.62 | 13.51 | 7.31 |
| Total ISL (tokens) | 11,698 | 11,698 | 33,160 |
| Total OSL (tokens) | 5,970 | 5,970 | 4,766 |
| Prefix cache hit rate (%) | 61.75 | 61.75 | 69.39 |
| Cache-read tokens | 7,224 | 7,224 | 23,010 |
| Benchmark duration (s) | 471.83 | 474.11 | 694.41 |
| Requests completed | 20 / 20 | 20 / 20 | 20 / 20 |
| Errors | 0 | 0 | 0 |
| OSL mismatches | 0 | 0 | 0 |

`agent_flat` posts the highest *total* token throughput (54.62 tok/s) only because 69 % of its
prompt tokens are prefix-cache hits and cost almost nothing. Its *request* throughput is the
lowest of the three (0.0288 req/s). Ranking by total token throughput inverts the real ordering.

## `agent_flat` c2 — INVALID, do not cite

The concurrency-2 point ran at 17:40–17:51 but **only 14 of 20 requests completed**. The other 6
were rejected by the ngrok tunnel, not by the server:

```
403 Forbidden — "This ngrok account has reached its network bandwidth
limit for the month."  ERR_NGROK_725   (count: 6)
```

The failures are a tunnel-level quota, and they also distort the concurrency timing for the
requests that did succeed. The numbers below are recorded for completeness only and must not be
compared with the valid points above.

| metric | value (14/20 requests) |
|---|--:|
| TTFT avg / p50 / p90 / p95 (ms) | 37,389.38 / 31,479.67 / 69,581.06 / 82,477.21 |
| ITL = TPOT avg / p50 / p90 / p95 (ms) | 238.45 / 245.00 / 309.65 / 443.31 |
| E2E request latency avg / p50 / p90 / p95 (ms) | 92,024.97 / 91,784.44 / 153,535.98 / 156,315.05 |
| ISL avg / p50 (tokens) | 1,551.0 / 1,466.0 |
| OSL avg / p50 (tokens) | 231.4 / 153.5 |
| Request throughput (req/s) | 0.0217 |
| Output token throughput (tok/s) | 5.02 |
| Total token throughput (tok/s) | 38.63 |
| Prefix cache hit rate (%) | 46.67 |
| Benchmark duration (s) | 646.02 |

As of 17:53 the endpoint returns HTTP 403 from ngrok for every request — the tunnel is serving
ngrok's error page instead of reaching Dynamo. **No further benchmarking is possible until the
bandwidth quota resets or the account is upgraded.**

## Artifacts

- `results/nvfp4/w0_chatbot/chatbot_flat/c1/`
- `results/nvfp4/w0_chatbot_rep/chatbot_flat/c1/`
- `results/nvfp4/w0_agent/agent_flat/c1/`
- `results/nvfp4/w0_agent/agent_flat/c2/` — invalid, see above
- logs: `results/nvfp4/w0_run.log`, `results/nvfp4/w0_agent_c2.log`

Full context, methodology caveats and the endpoint's known problems:
`results/nvfp4/qwen3vl_ngrok/RESULTS.md`
