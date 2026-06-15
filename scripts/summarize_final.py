#!/usr/bin/env python3
"""Summarize the v5 final run (results/final/<wl>/c<level>/), including prefix-cache hit rate."""
import csv, glob, json, os

ROOT = os.path.join(os.path.dirname(__file__), "..", "results", "final")
ORDER = ["chatbot", "rag", "toolagent", "agent", "coding"]
ROWS = [
    ("ISL", "Input Sequence Length (tokens)"),
    ("OSL", "Output Sequence Length (tokens)"),
    ("TTFT ms", "Time to First Token (ms)"),
    ("ITL ms", "Inter Token Latency (ms)"),
    ("ReqLat ms", "Request Latency (ms)"),
    ("Out tok/s", "Output Token Throughput (tokens/sec)"),
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


def main():
    for wl in ORDER:
        levels = sorted(glob.glob(os.path.join(ROOT, wl, "c*")),
                        key=lambda p: int(os.path.basename(p)[1:]))
        cols = []
        for d in levels:
            csvp = os.path.join(d, "profile_export_aiperf.csv")
            if os.path.isfile(csvp):
                cols.append((os.path.basename(d), d))
        if not cols:
            continue
        print(f"\n### {wl}")
        head = f"{'metric':<12}" + "".join(f"{c:>12}" for c, _ in cols)
        print(head); print("-" * len(head))
        for label, metric in ROWS:
            print(f"{label:<12}" + "".join(f"{num(get(os.path.join(d,'profile_export_aiperf.csv'), metric)):>12}" for _, d in cols))
        # prefix hit row
        cells = []
        for _, d in cols:
            pf = os.path.join(d, "prefix.json")
            if os.path.isfile(pf):
                j = json.load(open(pf))
                cells.append(f"{j.get('hit_rate',0)*100:.1f}%")
            else:
                cells.append("-")
        print(f"{'prefix-hit':<12}" + "".join(f"{c:>12}" for c in cells))
    print()


if __name__ == "__main__":
    main()
