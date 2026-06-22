#!/usr/bin/env python3
"""Summarize a vLLM trace JSONL produced by trace_proxy.py.

Usage: trace_summary.py [traces/vllm_trace.jsonl] [--head N]
Prints per-request rows (ts, tokens, ttft, latency, input/output previews) and
aggregate totals. Pass --head N to limit the per-request rows shown.
"""
import json, sys


def preview(x, n=60):
    if x is None:
        return ""
    if isinstance(x, dict):
        if x.get("messages"):
            x = " | ".join(str((m or {}).get("content", "")) for m in x["messages"])
        else:
            x = x.get("prompt", "")
    s = " ".join(str(x).split())
    return s[:n] + ("…" if len(s) > n else "")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = args[0] if args else "traces/vllm_trace.jsonl"
    head = None
    if "--head" in sys.argv:
        head = int(sys.argv[sys.argv.index("--head") + 1])

    recs = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    if not recs:
        print("(no records)")
        return

    def fmt(v):
        return f"{v:.0f}" if isinstance(v, (int, float)) else "-"

    print(f"{'ts':<27} {'in':>6} {'out':>6} {'ttft_ms':>8} {'lat_ms':>9}  input -> output")
    print("-" * 110)
    shown = recs if head is None else recs[:head]
    for r in shown:
        ts = (r.get("ts") or "")[:26]
        pin = str(r.get("prompt_tokens") if r.get("prompt_tokens") is not None else "-")
        pout = str(r.get("completion_tokens") if r.get("completion_tokens") is not None else "-")
        out = r.get("output")
        if not out and r.get("tool_calls"):
            out = "🔧 " + ", ".join(f"{t.get('name')}({t.get('arguments')})" for t in r["tool_calls"])
        io = f"{preview(r.get('input'), 34)} -> {preview(out, 40)}"
        print(f"{ts:<27} {pin:>6} {pout:>6} {fmt(r.get('ttft_ms')):>8} {fmt(r.get('latency_ms')):>9}  {io}")
    if head is not None and len(recs) > head:
        print(f"... ({len(recs) - head} more)")

    pin = sum(r.get("prompt_tokens") or 0 for r in recs)
    pout = sum(r.get("completion_tokens") or 0 for r in recs)
    lats = [r["latency_ms"] for r in recs if r.get("latency_ms")]
    ttfts = [r["ttft_ms"] for r in recs if r.get("ttft_ms")]
    print("-" * 110)
    print(f"requests={len(recs)}  input_tokens={pin:,}  output_tokens={pout:,}  "
          f"total_tokens={pin + pout:,}")
    if lats:
        print(f"latency_ms  avg={sum(lats)/len(lats):.0f}  min={min(lats):.0f}  max={max(lats):.0f}")
    if ttfts:
        print(f"ttft_ms     avg={sum(ttfts)/len(ttfts):.0f}  min={min(ttfts):.0f}  max={max(ttfts):.0f}")


if __name__ == "__main__":
    main()
