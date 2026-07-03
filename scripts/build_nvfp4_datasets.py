#!/usr/bin/env python3
"""NVFP4 run datasets: copy final_{rag,agent,coding}.jsonl with output_length clamped to 2048.

toolagent keeps the trace's own lengths (max 929 < 2048) and chatbot is aiperf's
built-in public dataset — neither needs a rewrite.
"""
import json
import pathlib

CAP = 2048
SRC = pathlib.Path(__file__).resolve().parent.parent / "datasets" / "aiperf"


def clamp(obj):
    """Recursively clamp any numeric 'output_length' field to CAP. Returns #changed."""
    n = 0
    if isinstance(obj, dict):
        v = obj.get("output_length")
        if isinstance(v, (int, float)) and v > CAP:
            obj["output_length"] = CAP
            n += 1
        for val in obj.values():
            n += clamp(val)
    elif isinstance(obj, list):
        for val in obj:
            n += clamp(val)
    return n


for wl in ("rag", "agent", "coding"):
    src, dst = SRC / f"final_{wl}.jsonl", SRC / f"nvfp4_{wl}.jsonl"
    lines = fields = changed = 0
    with src.open() as fin, dst.open("w") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            c = clamp(rec)
            changed += c
            fields += str(line).count('"output_length"')
            lines += 1
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"{wl}: {lines} lines, output_length fields seen={fields}, clamped={changed} -> {dst.name}")
    assert fields > 0, f"{wl}: no output_length fields found — schema assumption broken"
