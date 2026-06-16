#!/usr/bin/env python3
"""Pareto curves from the v6 concurrency sweep (results/final/<wl>/c<level>/).

Reads the v6 run (IN_DIR) and writes figures into a dedicated OUT_DIR
(report_v6/figures/), both overridable via SWEEP_DIR / OUT_DIR env vars.

Produces:
  <OUT>/pareto.png            - throughput vs interactivity + req/s vs TTFT (overview)
  <OUT>/pareto_per_gpu.png    - tok/s (1x GB10) vs ITL and vs TTFT, knee marked
  <OUT>/pareto_per_workload.png - small multiples, one per workload, knee marked
  <OUT>/pareto_uncapped.png   - capped sweep vs uncapped(thinking-on) overlay (if data present)
"""
import csv, os, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.join(os.path.dirname(__file__), "..")
IN_DIR = os.environ.get("SWEEP_DIR", os.path.join(ROOT, "results", "final"))
OUT_DIR = os.environ.get("OUT_DIR", os.path.join(ROOT, "report_v6", "figures"))
os.makedirs(OUT_DIR, exist_ok=True)
WLS = ["chatbot", "coding", "rag", "agent", "toolagent"]
DECODE = ["chatbot", "coding", "agent", "toolagent"]  # decode-bound (meaningful tok/s)
LEVELS = [4, 8, 16, 32]
COLORS = {"chatbot": "#1f77b4", "coding": "#ff7f0e", "rag": "#2ca02c",
          "agent": "#d62728", "toolagent": "#9467bd"}


def get(p, metric, stat="avg"):
    if not os.path.isfile(p):
        return None
    for r in csv.DictReader(open(p)):
        if r["Metric"].strip() == metric:
            try:
                return float(r.get(stat))
            except (TypeError, ValueError):
                return None
    return None


def csv_sweep(wl, c):
    return os.path.join(IN_DIR, wl, f"c{c}", "profile_export_aiperf.csv")


def series(wl, metric):
    return [get(csv_sweep(wl, c), metric) for c in LEVELS]


def knee(xs, ys, x_lower_better=True):
    """Closest-to-utopia knee. Returns index into the point list.
    x = latency (lower better), y = throughput (higher better)."""
    pts = [(i, x, y) for i, (x, y) in enumerate(zip(xs, ys)) if x and y]
    if not pts:
        return None
    X = [p[1] for p in pts]; Y = [p[2] for p in pts]
    xmin, xmax = min(X), max(X); ymin, ymax = min(Y), max(Y)
    best, bi = 1e9, None
    for i, x, y in pts:
        nx = (x - xmin) / (xmax - xmin) if xmax > xmin else 0  # latency: 0 best
        ny = (ymax - y) / (ymax - ymin) if ymax > ymin else 0  # throughput: 0 best
        d = math.hypot(nx, ny)
        if d < best:
            best, bi = d, i
    return bi


TOK = "Output Token Throughput (tokens/sec)"
TPU = "Output Token Throughput Per User (tokens/sec/user)"
TTFT = "Time to First Token (ms)"
ITL = "Inter Token Latency (ms)"
RPS = "Request Throughput (requests/sec)"
REQLAT = "Request Latency (ms)"


# ------------------------------------------------ per-metric charts vs concurrency
def tpot_ms(wl, c):
    """TPOT = time per output token (ms) = 1000 / per-user output token throughput."""
    tpu = get(csv_sweep(wl, c), TPU)
    return 1000.0 / tpu if tpu else None


# (title, value-fn(wl,c), y-label, log-y, p99-metric-or-None, lower_is_better, workloads)
# ITL/TPOT are per-output-token decode latencies — undefined for rag (OSL≈3), so
# those two charts cover only the decode-bound workloads.
METRICS = [
    ("TTFT (avg)",          lambda wl, c: get(csv_sweep(wl, c), TTFT),   "Time to First Token (ms)",     True,  TTFT,   True,  WLS),
    ("ITL",                 lambda wl, c: get(csv_sweep(wl, c), ITL),    "Inter Token Latency (ms/tok)", False, ITL,    True,  DECODE),
    ("TPOT",                tpot_ms,                                     "Time Per Output Token (ms)",   False, None,   True,  DECODE),
    ("Request throughput",  lambda wl, c: get(csv_sweep(wl, c), RPS),    "Requests / sec",               False, None,   False, WLS),
    ("Output token throughput", lambda wl, c: get(csv_sweep(wl, c), TOK), "System tokens / sec",         False, None,   False, WLS),
    ("Request latency (avg)", lambda wl, c: get(csv_sweep(wl, c), REQLAT), "Request Latency (ms)",       True,  REQLAT, True,  WLS),
]


def _plot_metric(ax, title, vfn, ylabel, logy, p99m, lower_better, wls=WLS):
    for wl in wls:
        xy = [(c, vfn(wl, c)) for c in LEVELS]
        xy = [(c, v) for c, v in xy if v is not None]
        if not xy:
            continue
        X, Y = zip(*xy)
        ax.plot(X, Y, "-o", color=COLORS[wl], label=wl, zorder=3)
        if p99m is not None:  # faint p99 band for latency metrics
            p = [(c, get(csv_sweep(wl, c), p99m, "p99")) for c in LEVELS]
            p = [(c, v) for c, v in p if v is not None]
            if p:
                px, py = zip(*p)
                ax.plot(px, py, "--", color=COLORS[wl], alpha=0.35, linewidth=1, zorder=2)
    ax.set_xscale("log", base=2); ax.set_xticks(LEVELS); ax.set_xticklabels(LEVELS)
    if logy:
        ax.set_yscale("log")
    ax.set_xlabel("concurrency")
    ax.set_ylabel(ylabel)
    arrow = "↓ lower better" if lower_better else "↑ higher better"
    extra = "  (decode workloads)" if wls is DECODE else ""
    ax.set_title(f"{title}  ({arrow}){extra}")
    ax.grid(True, which="both", alpha=0.3)


def fig_metrics():
    # combined grid
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    for ax, (title, vfn, ylabel, logy, p99m, lb, wls) in zip(axes.ravel(), METRICS):
        _plot_metric(ax, title, vfn, ylabel, logy, p99m, lb, wls)
    axes.ravel()[0].legend(fontsize=9, ncol=2)
    fig.suptitle("Per-metric vs concurrency — solid = avg, dashed = p99 (latency metrics)", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(os.path.join(OUT_DIR, "metrics_grid.png"), dpi=130)
    # individual charts
    slug = {"TTFT (avg)": "ttft", "ITL": "itl", "TPOT": "tpot",
            "Request throughput": "req_throughput",
            "Output token throughput": "token_throughput",
            "Request latency (avg)": "req_latency"}
    written = []
    for title, vfn, ylabel, logy, p99m, lb, wls in METRICS:
        fig, ax = plt.subplots(figsize=(8, 5.5))
        _plot_metric(ax, title, vfn, ylabel, logy, p99m, lb, wls)
        ax.legend(fontsize=9)
        fig.tight_layout()
        name = "metric_%s.png" % slug[title]
        fig.savefig(os.path.join(OUT_DIR, name), dpi=130)
        plt.close(fig)
        written.append(name)
    return ["metrics_grid.png"] + written


# ---------------------------------------------------------------- Fig 1: overview
def fig_overview():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    for wl in DECODE:
        xu, ys = series(wl, TPU), series(wl, TOK)
        pts = [(x, y, c) for x, y, c in zip(xu, ys, LEVELS) if x and y]
        if pts:
            X, Y, _ = zip(*pts)
            ax1.plot(X, Y, "-o", color=COLORS[wl], label=wl)
            for x, y, c in pts:
                ax1.annotate(f"c{c}", (x, y), textcoords="offset points", xytext=(5, 4), fontsize=8)
    ax1.set_xlabel("Per-user output speed (tokens/sec/user)  →  more interactive")
    ax1.set_ylabel("System output throughput (tokens/sec)")
    ax1.set_title("A. Throughput vs interactivity (decode-bound), c4→c32")
    ax1.grid(True, alpha=0.3); ax1.legend()
    for wl in WLS:
        xt, yr = series(wl, TTFT), series(wl, RPS)
        pts = [(x, y, c) for x, y, c in zip(xt, yr, LEVELS) if x and y]
        if pts:
            X, Y, _ = zip(*pts)
            ax2.plot(X, Y, "-o", color=COLORS[wl], label=wl)
            for x, y, c in pts:
                ax2.annotate(f"c{c}", (x, y), textcoords="offset points", xytext=(5, 4), fontsize=8)
    ax2.set_xlabel("TTFT (ms)  →  lower better"); ax2.set_ylabel("Request throughput (req/sec)")
    ax2.set_title("B. Request throughput vs TTFT (RAG prefill-bound)")
    ax2.grid(True, alpha=0.3); ax2.legend()
    fig.suptitle("Qwen3.6-35B-A3B-FP8 on vLLM (GB10) — concurrency sweep", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(os.path.join(OUT_DIR, "pareto.png"), dpi=130)


# ------------------------------------------------ Fig 2: throughput-per-GPU frontier
def fig_per_gpu():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    for ax, lat, name in ((ax1, ITL, "ITL (ms/token)"), (ax2, TTFT, "TTFT (ms)")):
        for wl in DECODE:
            xs, ys = series(wl, lat), series(wl, TOK)
            pts = [(x, y, c) for x, y, c in zip(xs, ys, LEVELS) if x and y]
            if not pts:
                continue
            X, Y, _ = zip(*pts)
            ax.plot(X, Y, "-o", color=COLORS[wl], label=wl)
            for x, y, c in pts:
                ax.annotate(f"c{c}", (x, y), textcoords="offset points", xytext=(5, 4), fontsize=8)
            ki = knee(list(X), list(Y))
            if ki is not None:
                ax.scatter([X[ki]], [Y[ki]], s=260, facecolors="none",
                           edgecolors=COLORS[wl], linewidths=2.2, zorder=5)
        ax.set_xlabel(f"{name}  →  lower better")
        ax.set_ylabel("Throughput per GPU = system tok/s (1× GB10)")
        ax.set_title(f"tok/s vs {name.split()[0]}  (○ = knee)")
        ax.grid(True, alpha=0.3); ax.legend()
    fig.suptitle("Throughput-per-GPU frontier — knee = closest-to-utopia concurrency", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(os.path.join(OUT_DIR, "pareto_per_gpu.png"), dpi=130)


# ------------------------------------------------ Fig 3: per-workload small multiples
def fig_per_workload():
    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    axes = axes.ravel()
    for ax, wl in zip(axes, WLS):
        ymetric = RPS if wl == "rag" else TOK
        ylabel = "req/sec" if wl == "rag" else "tok/sec"
        xs, ys = series(wl, ITL if wl != "rag" else TTFT), series(wl, ymetric)
        xname = "TTFT (ms)" if wl == "rag" else "ITL (ms/token)"
        pts = [(x, y, c) for x, y, c in zip(xs, ys, LEVELS) if x and y]
        if not pts:
            ax.set_visible(False); continue
        X, Y, C = zip(*pts)
        ax.plot(X, Y, "-o", color=COLORS[wl])
        for x, y, c in pts:
            ax.annotate(f"c{c}", (x, y), textcoords="offset points", xytext=(5, 4), fontsize=9)
        ki = knee(list(X), list(Y))
        if ki is not None:
            ax.scatter([X[ki]], [Y[ki]], s=300, facecolors="none",
                       edgecolors="black", linewidths=2.2, zorder=5)
            ax.set_title(f"{wl}   (knee @ c{C[ki]})")
        ax.set_xlabel(f"{xname}  →  lower better"); ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
    axes[-1].set_visible(False)
    fig.suptitle("Per-workload throughput vs latency — ○ marks the knee (best concurrency)", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(os.path.join(OUT_DIR, "pareto_per_workload.png"), dpi=130)


# ------------------------------------------------ Fig 4: capped vs uncapped overlay
def fig_uncapped():
    # uncapped runs: single operating point each (thinking ON, no cap).
    # These are from the earlier exploration; skip the figure if that data is absent.
    if not os.path.isdir(os.path.join(ROOT, "results", "uncapped")):
        return False
    unc_conc = {"rag": 8, "agent": 8, "coding": 4}
    fig, ax = plt.subplots(figsize=(11, 7))
    for wl in ["rag", "agent", "coding"]:
        xs, ys = series(wl, ITL), series(wl, TOK)
        pts = [(x, y, c) for x, y, c in zip(xs, ys, LEVELS) if x and y]
        if pts:
            X, Y, _ = zip(*pts)
            ax.plot(X, Y, "-o", color=COLORS[wl], label=f"{wl} capped (thinking off)")
            for x, y, c in pts:
                ax.annotate(f"c{c}", (x, y), textcoords="offset points", xytext=(5, 4), fontsize=8)
        p = os.path.join(ROOT, "results", "uncapped", wl, "profile_export_aiperf.csv")
        ux, uy = get(p, ITL), get(p, TOK)
        if ux and uy:
            ax.scatter([ux], [uy], marker="*", s=420, color=COLORS[wl], edgecolors="black",
                       zorder=6, label=f"{wl} UNCAPPED (thinking on, c{unc_conc[wl]})")
            uosl = get(p, "Output Sequence Length (tokens)")
            ax.annotate(f"OSL≈{uosl:,.0f}", (ux, uy), textcoords="offset points",
                        xytext=(8, -12), fontsize=9, fontweight="bold")
    ax.set_xlabel("ITL (ms/token)  →  lower better")
    ax.set_ylabel("System output throughput (tokens/sec)")
    ax.set_title("Capped sweep (○) vs uncapped + thinking-on (★)\n"
                 "tok/s is similar; what explodes is OSL → end-to-end latency")
    ax.grid(True, alpha=0.3); ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "pareto_uncapped.png"), dpi=130)
    return True


if __name__ == "__main__":
    fig_overview()
    fig_per_gpu()
    fig_per_workload()
    wrote_uncapped = fig_uncapped()
    metric_files = fig_metrics()
    names = ["pareto.png", "pareto_per_gpu.png", "pareto_per_workload.png"]
    if wrote_uncapped:
        names.append("pareto_uncapped.png")
    names += metric_files
    for f in names:
        print("wrote %s" % os.path.relpath(os.path.join(OUT_DIR, f), ROOT))
