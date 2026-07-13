#!/usr/bin/env python3
"""Tag every NVFP4 benchmark point as a Grafana region annotation + emit a deep-link index.

Reads results/nvfp4/<node>/<wl>/<pt>/meta.json (start/end epochs written by run_nvfp4.sh),
deletes any previous nvfp4-tagged annotations on the dashboard, then creates one region
annotation per point (tags: nvfp4, node:<n>, wl:<w>, pt:<p>) so each run is visible on the
vLLM dashboard. Also writes results/nvfp4/GRAFANA_LINKS.md with per-point dashboard links
(from/to preset to the run window ±30s).

Usage: python3 scripts/annotate_grafana_nvfp4.py [--grafana http://localhost:3000]
       [--auth admin:admin] [--uid <dashboard-uid>]
"""
import argparse
import base64
import glob
import json
import os
import urllib.request

ROOT = os.path.join(os.path.dirname(__file__), "..", "results", "nvfp4")


def req(url, auth, method="GET", payload=None):
    r = urllib.request.Request(url, method=method)
    r.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
    data = None
    if payload is not None:
        r.add_header("Content-Type", "application/json")
        data = json.dumps(payload).encode()
    with urllib.request.urlopen(r, data, timeout=30) as resp:
        return json.load(resp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grafana", default="http://localhost:3000")
    ap.add_argument("--auth", default="admin:admin")
    ap.add_argument("--uid", default="b281712d-8bff-41ef-9f3f-71ad43c05e9b")
    args = ap.parse_args()

    # wipe previous nvfp4 annotations (idempotent re-run)
    old = req(f"{args.grafana}/api/annotations?tags=nvfp4&limit=1000", args.auth)
    for a in old:
        req(f"{args.grafana}/api/annotations/{a['id']}", args.auth, method="DELETE")
    if old:
        print(f"deleted {len(old)} previous nvfp4 annotations")

    points = []
    for mf in sorted(glob.glob(os.path.join(ROOT, "*", "*", "*", "meta.json"))):
        meta = json.load(open(mf))
        if meta.get("failed") or "start" not in meta or "node" not in meta:
            continue
        points.append(meta)

    links = ["# Grafana deep links — one per benchmark point\n",
             f"Dashboard: `{args.grafana}/d/{args.uid}/vllm` (annotations tagged `nvfp4`)\n"]
    n = 0
    for m in sorted(points, key=lambda m: m["start"]):
        node, wl, pt = m["node"], m["wl"], m["point"]
        t0, t1 = m["start"] * 1000, m["end"] * 1000
        req(f"{args.grafana}/api/annotations", args.auth, method="POST", payload={
            "dashboardUID": args.uid,
            "time": t0, "timeEnd": t1, "isRegion": True,
            "tags": ["nvfp4", f"node:{node}", f"wl:{wl}", f"pt:{pt}"],
            "text": f"{node} {wl} {pt}",
        })
        links.append(f"- **{node} / {wl} / {pt}** — "
                     f"[{args.grafana}/d/{args.uid}/vllm?from={t0-30000}&to={t1+30000}]"
                     f"({args.grafana}/d/{args.uid}/vllm?from={t0-30000}&to={t1+30000})")
        n += 1
    print(f"created {n} region annotations on dashboard {args.uid}")

    out = os.path.join(ROOT, "GRAFANA_LINKS.md")
    with open(out, "w") as f:
        f.write("\n".join(links) + "\n")
    print("wrote", out)


if __name__ == "__main__":
    main()
