#!/usr/bin/env python3
"""Rebuild the flat traces with REAL text (mooncake_trace `messages` mode).

The synthetic flat traces (build_flat_traces.py) declared token *lengths* and let
aiperf synthesize prompt text. Per methodology decision, everything except
toolagent must send the original text instead. Each flattened turn becomes one
mooncake_trace entry:

    {"messages": [user_1, asst_1, ..., user_k], "output_length": OSL_k,
     "extra": {"chat_template_kwargs": {"enable_thinking": false}}}

The message text is fixed in the file, so the tokenized ISL is bit-identical
across machines and across runs (the whole point).

Assistant-reply sources:
  chatbot — the ShareGPT dataset's own gpt replies (true original text).
            Sessions follow the seed-42 materialized order of
            results/nvfp4/spark/chatbot/c2/inputs.json; each session is matched
            back to its ShareGPT entry by the exact user-text sequence, and
            output_length keeps the payload's max_completion_tokens (aiperf
            derives it from the gpt reply length, so they agree).
  agent, coding — the datasets carry no assistant text, so replies are
            generated ONCE against a vLLM server (greedy: temperature 0,
            seed 42, thinking off, max_tokens 2048) and frozen into the file.
            Raw generations are kept in datasets/aiperf/canonical/.

Usage (host, needs only stdlib):
  python3 scripts/build_flat_text_traces.py chatbot
  python3 scripts/build_flat_text_traces.py agent coding   # needs --url server
"""
import argparse
import concurrent.futures
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "datasets", "aiperf")
CANON = os.path.join(OUT, "canonical")
SHAREGPT = os.path.join(ROOT, ".cache", "aiperf", "datasets",
                        "ShareGPT_V3_unfiltered_cleaned_split.json")
CHATBOT_INPUTS = os.path.join(ROOT, "results", "nvfp4", "spark", "chatbot", "c2", "inputs.json")
N_ENTRIES = 240      # per file; each sweep point consumes warmup 16 + 96 = 112
OSL_CAP = 2048
THINKOFF = {"chat_template_kwargs": {"enable_thinking": False}}
# raw-messages mode skips aiperf's client-side input tokenization, so ISL must
# come from the server: force usage reporting on the streaming response.
#
# PIN_DECODE: aiperf sends output_length as max_completion_tokens, i.e. a CAP —
# the model still stops at its own EOS. On the NCHC GLM-5.2 gateway the OSL
# CANNOT be pinned to the trace: `ignore_eos`, `min_tokens` and
# `min_completion_tokens` are all silently dropped (verified — a cap-200 request
# still stops at 12 tokens). temperature 0 + seed 42 is reproducible for short
# prompts but NOT for the multi-turn contexts: replaying agent entries against
# the canonical lengths gave 332->214, 180->168, 188->171 (batch composition on
# a shared server moves the EOS point). So treat output_length as "declared cap,
# measured OSL <= it, usually close". Pinning the sampler still removes
# sampling-noise as a second source of drift; --no-pin-decode leaves the
# server's default sampler.
PIN_DECODE = {"temperature": 0, "seed": 42}
ENTRY_EXTRA = {**THINKOFF, "stream_options": {"include_usage": True}}


def emit(sessions, out_path):
    """sessions: [[(user_text, reply_text, osl), ...], ...] -> messages-mode jsonl.

    Turn k's entry carries the history user_1..user_k with replies 1..k-1; the
    reply for turn k itself only sets output_length (the model generates live).
    """
    n = 0
    with open(out_path, "w") as f:
        for turns in sessions:
            if n >= N_ENTRIES:
                break
            msgs = []
            for user, reply, osl in turns:
                if n >= N_ENTRIES:
                    break
                msgs = msgs + [{"role": "user", "content": user}]
                f.write(json.dumps({
                    "messages": msgs,
                    "output_length": max(1, min(int(osl), OSL_CAP)),
                    "extra": ENTRY_EXTRA,
                }, ensure_ascii=False) + "\n")
                n += 1
                msgs = msgs + [{"role": "assistant", "content": reply}]
    return n


# ---------- chatbot: ShareGPT original gpt replies ----------

def sharegpt_pairs(conversations):
    """Replicates aiperf ShareGPTLoader._sharegpt_prompt_completion_pairs."""
    msgs = [c for c in conversations if isinstance(c, dict)]
    if len(msgs) < 2:
        return []
    if not any(c.get("from") in ("human", "gpt") for c in msgs):
        p, c = msgs[0].get("value"), msgs[1].get("value")
        return [(p, c)] if p and c else []
    role_msgs = [c for c in msgs if c.get("from") in ("human", "gpt")]
    pairs, i = [], 0
    while i < len(role_msgs) - 1:
        if role_msgs[i].get("from") == "human" and role_msgs[i + 1].get("from") == "gpt":
            p, c = role_msgs[i].get("value"), role_msgs[i + 1].get("value")
            if p and c:
                pairs.append((p, c))
            i += 2
        else:
            i += 1
    return pairs


def chatbot_sessions():
    data = json.load(open(CHATBOT_INPUTS))["data"]
    idx = {}
    for entry in json.load(open(SHAREGPT)):
        pairs = sharegpt_pairs(entry.get("conversations") or [])
        if pairs:
            idx.setdefault(pairs[0][0], []).append(pairs)
    matched = missed = 0
    for sess in data:
        users, osls = [], []
        for p in sess["payloads"]:
            users.append(" ".join(m["content"] for m in p["messages"] if m["role"] == "user"))
            osls.append(p.get("max_completion_tokens") or 128)
        match = None
        for pairs in idx.get(users[0], []):
            if len(pairs) >= len(users) and all(pairs[i][0] == users[i] for i in range(len(users))):
                match = pairs
                break
        if match is None:
            missed += 1
            continue
        matched += 1
        yield [(users[i], match[i][1], osls[i]) for i in range(len(users))]
    print(f"  chatbot session match: {matched} ok, {missed} missed", file=sys.stderr)


# ---------- agent/coding: one-time greedy canonical generation ----------

def chat(url, model, messages, max_tokens, retries=5, api_key=""):
    body = json.dumps({
        "model": model, "messages": messages, "stream": False,
        "temperature": 0, "seed": 42, "max_tokens": max_tokens, **THINKOFF,
    }).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url + "/v1/chat/completions", data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=1800) as r:
                d = json.load(r)
            return (d["choices"][0]["message"]["content"] or "",
                    d["usage"]["completion_tokens"])
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"    retry {attempt+1}: {e}", file=sys.stderr)
            time.sleep(10 * (attempt + 1))


def gen_session(sess, url, model, api_key=""):
    msgs, out = [], []
    for t in sess["turns"]:
        msgs.append({"role": "user", "content": t["text"]})
        reply, ct = chat(url, model, msgs, OSL_CAP, api_key=api_key)
        msgs.append({"role": "assistant", "content": reply})
        out.append({"user": t["text"], "reply": reply, "completion_tokens": ct})
    return {"session_id": sess["session_id"], "turns": out}


def canonical_generate(wl, url, model, workers, api_key=""):
    """Generate (or load cached) greedy replies for enough sessions of `wl`."""
    os.makedirs(CANON, exist_ok=True)
    cache = os.path.join(CANON, f"{wl}_replies.jsonl")
    done = {}
    if os.path.isfile(cache):
        for line in open(cache):
            d = json.loads(line)
            done[d["session_id"]] = d
    sessions, total = [], 0
    for line in open(os.path.join(OUT, f"nvfp4_{wl}.jsonl")):
        d = json.loads(line)
        sessions.append(d)
        total += len(d["turns"])
        if total >= N_ENTRIES:
            break
    todo = [s for s in sessions if s["session_id"] not in done]
    print(f"  {wl}: {len(sessions)} sessions / {total} turns needed; "
          f"{len(done)} cached, {len(todo)} to generate", file=sys.stderr)
    if todo:
        with concurrent.futures.ThreadPoolExecutor(workers) as ex, open(cache, "a") as f:
            futs = {ex.submit(gen_session, s, url, model, api_key): s for s in todo}
            for i, fut in enumerate(concurrent.futures.as_completed(futs), 1):
                rec = fut.result()
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                done[rec["session_id"]] = rec
                print(f"  {wl} gen {i}/{len(todo)}: {rec['session_id']} "
                      f"({len(rec['turns'])} turns)", file=sys.stderr)
    for s in sessions:
        rec = done[s["session_id"]]
        yield [(t["user"], t["reply"], t["completion_tokens"]) for t in rec["turns"]]


def main():
    global N_ENTRIES, ENTRY_EXTRA, OSL_CAP
    ap = argparse.ArgumentParser()
    ap.add_argument("workloads", nargs="+", choices=["chatbot", "agent", "coding"])
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--model", default="qwen3.6-nvfp4")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--force-osl", action="store_true",
                    help="write ignore_eos into every entry so the measured OSL equals "
                         "output_length exactly. Works against a vLLM you control; the "
                         "NCHC gateway drops the parameter (see FLAT_TRACES.md)")
    ap.add_argument("--osl-cap", type=int, default=OSL_CAP,
                    help="max_tokens for canonical generation and the ceiling "
                         "written into output_length (default %(default)s)")
    ap.add_argument("--no-pin-decode", action="store_true",
                    help="do not write temperature 0 / seed 42 into each entry; "
                         "output_length then acts as a cap only")
    ap.add_argument("--api-key", default="",
                    help="bearer token for a gated endpoint (or env API_KEY)")
    ap.add_argument("--n-entries", type=int, default=N_ENTRIES,
                    help="entries per file; must be >= warmup + request-count of "
                         "the largest sweep point (default %(default)s)")
    args = ap.parse_args()
    N_ENTRIES = args.n_entries
    OSL_CAP = args.osl_cap
    if not args.no_pin_decode:
        ENTRY_EXTRA = {**ENTRY_EXTRA, **PIN_DECODE}
    if args.force_osl:
        ENTRY_EXTRA = {**ENTRY_EXTRA, "ignore_eos": True}
    for wl in args.workloads:
        if wl == "chatbot":
            sessions = chatbot_sessions()
        else:
            sessions = canonical_generate(wl, args.url, args.model, args.workers,
                                          args.api_key or os.environ.get("API_KEY", ""))
        path = os.path.join(OUT, f"nvfp4_{wl}_flat.jsonl")
        n = emit(sessions, path)
        osl = [json.loads(l)["output_length"] for l in open(path)]
        print(f"{wl}_flat: {n} entries -> {path} | OSL avg={sum(osl)/len(osl):,.0f} "
              f"min={min(osl)} max={max(osl)}")


if __name__ == "__main__":
    main()
