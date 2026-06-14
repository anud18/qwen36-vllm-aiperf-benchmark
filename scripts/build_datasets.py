#!/usr/bin/env python3
"""
Build aiperf-ready trace files from the raw benchmark datasets.

Outputs (datasets/aiperf/):
  coding_multiturn.jsonl   <- codex_swebenchpro.json   (--custom-dataset-type multi_turn)
  rag_singleturn.jsonl     <- MultiHopRAG.json+corpus   (--custom-dataset-type single_turn)
  agent_multiturn.jsonl    <- atbench_claw_test.json    (--custom-dataset-type multi_turn)
  toolagent_mooncake.jsonl <- toolagent_trace.jsonl     (--custom-dataset-type mooncake_trace)

aiperf measures *real* input tokens from the text we send; `output_length` only
caps generation, so we estimate it from the reference responses (chars/CHARS_PER_TOK),
clamped per workload. Chatbot/ShareGPT uses aiperf's built-in --public-dataset sharegpt.
"""
import argparse, json, os, sys

RAW = os.path.join(os.path.dirname(__file__), "..", "datasets", "raw")
OUT = os.path.join(os.path.dirname(__file__), "..", "datasets", "aiperf")
CHARS_PER_TOK = 4.0  # rough token estimate for output caps only
# Qwen3.6 is a reasoning model (emits chain-of-thought by default). For the
# explicitly "short output" workloads (coding, RAG) we disable thinking so the
# output length reflects the answer, not the reasoning trace. aiperf merges this
# `extra` object into each request body; vLLM honors chat_template_kwargs.
THINK_OFF = {"chat_template_kwargs": {"enable_thinking": False}}


def est_tokens(s):
    return max(1, int(len(s) / CHARS_PER_TOK))


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def blocks_to_text(content):
    """Flatten an Anthropic-style content (str or list of typed blocks) to text."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)
    parts = []
    for b in content:
        if not isinstance(b, dict):
            parts.append(str(b)); continue
        t = b.get("type")
        if t == "text":
            parts.append(b.get("text", ""))
        elif t == "thinking":
            parts.append(b.get("thinking", ""))
        elif t in ("tool_use", "toolUse"):
            parts.append(f"[tool_call {b.get('name','')}: {json.dumps(b.get('input',{}))[:2000]}]")
        elif t in ("tool_result", "toolResult"):
            parts.append(blocks_to_text(b.get("content", "")))
        else:
            parts.append(b.get("text", "") or "")
    return "\n".join(p for p in parts if p)


# ---------------------------------------------------------------- coding
def build_coding(max_sessions, max_turns, out_cap):
    src = json.load(open(os.path.join(RAW, "codex_swebenchpro.json")))
    rows = []
    for i, rec in enumerate(src[:max_sessions]):
        conv = rec["conversations"]
        turns = []
        # walk human/gpt pairs; each human turn -> one benchmark turn,
        # output_length estimated from the following gpt turn
        j = 0
        while j < len(conv) and len(turns) < max_turns:
            if conv[j].get("from") == "human":
                text = conv[j].get("value", "")
                nxt = conv[j + 1] if j + 1 < len(conv) else None
                olen = est_tokens(nxt["value"]) if nxt and nxt.get("from") == "gpt" else 256
                turns.append({"text": text, "output_length": clamp(olen, 1, out_cap), "extra": THINK_OFF})
                j += 2
            else:
                j += 1
        if turns:
            rows.append({"session_id": f"codex_{i}", "turns": turns})
    return "coding_multiturn.jsonl", rows


# ---------------------------------------------------------------- rag
def build_rag(max_queries, min_ctx_chars, max_ctx_chars, out_cap):
    queries = json.load(open(os.path.join(RAW, "MultiHopRAG.json")))
    corpus = json.load(open(os.path.join(RAW, "corpus.json")))
    title2body = {c["title"]: (c.get("body") or "") for c in corpus}
    rows = []
    for q in queries:
        seen, ctx = set(), []
        for e in q.get("evidence_list", []):
            t = e.get("title")
            if t in title2body and t not in seen:
                seen.add(t)
                ctx.append(f"Title: {t}\nSource: {e.get('source','')}\n{title2body[t]}")
        context = "\n\n---\n\n".join(ctx)
        if len(context) < min_ctx_chars:
            continue
        context = context[:max_ctx_chars]
        prompt = (
            "You are a retrieval-augmented QA assistant. Using ONLY the documents "
            "below, answer the question concisely (a few words).\n\n"
            f"=== DOCUMENTS ===\n{context}\n\n=== QUESTION ===\n{q['query']}\n\nAnswer:"
        )
        rows.append({"text": prompt, "output_length": out_cap, "extra": THINK_OFF})
        if len(rows) >= max_queries:
            break
    return "rag_singleturn.jsonl", rows


# ---------------------------------------------------------------- agent
def build_agent(max_sessions, max_turns, out_cap):
    src = json.load(open(os.path.join(RAW, "atbench_claw_test.json")))
    rows = []
    for i, rec in enumerate(src[:max_sessions]):
        events = rec.get("trajectory", {}).get("events", [])
        msgs = [e["message"] for e in events if e.get("type") == "message" and "message" in e]
        # group runs of non-assistant msgs (user+toolResult) as one input turn,
        # output_length estimated from the following assistant run
        turns, buf = [], []
        k = 0
        while k < len(msgs) and len(turns) < max_turns:
            role = msgs[k].get("role")
            if role == "assistant":
                if buf:
                    text = "\n\n".join(blocks_to_text(m.get("content")) for m in buf)
                    # gather following assistant run length
                    a_len = 0
                    while k < len(msgs) and msgs[k].get("role") == "assistant":
                        a_len += len(blocks_to_text(msgs[k].get("content")))
                        k += 1
                    if text.strip():
                        turns.append({"text": text, "output_length": clamp(est_tokens("x" * a_len), 1, out_cap)})
                    buf = []
                else:
                    k += 1
            else:
                buf.append(msgs[k]); k += 1
        if buf and len(turns) < max_turns:
            text = "\n\n".join(blocks_to_text(m.get("content")) for m in buf)
            if text.strip():
                turns.append({"text": text, "output_length": out_cap})
        if turns:
            rows.append({"session_id": f"atbench_{i}", "turns": turns})
    return "agent_multiturn.jsonl", rows


# ---------------------------------------------------------------- toolagent
def build_toolagent(max_requests):
    inp = os.path.join(RAW, "toolagent_trace.jsonl")
    rows = []
    with open(inp) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if max_requests and len(rows) >= max_requests:
                break
    return "toolagent_mooncake.jsonl", rows


def uncap(rows):
    """Strip output_length and extra so aiperf sends no max_completion_tokens and
    leaves thinking on (model generates to natural EOS)."""
    for r in rows:
        for turn in (r["turns"] if "turns" in r else [r]):
            turn.pop("output_length", None)
            turn.pop("extra", None)
    return rows


def write(name, rows):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name)
    with open(p, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # quick stats
    if rows and "turns" in rows[0]:
        nt = sum(len(r["turns"]) for r in rows)
        print(f"  {name}: {len(rows)} sessions, {nt} turns -> {p}")
    else:
        print(f"  {name}: {len(rows)} requests -> {p}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coding-sessions", type=int, default=100)
    ap.add_argument("--coding-turns", type=int, default=6)
    ap.add_argument("--coding-out-cap", type=int, default=512)
    ap.add_argument("--rag-queries", type=int, default=500)
    ap.add_argument("--rag-min-ctx-chars", type=int, default=4000)
    ap.add_argument("--rag-max-ctx-chars", type=int, default=120000)
    ap.add_argument("--rag-out-cap", type=int, default=64)
    ap.add_argument("--agent-sessions", type=int, default=200)
    ap.add_argument("--agent-turns", type=int, default=8)
    ap.add_argument("--agent-out-cap", type=int, default=512)
    ap.add_argument("--toolagent-requests", type=int, default=2000)
    ap.add_argument("--only", nargs="*", choices=["coding", "rag", "agent", "toolagent"])
    ap.add_argument("--uncapped", action="store_true",
                    help="omit output_length + extra (no max_completion_tokens, thinking on); "
                         "write to *_uncapped.jsonl")
    a = ap.parse_args()
    sel = a.only or ["coding", "rag", "agent", "toolagent"]
    suf = "_uncapped" if a.uncapped else ""
    print("Building aiperf datasets ->", os.path.abspath(OUT))

    def emit(name, rows):
        if a.uncapped:
            rows = uncap(rows)
            name = name.replace(".jsonl", "_uncapped.jsonl")
        write(name, rows)

    if "coding" in sel:
        emit(*build_coding(a.coding_sessions, a.coding_turns, a.coding_out_cap))
    if "rag" in sel:
        emit(*build_rag(a.rag_queries, a.rag_min_ctx_chars, a.rag_max_ctx_chars, a.rag_out_cap))
    if "agent" in sel:
        emit(*build_agent(a.agent_sessions, a.agent_turns, a.agent_out_cap))
    if "toolagent" in sel:
        emit(*build_toolagent(a.toolagent_requests))


if __name__ == "__main__":
    main()
