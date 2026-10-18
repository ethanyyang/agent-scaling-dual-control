#!/usr/bin/env python3
"""Health check for M1 smoke runs. Reads results.json files and prints the bars fixed in
`M1 smoke test plan v1.md`. Reward is printed last on purpose: read health first.

Usage:  python3 smoke_health.py <run-name> [<run-name> ...]
        (run-name = folder under tau2-bench/data/simulations/)

Not part of the pre-registered analysis. Diagnostic only.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SIMS = ROOT / "tau2-bench" / "data" / "simulations"
MA = "transfer_testing_multi_agent"
BUD = "transfer_testing_completion_budget"
TERM = "transfer_testing_termination"
CANARY = "contract_end_suspension"  # S1 passes this task 3 of 3 on telecom x gemini-3.1-flash-lite

# Bars fixed before the run (M1 smoke test plan v1, section 4).
MAX_CUT_CALL_SHARE = 0.05
MAX_CUT_TOKEN_SHARE = 0.10
MIN_ADVISOR_EPISODE_SHARE = 0.80
MIN_TOOL_CALLS_PER_EPISODE = 5.0


def check(name: str) -> None:
    path = SIMS / name / "results.json"
    data = json.load(open(path))
    sims = data["simulations"]
    n_eps = len(sims)
    calls = cut_calls = tokens = cut_tokens = 0
    double_cut_turns = json_to_customer = cut_text_to_customer = holding_lines = 0
    advisor_eps = exhausted = tool_calls = 0
    max_call = 0
    per_ep = []
    archs = set()
    review = {}
    plan_fail = 0
    s2_events = {}
    orch_tool_calls = 0   # G1 write-order fix A1: tool calls the orchestrator returned (charged, dropped)
    otd = set()           # orchestrator_tool_definitions flags seen in the run
    infra = sum(1 for s in sims if s.get("termination_reason") == "infrastructure_error")
    for s in sims:
        used_advisor = False
        label = "normal"
        spent = limit = None
        ep_tools = 0
        for m in s["messages"]:
            if m["role"] != "assistant":
                continue
            if m.get("tool_calls"):
                ep_tools += len(m["tool_calls"])
            rd = m.get("raw_data") or {}
            if MA not in rd:
                continue
            comps = rd[MA]["components"]
            archs.add(rd[MA].get("architecture", "M1"))
            outcome = (rd[MA].get("review") or {}).get("outcome")
            if outcome:
                review[outcome] = review.get(outcome, 0) + 1
            plan_fail += sum(1 for e in (rd[MA].get("events") or []) if e == "plan_parse_failed")
            orch_tool_calls += sum(1 for e in (rd[MA].get("events") or []) if str(e).startswith("orchestrator_returned_tool_call"))
            otd.add(rd[MA].get("orchestrator_tool_definitions", False))
            for e in rd[MA].get("events") or []:
                if e in ("policy_check_missing", "forced_closing", "act_json_reply", "act_json_used_message", "plan_returned_tool_call", "plan_truncated"):
                    s2_events[e] = s2_events.get(e, 0) + 1
            n_cut = 0
            for c in comps:
                ct = (c.get("usage") or {}).get("completion_tokens", 0) or 0
                calls += 1
                tokens += ct
                max_call = max(max_call, ct)
                if c.get("truncated"):
                    n_cut += 1
                    cut_calls += 1
                    cut_tokens += ct
                if c["call_name"] == "m1_advisor":
                    used_advisor = True
            if n_cut >= 2:
                double_cut_turns += 1
            label = rd.get(TERM, label)
            b = rd.get(BUD) or {}
            spent, limit = b.get("spent", spent), b.get("limit", limit)
            events = rd[MA].get("events") or []
            if any("fallback_text" in str(e) for e in events):
                holding_lines += 1
            text = (m.get("content") or "").strip()
            if text and not m.get("tool_calls"):
                if text.startswith("{") or text.startswith("```"):
                    json_to_customer += 1
                elif n_cut and comps and comps[-1].get("truncated") and label != "budget_exhausted" \
                        and not any("fallback_text" in str(e) for e in events):
                    cut_text_to_customer += 1
        advisor_eps += used_advisor
        exhausted += label == "budget_exhausted"
        tool_calls += ep_tools
        reward = (s.get("reward_info") or {}).get("reward")
        per_ep.append((s["task_id"], reward, label, spent, limit, ep_tools))

    def bar(ok: bool) -> str:
        return "PASS" if ok else "FAIL"

    cut_share = cut_calls / calls if calls else 0.0
    cut_tok_share = cut_tokens / tokens if tokens else 0.0
    adv_share = advisor_eps / n_eps if n_eps else 0.0
    tools_per_ep = tool_calls / n_eps if n_eps else 0.0
    print(f"\n== {name}")
    print(f"   episodes {n_eps} | LLM calls {calls} | completion tokens {tokens} | largest single call {max_call}")
    print(f"   [{bar(infra == 0)}] infrastructure errors: {infra} (bar 0)")
    print(f"   [{bar(cut_share <= MAX_CUT_CALL_SHARE)}] calls cut at the cap: {cut_calls}/{calls} = {cut_share:.0%} (bar <= {MAX_CUT_CALL_SHARE:.0%})")
    print(f"   [{bar(cut_tok_share <= MAX_CUT_TOKEN_SHARE)}] tokens spent in cut calls: {cut_tok_share:.0%} (bar <= {MAX_CUT_TOKEN_SHARE:.0%})")
    print(f"   [{bar(double_cut_turns == 0)}] turns with two or more cut calls: {double_cut_turns} (bar 0)")
    print(f"   [{bar(json_to_customer == 0 and cut_text_to_customer == 0)}] customer messages that were JSON: {json_to_customer}; cut text: {cut_text_to_customer} (bar 0 and 0)")
    if archs == {"S2"}:
        print(f"   [info] S2: no advisor; plan-parse failures (turns) {plan_fail}; events {dict(sorted(s2_events.items()))}")
        print(f"   [info] S2 review outcomes (turns): {dict(sorted(review.items()))}")
    else:
        print(f"   [info] orchestrator sees tool definitions (fix A1): {sorted(otd)}; tool calls returned by the orchestrator (dropped): {orch_tool_calls}")
        print(f"   [{bar(adv_share >= MIN_ADVISOR_EPISODE_SHARE)}] episodes that consulted the advisor: {advisor_eps}/{n_eps} (reported indicator since the 2026-09-22 amendment; was bar >= {MIN_ADVISOR_EPISODE_SHARE:.0%})")
    if archs == {"S2"}:
        print(f"   [info] agent tool calls per episode: {tools_per_ep:.1f} (the >= {MIN_TOOL_CALLS_PER_EPISODE:.0f} bar is M1's delegation check; not applied to S2)")
    else:
        print(f"   [{bar(tools_per_ep >= MIN_TOOL_CALLS_PER_EPISODE)}] agent tool calls per episode: {tools_per_ep:.1f} (bar >= {MIN_TOOL_CALLS_PER_EPISODE:.0f}; read at 3x and above only)")
    print(f"   [info] holding lines sent: {holding_lines} | episodes ended budget_exhausted: {exhausted}/{n_eps}")
    print("   ---- reward (read last) ----")
    for task_id, reward, label, spent, limit, ep_tools in per_ep:
        mark = "  <- canary" if CANARY in task_id else ""
        print(f"   reward={reward} {label:16s} spent={spent}/{limit} tools={ep_tools} {task_id[:60]}{mark}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for run in sys.argv[1:]:
        check(run)
