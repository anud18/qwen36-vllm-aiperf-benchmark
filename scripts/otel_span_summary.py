#!/usr/bin/env python3
"""Summarize vLLM native OTLP spans written by the OTel collector (file exporter).

Usage: otel_span_summary.py [traces/vllm_spans.jsonl]
Each line is an OTLP-JSON export batch; vLLM emits one span per request with
gen_ai.* attributes (token counts + server-internal latencies). This flattens
them to a per-request table — the server-side complement to the proxy's
content trace, correlatable by request id.
"""
import json, sys

# vLLM reports gen_ai.latency.* in seconds; convert these to ms for display
SEC_TO_MS = {"gen_ai.latency.time_in_queue", "gen_ai.latency.time_to_first_token",
             "gen_ai.latency.e2e", "gen_ai.latency.time_in_scheduler",
             "gen_ai.latency.time_in_model_forward", "gen_ai.latency.time_in_model_execute"}


def attr_val(v):
    for k in ("stringValue", "intValue", "doubleValue", "boolValue"):
        if k in v:
            return v[k]
    return None


def load(path):  # accept a JSON array or JSONL (one batch per line)
    txt = open(path).read().strip()
    return json.loads(txt) if txt[:1] == "[" else [json.loads(l) for l in txt.splitlines() if l.strip()]


def flatten(path):
    spans = []
    if True:
        for batch in load(path):
            for rs in batch.get("resourceSpans", []):
                for ss in rs.get("scopeSpans", []):
                    for sp in ss.get("spans", []):
                        a = {x["key"]: attr_val(x["value"]) for x in sp.get("attributes", [])}
                        a["_name"] = sp.get("name")
                        a["_start"] = int(sp.get("startTimeUnixNano", 0))
                        spans.append(a)
    return spans


def ms(a, key):
    v = a.get(key)
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v * 1000 if key in SEC_TO_MS else v


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "traces/vllm_spans.jsonl"
    spans = flatten(path)
    spans.sort(key=lambda a: a["_start"])
    if not spans:
        print("(no spans yet — has a request gone through the OTLP-enabled server?)")
        return
    hdr = f"{'request_id':<36} {'in':>6} {'out':>6} {'queue_ms':>9} {'ttft_ms':>9} {'e2e_ms':>9}"
    print(hdr); print("-" * len(hdr))
    tin = tout = 0
    for a in spans:
        rid = (a.get("gen_ai.request.id") or "")[:34]
        itk = a.get("gen_ai.usage.prompt_tokens"); otk = a.get("gen_ai.usage.completion_tokens")
        tin += int(itk or 0); tout += int(otk or 0)

        def f(key):
            v = ms(a, key)
            return f"{v:.0f}" if v is not None else "-"
        print(f"{rid:<36} {str(itk or '-'):>6} {str(otk or '-'):>6} "
              f"{f('gen_ai.latency.time_in_queue'):>9} "
              f"{f('gen_ai.latency.time_to_first_token'):>9} "
              f"{f('gen_ai.latency.e2e'):>9}")
    print("-" * len(hdr))
    print(f"spans={len(spans)}  input_tokens={tin:,}  output_tokens={tout:,}")
    # show which gen_ai.* attributes are present (handy for discovery)
    keys = sorted({k for a in spans for k in a if k.startswith("gen_ai.")})
    print("attributes present:", ", ".join(keys))


if __name__ == "__main__":
    main()
