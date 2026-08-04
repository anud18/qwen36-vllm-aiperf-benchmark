#!/usr/bin/env python3
"""Drop flat-trace entries that cannot fit a small context window.

The optimumxt Dynamo deployments cap context at 4096 tokens, which rejects a
large share of agent_flat with HTTP 400 before the request ever reaches the
engine. This writes filtered copies keeping only entries with ISL + OSL <= LIMIT,
preserving file order so a run still consumes a deterministic prefix.

    python3 scripts/filter_le4096.py --tokenizer NousResearch/Meta-Llama-3.1-8B-Instruct

Filtering is tokenizer-dependent: a different model keeps a different set, so
regenerate before benchmarking a different endpoint. Point the runner at the
output with DATA_DIR=datasets/aiperf/le4096.

Note the result is a NEW workload, not a subset of the old one for comparison
purposes -- dropping the long entries shifts the length distribution. Do not
compare filtered agent_flat numbers against unfiltered ones.
"""
import argparse, json, os

p = argparse.ArgumentParser()
p.add_argument("--tokenizer", default="NousResearch/Meta-Llama-3.1-8B-Instruct")
p.add_argument("--limit", type=int, default=4096)
p.add_argument("--src", default="datasets/aiperf")
p.add_argument("--out", default="datasets/aiperf/le4096")
p.add_argument("--workloads", nargs="+", default=["chatbot", "agent"])
a = p.parse_args()

from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained(a.tokenizer)
os.makedirs(a.out, exist_ok=True)

for name in a.workloads:
    src = f"{a.src}/nvfp4_{name}_flat.jsonl"
    kept, dropped = [], 0
    for line in open(src):
        d = json.loads(line)
        isl = len(tok.apply_chat_template(
            d["messages"], tokenize=True, add_generation_prompt=True, return_dict=False))
        if isl + d["output_length"] <= a.limit:
            kept.append(line)
        else:
            dropped += 1
    dst = f"{a.out}/nvfp4_{name}_flat.jsonl"
    with open(dst, "w") as fh:
        fh.writelines(kept)
    print(f"{name}_flat: kept {len(kept)}/{len(kept)+dropped}, dropped {dropped} -> {dst}")
