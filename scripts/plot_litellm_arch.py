#!/usr/bin/env python3
"""Render the LiteLLM trace-recording architecture diagram -> docs/litellm_arch.png."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "docs", "litellm_arch.png")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

fig, ax = plt.subplots(figsize=(14, 8))
ax.set_xlim(0, 14); ax.set_ylim(0, 8.6); ax.axis("off")


def box(x, y, w, h, title, sub, fc, ec, tcolor="black"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06,rounding_size=0.12",
                                linewidth=1.8, edgecolor=ec, facecolor=fc, zorder=2))
    ax.text(x + w / 2, y + h - 0.34, title, ha="center", va="center",
            fontsize=11.5, fontweight="bold", color=tcolor, zorder=3)
    ax.text(x + w / 2, y + 0.40, sub, ha="center", va="center", fontsize=8.5,
            color="#333", zorder=3)


def arrow(x1, y1, x2, y2, label, color, lx=None, ly=None, ls="-", rad=0.0):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), connectionstyle=f"arc3,rad={rad}",
                 arrowstyle="-|>", mutation_scale=18, linewidth=1.8, color=color,
                 linestyle=ls, zorder=1))
    if label:
        ax.text(lx if lx is not None else (x1 + x2) / 2,
                ly if ly is not None else (y1 + y2) / 2 + 0.22,
                label, ha="center", va="center", fontsize=8.8, color=color, zorder=4)

# request path: client -> LiteLLM (gateway) -> vLLM
box(0.4, 5.3, 3.0, 1.5, "Client", "aiperf / app\nOpenAI request", "#e8f0fe", "#1f77b4")
box(5.3, 5.3, 3.4, 1.5, "LiteLLM", "gateway / SDK\n+ CustomLogger callback", "#fff4e6", "#ff7f0e")
box(10.6, 5.3, 3.0, 1.5, "vLLM server", ":8000 · Docker\nOpenAI API", "#e9f7ec", "#2ca02c")

# trace output + optional fan-out
box(5.3, 2.3, 3.4, 1.5, "traces/litellm_trace.jsonl", "1 line / request\ncontent·tokens·cost·latency",
    "#f3eafe", "#9467bd")
box(10.6, 2.5, 3.0, 1.3, "Prometheus /\nother backends", "optional callback\nfan-out", "#fdeaea", "#d62728")

# forward path (top lane)
arrow(3.4, 6.25, 5.3, 6.25, "① request", "#1f77b4", lx=4.35, ly=6.5)
arrow(8.7, 6.25, 10.6, 6.25, "② forward", "#ff7f0e", lx=9.65, ly=6.5)
# return path (lower lane)
arrow(10.6, 5.65, 8.7, 5.65, "③ response (+usage)", "#2ca02c", lx=9.65, ly=5.42)
arrow(5.3, 5.65, 3.4, 5.65, "④ response", "#ff7f0e", lx=4.35, ly=5.42)
# record + optional fan-out
arrow(7.0, 5.3, 7.0, 3.8, "⑤ log_success_event", "#9467bd", lx=8.5, ly=4.55)
arrow(8.7, 3.15, 10.6, 3.15, "⑥ optional", "#d62728", lx=9.65, ly=3.35, ls="--")

# recorded-fields callout (bottom, clear of boxes)
ax.text(7.0, 1.15,
        "Recorded per request:  ts · input · output · tool_calls · prompt_tokens · completion_tokens "
        "· cost_usd · latency_ms · model",
        ha="center", va="center", fontsize=9.2, family="monospace",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#f7f7f7", edgecolor="#bbb"))

ax.set_title("LLM trace recording with LiteLLM — gateway logs every request "
             "(content + tokens + cost)", fontsize=13.5, fontweight="bold", pad=14)
fig.tight_layout()
fig.savefig(OUT, dpi=140, bbox_inches="tight")
print("wrote", os.path.relpath(OUT, ROOT))
