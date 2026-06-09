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


def sweep():
    """Print per-workload concurrency-sweep tables from results/sweep/<wl>/c<level>/."""
    base = os.path.join(os.path.dirname(__file__), "..", "results", "sweep")
    if not os.path.isdir(base):
        print("no sweep results yet"); return
    metrics = [
        ("ISL", "Input Sequence Length (tokens)", "avg"),
        ("OSL", "Output Sequence Length (tokens)", "avg"),
        ("TTFT ms", "Time to First Token (ms)", "avg"),
        ("ITL ms", "Inter Token Latency (ms)", "avg"),
        ("ReqLat ms", "Request Latency (ms)", "avg"),
        ("Out tok/s", "Output Token Throughput (tokens/sec)", "avg"),
        ("Req/s", "Request Throughput (requests/sec)", "avg"),
    ]
    for wl in ORDER:
        wld = os.path.join(base, wl)
        if not os.path.isdir(wld):
            continue
        levels = sorted((d for d in os.listdir(wld) if d.startswith("c")),
                        key=lambda x: int(x[1:]))
        cols = []
        for lv in levels:
            p = os.path.join(wld, lv, "profile_export_aiperf.csv")
            if os.path.isfile(p):
                cols.append((lv, load(p)))
        if not cols:
            continue
        print(f"\n### {wl}  (concurrency sweep)")
        print(f"{'metric':<12}" + "".join(f"{lv:>12}" for lv, _ in cols))
        print("-" * (12 + 12 * len(cols)))
        for label, metric, stat in metrics:
            print(f"{label:<12}" + "".join(f"{num(d.get(metric,{}).get(stat)):>12}" for _, d in cols))
    print()


def main():
    import sys
    if "--sweep" in sys.argv:
        return sweep()
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
