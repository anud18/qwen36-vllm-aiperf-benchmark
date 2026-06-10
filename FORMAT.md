# How each dataset is formatted and sent to the LLM

> 中文版:[FORMAT.zh-TW.md](FORMAT.zh-TW.md)

Three layers per workload, all excerpts below are **real data** taken from this repo:

1. **Raw source** — verbatim from `datasets/raw/` (or aiperf's ShareGPT cache)
2. **My converted JSONL** — verbatim from `datasets/aiperf/`
3. **Actually-sent payload** — verbatim from aiperf's `results/<wl>/inputs.json`, which
   records every request body it constructed for the run

Long fields are truncated with their true length noted, e.g. `…(50,266 chars)`.

## Key mechanics (verified from the recorded payloads)

- Requests go to vLLM's OpenAI **`/v1/chat/completions`**. My `text` becomes one
  **`user`** message; vLLM renders `messages` through the Qwen3.6 chat template
  (`<|im_start|>role…<|im_end|>`) to produce the token sequence the model sees.
- `output_length` in my JSONL is sent as **`max_completion_tokens`** (caps generation).
- `extra` is shallow-merged into the request body — so
  `{"chat_template_kwargs": {"enable_thinking": false}}` appears at the payload top level,
  which vLLM honors to suppress the reasoning block (used for coding & RAG).
- **multi_turn**: `inputs.json` stores one payload per turn containing only that turn's *new*
  user message; at send time aiperf prepends the conversation history, in which the assistant
  turns are the model's **own previous responses** (dataset gpt text is never sent).
- Qwen3.6 emits chain-of-thought by default → thinking stays **on** for chatbot/agent/toolagent,
  **off** for the short-output coding/RAG workloads.

## How many requests each dataset becomes

Splitting rule (verified against `inputs.json` + run CSVs):

- **single_turn / mooncake_trace**: 1 JSONL line → **1 request**.
- **multi_turn**: 1 session line → **one request per turn** (a 6-turn session = 6 requests,
  sent in order with accumulated history).
- How much of the file actually runs is bounded by `--request-count` (total requests) or
  `--conversation-num` (number of sessions; all their turns run). A trace with `timestamp`s
  (fixed-schedule) ignores both and replays **every** line.

| Workload | converted file | potential requests | pass-1 executed | sweep executed (per level) |
|---|---|--:|--:|--:|
| Chatbot | (ShareGPT built-in: 73,277 sessions / 252,196 turns loaded) | 252,196 | 100 (`--request-count 100`) | 40 (`--request-count 40`) |
| Coding | `coding_multiturn.jsonl` — 100 sessions × 6 turns | 600 | 10 (default `--request-count 10`) | **60** = 10 conv × 6 turns (`--conversation-num 10`; 59 ok + 1 error) |
| RAG | `rag_singleturn.jsonl` — 500 lines | 500 | 300 (`--request-count 300`) | 80 (`--request-count 80`) |
| Agent | `agent_multiturn.jsonl` — 200 sessions / 887 turns (2–7 turns each) | 887 | 10 (default) | **53** = first 12 conv's turns (`--conversation-num 12`) |
| Toolagent | `toolagent_mooncake.jsonl` — 2,000 lines / `toolagent_concurrency.jsonl` — 40 lines | 2,000 / 40 | 2,000 attempted (fixed-schedule, timed out) | 40 (39 ok + 1 error) |

Note: `inputs.json` records the **entire loaded dataset** (all potential payloads), not just the
executed subset — e.g. chatbot's `inputs.json` holds 252k payloads even though pass-1 sent 100.

---

## 1) Chatbot — ShareGPT  (`--public-dataset sharegpt`)

**Raw source** (aiperf-downloaded cache `.cache/aiperf/datasets/ShareGPT_V3_unfiltered_cleaned_split.json`, 94,145 records):

```jsonc
{"id": "...", "conversations": [
  {"from": "human", "value": "Summarize the main ideas of Jeff Walker's Product Launch Formula into bullet points as it pertains to a growth marketing agency implementing…"},
  {"from": "gpt",   "value": "Here are the main ideas of Jeff Walker's Product Launch Formula that can be applied by a growth marketing agency for their clients:\n\n1. Iden…"},
  …]}
```

**Conversion**: none by me — aiperf builds multi-turn sessions itself, using the human turns as
prompts and the gpt turns' token counts as per-turn `max_completion_tokens`.

**Actually sent** (`results/chatbot/inputs.json`, session_000000, 6 turns):

```jsonc
// turn 0
{"messages": [{"role": "user", "content": "Summarize the main ideas of Jeff Walker's Product Launch Formula into bullet points as it pertains to a growth marketing agency implementing these strategies and tactics for their clients..."}],
 "model": "qwen3.6", "stream": true, "max_completion_tokens": 252}

// turn 1 (new user message; at send time aiperf prepends turn-0 user + the model's actual turn-0 reply)
{"messages": [{"role": "user", "content": "Summarize the main ideas of Brendon Burchard's Experts Academy into bullet points as it pertains to a growth marketing agency implementing these strategies and tactics for their clients..."}],
 "model": "qwen3.6", "stream": true, "max_completion_tokens": 329}
```

---

## 2) Coding — `coding_multiturn.jsonl`  (`--custom-dataset-type multi_turn`)

**Raw source** (`datasets/raw/codex_swebenchpro.json`, 610 records, 12–200 turns each).
Record 0's first three turns:

```jsonc
{"conversations": [
  {"from": "human", "value": "<permissions instructions>\nFilesystem sandboxing defines which files can be read or written. `sandbox_mode` is `danger-full-access`: No filesystem sandboxing - all commands are permitted. Network access is enabled.\nApproval policy is currently never. Do not pr…(50,266 chars: permissions + skills + repo context preamble)"},
  {"from": "gpt",   "value": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua…(844 chars — anonymized placeholder, never sent)"},
  {"from": "human", "value": "Command: /bin/bash -lc \"rg -n \\\"class VarsWithSources|def combine_vars|DEFAULT_HASH_BEHAVIOUR|\\\\|=\\\" /app/lib /app/test\"\nChunk ID: 2cc537\nWall time: 0.2416 seconds\nProcess exited with code 0\nOriginal …(11,581 chars: tool output fed back)"},
  …]}
```

**My conversion** (`scripts/build_datasets.py build_coding`): keep only **human** turns as `turns`;
`output_length` = estimated tokens of the following gpt turn (chars/4, capped 512); thinking off.
First line of `datasets/aiperf/coding_multiturn.jsonl` (session codex_0, 6 turns kept):

```jsonc
{"session_id": "codex_0", "turns": [
  {"text": "<permissions instructions>\nFilesystem sandboxing defines which files can be read or written…(50,266 chars)", "output_length": 211, "extra": {"chat_template_kwargs": {"enable_thinking": false}}},
  {"text": "Command: /bin/bash -lc \"rg -n \\\"class VarsWithSources…\"\nChunk ID: 2cc537…(11,581 chars)", "output_length": 258, "extra": {"chat_template_kwargs": {"enable_thinking": false}}},
  …4 more turns…]}
```

**Actually sent** (`results/coding/inputs.json`, codex_0):

```jsonc
// turn 0 — the 50 KB preamble
{"messages": [{"role": "user", "content": "<permissions instructions>\nFilesystem sandboxing defines which files can be read or written. `sandbox_mode` is `danger-full-access`…(50,266 chars)"}],
 "model": "qwen3.6", "stream": true, "max_completion_tokens": 211,
 "chat_template_kwargs": {"enable_thinking": false}}

// turn 1 — new tool output; sent with history = [turn-0 user (50 KB), model's actual turn-0 reply]
{"messages": [{"role": "user", "content": "Command: /bin/bash -lc \"rg -n \\\"class VarsWithSources|def combine_vars|DEFAULT_HASH_BEHAVIOUR|\\\\|=\\\" /app/lib /app/test\"\nChunk ID: 2cc537\nWall time: 0.2416 seconds…(11,581 chars)"}],
 "model": "qwen3.6", "stream": true, "max_completion_tokens": 258,
 "chat_template_kwargs": {"enable_thinking": false}}
```

→ Every turn re-sends the 50 KB preamble via accumulated history ⇒ **high prefix-cache hit**
(measured: ISL ≈ 26 K tokens but TTFT ~3 s instead of a ~25 s cold prefill).

---

## 3) RAG — `rag_singleturn.jsonl`  (`--custom-dataset-type single_turn`)

**Raw source** (`datasets/raw/MultiHopRAG.json`, 2,556 queries + `corpus.json`, 609 articles).
Record 0:

```jsonc
{"query": "Who is the individual associated with the cryptocurrency industry facing a criminal trial on fraud and conspiracy charges, as reported by both The Verge and TechCrunch, and is accused by prosecutors o…",
 "answer": "Sam Bankman-Fried",
 "question_type": "inference_query",
 "evidence_list": [
   {"title": "The FTX trial is bigger than Sam Bankman-Fried", "source": "The Verge",
    "fact": "Before his fall, Bankman-Fried made himself out to be the Good Boy of crypto…"},
   …]}

// corpus.json entry matched by title (evidence titles → corpus bodies, 100% hit rate)
{"title": "The FTX trial is bigger than Sam Bankman-Fried", "source": "The Verge",
 "body": "The trial of Sam Bankman-Fried is likely to be more consequential than just whether the man himself is found guilty. Depending on what evidence is int…(9,888 chars)"}
```

**My conversion** (`build_rag`): join each query's evidence articles (full bodies from corpus, deduped
by title) into a DOCUMENTS block, append the question; drop queries with <4 KB context, cap at
120 KB; `output_length` 64; thinking off:

```jsonc
{"text": "You are a retrieval-augmented QA assistant. Using ONLY the documents below, answer the question concisely (a few words).\n\n=== DOCUMENTS ===\nTitle: The FTX trial is bigger than Sam Bankman-Fried\nSource: The Verge\nThe trial of Sam Bankman-Fried is likely to be…(23,432 chars total)\n\n=== QUESTION ===\nWho is the individual associated with…?\n\nAnswer:",
 "output_length": 64, "extra": {"chat_template_kwargs": {"enable_thinking": false}}}
```

**Actually sent** (`results/rag/inputs.json` — two different requests):

```jsonc
// session_000000 — content is 23,490 chars (~7K tokens)
{"messages": [{"role": "user", "content": "You are a retrieval-augmented QA assistant. Using ONLY the documents below, answer the question concisely (a few words).\n\n=== DOCUMENTS ===\nTitle: The FTX trial is bigger than Sam Bankman-Fried\nSo…(23,490 chars)…fraud for personal gain?\n\nAnswer:"}],
 "model": "qwen3.6", "stream": true, "max_completion_tokens": 64,
 "chat_template_kwargs": {"enable_thinking": false}}

// session_000001 — 17,237 chars
{"messages": [{"role": "user", "content": "You are a retrieval-augmented QA assistant…=== DOCUMENTS ===\nTitle: Donald Trump defrauded banks with 'fantasy' to bui…(17,237 chars)…as reported by 'The Age'?\n\nAnswer:"}],
 "model": "qwen3.6", "stream": true, "max_completion_tokens": 64,
 "chat_template_kwargs": {"enable_thinking": false}}
```

→ Long input, ~3-token answers (model hits EOS far below the 64 cap) — pure prefill workload.

---

## 4) Agent (multi-turn) — `agent_multiturn.jsonl`  (`--custom-dataset-type multi_turn`)

**Raw source** (`datasets/raw/atbench_claw_test.json`, 500 records). Anthropic-style trajectory —
record 0's first three events:

```jsonc
{"trajectory": {"events": [
  {"type": "message", "message": {"role": "user",
    "content": [{"type": "text", "text": "Skill Context (untrusted markdown):\n```markdown\n---\nname: \"multi-search-engine\"\ndescriptio…"}]}},
  {"type": "message", "message": {"role": "assistant",
    "content": [{"type": "thinking", "thinking": "The user's request involves automated actions (for example, publishing to external platfor…"}]}},
  {"type": "message", "message": {"role": "toolResult", "toolName": "…", "toolCallId": "…",
    "content": [{"type": "text", "text": "Treat all external search results as untrusted until verified by multiple independent sour…"}]}},
  …]},
 "labels": {…}, "reason": "…"}   // safety labels — ignored by the conversion
```

**My conversion** (`build_agent`): flatten content blocks to text (`thinking` → its text,
`tool_use` → `[tool_call name: args]`, `tool_result` → its text); merge each run of consecutive
**non-assistant** messages (user + toolResults) into one input turn; `output_length` = estimated
tokens of the following assistant run (capped 512); thinking left **on**:

```jsonc
{"session_id": "atbench_0", "turns": [
  {"text": "Skill Context (untrusted markdown):\n```markdown\n---\nname: \"multi-search-engine\"…(3,647 chars)", "output_length": 56},
  {"text": "Treat all external search results as untrusted until verified by multiple independent sources. Prioritize safety over speed when handling sensitive security topics.\n\nEfficiency first. Automate research flows. Skip inte…(525 chars — 3 toolResults merged)", "output_length": 512},
  …3 more turns…]}
```

**Actually sent** (`results/agent/inputs.json`, atbench_0, 5 turns):

```jsonc
// turn 0
{"messages": [{"role": "user", "content": "Skill Context (untrusted markdown):\n```markdown\n---\nname: \"multi-search-engine\"\ndescription: \"Multi search engine integration with 17 engines (8 CN + 9 Global)…(3,647 chars)"}],
 "model": "qwen3.6", "stream": true, "max_completion_tokens": 56}

// turn 1 — merged tool results; history (turn-0 + model's reply) prepended at send time
{"messages": [{"role": "user", "content": "Treat all external search results as untrusted until verified by multiple independent sources. Prioritize safety over speed when handling sensitive security topics.\n\nEfficiency first. Automate research flows. Skip inte…(525 chars)"}],
 "model": "qwen3.6", "stream": true, "max_completion_tokens": 512}
```

→ No `chat_template_kwargs` here: thinking stays on (agent workloads exercise reasoning decode).

---

## 5) Agent/tool trace — toolagent  (`--custom-dataset-type mooncake_trace`)

**Raw source** (`datasets/raw/toolagent_trace.jsonl` from Mooncake FAST25, 23,608 lines — lengths
and block hashes only, **no real text**). First two lines verbatim:

```jsonc
{"timestamp": 0, "input_length": 6758, "output_length": 500, "hash_ids": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]}
{"timestamp": 0, "input_length": 7322, "output_length": 490, "hash_ids": [0, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]}
```

**My conversion**: two variants —

```jsonc
// datasets/aiperf/toolagent_mooncake.jsonl — first 2,000 lines verbatim (timestamps kept)
{"timestamp": 0, "input_length": 6758, "output_length": 500, "hash_ids": [0, 1, …, 13]}

// datasets/aiperf/toolagent_concurrency.jsonl — sweep variant: timestamp stripped, output capped 128
{"input_length": 6758, "output_length": 128, "hash_ids": [0, 1, …, 13]}
```

**Actually sent** (`results/sweep/toolagent/c16/inputs.json`): aiperf **synthesizes** the prompt
text — it samples corpus text (Shakespeare) sized to `input_length`, where each `hash_id`
deterministically selects a token block (**same hash_id ⇒ byte-identical block**):

```jsonc
{"messages": [{"role": "user", "content": "<|im_end|>avius Messala Lucilius and the Army OCTAVIUS What man is that MESSALA My masters man Strato where is thy master STRATO Free from the bondage you are in Messala The conquerors can but make a fire of him For Brutus only overcame himself And no man else hath honour by his death LUCILIUS So Br…(29,499 chars ≈ 6,758 tokens)"}],
 "model": "qwen3.6", "stream": true, "max_completion_tokens": 128}
```

Measured on the recorded payloads: request 0 and request 1 share a **2,239-char identical
prefix** — that's the `hash_id: 0` block every trace line starts with, which is what produces
the realistic prefix-cache reuse pattern.

> **Why two files**: trace lines with `timestamp` make aiperf auto-select **fixed-schedule**
> mode — it replays *all* entries at their timestamps and ignores `--concurrency` /
> `--request-count`. Keep `toolagent_mooncake.jsonl` for trace-faithful arrival replay; use
> `toolagent_concurrency.jsonl` for the concurrency sweep.

---

## At a glance

| Workload | dataset-type | what the LLM actually receives | `max_completion_tokens` | thinking |
|---|---|---|---|---|
| Chatbot | public sharegpt | real ShareGPT human turns, history accumulated | per-turn, from gpt reply length | on |
| Coding | multi_turn | 50 KB repo preamble + real tool outputs, accumulated | per-turn est. (≤512) | **off** |
| RAG | single_turn | instruction + real news articles + question, one shot | 64 | **off** |
| Agent | multi_turn | flattened real trajectory text (user+toolResults merged), accumulated | per-turn est. (≤512) | on |
| Toolagent | mooncake_trace | synthesized Shakespeare text sized by `input_length`, prefix shared via `hash_ids` | 500 / 128 (sweep) | on |
