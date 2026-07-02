#!/usr/bin/env python3
"""Build final_coding_split.jsonl — coding workload with guaranteed prefix-cache reuse.

Instead of aiperf `multi_turn` sessions (100 conv x 6 turns, where cross-request
prefix reuse depends on aiperf's session mechanics and the model's own outputs),
this picks a few full traces and explodes each into cumulative single_turn
requests: request N of a trace = the concatenation of that trace's first N
turns (human tool-outputs + the trace's gpt placeholder replies, role-marked).

Request N is a byte-exact prefix of request N+1, so the server's prefix cache
is exercised deterministically — independent of scheduling, session affinity,
or generation nondeterminism.

Same generation settings as final_coding.jsonl: output_length 5000, reasoning ON.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import build_datasets as bd

OCAP = 5000


def build_split(n_requests, max_chars):
    src = json.load(open(os.path.join(bd.RAW, "codex_swebenchpro.json")))
    rows, n_trunc, n_traces = [], 0, 0
    for i, rec in enumerate(src):
        if len(rows) >= n_requests:
            break
        n_traces += 1
        history = []
        cum = 0
        for c in rec["conversations"]:
            role = "user" if c.get("from") == "human" else "assistant"
            piece = f"[{role}]\n{c.get('value', '')}"
            if cum + len(piece) > max_chars:
                n_trunc += 1
                break
            history.append(piece)
            cum += len(piece)
            if role == "user":
                # model is asked to respond right after each human turn,
                # so this cumulative history is exactly what it would see
                rows.append({
                    "session_id": f"codex_{i}",  # kept for traceability; ignored by single_turn
                    "text": "\n\n".join(history),
                    "output_length": OCAP,
                })
                if len(rows) >= n_requests:
                    break
    return rows, n_trunc, n_traces


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--requests", type=int, default=320,
                    help="total requests to emit; traces are consumed in order and the "
                         "last one may be cut mid-trace")
    ap.add_argument("--max-chars", type=int, default=600000,
                    help="stop emitting deeper requests for a trace beyond this "
                         "cumulative size (600K chars ~ 150K tok, fits max-model-len 248320)")
    a = ap.parse_args()

    rows, n_trunc, n_traces = build_split(a.requests, a.max_chars)
    out = os.path.join(bd.OUT, "final_coding_split.jsonl")
    with open(out, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # prefix-reuse accounting: request N shares its full text with request N+1
    total = sum(len(r["text"]) for r in rows)
    shared = 0
    for j in range(1, len(rows)):
        if rows[j]["session_id"] == rows[j - 1]["session_id"]:
            shared += len(rows[j - 1]["text"])
    print(f"  final_coding_split.jsonl: {len(rows)} requests from {n_traces} traces "
          f"({n_trunc} traces truncated at --max-chars)")
    print(f"  total chars {total:,}; chars re-served from a prior request's prefix: "
          f"{shared:,} ({shared / total:.1%})")


if __name__ == "__main__":
    main()
