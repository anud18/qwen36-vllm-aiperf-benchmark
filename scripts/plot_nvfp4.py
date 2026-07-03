#!/usr/bin/env python3
"""NVFP4 cross-hardware comparison plots (spark GB10 vs RTX 5090).

Reads results/nvfp4/<node>/<wl>/<pt>/{profile_export_aiperf.csv,prefix.json,prom.json}
and emits four light-mode PNGs into results/nvfp4/:
  nvfp4_throughput.png   Req/s vs concurrency (closed loop)
  nvfp4_ttft.png         TTFT avg vs concurrency (log y)
  nvfp4_rate_ttft.png    TTFT p99 at r0.8/1.0/1.2 (open loop, log y)
  nvfp4_kv_recompute.png prefix-cache queries per point (KV thrash signal, log y)
Plus the flat-trace variants (machine-independent ISL):
  nvfp4_flat_throughput.png  Req/s vs concurrency, *_flat workloads
  nvfp4_flat_ttft.png        TTFT avg vs concurrency, *_flat (log y)
  nvfp4_flat_vs_orig.png     flat (solid) vs original multi-turn (dashed) Req/s
"""
import csv
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.join(os.path.dirname(__file__), "..", "results", "nvfp4")
WLS = ["chatbot", "rag", "toolagent", "agent", "coding"]
NODES = [("spark", "#2a78d6"), ("5090", "#1baf7a")]  # dataviz reference palette slots 1-2
INK, MUTED, GRID = "#1a1a2e", "#6b6b7b", "#e8e8ee"
CLEVELS = [2, 4, 8, 16, 32]
RLEVELS = [0.8, 1.0, 1.2]


def aiperf_metric(node, wl, pt, metric, stat="avg"):
    p = os.path.join(ROOT, node, wl, pt, "profile_export_aiperf.csv")
    if not os.path.isfile(p):
        return None
    for r in csv.DictReader(open(p)):
        if r["Metric"].strip() == metric:
            try:
                return float(r.get(stat))
            except (TypeError, ValueError):
                return None
    return None


def prefix_queries(node, wl, pt):
    p = os.path.join(ROOT, node, wl, pt, "prefix.json")
    if not os.path.isfile(p):
        return None
    d = json.load(open(p))
    return None if d.get("failed") else d.get("queries")


def style(ax, title):
    ax.set_title(title, fontsize=11, color=INK, pad=8)
    ax.grid(True, color=GRID, linewidth=0.8, zorder=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8.5)


def grid_figure(fname, xlevels, xlabel, ylabel, suptitle, get_y, logy=False, logx2=False,
                wls=WLS):
    fig, axes = plt.subplots(1, len(wls), figsize=(3.2 * len(wls) + 0.4, 3.4),
                             constrained_layout=True)
    for ax, wl in zip(axes, wls):
        style(ax, wl)
        prev_end = None
        for node, color in NODES:
            pts = [f"c{int(x)}" if xlabel.startswith("conc") else f"r{x}" for x in xlevels]
            ys = [get_y(node, wl, pt) for pt in pts]
            xs = [x for x, y in zip(xlevels, ys) if y is not None]
            yv = [y for y in ys if y is not None]
            if not xs:
                continue
            ax.plot(xs, yv, color=color, linewidth=2, marker="o", markersize=5,
                    markeredgecolor="white", markeredgewidth=1, zorder=3)
            # direct label at line end (relief rule: identity not by color alone);
            # dodge vertically when both series end at nearly the same y
            dy = 0
            if prev_end is not None:
                lo, hi = sorted((prev_end, yv[-1]))
                if lo > 0 and hi / max(lo, 1e-12) < 1.35:
                    dy = -11
            ax.annotate(node, (xs[-1], yv[-1]), textcoords="offset points",
                        xytext=(5, dy), fontsize=8.5, color=color, fontweight="bold")
            prev_end = yv[-1]
        if logx2:
            ax.set_xscale("log", base=2)
            ax.set_xticks(xlevels)
            ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
        else:
            ax.set_xticks(xlevels)
        if logy:
            ax.set_yscale("log")
        ax.set_xlabel(xlabel, fontsize=9, color=MUTED)
    axes[0].set_ylabel(ylabel, fontsize=9, color=MUTED)
    handles = [plt.Line2D([], [], color=c, linewidth=2, marker="o", markersize=5,
                          markeredgecolor="white", label=n) for n, c in NODES]
    fig.legend(handles=handles, loc="upper right", frameon=False, fontsize=9,
               bbox_to_anchor=(0.995, 1.06), ncol=2)
    fig.suptitle(suptitle, fontsize=13, color=INK, x=0.01, ha="left")
    out = os.path.join(ROOT, fname)
    fig.savefig(out, dpi=150, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def flat_vs_orig(fname):
    """Validation chart: flat-trace (solid) vs original multi-turn (dashed) Req/s."""
    pairs = [("chatbot", "chatbot_flat"), ("agent", "agent_flat"), ("coding", "coding_flat")]
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.4), constrained_layout=True)
    for ax, (orig, flat) in zip(axes, pairs):
        style(ax, orig)
        prev_end = None
        for node, color in NODES:
            for wl, ls, alpha in ((orig, "--", 0.5), (flat, "-", 1.0)):
                pts = [f"c{c}" for c in CLEVELS]
                ys = [aiperf_metric(node, wl, p, "Request Throughput (requests/sec)")
                      for p in pts]
                xs = [x for x, y in zip(CLEVELS, ys) if y is not None]
                yv = [y for y in ys if y is not None]
                if not xs:
                    continue
                ax.plot(xs, yv, color=color, linewidth=2, linestyle=ls, alpha=alpha,
                        marker="o" if ls == "-" else None, markersize=5,
                        markeredgecolor="white", markeredgewidth=1, zorder=3)
                if ls == "-":  # direct-label the flat lines only
                    dy = 0
                    if prev_end is not None:
                        lo, hi = sorted((prev_end, yv[-1]))
                        if lo > 0 and hi / max(lo, 1e-12) < 1.35:
                            dy = -11
                    ax.annotate(node, (xs[-1], yv[-1]), textcoords="offset points",
                                xytext=(5, dy), fontsize=8.5, color=color,
                                fontweight="bold")
                    prev_end = yv[-1]
        ax.set_xscale("log", base=2)
        ax.set_xticks(CLEVELS)
        ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
        ax.set_xlabel("concurrency", fontsize=9, color=MUTED)
    axes[0].set_ylabel("Req/s", fontsize=9, color=MUTED)
    handles = [plt.Line2D([], [], color=c, linewidth=2, linestyle=ls, alpha=a,
                          marker="o" if ls == "-" else None, markersize=5,
                          markeredgecolor="white", label=f"{n} {v}")
               for n, c in NODES for v, ls, a in (("flat", "-", 1.0), ("multi-turn", "--", 0.5))]
    fig.legend(handles=handles, loc="upper right", frameon=False, fontsize=8,
               bbox_to_anchor=(0.995, 1.10), ncol=4)
    fig.suptitle("Flat trace vs original multi-turn — same load intensity, fixed ISL",
                 fontsize=13, color=INK, x=0.01, ha="left")
    out = os.path.join(ROOT, fname)
    fig.savefig(out, dpi=150, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


def main():
    grid_figure(
        "nvfp4_throughput.png", CLEVELS, "concurrency", "Req/s",
        "Request throughput vs concurrency — Qwen3.6-35B-A3B-NVFP4, closed loop, 96 req/point",
        lambda n, w, p: aiperf_metric(n, w, p, "Request Throughput (requests/sec)"),
        logx2=True)
    grid_figure(
        "nvfp4_ttft.png", CLEVELS, "concurrency", "TTFT avg (ms)",
        "Time-to-first-token vs concurrency — closed loop (log y)",
        lambda n, w, p: aiperf_metric(n, w, p, "Time to First Token (ms)"),
        logy=True, logx2=True)
    grid_figure(
        "nvfp4_rate_ttft.png", RLEVELS, "req/s offered", "TTFT p99 (ms)",
        "Open-loop TTFT p99 at 0.8 / 1.0 / 1.2 req/s (poisson; log y)",
        lambda n, w, p: aiperf_metric(n, w, p, "Time to First Token (ms)", "p99"),
        logy=True)
    grid_figure(
        "nvfp4_kv_recompute.png", CLEVELS, "concurrency", "prefix-cache queries (tokens)",
        "KV pressure: prefix-cache queries per point — recompute amplification on the 24x-smaller 5090 KV (log y)",
        lambda n, w, p: prefix_queries(n, w, p),
        logy=True, logx2=True)
    FLAT = ["chatbot_flat", "agent_flat", "coding_flat"]
    grid_figure(
        "nvfp4_flat_throughput.png", CLEVELS, "concurrency", "Req/s",
        "Flat-trace request throughput vs concurrency — machine-independent ISL "
        "(620 / 3,041 / 29,869 tokens at every point)",
        lambda n, w, p: aiperf_metric(n, w, p, "Request Throughput (requests/sec)"),
        logx2=True, wls=FLAT)
    grid_figure(
        "nvfp4_flat_ttft.png", CLEVELS, "concurrency", "TTFT avg (ms)",
        "Flat-trace time-to-first-token vs concurrency — closed loop (log y)",
        lambda n, w, p: aiperf_metric(n, w, p, "Time to First Token (ms)"),
        logy=True, logx2=True, wls=FLAT)
    flat_vs_orig("nvfp4_flat_vs_orig.png")


if __name__ == "__main__":
    main()
