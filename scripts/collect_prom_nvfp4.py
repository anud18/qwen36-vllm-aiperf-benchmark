#!/usr/bin/env python3
"""Per-point Prometheus extracts for the NVFP4 run.

For every results/nvfp4/<node>/<wl>/<pt>/meta.json (written by run_nvfp4.sh with the
point's start/end epochs), query the Spark Prometheus (scrapes both nodes with a
`node` label) over that window and write prom.json next to it:
  gen_tok_s, prompt_tok_s (increase/duration), running_avg, waiting_avg,
  kv_usage_avg, kv_usage_max.

Usage: python3 scripts/collect_prom_nvfp4.py [--prom http://localhost:9090]
"""
import argparse
import glob
import json
import os
import urllib.parse
import urllib.request

ROOT = os.path.join(os.path.dirname(__file__), "..", "results", "nvfp4")


def q(prom, expr, ts):
    url = f"{prom}/api/v1/query?" + urllib.parse.urlencode({"query": expr, "time": ts})
    with urllib.request.urlopen(url, timeout=30) as r:
        d = json.load(r)
    if d.get("status") != "success" or not d["data"]["result"]:
        return None
    return float(d["data"]["result"][0]["value"][1])


def pick_metric(prom, candidates, node, ts):
    """First candidate metric name that has data for this node."""
    for m in candidates:
        if q(prom, f'present_over_time({m}{{node="{node}"}}[1h])', ts) is not None:
            return m
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prom", default="http://localhost:9090")
    args = ap.parse_args()

    kv_candidates = ["vllm:kv_cache_usage_perc", "vllm:gpu_cache_usage_perc"]
    n_done = n_skip = 0
    for mf in sorted(glob.glob(os.path.join(ROOT, "*", "*", "*", "meta.json"))):
        meta = json.load(open(mf))
        if meta.get("failed") or "start" not in meta:
            n_skip += 1
            continue
        node, t0, t1 = meta["node"], meta["start"], meta["end"]
        dur = max(t1 - t0, 30)
        w = f"[{dur}s]"
        sel = f'{{node="{node}"}}'
        kv = pick_metric(args.prom, kv_candidates, node, t1)
        out = {
            "window_s": dur,
            "gen_tok_s": q(args.prom, f"increase(vllm:generation_tokens_total{sel}{w})", t1),
            "prompt_tok_s": q(args.prom, f"increase(vllm:prompt_tokens_total{sel}{w})", t1),
            "running_avg": q(args.prom, f"avg_over_time(vllm:num_requests_running{sel}{w})", t1),
            "waiting_avg": q(args.prom, f"avg_over_time(vllm:num_requests_waiting{sel}{w})", t1),
            "kv_usage_avg": q(args.prom, f"avg_over_time({kv}{sel}{w})", t1) if kv else None,
            "kv_usage_max": q(args.prom, f"max_over_time({kv}{sel}{w})", t1) if kv else None,
        }
        for k in ("gen_tok_s", "prompt_tok_s"):
            if out[k] is not None:
                out[k] = out[k] / dur
        with open(os.path.join(os.path.dirname(mf), "prom.json"), "w") as f:
            json.dump(out, f, indent=1)
        n_done += 1
    print(f"prom extracts: {n_done} points written, {n_skip} skipped (failed/no window)")


if __name__ == "__main__":
    main()
