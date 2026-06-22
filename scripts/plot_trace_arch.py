#!/usr/bin/env python3
"""Render the vLLM trace-recording architecture diagram -> docs/trace_arch.png."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "docs", "trace_arch.png")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

fig, ax = plt.subplots(figsize=(13, 7.6))
ax.set_xlim(0, 13); ax.set_ylim(0, 8.0); ax.axis("off")


def box(x, y, w, h, title, sub, fc, ec):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06,rounding_size=0.12",
                                linewidth=1.8, edgecolor=ec, facecolor=fc, zorder=2))
    ax.text(x + w / 2, y + h - 0.34, title, ha="center", va="center",
            fontsize=11.5, fontweight="bold", zorder=3)
    ax.text(x + w / 2, y + 0.36, sub, ha="center", va="center", fontsize=8.6,
            color="#333", zorder=3)


def arrow(x1, y1, x2, y2, label, color, rad=0.0, lx=None, ly=None, ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), connectionstyle=f"arc3,rad={rad}",
                 arrowstyle="-|>", mutation_scale=18, linewidth=1.8, color=color,
                 linestyle=ls, zorder=1))
    if label:
        ax.text(lx if lx is not None else (x1 + x2) / 2,
                ly if ly is not None else (y1 + y2) / 2 + 0.2,
                label, ha="center", va="center", fontsize=8.8, color=color, zorder=4)


# nodes
box(0.4, 5.0, 3.0, 1.5, "Client", "aiperf  /  curl\nOpenAI chat·completions", "#e8f0fe", "#1f77b4")
box(5.0, 5.0, 3.0, 1.5, "trace_proxy.py", ":8001 · aiohttp\nforward + record", "#fff4e6", "#ff7f0e")
box(9.6, 5.0, 3.0, 1.5, "vLLM server", ":8000 · Docker\nOpenAI API", "#e9f7ec", "#2ca02c")
box(5.0, 2.5, 3.0, 1.5, "traces/*.jsonl", "1 line / request\n(append, locked)", "#f3eafe", "#9467bd")
box(9.6, 2.5, 3.0, 1.5, "trace_summary.py", "tables · totals\n(or jq)", "#fdeaea", "#d62728")

# forward path (top)
arrow(3.4, 5.95, 5.0, 5.95, "① request", "#1f77b4", lx=4.2, ly=6.2)
arrow(8.0, 5.95, 9.6, 5.95, "② forward\n+ include_usage", "#ff7f0e", lx=8.8, ly=6.35)
# return path (bottom of the top lane)
arrow(9.6, 5.35, 8.0, 5.35, "③ stream / response", "#2ca02c", lx=8.8, ly=5.1)
arrow(5.0, 5.35, 3.4, 5.35, "④ forward unchanged", "#ff7f0e", lx=4.2, ly=5.1)
# record + read
arrow(6.5, 5.0, 6.5, 4.0, "⑤ append record", "#9467bd", lx=7.95, ly=4.5)
arrow(8.0, 3.25, 9.6, 3.25, "⑥ read", "#d62728", lx=8.8, ly=3.45)

# recorded fields callout (bottom, clear of the boxes)
ax.text(6.5, 1.35,
        "Recorded per request:  ts / ts_epoch · input content · output content · reasoning\n"
        "prompt_tokens · completion_tokens · total_tokens · ttft_ms · latency_ms · status",
        ha="center", va="center", fontsize=9.4, family="monospace",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#f7f7f7", edgecolor="#bbb"))

ax.set_title("vLLM request/response trace recording — transparent logging proxy",
             fontsize=14, fontweight="bold", pad=14)
fig.tight_layout()
fig.savefig(OUT, dpi=140, bbox_inches="tight")
print("wrote", os.path.relpath(OUT, ROOT))
