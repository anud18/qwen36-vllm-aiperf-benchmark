#!/usr/bin/env python3
"""Aggregate aiperf results across workloads into one comparison table."""
import csv, glob, os

ROWS = [
    ("Request Count", "Request Count (requests)", "avg"),
    ("ISL avg", "Input Sequence Length (tokens)", "avg"),
    ("OSL avg", "Output Sequence Length (tokens)", "avg"),
    ("TTFT avg ms", "Time to First Token (ms)", "avg"),
    ("TTFT p99 ms", "Time to First Token (ms)", "p99"),
    ("ITL avg ms", "Inter Token Latency (ms)", "avg"),
    ("ReqLat avg ms", "Request Latency (ms)", "avg"),
    ("Out tok/s", "Output Token Throughput (tokens/sec)", "avg"),
    ("Req/s", "Request Throughput (requests/sec)", "avg"),
]
ORDER = ["chatbot", "coding", "rag", "agent", "toolagent"]


def load(path):
    d = {}
    for row in csv.DictReader(open(path)):
        d[row.get("Metric", "").strip()] = row
    return d


def num(v):
    try:
        return f"{float(v):,.2f}"
    except Exception:
        return "-"


def main():
    base = os.path.join(os.path.dirname(__file__), "..", "results")
    data = {}
    for wl in ORDER + sorted(os.listdir(base)):
        p = os.path.join(base, wl, "profile_export_aiperf.csv")
        if wl not in data and os.path.isfile(p):
            data[wl] = load(p)
    cols = [w for w in ORDER if w in data]
    w0 = 16
    print(f"\n{'metric':<16}" + "".join(f"{c:>14}" for c in cols))
    print("-" * (16 + 14 * len(cols)))
    for label, metric, stat in ROWS:
        cells = []
        for c in cols:
            row = data[c].get(metric, {})
            cells.append(num(row.get(stat)))
        print(f"{label:<16}" + "".join(f"{x:>14}" for x in cells))
    print()


if __name__ == "__main__":
    main()
