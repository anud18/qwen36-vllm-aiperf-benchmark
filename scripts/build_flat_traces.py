#!/usr/bin/env python3
"""Flatten the multi-turn chatbot/agent workloads into mooncake_trace files with
machine-independent ISL (the toolagent approach: lengths declared per entry).

Each conversation turn becomes one independent trace entry:
  input_length(turn k)  = tokens(user texts 1..k) + sum(output_length 1..k-1)
  output_length(turn k) = the turn's requested completion length (cap 2048)
  hash_ids              = 512-token blocks; turn k reuses turn k-1's full blocks,
                          so per-session prefix sharing survives the flattening.
Entries are ordered session-by-session, turn-by-turn; every sweep point consumes
the same first warmup+request-count entries in the same order, so ISL is identical
across concurrency/rate points and across machines.

Sources:
  agent   — datasets/aiperf/nvfp4_agent.jsonl (multi_turn: 200 sessions, 887 turns)
  chatbot — the seed-42 ShareGPT sample aiperf materialized, taken verbatim from
            results/nvfp4/spark/chatbot/c2/inputs.json (sessions in file order)

Run inside the aiperf image (needs transformers + the HF cache):
  docker run --rm -v ~/.cache/huggingface:/hf -e HF_HOME=/hf -e HF_HUB_OFFLINE=1 \
    -v "$PWD":/work -w /work --entrypoint python3 aiperf:local scripts/build_flat_traces.py
"""
import json
import os

BLOCK = 512          # mooncake hash-id block size (matches final_toolagent.jsonl)
OSL_CAP = 2048
N_ENTRIES = 240      # per file; each point consumes warmup 16 + 96 = 112
TOKENIZER = "nvidia/Qwen3.6-35B-A3B-NVFP4"
CHATBOT_INPUTS = "results/nvfp4/spark/chatbot/c2/inputs.json"
OUT = "datasets/aiperf"


def flatten(sessions, tok, out_path):
    """sessions: [[(user_text, output_length), ...], ...] -> trace jsonl"""
    next_id = 0
    n = 0
    with open(out_path, "w") as f:
        for turns in sessions:
            if n >= N_ENTRIES:
                break
            ctx_tokens = 0     # context before this turn's user text: L_{k-1} + reply_{k-1}
            prev_isl = 0       # L_{k-1}: previous turn's input length
            prev_ids = []      # previous turn's hash_ids
            for text, osl in turns:
                if n >= N_ENTRIES:
                    break
                user_tok = len(tok(text, add_special_tokens=False)["input_ids"])
                isl = ctx_tokens + user_tok
                nblocks = (isl + BLOCK - 1) // BLOCK
                # share only the previous *input*'s full blocks; the partial block and
                # the reply tokens are new content from this turn's perspective
                shared = min(prev_isl // BLOCK, len(prev_ids))
                ids = prev_ids[:shared]
                while len(ids) < nblocks:
                    ids.append(next_id)
                    next_id += 1
                capped = min(int(osl), OSL_CAP)
                f.write(json.dumps({"input_length": isl,
                                    "output_length": capped,
                                    "hash_ids": ids}) + "\n")
                n += 1
                prev_ids, prev_isl = ids, isl
                ctx_tokens = isl + capped  # next turn appends the reply
    return n


def measured_osl_lookup(wl):
    """Measured per-(session, turn) OSL from the real multi-turn runs of `wl`.

    The agent/coding datasets declare output_length 2048 everywhere (clamped),
    but the model EOSes at ~460/~640 avg — and in trace mode aiperf's synthetic
    prompts DO generate close to the declared length (toolagent: declared 216 vs
    measured 207). Using 2048 would make the flat workloads ~3-4x heavier on
    decode than the originals, so declare the measured lengths instead.
    """
    import glob
    import statistics
    per_pair, per_ti = {}, {}
    for p in glob.glob(f"results/nvfp4/*/{wl}/*/profile_export.jsonl"):
        for line in open(p):
            d = json.loads(line)
            m = d["metadata"]
            v = d["metrics"]["output_sequence_length"]["value"]
            per_pair.setdefault((m["conversation_id"], m["turn_index"]), []).append(v)
            per_ti.setdefault(m["turn_index"], []).append(v)
    pair_med = {k: statistics.median(v) for k, v in per_pair.items()}
    ti_avg = {k: sum(v) / len(v) for k, v in per_ti.items()}
    overall = sum(sum(v) for v in per_ti.values()) / sum(len(v) for v in per_ti.values())

    def lookup(sid, ti):
        return max(1, int(pair_med.get((sid, ti)) or ti_avg.get(ti) or overall))
    return lookup


def multiturn_sessions(wl):
    osl_of = measured_osl_lookup(wl)
    for line in open(os.path.join(OUT, f"nvfp4_{wl}.jsonl")):
        d = json.loads(line)
        yield [(t["text"], osl_of(d["session_id"], i)) for i, t in enumerate(d["turns"])]


def chatbot_sessions():
    data = json.load(open(CHATBOT_INPUTS))["data"]
    for sess in data:
        turns = []
        for p in sess["payloads"]:
            user = " ".join(m["content"] for m in p["messages"] if m["role"] == "user")
            turns.append((user, p.get("max_completion_tokens") or 128))
        if turns:
            yield turns


def main():
    # v1 SYNTHETIC generator — superseded by build_flat_text_traces.py (original
    # text, messages mode). Running this would overwrite the text-mode
    # nvfp4_*_flat.jsonl files with synthetic ones, so it now requires opt-in.
    if os.environ.get("FORCE_V1") != "1":
        raise SystemExit(
            "build_flat_traces.py is the SUPERSEDED v1 synthetic generator; the "
            "current nvfp4_*_flat.jsonl are original-text (see FLAT_TRACES.md, "
            "scripts/build_flat_text_traces.py). Set FORCE_V1=1 to overwrite anyway.")
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(TOKENIZER)
    for name, sessions in [("agent_flat", multiturn_sessions("agent")),
                           ("coding_flat", multiturn_sessions("coding")),
                           ("chatbot_flat", chatbot_sessions())]:
        path = os.path.join(OUT, f"nvfp4_{name}.jsonl")
        n = flatten(sessions, tok, path)
        isl = [json.loads(l)["input_length"] for l in open(path)]
        osl = [json.loads(l)["output_length"] for l in open(path)]
        head = isl[:112]
        print(f"{name}: {n} entries -> {path}")
        print(f"  first112 ISL avg={sum(head)/len(head):,.0f} min={min(head)} max={max(head)}"
              f" | all OSL avg={sum(osl)/len(osl):,.0f}")


if __name__ == "__main__":
    main()
