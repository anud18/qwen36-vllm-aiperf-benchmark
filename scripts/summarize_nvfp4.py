#!/usr/bin/env python3
"""Summarize the NVFP4 cross-hardware run (results/nvfp4/<node>/<wl>/<pt>/).

Points are c<N> (closed-loop concurrency) and r<R> (open-loop poisson rate).
Emits per-node tables plus a spark-vs-5090 comparison, from
profile_export_aiperf.csv + prefix.json + prom.json.

Usage: summarize_nvfp4.py [--md]
"""
import csv
import glob
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..", "results", "nvfp4")
NODES = ["spark", "5090"]
ORDER = ["chatbot", "rag", "toolagent", "agent", "coding", "toolagent_ts",
         "chatbot_flat", "agent_flat", "coding_flat"]
ROWS = [
    ("ISL", "Input Sequence Length (tokens)"),
    ("OSL", "Output Sequence Length (tokens)"),
    ("TTFT ms", "Time to First Token (ms)"),
    ("ITL ms", "Inter Token Latency (ms)"),
    ("ReqLat ms", "Request Latency (ms)"),
    ("Out tok/s", "Output Token Throughput (tokens/sec)"),
    ("Out tok/s/user", "Output Token Throughput Per User (tokens/sec/user)"),
    ("Req/s", "Request Throughput (requests/sec)"),
]


def point_key(p):
    b = os.path.basename(p)
    if b.startswith("c"):
        return (0, float(b[1:]))
    if b.startswith("r") and b[1:].replace(".", "").isdigit():
        return (1, float(b[1:]))
    return (2, 0.0)  # fixed-schedule replay


def get(d, metric, stat="avg"):
    p = os.path.join(d, "profile_export_aiperf.csv")
    if not os.path.isfile(p):
        return None
    for r in csv.DictReader(open(p)):
        if r["Metric"].strip() == metric:
            try:
                return float(r.get(stat))
            except (TypeError, ValueError):
                return None
    return None


def jget(d, fname, key, scale=1.0):
    p = os.path.join(d, fname)
    if not os.path.isfile(p):
        return None
    v = json.load(open(p)).get(key)
    return v * scale if isinstance(v, (int, float)) else None


def num(v):
    return f"{v:,.1f}" if isinstance(v, float) else "-"


def cols_for(node, wl):
    pts = sorted(glob.glob(os.path.join(ROOT, node, wl, "*")), key=point_key)
    return [(os.path.basename(d), d) for d in pts
            if os.path.isfile(os.path.join(d, "profile_export_aiperf.csv"))]


def table(node, wl, md):
    cols = cols_for(node, wl)
    if not cols:
        return
    extra = [
        ("prefix-hit %", lambda d: jget(d, "prefix.json", "hit_rate", 100.0)),
        ("KV max %", lambda d: jget(d, "prom.json", "kv_usage_max", 100.0)),
        ("wait avg", lambda d: jget(d, "prom.json", "waiting_avg")),
    ]
    if md:
        print(f"### {wl} — {node}\n")
        print("| metric | " + " | ".join(c for c, _ in cols) + " |")
        print("|---|" + "--:|" * len(cols))
        for label, metric in ROWS:
            print(f"| {label} | " + " | ".join(num(get(d, metric)) for _, d in cols) + " |")
        for label, fn in extra:
            print(f"| {label} | " + " | ".join(num(fn(d)) for _, d in cols) + " |")
        print()
    else:
        print(f"\n### {wl} — {node}")
        head = f"{'metric':<14}" + "".join(f"{c:>11}" for c, _ in cols)
        print(head)
        print("-" * len(head))
        for label, metric in ROWS:
            print(f"{label:<14}" + "".join(f"{num(get(d, metric)):>11}" for _, d in cols))
        for label, fn in extra:
            print(f"{label:<14}" + "".join(f"{num(fn(d)):>11}" for _, d in cols))


def comparison(md):
    """spark vs 5090: Req/s, TTFT avg, Out tok/s per (workload, point)."""
    hdr = "## spark vs 5090\n" if md else "\n=== spark vs 5090 ==="
    print(hdr)
    for wl in ORDER:
        pts = []
        for node in NODES:
            pts += [c for c, _ in cols_for(node, wl)]
        pts = sorted(set(pts), key=lambda b: point_key(b))
        if not pts:
            continue
        rows = [("Req/s", "Request Throughput (requests/sec)"),
                ("TTFT ms", "Time to First Token (ms)"),
                ("ITL ms", "Inter Token Latency (ms)"),
                ("E2E ms", "Request Latency (ms)"),
                ("Out tok/s", "Output Token Throughput (tokens/sec)")]
        if md:
            print(f"### {wl}\n")
            print("| metric | node | " + " | ".join(pts) + " |")
            print("|---|---|" + "--:|" * len(pts))
        else:
            print(f"\n### {wl}")
        for label, metric in rows:
            for node in NODES:
                by = dict(cols_for(node, wl))
                vals = [num(get(by[p], metric)) if p in by else "-" for p in pts]
                if md:
                    print(f"| {label} | {node} | " + " | ".join(vals) + " |")
                else:
                    print(f"{label:<10}{node:<7}" + "".join(f"{v:>11}" for v in vals))
        if md:
            print()


def main(md=False):
    if md:
        print("# NVFP4 cross-hardware run — summary\n")
        print("`nvidia/Qwen3.6-35B-A3B-NVFP4` on vLLM v0.24.0 — GB10 Spark (util 0.5, bt 32768) "
              "vs RTX 5090 (util 0.9, bt 8192); reasoning OFF, OSL cap 2048, 96 req/point, "
              "prefix cache reset per point.\n")
    for node in NODES:
        if md:
            print(f"## {node}\n")
        for wl in ORDER:
            table(node, wl, md)
    comparison(md)


if __name__ == "__main__":
    main(md="--md" in sys.argv)
