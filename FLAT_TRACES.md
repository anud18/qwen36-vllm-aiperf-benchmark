# Flat traces — flattened multi-turn workloads with machine-independent input tokens

How to build, run, and inspect the `*_flat` datasets used in the NVFP4 cross-hardware
sweep. Results and analysis live in [RESULTS_nvfp4.md](RESULTS_nvfp4.md) (flat-trace
sections); this file is the usage guide.

## Why they exist

The multi-turn workloads (chatbot/agent/coding) have *emergent* ISL: which sessions reach
which turn depth inside the request budget depends on concurrency and machine speed, so two
machines never measure the same input tokens (e.g. coding r1.0: Spark ISL 13.9k vs 5090's
21.8k — the slow machine degenerates to mostly first turns). The flat variants remove that
confound by pre-flattening every conversation turn into one **independent** request whose
full history is fixed in the file — any machine serving the same model/template receives
bit-identical input tokens.

**Verified**: full sweep run twice on the H100 (`results/nvfp4/h100/*_flat` vs
`results/nvfp4/h100run2/`) — 9 points × 96 requests, per-request ISL bit-identical,
prefix-cache queries reproduce exactly.

## Files & format (v2, original text)

`datasets/aiperf/nvfp4_{chatbot,agent,coding}_flat.jsonl` — 240 entries each, aiperf
`mooncake_trace` **`messages` mode**. Entry k of a session carries the real conversation
history verbatim and always ends on a user turn:

```json
{"messages": [{"role":"user","content":"..."},
              {"role":"assistant","content":"..."},
              {"role":"user","content":"..."}],
 "output_length": 329,
 "extra": {"chat_template_kwargs": {"enable_thinking": false}}}
```

Entries are ordered session-by-session, turn-by-turn, so every sweep point consumes the
same first `warmup + request-count` entries in the same order.

Assistant-reply sources:

- **chatbot** — ShareGPT's own gpt replies (true original text); sessions matched back to
  their ShareGPT entries by exact user-text sequence, `output_length` keeps the payload's
  `max_completion_tokens` (aiperf derives it from the same reply).
- **agent / coding** — the datasets carry no assistant text, so replies were generated once
  (greedy: temperature 0, seed 42, thinking off) and frozen; raw generations live in
  `datasets/aiperf/canonical/*_replies.jsonl`.
- **toolagent** needs no flat variant — it is already a lengths-declared trace.

| file | entries | sessions | max turns | ISL avg/min/max (server tokens) | OSL avg |
|---|--:|--:|--:|---|--:|
| `nvfp4_chatbot_flat.jsonl` | 240 | 68 | 11 | 654 / 20 / 1,947 | 233 |
| `nvfp4_agent_flat.jsonl` | 240 | 56 | 6 | 2,977 / 405 / 10,106 | 448 |
| `nvfp4_coding_flat.jsonl` | 240 | 40 | 6 | 29,646 / 12,632 / 76,884 | 673 |

## Rebuild

```bash
# chatbot: no server needed (ShareGPT cache at .cache/aiperf/datasets/ + a materialized
# inputs.json from any past chatbot run for session order)
python3 scripts/build_flat_text_traces.py chatbot

# agent/coding: needs a vLLM endpoint for the one-time canonical generation
# (cached in datasets/aiperf/canonical/ — reruns only generate missing sessions)
python3 scripts/build_flat_text_traces.py agent coding --url http://localhost:8000
```

## Run

Same driver as every other workload — the flat cases are wired into `run_nvfp4.sh`:

```bash
# local box (spark/5090)
NODE=spark POINTS="c2 c8 c32" bash scripts/run_nvfp4.sh chatbot_flat agent_flat coding_flat

# shared box (H100 example: container-name prefixes + user-dir HF cache)
NODE=h100 VLLM_CNAME=an-hao-vllm-nvfp4 CPREFIX=an-hao-aiperf HF_DIR=$HOME/900g/an-hao/hf \
  POINTS="c2 c8 c32" bash scripts/run_nvfp4.sh chatbot_flat agent_flat coding_flat
```

Two things the messages mode requires (both already wired in):

- aiperf **cannot client-side-tokenize raw messages** → the runner passes
  `--use-server-token-count`, so ISL = server-reported `usage.prompt_tokens`
  (includes chat-template tokens — slightly above client-side text counts).
- The server must return usage on streaming responses; aiperf configures
  `stream_options` itself when server token counts are enabled (entries may also carry
  `extra.stream_options.include_usage` — redundant but harmless).

OSL is intentionally **not** pinned: generation stays live, `output_length` only caps it.
Sampling/batching nondeterminism on the output side is expected; the input side is what
the flat variants fix.

## Preview

Up to 5 entries per dataset, up to 1000 chars per entry:

```bash
python3 - <<'EOF' | less
import json
for f in ["datasets/aiperf/nvfp4_chatbot_flat.jsonl",
          "datasets/aiperf/nvfp4_agent_flat.jsonl",
          "datasets/aiperf/nvfp4_coding_flat.jsonl"]:
    print("\n" + "=" * 30, f, "=" * 30)
    for i, line in enumerate(open(f)):
        if i >= 5:                         # up to 5 entries per dataset
            break
        d = json.loads(line)
        print(f"\n--- entry {i} | {len(d['messages'])} msgs | output_length={d['output_length']}")
        budget = 1000                      # up to 1000 chars per entry
        for m in d["messages"]:
            if budget <= 0:
                print("      …(entry truncated at 1000 chars)")
                break
            c = m["content"].replace("\n", "\\n")
            shown = c[:budget]
            more = f" …[+{len(c)-len(shown)} chars]" if len(c) > len(shown) else ""
            print(f"  [{m['role']:>9}] {shown}{more}")
            budget -= len(shown)
EOF
```

## v1 (synthetic) note

The first flat generation (`scripts/build_flat_traces.py`) declared token *lengths* +
`hash_ids` and let aiperf synthesize prompt text. The Spark/5090 flat results under
`results/nvfp4/{spark,5090}/*_flat` predate v2 and were measured against those synthetic
files — regenerate with that script if you ever need the synthetic form back. v2 (this
guide) supersedes it: real text also restores realistic prefix sharing that the 512-token
hash blocks understated for chat (chatbot hit-rate 1.5% → ~22–26%).
