#!/usr/bin/env python3
"""Build the v5 final datasets (reuses build_datasets helpers).

Spec:
  coding   : multi_turn, reasoning ON (no enable_thinking), output max 5000, 100 conv x 6 turns
  rag      : single_turn, reasoning OFF, output max 5000, 500 prompts
  agent    : multi_turn, reasoning OFF, output max 5000, 200 conv
  toolagent: mooncake_trace, no timestamp, keep trace output_length, >=160 lines
             (reasoning OFF is applied at run time via --extra-inputs)
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import build_datasets as bd

OUT = bd.OUT
OCAP = 5000
THINK_OFF = bd.THINK_OFF


def write(name, rows):
    p = os.path.join(OUT, name)
    with open(p, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if rows and "turns" in rows[0]:
        nt = sum(len(r["turns"]) for r in rows)
        print(f"  {name}: {len(rows)} conv, {nt} turns")
    else:
        print(f"  {name}: {len(rows)} requests")


# --- coding: reasoning ON, flat output cap 5000, drop enable_thinking ---
_, coding = bd.build_coding(100, 6, OCAP)
for r in coding:
    for t in r["turns"]:
        t["output_length"] = OCAP
        t.pop("extra", None)            # reasoning ON
write("final_coding.jsonl", coding)

# --- rag: reasoning OFF (THINK_OFF), flat output cap 5000 ---
_, rag = bd.build_rag(500, 4000, 120000, OCAP)
for r in rag:
    r["output_length"] = OCAP
    r["extra"] = THINK_OFF
write("final_rag.jsonl", rag)

# --- agent: reasoning OFF, flat output cap 5000 ---
_, agent = bd.build_agent(200, 8, OCAP)
for r in agent:
    for t in r["turns"]:
        t["output_length"] = OCAP
        t["extra"] = THINK_OFF
write("final_agent.jsonl", agent)

# --- toolagent: mooncake, drop timestamp, keep trace output_length, >=160 lines ---
tool = []
with open(os.path.join(bd.RAW, "toolagent_trace.jsonl")) as f:
    for line in f:
        if len(tool) >= 200:
            break
        d = json.loads(line)
        d.pop("timestamp", None)        # disable fixed-schedule -> concurrency applies
        tool.append(d)
write("final_toolagent.jsonl", tool)

print("done ->", os.path.abspath(OUT))
