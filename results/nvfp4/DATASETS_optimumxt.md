# Datasets used in the optimumxt benchmarks

What `nvfp4_chatbot_flat.jsonl` and `nvfp4_agent_flat.jsonl` actually contain, their ISL/OSL
distributions under both tokenizers, and where their prefix-cache hit rates come from.

Build procedure and design rationale live in [`../../FLAT_TRACES.md`](../../FLAT_TRACES.md); this
file is the data description. Metric formulas: [`SPARK_REPRO.md` § Metric
definitions](SPARK_REPRO.md#metric-definitions).

## Format

`mooncake_trace` in **`messages` mode**. One JSON object per line; one line is one independent
request that carries its full conversation history inline.

```json
{
  "messages": [
    {"role": "user", "content": "Summarize the main ideas of Jeff Walker's Product Launch Formula…"}
  ],
  "output_length": 252,
  "extra": {
    "chat_template_kwargs": {"enable_thinking": false},
    "stream_options": {"include_usage": true},
    "temperature": 0,
    "seed": 42,
    "ignore_eos": true
  }
}
```

Everything that makes a run reproducible is **in the data**, not on the command line:
`temperature 0`, `seed 42`, thinking off, and `ignore_eos` — which is what pins OSL to
`output_length` and gives `osl_mismatch_count = 0` on every valid point.

### "Flat" means the history is materialised

Entry 1 of the same session repeats entry 0's user turn *and its assistant reply*, then adds the
next user turn:

```
[0] user       Summarize the main ideas of Jeff Walker's Product Launch Formula…   (190 chars)
[1] assistant  Here are the main ideas of Jeff Walker's Product Launch Formula…  (1,298 chars)
[2] user       Summarize the main ideas of Brendon Burchard's Experts Academy…    (188 chars)
output_length = 329
```

So ISL is fixed by the file rather than emerging from how far a session got before the request
budget ran out — the property the flat variants exist for. It is also the direct cause of the
prefix-cache behaviour below.

`agent_flat` entries look different: turn 0 is already a single 3,647-character user message
carrying a skill definition, which is why its ISL is ~2.6× chatbot's.

```
[0] user  Skill Context (untrusted markdown): ```markdown --- name: "multi-search-engine"…  (3,647 chars)
output_length = 332
```

## Structure

| | `chatbot_flat` | `agent_flat` |
|---|--:|--:|
| entries (= requests) | 384 | 384 |
| distinct sessions | 109 | 88 |
| turns per session — min / median / max | 1 / 3 / 11 | 3 / 4 / 6 |
| mean turns per session | 3.5 | 4.4 |
| messages per entry — min / max | 1 / 21 | 1 / 11 |

Entries are in session order, so any prefix of the file is a set of whole-or-partial sessions —
which is why a run consuming `entries[0:N]` is deterministic but is *not* a uniform sample of the
workload.

## ISL and OSL, whole file

OSL comes from the trace and is identical under every tokenizer. ISL is tokenizer-dependent, so
both are given.

| dataset | tokenizer | ISL mean | p50 | p90 | p99 | max | ISL sum | ISL+OSL max | over 4096 |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|
| `chatbot_flat` | Llama-3.1-8B | 641.5 | 530 | 1,453 | 1,951 | 2,062 | 246,334 | 2,404 | **0 / 384** |
| `chatbot_flat` | Qwen3-VL-30B-A3B | 622.2 | 518 | 1,446 | 1,945 | 2,054 | 238,918 | 2,390 | **0 / 384** |
| `agent_flat` | Llama-3.1-8B | 3,038.3 | 2,172 | 6,145 | 11,491 | 12,282 | 1,166,691 | 12,510 | 105 / 384 |
| `agent_flat` | Qwen3-VL-30B-A3B | 3,063.0 | 2,185 | 6,172 | 11,670 | 12,500 | 1,176,193 | 12,728 | 107 / 384 |

| dataset | OSL mean | p50 | p90 | max | OSL sum |
|---|--:|--:|--:|--:|--:|
| `chatbot_flat` | 249.9 | 233 | 460 | 870 | 95,954 |
| `agent_flat` | 256.1 | 192 | 490 | 1,381 | 98,324 |

Both datasets are **decode-heavy relative to their prefill cost on healthy hardware** but
prefill-dominated on the Dynamo endpoints — that inversion is the subject of
[`SPARK_REPRO.md`](SPARK_REPRO.md).

`agent_flat` does not fit a 4096-token context: 105–107 of its 384 entries exceed the cap and are
rejected with HTTP 400 before reaching the engine. Hence the filtered variants.

## Filtered variants for a 4096 cap

Produced by [`../../scripts/filter_le4096.py`](../../scripts/filter_le4096.py), keeping entries
with `ISL + OSL ≤ 4096`, in file order.

| variant | dataset | kept | dropped |
|---|---|--:|--:|
| `datasets/aiperf/le4096/` (Llama) | `chatbot_flat` | 384 / 384 | 0 |
| `datasets/aiperf/le4096/` (Llama) | `agent_flat` | 279 / 384 | **105** |
| `datasets/aiperf/le4096_qwen3vl/` | `chatbot_flat` | 384 / 384 | 0 |
| `datasets/aiperf/le4096_qwen3vl/` | `agent_flat` | 277 / 384 | **107** |

Filtering is tokenizer-dependent, so the two models keep different entry sets — their filtered
`agent_flat` points are not identical workloads *to each other*. The chatbot copies are
byte-identical to the originals and exist only so `DATA_DIR` resolves.

**Filtered `agent_flat` is a new workload, not a subset for comparison.** Dropping the long
entries shifts the length distribution downward; do not compare its numbers with unfiltered
`agent_flat` runs.

## Per-slice figures, as actually consumed

aiperf consumes entries in file order: a point uses `entries[warmup : warmup + requests]`. These
are the exact slices behind every point in the reports.

| slice | tokenizer | entries | n | ISL sum | ISL avg | ISL max | OSL sum | OSL avg | OSL max |
|---|---|---|--:|--:|--:|--:|--:|--:|--:|
| chatbot_flat w2 c1 (10 req) | Llama | `[2:12]` | 10 | 6,199 | 619.9 | 1,665 | 2,790 | 279.0 | 456 |
| chatbot_flat w2 c1 (10 req) | Qwen | `[2:12]` | 10 | 5,937 | 593.7 | 1,639 | 2,790 | 279.0 | 456 |
| chatbot_flat w2 c2 (20 req) | Llama | `[2:22]` | 20 | 12,518 | 625.9 | 1,665 | 6,080 | 304.0 | 641 |
| chatbot_flat w2 c2 (20 req) | Qwen | `[2:22]` | 20 | 12,040 | 602.0 | 1,639 | 6,080 | 304.0 | 641 |
| chatbot_flat w0 (20 req) | Llama | `[0:20]` | 20 | 12,176 | 608.8 | 1,665 | 5,970 | 298.5 | 641 |
| chatbot_flat w0 (20 req) | Qwen | `[0:20]` | 20 | 11,698 | 584.9 | 1,639 | 5,970 | 298.5 | 641 |
| agent_flat w2 c1 (10 req) | Llama | `[2:12]` | 10 | 16,967 | 1,696.7 | 2,985 | 2,344 | 234.4 | 436 |
| agent_flat w2 c1 (10 req) | Qwen | `[2:12]` | 10 | 16,864 | 1,686.4 | 2,978 | 2,344 | 234.4 | 436 |
| agent_flat w2 c2 (20 req) | Llama | `[2:22]` | 20 | 33,010 | 1,650.5 | 3,054 | 4,563 | 228.2 | 452 |
| agent_flat w2 c2 (20 req) | Qwen | `[2:22]` | 20 | 32,937 | 1,646.8 | 3,124 | 4,563 | 228.2 | 452 |
| agent_flat w0 (20 req) | Llama | `[0:20]` | 20 | 33,226 | 1,661.3 | 3,054 | 4,766 | 238.3 | 452 |
| agent_flat w0 (20 req) | Qwen | `[0:20]` | 20 | 33,160 | 1,658.0 | 3,124 | 4,766 | 238.3 | 452 |
| chatbot_flat r100 (100 req, filtered) | Llama | `[0:100]` | 100 | 65,546 | 655.5 | 1,951 | 24,723 | 247.2 | 740 |
| chatbot_flat r100 (100 req, filtered) | Qwen | `[0:100]` | 100 | 63,251 | 632.5 | 1,924 | 24,723 | 247.2 | 740 |
| agent_flat r100 (100 req, filtered) | Llama | `[0:100]` | 100 | 163,441 | 1,634.4 | 3,832 | 22,348 | 223.5 | 913 |
| agent_flat r100 (100 req, filtered) | Qwen | `[0:100]` | 100 | 161,083 | 1,610.8 | 3,312 | 22,411 | 224.1 | 913 |

These ISL sums are what the endpoint and spark runs reproduce exactly — the parity check in
[`SPARK_REPRO.md`](SPARK_REPRO.md).

Note the OSL sums differ slightly between the two filtered `agent_flat` variants (22,348 vs
22,411): different entries survive filtering, so the first 100 are not the same 100.

## Prefix cache rate — why it is what it is

The hit rate is a **property of the data**, not of the server. Because entry *k* of a session
contains entry *k−1* verbatim as its opening, everything up to `len(entry k−1)` is a reusable
prefix. With a 16-token KV block, the theoretical ceiling over the whole file is:

| dataset | tokenizer | theoretical prefix reuse |
|---|---|--:|
| `chatbot_flat` | Llama-3.1-8B | **64.8 %** |
| `chatbot_flat` | Qwen3-VL-30B-A3B | **64.6 %** |
| `agent_flat` | Llama-3.1-8B | **72.8 %** |
| `agent_flat` | Qwen3-VL-30B-A3B | **72.6 %** |

Measured against the Dynamo endpoints:

| point | measured hit rate | theoretical | source |
|---|--:|--:|---|
| Qwen `chatbot_flat` w0 c1 | 61.75 % | 64.6 % | [`TABLES_w0.md`](TABLES_w0.md) |
| Qwen `agent_flat` w0 c1 | 69.39 % | 72.6 % | [`TABLES_w0.md`](TABLES_w0.md) |
| Llama `chatbot_flat` w0 c1 | 63.83 % | 64.8 % | [`TABLES_llama31_cf.md`](TABLES_llama31_cf.md) |
| Llama `agent_flat` w0 c1 | 69.90 % | 72.8 % | [`TABLES_llama31_cf.md`](TABLES_llama31_cf.md) |
| Llama `chatbot_flat` r100 c1 | 67.04 % | 64.8 % | [`TABLES_r100.md`](TABLES_r100.md) |
| Llama `chatbot_flat` r100 **c2** | 46.77 % | 64.8 % | [`TABLES_r100.md`](TABLES_r100.md) |

Every c1 measurement lands within ~3 points of the ceiling, which is the expected shortfall: a
short slice contains partial sessions whose earlier turns are outside the window, and the final
partial block of each prefix is not reusable.

**Concurrency is what breaks it.** At c2 the same slice — identical ISL totals — drops to 46.77 %,
because two sessions are in flight at once and a turn can start before the previous turn of its own
session has finished writing its blocks. That is a real effect of the request schedule, not a
measurement artefact, and it is why hit rate must be compared only at equal concurrency.

**Cross-round carryover is zero**, verified on a restarted worker with a provably cold cache that
still reported the identical 7,772 cache-read tokens — see the repeatability section of
[`TABLES_llama31_cf.md`](TABLES_llama31_cf.md). All of the hit rate above is intra-run.

> The local spark runs have **no** prefix-cache figures — `REMOTE=1` plus vLLM returning
> `prompt_tokens_details: null` leaves aiperf without a per-request cache count. The theoretical
> ceilings above are the only prefix-reuse numbers that apply to those runs. See *Known gap* in
> [`SPARK_REPRO.md`](SPARK_REPRO.md).

## Not used here

`coding_flat`, `rag` and `toolagent` were never run against these endpoints — their prompts exceed
4096 by a wide margin (`coding_flat` on 384/384 entries, `toolagent` reaching 120,633 tokens). The
feasibility table is in [`qwen3vl_ngrok/RESULTS.md`](qwen3vl_ngrok/RESULTS.md).
