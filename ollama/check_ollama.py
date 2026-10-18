#!/usr/bin/env python3
"""Check a local Ollama model before it is used as a tau2 agent. Standard library only.

Checks, in order:
  1. thinking   : the thinking trace is returned apart from the answer, and
                  usage.completion_tokens counts the thinking tokens (the budget ledger needs this)
  2. effort     : reasoning_effort 'high' is accepted; 'none' is logged for contrast
  3. tools      : a tool call comes back as structured tool_calls, and the tool result round-trip works
  4. context    : a long prompt (about 30% of num_ctx) arrives whole (Ollama's default is 4k and it cuts silently)
  5. placement  : `ollama ps` shows the model fully on the GPU
  6. speed      : single-stream and parallel tokens per second, with a rough hours-per-cell estimate

Exit code 0 means checks 1, 3, 4 and 5 passed. Speed and effort are reported, never failed.
"""
import argparse
import concurrent.futures as cf
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:11434"


def chat(model, messages, tools=None, max_tokens=None, extra=None, timeout=3600):
    body = {"model": model, "messages": messages}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"  # tau2 always sends this; Ollama must tolerate it
    if max_tokens:
        body["max_tokens"] = max_tokens
    if extra:
        body.update(extra)
    req = urllib.request.Request(
        BASE + "/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer ollama"},
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:500]}")
    return out, time.time() - t0


def parts(resp):
    msg = resp["choices"][0]["message"]
    reasoning = msg.get("reasoning") or msg.get("reasoning_content") or msg.get("thinking") or ""
    field = next((k for k in ("reasoning", "reasoning_content", "thinking") if msg.get(k)), None)
    return msg, (msg.get("content") or ""), reasoning, field, resp.get("usage") or {}


RESULTS = {}


def record(name, ok, detail):
    RESULTS[name] = {"pass": ok, **detail}
    tag = "INFO" if ok is None else ("PASS" if ok else "FAIL")
    print(f"[{tag}] {name}: " + json.dumps(detail, ensure_ascii=False)[:900], flush=True)


TOOLS = [
    {"type": "function", "function": {
        "name": "get_customer_by_phone",
        "description": "Look up a customer account by phone number.",
        "parameters": {"type": "object", "properties": {"phone_number": {"type": "string"}}, "required": ["phone_number"]}}},
    {"type": "function", "function": {
        "name": "suspend_line",
        "description": "Suspend a phone line. Only after the customer is verified.",
        "parameters": {"type": "object", "properties": {"line_id": {"type": "string"}, "reason": {"type": "string"}}, "required": ["line_id", "reason"]}}},
]


def check_thinking(model):
    q = ("A customer has a 15 GB plan and used 17.4 GB. Overage costs $2 for every started 0.5 GB. "
         "What is the overage charge in dollars? Reply with the number only.")
    # the runner sends reasoning_effort=high on every call; the 0.8B and 2B sizes do not think unless asked
    resp, dt = chat(model, [{"role": "user", "content": q}], max_tokens=8000, extra={"reasoning_effort": "high"})
    msg, content, reasoning, field, usage = parts(resp)
    ct = usage.get("completion_tokens") or 0
    leak = "<think>" in content or "</think>" in content
    # thinking tokens are counted if completion_tokens is far above what the short answer alone needs
    counted = bool(reasoning) and ct * 6 >= len(reasoning)
    ok = bool(reasoning) and not leak and counted
    record("1_thinking", ok, {
        "thinking_field": field, "thinking_chars": len(reasoning), "answer": content.strip()[:80],
        "expected_answer": "10", "think_tag_leaked_into_answer": leak,
        "completion_tokens": ct, "thinking_tokens_counted_in_usage": counted,
        "seconds": round(dt, 1), "tokens_per_second_single": round(ct / dt, 1) if dt else None,
        "finish_reason": resp["choices"][0].get("finish_reason")})
    return (ct / dt) if dt else None


def check_effort(model):
    q = "Is 391 a prime number? Reply yes or no."
    out = {}
    for label, extra in (("unset", None), ("high", {"reasoning_effort": "high"}), ("none", {"reasoning_effort": "none"})):
        try:
            resp, dt = chat(model, [{"role": "user", "content": q}], max_tokens=6000, extra=extra)
            _, content, reasoning, _, usage = parts(resp)
            out[label] = {"thinking_chars": len(reasoning), "completion_tokens": usage.get("completion_tokens"),
                          "answer": content.strip()[:40]}
        except Exception as e:  # noqa: BLE001
            out[label] = {"error": str(e)[:300]}
    record("2_effort", None, out)


def check_tools(model):
    sys_p = "You are a telecom support agent. Use the tools to look things up. Never guess account data."
    msgs = [{"role": "system", "content": sys_p},
            {"role": "user", "content": "Hi, my number is 555-123-2002. Can you pull up my account?"}]
    resp, dt = chat(model, msgs, tools=TOOLS, max_tokens=6000)
    msg, content, _, _, usage = parts(resp)
    calls = msg.get("tool_calls") or []
    detail = {"n_tool_calls": len(calls), "content_head": content[:120], "seconds": round(dt, 1)}
    ok = False
    if calls:
        fn = calls[0].get("function", {})
        detail["name"] = fn.get("name")
        try:
            args = json.loads(fn.get("arguments") or "{}")
            detail["arguments"] = args
            ok = fn.get("name") == "get_customer_by_phone" and "555" in json.dumps(args)
        except Exception as e:  # noqa: BLE001
            detail["arguments_error"] = str(e)
    if ok:
        # round trip: give the tool result back, expect a normal text reply and no think tags
        msgs2 = msgs + [
            {"role": "assistant", "content": content or None, "tool_calls": calls},
            {"role": "tool", "tool_call_id": calls[0].get("id", "call_0"),
             "content": json.dumps({"customer_id": "C1001", "name": "Dana Reyes", "lines": ["L2002"], "status": "active"})},
        ]
        try:
            resp2, dt2 = chat(model, msgs2, tools=TOOLS, max_tokens=6000)
            _, content2, _, _, _ = parts(resp2)
            detail["round_trip_reply_head"] = content2[:160]
            detail["round_trip_ok"] = bool(content2.strip()) and "<think>" not in content2
            ok = ok and detail["round_trip_ok"]
        except Exception as e:  # noqa: BLE001
            detail["round_trip_error"] = str(e)[:300]
            ok = False
    record("3_tools", ok, detail)


def check_context(model, ctx):
    target = int(min(40000, 0.30 * ctx))          # tokens we try to send
    n_lines = target // 24                         # about 24 tokens per filler line
    lines = [f"Rule {i}: plan code P{i:05d} has a monthly allowance of {5 + i % 40} GB and a late fee of ${3 + i % 9}."
             for i in range(n_lines)]
    lines.insert(0, "VERIFICATION WORD ONE: PELICAN-4471.")
    lines.insert(len(lines) // 2, "VERIFICATION WORD TWO: GRANITE-9038.")
    sys_p = "Policy manual. Read all of it.\n" + "\n".join(lines)
    q = "What are verification word one and verification word two? Reply with the two words only."
    resp, dt = chat(model, [{"role": "system", "content": sys_p}, {"role": "user", "content": q}], max_tokens=4000)
    _, content, _, _, usage = parts(resp)
    pt = usage.get("prompt_tokens") or 0
    got1, got2 = "PELICAN-4471" in content, "GRANITE-9038" in content
    whole = pt >= 0.6 * target
    record("4_context", whole and got1 and got2, {
        "prompt_tokens_reported": pt, "prompt_tokens_aimed": target, "prompt_arrived_whole": whole,
        "word_one_found": got1, "word_two_found": got2, "answer": content.strip()[:80],
        "seconds": round(dt, 1), "note": "prompt_tokens near 4096 means the 4k default is in force"})


def check_placement(ollama_bin):
    try:
        ps = subprocess.run([ollama_bin, "ps"], capture_output=True, text=True, timeout=30).stdout
    except Exception as e:  # noqa: BLE001
        record("5_placement", False, {"error": str(e)})
        return
    on_gpu = "100% GPU" in ps
    record("5_placement", on_gpu, {"ollama_ps": ps.strip().splitlines(),
                                   "note": "anything other than 100% GPU means it spilled to CPU: lower PAR or CTX, or use q4"})


def check_speed(model, parallel, single_tps):
    topics = ["mobile data roaming", "SIM card activation", "APN settings", "airline change fees",
              "retail return windows", "baggage allowance rules", "two-factor login", "billing cycles"]

    def one(i):
        p = f"Explain {topics[i % len(topics)]} to a new support agent in about 400 words."
        resp, _ = chat(model, [{"role": "user", "content": p}], max_tokens=500)
        return (resp.get("usage") or {}).get("completion_tokens") or 0

    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=parallel) as ex:
        toks = list(ex.map(one, range(parallel)))
    wall = time.time() - t0
    agg = sum(toks) / wall if wall else 0
    est = {f"hours_per_150_episodes_at_{k}k_tokens_each": round(150 * k * 1000 / agg / 3600, 1) if agg else None
           for k in (10, 30, 60)}
    record("6_speed", None, {"parallel": parallel, "tokens": toks, "wall_seconds": round(wall, 1),
                             "aggregate_tokens_per_second": round(agg, 1),
                             "single_stream_tokens_per_second": round(single_tps, 1) if single_tps else None,
                             **est, "note": "generation only; prompt reading time comes on top"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--ctx", type=int, default=131072)
    ap.add_argument("--parallel", type=int, default=2)
    ap.add_argument("--ollama-bin", default="ollama")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    print(f"model {a.model} | ctx {a.ctx} | parallel {a.parallel}", flush=True)
    single = None
    steps = [
        ("1_thinking", lambda: check_thinking(a.model)),
        ("2_effort", lambda: check_effort(a.model)),
        ("3_tools", lambda: check_tools(a.model)),
        ("4_context", lambda: check_context(a.model, a.ctx)),
        ("5_placement", lambda: check_placement(a.ollama_bin)),
    ]
    for name, fn in steps:
        try:
            r = fn()
            if name == "1_thinking":
                single = r
        except Exception as e:  # noqa: BLE001
            record(name, False, {"error": str(e)[:500]})
    try:
        check_speed(a.model, a.parallel, single)
    except Exception as e:  # noqa: BLE001
        record("6_speed", None, {"error": str(e)[:500]})

    must = ["1_thinking", "3_tools", "4_context", "5_placement"]
    failed = [k for k in must if not RESULTS.get(k, {}).get("pass")]
    RESULTS["_summary"] = {"model": a.model, "ctx": a.ctx, "parallel": a.parallel,
                           "failed": failed, "time_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())}
    if a.out:
        with open(a.out, "w") as f:
            json.dump(RESULTS, f, indent=1, ensure_ascii=False)
    print("SUMMARY:", "all required checks passed" if not failed else f"FAILED: {failed}", flush=True)
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
