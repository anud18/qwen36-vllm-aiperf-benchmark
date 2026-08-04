#!/usr/bin/env python3
"""Per-stream prefill and decode throughput from aiperf per-request records.

    python3 scripts/throughput_split.py results/nvfp4/<point-dir> [...]

aiperf reports TTFT, ITL and a system-level output_token_throughput, but no
prefill/decode split. These are computed from profile_export.jsonl so the same
definition applies to any endpoint:

    prefill = sum(ISL) / sum(TTFT)
    decode  = sum(OSL - 1) / sum(latency - TTFT)

Both are PER-STREAM rates. Summing each request's decode time counts the same
wall clock once per concurrent stream, so at concurrency > 1 these describe what
one client sees, not what the server delivers -- use aiperf's
output_token_throughput for that.

Prefill is inflated wherever prefix caching is on: cached tokens count toward ISL
but are never computed, so the true rate is lower than reported.

Requests with OSL < 2 are skipped: decode time is undefined without at least one
inter-token gap.
"""
import json
import sys


def agg(d):
    """per-stream prefill / decode throughput for one point directory"""
    isl = osl = ttft = dec = 0.0
    n = 0
    for line in open(d + "/profile_export.jsonl"):
        m = json.loads(line).get("metrics", {})
        if "time_to_first_token" not in m:
            continue
        o = m["output_sequence_length"]["value"]
        if o < 2:
            continue
        t = m["time_to_first_token"]["value"]
        lat = m["request_latency"]["value"]
        isl += m["input_sequence_length"]["value"]
        osl += o
        ttft += t
        dec += lat - t
        n += 1
    return dict(n=n,
                prefill=isl / (ttft / 1000) if ttft else None,
                decode=(osl - n) / (dec / 1000) if dec else None)


if __name__ == "__main__":
    for d in sys.argv[1:]:
        a = agg(d)
        print(f"{d}  n={a['n']}  prefill={a['prefill']:,.0f} tok/s/stream  "
              f"decode={a['decode']:,.1f} tok/s/stream")
