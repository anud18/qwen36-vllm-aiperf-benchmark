#!/usr/bin/env python3
"""Pareto curves from the concurrency sweep (results/sweep/<wl>/c<level>/)."""
import csv, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.join(os.path.dirname(__file__), "..")
WLS = ["chatbot", "coding", "rag", "agent", "toolagent"]
LEVELS = [4, 8, 16, 32]
COLORS = {"chatbot": "#1f77b4", "coding": "#ff7f0e", "rag": "#2ca02c",
          "agent": "#d62728", "toolagent": "#9467bd"}


def get(p, metric, stat="avg"):
    for r in csv.DictReader(open(p)):
        if r["Metric"].strip() == metric:
            try:
                return float(r.get(stat))
            except (TypeError, ValueError):
                return None
    return None


def series(wl, metric, stat="avg"):
    xs = []
    for c in LEVELS:
        p = os.path.join(ROOT, "results", "sweep", wl, f"c{c}", "profile_export_aiperf.csv")
        xs.append(get(p, metric, stat) if os.path.isfile(p) else None)
    return xs


fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

# Panel A: system throughput vs per-user interactivity (decode-bound)
for wl in ["chatbot", "coding", "agent", "toolagent"]:
    xu = series(wl, "Output Token Throughput Per User (tokens/sec/user)")
    ysys = series(wl, "Output Token Throughput (tokens/sec)")
    pts = [(x, y, c) for x, y, c in zip(xu, ysys, LEVELS) if x and y]
    if not pts:
        continue
    X, Y, C = zip(*pts)
    ax1.plot(X, Y, "-o", color=COLORS[wl], label=wl)
    for x, y, c in pts:
        ax1.annotate(f"c{c}", (x, y), textcoords="offset points", xytext=(5, 4), fontsize=8)
ax1.set_xlabel("Per-user output speed (tokens/sec/user)  →  more interactive")
ax1.set_ylabel("System output throughput (tokens/sec)  →  higher")
ax1.set_title("A. Throughput vs interactivity (decode-bound)\nconcurrency 4→32")
ax1.grid(True, alpha=0.3)
ax1.legend()

# Panel B: request throughput vs TTFT (captures prefill-bound RAG too)
for wl in WLS:
    ttft = series(wl, "Time to First Token (ms)")
    rps = series(wl, "Request Throughput (requests/sec)")
    pts = [(x, y, c) for x, y, c in zip(ttft, rps, LEVELS) if x and y]
    if not pts:
        continue
    X, Y, C = zip(*pts)
    ax2.plot(X, Y, "-o", color=COLORS[wl], label=wl)
    for x, y, c in pts:
        ax2.annotate(f"c{c}", (x, y), textcoords="offset points", xytext=(5, 4), fontsize=8)
ax2.set_xlabel("TTFT (ms)  →  lower is better")
ax2.set_ylabel("Request throughput (req/sec)  →  higher")
ax2.set_title("B. Request throughput vs TTFT\n(RAG is prefill-bound: high req/s, tiny output)")
ax2.grid(True, alpha=0.3)
ax2.legend()

fig.suptitle("Qwen3.6-35B-A3B-FP8 on vLLM (GB10) — concurrency sweep Pareto curves", fontsize=13)
fig.tight_layout(rect=[0, 0, 1, 0.96])
out = os.path.join(ROOT, "results", "pareto.png")
fig.savefig(out, dpi=130)
print("wrote", out)
