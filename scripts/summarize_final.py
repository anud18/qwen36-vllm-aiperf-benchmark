#!/usr/bin/env python3
"""Summarize the v6 final run (results/final/<wl>/c<level>/), including prefix-cache hit rate.

Usage: summarize_final.py [--md]   (--md emits GitHub markdown tables)
"""
import csv, glob, json, os, sys

ROOT = os.path.join(os.path.dirname(__file__), "..", "results", "final")
ORDER = ["chatbot", "rag", "toolagent", "agent", "coding"]
ROWS = [
    ("ISL", "Input Sequence Length (tokens)"),
    ("OSL", "Output Sequence Length (tokens)"),
    ("TTFT ms", "Time to First Token (ms)"),
    ("ITL ms", "Inter Token Latency (ms)"),
    ("ReqLat ms", "Request Latency (ms)"),
    ("Out tok/s", "Output Token Throughput (tokens/sec)"),
    ("Out tok/s/user", "Output Token Throughput Per User (tokens/sec/user)"),
    ("Req/s", "Request Throughput (requests/sec)"),
    ("Requests", "Request Count"),
]


def get(p, m, s="avg"):
    if not os.path.isfile(p):
        return None
    for r in csv.DictReader(open(p)):
        if r["Metric"].strip() == m:
            try:
                return float(r.get(s))
            except (TypeError, ValueError):
                return None
    return None


def num(v):
    return f"{v:,.1f}" if isinstance(v, float) else "-"


def prefix_cells(cols):
    out = []
    for _, d in cols:
        pf = os.path.join(d, "prefix.json")
        if os.path.isfile(pf):
            out.append(f"{json.load(open(pf)).get('hit_rate',0)*100:.1f}%")
        else:
            out.append("-")
    return out


def workload_cols(wl):
    levels = sorted(glob.glob(os.path.join(ROOT, wl, "c*")),
                    key=lambda p: int(os.path.basename(p)[1:]))
    return [(os.path.basename(d), d) for d in levels
            if os.path.isfile(os.path.join(d, "profile_export_aiperf.csv"))]


def main(md=False):
    if md:
        print("# v6 final run — summary tables\n")
        print("Per-workload metrics (avg) across the concurrency sweep, from "
              "`results/final/<wl>/c<level>/profile_export_aiperf.csv` + `prefix.json`.\n")
    for wl in ORDER:
        cols = workload_cols(wl)
        if not cols:
            continue
        if md:
            print(f"## {wl}\n")
            print("| metric | " + " | ".join(c for c, _ in cols) + " |")
            print("|---|" + "--:|" * len(cols))
            for label, metric in ROWS:
                vals = (num(get(os.path.join(d, 'profile_export_aiperf.csv'), metric)) for _, d in cols)
                print(f"| {label} | " + " | ".join(vals) + " |")
            print(f"| prefix-hit | " + " | ".join(prefix_cells(cols)) + " |\n")
        else:
            print(f"\n### {wl}")
            head = f"{'metric':<14}" + "".join(f"{c:>12}" for c, _ in cols)
            print(head); print("-" * len(head))
            for label, metric in ROWS:
                print(f"{label:<14}" + "".join(f"{num(get(os.path.join(d,'profile_export_aiperf.csv'), metric)):>12}" for _, d in cols))
            print(f"{'prefix-hit':<14}" + "".join(f"{c:>12}" for c in prefix_cells(cols)))
    if not md:
        print()


if __name__ == "__main__":
    main(md="--md" in sys.argv)
