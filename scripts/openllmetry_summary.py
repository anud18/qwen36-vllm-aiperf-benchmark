#!/usr/bin/env python3
"""Summarize OpenLLMetry (OpenAI-instrumentation) spans from the OTel span file.

Reads traces/vllm_spans.jsonl, keeps spans from the openai instrumentation scope,
and prints input/output content + tokens + response id. The response id matches
vLLM's own server span (gen_ai.request.id), so client content joins server timing.

Usage: openllmetry_summary.py [traces/vllm_spans.jsonl]
"""
import json, sys


def first_text(messages_json):
    """messages attr is a JSON string: [{"role","parts":[{"content":...}]}]."""
    try:
        msgs = json.loads(messages_json)
    except (TypeError, ValueError):
        return ""
    out = []
    for m in msgs:
        for p in m.get("parts", []):
            c = p.get("content")
            if c:
                out.append(c)
            elif p.get("type") == "tool_call" or p.get("tool_call"):
                out.append("🔧 " + json.dumps(p, ensure_ascii=False)[:60])
    return " ".join(" ".join(str(o).split()) for o in out)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "traces/vllm_spans.jsonl"
    rows = []
    for b in map(json.loads, filter(str.strip, open(path))):
        for rs in b.get("resourceSpans", []):
            for ss in rs.get("scopeSpans", []):
                if "openai" not in (ss.get("scope") or {}).get("name", ""):
                    continue
                for sp in ss.get("spans", []):
                    a = {x["key"]: list(x["value"].values())[0] for x in sp.get("attributes", [])}
                    rows.append(a)
    if not rows:
        print("(no OpenLLMetry spans — run scripts/openllmetry_client.py first)")
        return
    print(f"{'response_id':<34} {'in':>5} {'out':>5}  input -> output")
    print("-" * 100)
    for a in rows:
        rid = (a.get("gen_ai.response.id") or "")[:32]
        itk = a.get("gen_ai.usage.input_tokens", "-"); otk = a.get("gen_ai.usage.output_tokens", "-")
        inp = first_text(a.get("gen_ai.input.messages"))[:30]
        out = first_text(a.get("gen_ai.output.messages"))[:40]
        print(f"{rid:<34} {str(itk):>5} {str(otk):>5}  {inp} -> {out}")
    print("-" * 100)
    print(f"spans={len(rows)}  (join to vLLM server spans by response_id == gen_ai.request.id)")


if __name__ == "__main__":
    main()
