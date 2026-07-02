#!/usr/bin/env python3
"""Per-workload characteristics of the converted aiperf datasets.

Reads datasets/aiperf/final_*.jsonl and prints, per workload:
  - conversations / turns (and turns-per-conversation distribution)
  - per-turn input length (chars + est. tokens, chars/4 like build_datasets.py)
  - accumulated input at the last turn of each conversation (multi_turn workloads
    re-send the whole history, so this is the ISL the server actually sees)
  - output_length (the max_completion_tokens cap sent per request)

Toolagent lines carry token counts directly (input_length/output_length),
so those are reported verbatim.  Chatbot uses aiperf's built-in ShareGPT
pool and has no file here.
"""
import json, os, statistics as st

DATA = os.path.join(os.path.dirname(__file__), "..", "datasets", "aiperf")
CHARS_PER_TOK = 4.0


def toks(nchars):
    return int(nchars / CHARS_PER_TOK)


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p / 100 * len(xs)))]


def dist(name, xs, unit=""):
    print(f"    {name:<28} min={min(xs):>8,}  p50={pct(xs,50):>8,}  "
          f"mean={int(st.mean(xs)):>8,}  p90={pct(xs,90):>8,}  max={max(xs):>8,} {unit}")


def multi_turn(path):
    rows = [json.loads(l) for l in open(path)]
    nturn = [len(r["turns"]) for r in rows]
    tchars = [len(t["text"]) for r in rows for t in r["turns"]]
    ttoks = [toks(c) for c in tchars]
    ocaps = sorted({t["output_length"] for r in rows for t in r["turns"]})
    # accumulated user-side input at the final turn (history re-sent each turn)
    acc = [toks(sum(len(t["text"]) for t in r["turns"])) for r in rows]
    first = [toks(len(r["turns"][0]["text"])) for r in rows]
    think = {json.dumps(t.get("extra")) for r in rows for t in r["turns"]}
    print(f"  {len(rows)} conversations, {sum(nturn)} turns "
          f"(output_length caps: {ocaps if len(ocaps)<6 else ocaps[:5]+['...']}, extra: {sorted(think)})")
    dist("turns / conversation", nturn)
    dist("turn-0 input (est tok)", first)
    dist("per-turn new input (est tok)", ttoks)
    dist("cum. user text / conv (tok)", acc)


def single_turn(path):
    rows = [json.loads(l) for l in open(path)]
    chars = [len(r["text"]) for r in rows]
    ocaps = sorted({r["output_length"] for r in rows})
    think = {json.dumps(r.get("extra")) for r in rows}
    print(f"  {len(rows)} requests (output_length caps: {ocaps}, extra: {sorted(think)})")
    dist("input (chars)", chars)
    dist("input (est tok)", [toks(c) for c in chars])


def mooncake(path):
    rows = [json.loads(l) for l in open(path)]
    has_ts = any("timestamp" in r for r in rows)
    isl = [r["input_length"] for r in rows]
    osl = [r["output_length"] for r in rows]
    nh = [len(r["hash_ids"]) for r in rows]
    # prefix sharing: how often each hash block reappears
    from collections import Counter
    c = Counter(h for r in rows for h in r["hash_ids"])
    shared = sum(v for v in c.values() if v > 1) / sum(c.values()) * 100
    print(f"  {len(rows)} requests (timestamps {'kept' if has_ts else 'stripped'}; "
          f"token counts are exact, not estimates)")
    dist("input_length (tok)", isl)
    dist("output_length (tok)", osl)
    dist("hash blocks / request", nh)
    print(f"    block reuse: {shared:.1f}% of hash_id references are to blocks that occur "
          f"in 2+ requests (hash_id 0 appears in {c[0]}/{len(rows)} requests)")


for title, fn, path in [
    ("coding — final_coding.jsonl (multi_turn)", multi_turn, "final_coding.jsonl"),
    ("rag — final_rag.jsonl (single_turn)", single_turn, "final_rag.jsonl"),
    ("agent — final_agent.jsonl (multi_turn)", multi_turn, "final_agent.jsonl"),
    ("toolagent — final_toolagent.jsonl (mooncake_trace)", mooncake, "final_toolagent.jsonl"),
]:
    print(f"\n== {title}")
    fn(os.path.join(DATA, path))
