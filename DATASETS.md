# Datasets — original sources and workload characteristics

What each of the five workloads is made from, where the raw data comes from, and the
measured input/output/turn characteristics of the converted files in `datasets/aiperf/`.

- **Conversion code**: `scripts/build_datasets.py` (helpers) + `scripts/build_final.py` (v6 `final_*.jsonl`).
- **Stats below**: `python3 scripts/dataset_stats.py` (token counts estimated at 4 chars/token,
  same convention as the build scripts; toolagent counts are exact — the trace carries token
  numbers, not text; p50/p90 are nearest-rank percentiles). For the byte-level payload
  walkthrough see [FORMAT.md](FORMAT.md).
- Raw sources live in `datasets/raw/` (gitignored — re-download from the URLs below).

## At a glance

| Workload | original dataset | raw size | converted file (v6) | aiperf type | scenario it models |
|---|---|---|---|---|---|
| chatbot | [ShareGPT V3 unfiltered_cleaned_split](https://huggingface.co/datasets/anon8231489123/ShareGPT_Vicuna_unfiltered) (aiperf built-in) | 94,145 records → 73,277 sessions / 252,196 turns loaded | — (aiperf downloads its own cache) | `public` (`--public-dataset sharegpt`) | human↔ChatGPT open-domain chat, medium in / medium out |
| coding | [Inferact/codex_swebenchpro_traces](https://huggingface.co/datasets/Inferact/codex_swebenchpro_traces) | 610 traces, 12–200 turns each | `final_coding.jsonl` — 100 conv × 6 turns | `multi_turn` | coding agent: huge repo-context preamble + tool outputs, history re-sent every turn |
| rag | [yixuantt/MultiHopRAG](https://huggingface.co/datasets/yixuantt/MultiHopRAG) | 2,556 queries + 609-article news corpus | `final_rag.jsonl` — 500 requests | `single_turn` | retrieval-augmented QA: long stuffed context, few-word answer |
| agent | [AI45Research/ATBench-Claw](https://huggingface.co/datasets/AI45Research/ATBench-Claw) | 500 trajectories | `final_agent.jsonl` — 200 conv / 887 turns | `multi_turn` | tool-using assistant: short mixed user+tool-result turns |
| toolagent | [Mooncake FAST'25 toolagent trace](https://github.com/kvcache-ai/Mooncake/blob/main/FAST25-release/traces/toolagent_trace.jsonl) | 23,608 trace lines (lengths + block hashes, no text) | `final_toolagent.jsonl` — 320 requests | `mooncake_trace` | production tool/agent traffic replay with realistic prefix reuse |

All v6 `final_*` files cap generation at `output_length` 5000 (toolagent keeps the trace's own
per-request output lengths). Reasoning/thinking flags per workload are listed in
[RUNBOOK.md §5](RUNBOOK.md); this file is about the data itself.

The NVFP4 cross-hardware sweep additionally uses flattened multi-turn variants with
machine-independent input tokens — build/run/preview guide in [FLAT_TRACES.md](FLAT_TRACES.md).

---

## 1) chatbot — ShareGPT

**Original**: ShareGPT — real user↔ChatGPT conversations that users published through the
ShareGPT Chrome extension / sharegpt.com, collected via its public API before it closed (the
corpus Vicuna was trained on). `ShareGPT_V3_unfiltered_cleaned_split.json` is the Vicuna-prep
cleaned split from [anon8231489123/ShareGPT_Vicuna_unfiltered](https://huggingface.co/datasets/anon8231489123/ShareGPT_Vicuna_unfiltered)
(Apache-2.0): non-English and "AI moralizing" removed, long conversations split into
2,048-token chunks → **94,145 records**, the de-facto LLM-serving benchmark set.
Each record: `{"id", "conversations": [{"from": "human"|"gpt", "value": text}, …]}`.

**Conversion**: none — aiperf downloads and parses it itself (`--public-dataset sharegpt`),
using human turns as prompts and each following gpt turn's token count as that turn's
`max_completion_tokens`. It loads 73,277 multi-turn sessions / 252,196 turns.

**Characteristics** (from the recorded `inputs.json` payloads, see FORMAT.md):

| property | value |
|---|---|
| structure | multi-turn chat, history accumulated (assistant turns = model's own replies) |
| input / turn | one human message, typically a few hundred tokens |
| output cap / turn | the original gpt reply's length (e.g. 252, 329 tokens for session 0) |
| traffic shape | balanced prefill/decode, conversational |

## 2) coding — Codex traces on SWE-bench Pro

**Original**: `Inferact/codex_swebenchpro_traces` (Inferact Inc., MIT) — traces of the Codex
coding agent solving SWE-bench Pro tasks: 731 trials over 11 open-source repos, of which the
**610 successful** ones are published (20,230 LLM calls total). Each record is a ShareGPT-style
`conversations` list of 12–200 turns: the first human turn is a ~50 KB preamble (permissions +
skills + repo context), later human turns are real shell/tool outputs fed back to the agent;
gpt turns are anonymized lorem-ipsum placeholders (never sent). The upstream card reports the
workload is massively prefill-dominated (~131:1 input:output tokens, 94.2% cache hit rate in
the original runs) — exactly the character this workload reproduces.

**Conversion** (`build_coding`): first 100 traces, first 6 human turns each → `multi_turn`
sessions; v6 sets every `output_length` to 5000 and keeps reasoning ON.

**Measured** (`final_coding.jsonl`, 100 conv / 600 turns, est. tokens @4 chars):

| property | min | p50 | mean | p90 | max |
|---|--:|--:|--:|--:|--:|
| turns / conversation | 6 | 6 | 6 | 6 | 6 |
| turn-0 input (preamble) | 11,898 | 12,412 | 12,518 | 13,174 | 14,142 |
| per-turn new input | 3 | 5,249 | 6,864 | 13,191 | 32,017 |
| cumulative user text / conv | 18,561 | 37,449 | 41,188 | 63,370 | 93,552 |

**Traffic shape**: the defining feature is the ~12 K-token turn-0 preamble that is re-sent
(via accumulated history) on all 6 turns ⇒ very high prefix-cache hit; ISL grows to tens of
thousands of tokens by the last turn while each turn's *new* text is tool output. With
reasoning ON this is also the decode-heaviest workload (700–4,000 output tok/req observed).

## 3) rag — MultiHopRAG

**Original**: `yixuantt/MultiHopRAG` (paper: *MultiHop-RAG: Benchmarking Retrieval-Augmented
Generation for Multi-Hop Queries*, Tang & Yang, [arXiv:2401.15391](https://arxiv.org/abs/2401.15391);
ODC-BY) — multi-hop QA over English news articles published Sep–Dec 2023 (TechCrunch, The
Verge, Fortune, …): 2,556 queries whose evidence spans 2–4 documents, each with an answer, a
`question_type` (inference / comparison / temporal / null) and an `evidence_list` pointing
into a 609-article news corpus (`corpus.json`); evidence titles resolve to full article bodies
with a 100% hit rate.

**Conversion** (`build_rag`): for each query, join the (deduped) full evidence articles into a
`=== DOCUMENTS ===` block and append the question — i.e. an oracle-retrieval, stuffed-context
RAG prompt. Queries with <4,000 chars of context dropped, context truncated at 120,000 chars;
first 500 kept.
Thinking off (in-data `chat_template_kwargs`).

**Measured** (`final_rag.jsonl`, 500 single-turn requests):

| property | min | p50 | mean | p90 | max |
|---|--:|--:|--:|--:|--:|
| input (chars) | 11,240 | 22,894 | 27,314 | 46,326 | 120,395 |
| input (est. tokens) | 2,810 | 5,723 | 6,828 | 11,581 | 30,098 |

**Traffic shape**: long unique input, few-word answer (model hits EOS after ~3 tokens in
practice) ⇒ essentially a pure-prefill / TTFT workload; no cross-request prefix sharing.

## 4) agent — ATBench-Claw

**Original**: `AI45Research/ATBench-Claw` (Apache-2.0) — the OpenClaw-specific extension of
ATBench, the Agent Trajectory Benchmark for safety evaluation
([arXiv:2604.02022](https://arxiv.org/abs/2604.02022), [arXiv:2604.14858](https://arxiv.org/abs/2604.14858)):
500 trajectories (204 safe / 296 unsafe, avg ~13 message events each) of an OpenClaw-style
assistant with skills/tools handling user tasks. Each record is an Anthropic-style trajectory:
`trajectory.events` = messages with typed content blocks (`text`, `thinking`, `toolCall`,
`toolResult`) plus safety `labels` (risk source / failure mode / harm type — ignored by the
conversion; we use only the message flow).

**Conversion** (`build_agent`): flatten blocks to text (`tool_use` → `[tool_call name: args]`),
merge each run of consecutive non-assistant messages (user + tool results) into one input
turn; first 200 trajectories, ≤8 turns each. Thinking off (in-data).

**Measured** (`final_agent.jsonl`, 200 conv / 887 turns, est. tokens @4 chars):

| property | min | p50 | mean | p90 | max |
|---|--:|--:|--:|--:|--:|
| turns / conversation | 2 | 4 | 4 | 5 | 7 |
| turn-0 input | 333 | 1,107 | 2,075 | 5,213 | 8,279 |
| per-turn new input | 1 | 127 | 554 | 1,340 | 8,279 |
| cumulative user text / conv | 508 | 1,502 | 2,458 | 5,782 | 9,376 |

**Traffic shape**: many short multi-turn exchanges — small contexts, frequent requests;
stresses scheduling/latency rather than KV capacity (contrast with coding).

## 5) toolagent — Mooncake trace

**Original**: Mooncake — the KVCache-centric serving platform behind Moonshot AI's Kimi
(FAST'25 **best paper**: *Mooncake: Trading More Storage for Less Computation*, Qin et al.,
[arXiv:2407.00079](https://arxiv.org/abs/2407.00079); traces Apache-2.0) — published
anonymized production traces. `toolagent_trace.jsonl` is a **1-hour sample of Kimi's
tool/agent traffic**: 23,608 requests, upstream averages 8,596 input / 182 output tokens, 59%
cache ratio; the workload is "pre-designed, often lengthy, fully repetitive system prompts".
Each line has only `timestamp`, `input_length`, `output_length`, and `hash_ids` — cumulative
512-token block hashes where equal ids ⇒ identical prefix content — **no text** (privacy).

**Conversion** (`build_final.py`): first 320 lines, `timestamp` removed (a timestamped trace
forces fixed-schedule replay and ignores `--concurrency`); lengths kept verbatim. At run time
aiperf *synthesizes* prompt text to the exact `input_length`, deterministically per `hash_id`,
so equal blocks are byte-identical — reproducing the trace's real prefix-reuse pattern.

**Measured** (`final_toolagent.jsonl`, 320 requests, exact token counts from the trace):

| property | min | p50 | mean | p90 | max |
|---|--:|--:|--:|--:|--:|
| input_length | 893 | 6,520 | 9,283 | 18,720 | 120,633 |
| output_length | 1 | 34 | 192 | 548 | 929 |
| hash blocks / request | 2 | 13 | 18 | 37 | 236 |

Prefix sharing in the kept slice: 31.9% of block references are to blocks that occur in 2+
requests; the `hash_id 0` system-prompt block opens 149/320 requests.

**Traffic shape**: heavy-tailed inputs (median 6.6 K but max 120 K tokens), short-to-medium
outputs, realistic cross-request prefix reuse ⇒ exercises prefix caching and long-context
prefill under concurrency.

---

## Workload contrast (why these five)

| | input / request | output / request | turns | cross-request prefix reuse | mainly stresses |
|---|---|---|---|---|---|
| chatbot | medium | medium | multi (2–6+) | low | balanced serving |
| coding | very long (served ISL avg 20–24 K; final-turn context larger) | long (reasoning ON) | 6 | **within-conversation, very high** | KV capacity + prefix cache + decode |
| rag | long (mean ~7 K) | tiny | 1 | none | prefill / TTFT |
| agent | short | short-medium | 2–7 | within-conversation | scheduling, many small requests |
| toolagent | heavy-tailed (0.9 K–120 K) | short (≤929) | 1 (trace replay) | **cross-request, block-level** | prefix cache + mixed lengths |
