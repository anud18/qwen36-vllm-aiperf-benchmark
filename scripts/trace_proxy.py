#!/usr/bin/env python3
"""Transparent logging proxy in front of a vLLM OpenAI-compatible server.

Forwards every request unchanged to the upstream vLLM and appends one JSONL
trace record per `/v1/chat/completions` or `/v1/completions` call:

  {
    "ts": "2026-06-23T10:00:00.123456+00:00",  # request received (ISO 8601)
    "ts_epoch": 1750671600.123,
    "request_id": "...",                        # vLLM x-request-id if present
    "endpoint": "/v1/chat/completions",
    "model": "qwen3.6",
    "streamed": true,
    "input": {"messages": [...]} | {"prompt": "..."},   # full request content
    "output": "the assistant's full text",              # reassembled content
    "reasoning": "chain-of-thought, if any",            # delta.reasoning_content
    "prompt_tokens": 511, "completion_tokens": 217, "total_tokens": 728,
    "ttft_ms": 253.4,          # time to first token (streaming only)
    "latency_ms": 7934.2,      # request received -> last byte
    "status": 200
  }

For streaming requests the proxy injects `stream_options.include_usage=true`
upstream so vLLM emits a final usage chunk (→ exact token counts); all chunks
are still forwarded to the client, so the client sees standard OpenAI behavior.

Run:
  VLLM_UPSTREAM=http://localhost:8000 TRACE_PORT=8001 \
  TRACE_FILE=traces/vllm_trace.jsonl python3 scripts/trace_proxy.py
Then point the client at the proxy instead of vLLM:
  aiperf ... --url http://localhost:8001
"""
import os, json, time, datetime, asyncio
from aiohttp import web, ClientSession, ClientTimeout

UPSTREAM = os.environ.get("VLLM_UPSTREAM", "http://localhost:8000").rstrip("/")
PORT = int(os.environ.get("TRACE_PORT", "8001"))
TRACE_FILE = os.environ.get("TRACE_FILE", "traces/vllm_trace.jsonl")
RECORD_PATHS = ("/v1/chat/completions", "/v1/completions")
HOP = {"host", "content-length", "transfer-encoding", "connection", "keep-alive"}
os.makedirs(os.path.dirname(TRACE_FILE) or ".", exist_ok=True)
_lock = asyncio.Lock()


async def write_trace(rec):
    line = json.dumps(rec, ensure_ascii=False)
    async with _lock:
        with open(TRACE_FILE, "a") as f:
            f.write(line + "\n")


def now_rec():
    t = time.time()
    return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).isoformat(), t


def req_input(path, body):
    if body is None:
        return None
    if path.endswith("chat/completions"):
        return {"messages": body.get("messages")}
    return {"prompt": body.get("prompt")}


def _accumulate(ev, st):
    """Pull content/reasoning/usage out of one streamed chunk into state st.
    TTFT = time of the first emitted token, whether reasoning or content."""
    for ch in ev.get("choices") or []:
        d = ch.get("delta") or {}
        # streaming reasoning is `delta.reasoning` on this vLLM nightly
        # (some builds use `reasoning_content`); accept either
        rc = d.get("reasoning") or d.get("reasoning_content")
        txt = d.get("content") or ch.get("text")  # chat delta or /v1/completions text
        if rc:
            st["reason"].append(rc)
            if st["ttft"] is None:
                st["ttft"] = time.time()
        if txt:
            st["out"].append(txt)
            if st["ttft"] is None:
                st["ttft"] = time.time()
    if ev.get("usage"):
        st["usage"] = ev["usage"]


async def handle(request: web.Request):
    path = request.path
    method = request.method
    raw_body = await request.read()
    record = path in RECORD_PATHS
    reqj, is_stream, rec_in = None, False, None
    if record and raw_body:
        try:
            reqj = json.loads(raw_body)
            is_stream = bool(reqj.get("stream"))
            rec_in = req_input(path, reqj)
        except Exception:
            record = False

    fwd_body = raw_body
    if record and is_stream:  # ask upstream for a usage chunk so we get token counts
        so = dict(reqj.get("stream_options") or {})
        if not so.get("include_usage"):
            so["include_usage"] = True
            reqj["stream_options"] = so
            fwd_body = json.dumps(reqj).encode()

    fwd_headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP}
    ts_iso, t0 = now_rec()
    session: ClientSession = request.app["session"]
    url = UPSTREAM + path
    try:
        up = await session.request(method, url, data=fwd_body, headers=fwd_headers,
                                   params=request.query)
    except Exception as e:
        if record:
            await write_trace({"ts": ts_iso, "ts_epoch": t0, "endpoint": path,
                               "model": (reqj or {}).get("model"), "input": rec_in,
                               "error": f"upstream: {e}", "status": 502})
        return web.json_response({"error": str(e)}, status=502)

    resp_headers = {k: v for k, v in up.headers.items() if k.lower() not in HOP}
    rid = up.headers.get("x-request-id")

    # ---- non-streaming: read whole body, record, return ----
    if not (record and is_stream):
        data = await up.read()
        if record:
            out = reason = None
            usage = {}
            try:
                j = json.loads(data)
                usage = j.get("usage") or {}
                ch = (j.get("choices") or [{}])[0]
                msg = ch.get("message") or {}
                out = msg.get("content") if "message" in ch else ch.get("text")
                reason = msg.get("reasoning_content") or msg.get("reasoning")
            except Exception:
                pass
            await write_trace({
                "ts": ts_iso, "ts_epoch": t0, "request_id": rid, "endpoint": path,
                "model": (reqj or {}).get("model"), "streamed": False,
                "input": rec_in, "output": out, "reasoning": reason,
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "ttft_ms": None, "latency_ms": round((time.time() - t0) * 1000, 1),
                "status": up.status})
        return web.Response(status=up.status, body=data, headers=resp_headers)

    # ---- streaming (SSE): forward chunks, accumulate, record at end ----
    resp = web.StreamResponse(status=up.status, headers=resp_headers)
    await resp.prepare(request)
    st = {"out": [], "reason": [], "usage": None, "ttft": None}
    try:
        async for raw in up.content:
            await resp.write(raw)
            line = raw.strip()
            if line.startswith(b"data:"):
                payload = line[5:].strip()
                if payload and payload != b"[DONE]":
                    try:
                        _accumulate(json.loads(payload), st)
                    except Exception:
                        pass
    finally:
        await resp.write_eof()
        usage = st["usage"] or {}
        await write_trace({
            "ts": ts_iso, "ts_epoch": t0, "request_id": rid, "endpoint": path,
            "model": (reqj or {}).get("model"), "streamed": True,
            "input": rec_in, "output": "".join(st["out"]),
            "reasoning": "".join(st["reason"]) or None,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "ttft_ms": round((st["ttft"] - t0) * 1000, 1) if st["ttft"] else None,
            "latency_ms": round((time.time() - t0) * 1000, 1),
            "status": up.status})
    return resp


async def on_startup(app):
    app["session"] = ClientSession(timeout=ClientTimeout(total=None, sock_read=None))


async def on_cleanup(app):
    await app["session"].close()


def main():
    app = web.Application(client_max_size=1024 ** 3)  # allow big prompts (≤1 GiB)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    app.router.add_route("*", "/{tail:.*}", handle)
    print(f">>> trace proxy on :{PORT}  ->  {UPSTREAM}   logging to {TRACE_FILE}")
    web.run_app(app, host="0.0.0.0", port=PORT, print=None)


if __name__ == "__main__":
    main()
