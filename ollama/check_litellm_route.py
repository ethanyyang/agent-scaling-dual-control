#!/usr/bin/env python3
"""Check the exact litellm route the tau2 runner will use for the local Ollama model.

Run with the tau2 environment, for example:
    tau2-bench/.venv/bin/python ollama/check_litellm_route.py --model tt-qwen3.5-4b:q4

It sends one tool-calling request the way tau2's generate() does (tools, tool_choice="auto",
num_retries, seed) plus the llm_args planned for cells.json, and prints what tau2 will read:
content, tool_calls and usage. Exit code 0 means tau2 can use the route.
"""
import argparse
import json
import sys

LLM_ARGS = {
    "api_base": "http://127.0.0.1:11434/v1",
    "api_key": "ollama",            # placeholder; keeps the real OPENAI_API_KEY off this route
    "timeout": 3600,                 # a long thinking call on a laptop can pass litellm's default limit
    "extra_body": {"reasoning_effort": "high"},
}

TOOLS = [{"type": "function", "function": {
    "name": "get_customer_by_phone",
    "description": "Look up a customer account by phone number.",
    "parameters": {"type": "object", "properties": {"phone_number": {"type": "string"}}, "required": ["phone_number"]}}}]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="Ollama model name, e.g. tt-qwen3.5-4b:q4")
    a = ap.parse_args()

    import litellm
    from litellm import completion

    try:
        from importlib.metadata import version
        print("litellm version:", version("litellm"))
    except Exception:  # noqa: BLE001
        print("litellm version: unknown")
    model = "openai/" + a.model
    print("route:", model, json.dumps(LLM_ARGS))
    messages = [
        {"role": "system", "content": "You are a telecom support agent. Use the tools to look things up."},
        {"role": "user", "content": "My number is 555-123-2002. Please pull up my account."},
    ]
    try:
        resp = completion(model=model, messages=messages, tools=TOOLS, tool_choice="auto",
                          num_retries=3, seed=300, **LLM_ARGS)
    except Exception as e:  # noqa: BLE001
        print("[FAIL] litellm call raised:", repr(e)[:800])
        sys.exit(1)

    msg = resp.choices[0].message
    calls = msg.tool_calls or []
    usage = resp.get("usage")
    print("finish_reason:", resp.choices[0].finish_reason)
    print("content head:", (msg.content or "")[:160].replace("\n", " "))
    print("reasoning_content chars:", len(getattr(msg, "reasoning_content", None) or ""))
    print("usage:", {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens} if usage else None)
    ok = False
    if calls:
        try:
            args = json.loads(calls[0].function.arguments)   # tau2 does exactly this
            print("tool call:", calls[0].function.name, args)
            ok = calls[0].function.name == "get_customer_by_phone"
        except Exception as e:  # noqa: BLE001
            print("tool arguments are not valid JSON:", e)
    else:
        print("no tool call returned")
    think_leak = "<think>" in (msg.content or "")
    if think_leak:
        print("think tags leaked into content: the customer would see the thinking")
    ok = ok and usage is not None and (usage.completion_tokens or 0) > 0 and not think_leak
    try:
        from litellm import completion_cost
        print("litellm cost:", completion_cost(completion_response=resp))
    except Exception as e:  # noqa: BLE001
        print("litellm has no price for this model (tau2 will record cost 0.0):", str(e)[:120])
    print("[PASS] route works" if ok else "[FAIL] route check failed")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
