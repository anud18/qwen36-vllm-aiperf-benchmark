#!/usr/bin/env python3
"""Rebuild aiperf's original console-output tables for every NVFP4 point, spark vs 5090.

Reproduces the "NVIDIA AIPerf | LLM Metrics" table (same metric rows, same
avg/min/max/p99/p90/p50/std columns) from profile_export_aiperf.csv, one table per
(workload, point) with both nodes interleaved per metric row.

Usage: aiperf_tables_nvfp4.py > results/nvfp4/AIPERF_TABLES.md
"""
import csv
import glob
import os

ROOT = os.path.join(os.path.dirname(__file__), "..", "results", "nvfp4")
NODES = ["spark", "5090"]
ORDER = ["chatbot", "rag", "toolagent", "agent", "coding", "toolagent_ts"]
STATS = ["avg", "min", "max", "p99", "p90", "p50", "std"]
# exactly the rows aiperf prints, in its order; value-only metrics have stats=False
METRICS = [
    ("Time to First Token (ms)", True),
    ("Time to Second Token (ms)", True),
    ("Time to First Output Token (ms)", True),
    ("Request Latency (ms)", True),
    ("Inter Token Latency (ms)", True),
    ("Output Token Throughput Per User (tokens/sec/user)", True),
    ("E2E Output Token Throughput (tokens/sec/user)", True),
    ("Output Sequence Length (tokens)", True),
    ("Input Sequence Length (tokens)", True),
    ("Output Token Throughput (tokens/sec)", False),
    ("Request Throughput (requests/sec)", False),
    ("Request Count (requests)", False),
]
VALUE_KEYS = {  # value-only metrics live in the second CSV section under other names
    "Output Token Throughput (tokens/sec)": "Output Token Throughput (tokens/sec)",
    "Request Throughput (requests/sec)": "Request Throughput (requests/sec)",
    "Request Count (requests)": "Request Count",
}


def point_key(b):
    if b.startswith("c"):
        return (0, float(b[1:]))
    if b.startswith("r") and b[1:].replace(".", "").isdigit():
        return (1, float(b[1:]))
    return (2, 0.0)


def parse_sections(d):
    """Parse both header sections (stats + Metric,Value) of profile_export_aiperf.csv."""
    p = os.path.join(d, "profile_export_aiperf.csv")
    if not os.path.isfile(p):
        return None
    out, header = {}, None
    for row in csv.reader(open(p)):
        if not row or not row[0].strip():
            header = None
            continue
        if row[0] == "Metric":
            header = row
            continue
        if row[0] == "Endpoint":  # GPU section header
            header = None
            continue
        if header is None:
            continue
        rec = dict(zip(header, row))
        m = rec.get("Metric", "").strip()
        if "Value" in header:
            try:
                out[m] = {"avg": float(rec["Value"])}
            except (ValueError, KeyError):
                pass
        else:
            out[m] = {}
            for s in STATS:
                try:
                    out[m][s] = float(rec[s])
                except (ValueError, KeyError):
                    pass
    return out


def fmt(v):
    return f"{v:,.2f}" if isinstance(v, float) else "N/A"


def table(wl, pt, data):
    print(f"### {wl} — {pt}\n")
    print("| Metric | node | " + " | ".join(STATS) + " |")
    print("|---|---|" + "--:|" * len(STATS))
    for metric, has_stats in METRICS:
        key = VALUE_KEYS.get(metric, metric)
        for i, node in enumerate(NODES):
            rec = (data.get(node) or {}).get(key, {})
            if has_stats:
                cells = [fmt(rec.get(s)) for s in STATS]
            else:
                cells = [fmt(rec.get("avg"))] + ["N/A"] * (len(STATS) - 1)
            name = metric if i == 0 else ""
            print(f"| {name} | **{node}** | " + " | ".join(cells) + " |")
    print()


def main():
    print("# NVFP4 — aiperf console tables, spark vs 5090\n")
    print("Every benchmark point rebuilt in aiperf's original `NVIDIA AIPerf | LLM Metrics` "
          "output format (same metric rows, same avg/min/max/p99/p90/p50/std columns), "
          "both nodes interleaved per metric. Source: each point's "
          "`profile_export_aiperf.csv`.\n")
    for wl in ORDER:
        pts = set()
        for node in NODES:
            for d in glob.glob(os.path.join(ROOT, node, wl, "*")):
                if os.path.isfile(os.path.join(d, "profile_export_aiperf.csv")):
                    pts.add(os.path.basename(d))
        if not pts:
            continue
        print(f"## {wl}\n")
        for pt in sorted(pts, key=point_key):
            data = {n: parse_sections(os.path.join(ROOT, n, wl, pt)) for n in NODES}
            table(wl, pt, data)


if __name__ == "__main__":
    main()
