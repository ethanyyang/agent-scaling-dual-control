#!/usr/bin/env python3
"""Read the A1 smoke runs in the fixed order and write the gate file for the A1 grid.

Fixed order (ANALYSIS.md CHANGELOG 2026-10-12): infrastructure errors, the mechanical G1 bars,
the write-order bar (at least 90% of unique write orders executed as issued; a refused order
counts as not executed), dropped orchestrator tool calls, reward last. Reward is printed and
never gates anything.

    python3 a1_gate.py            # the three registered smokes; writes results/a1-smoke-gate.json
    python3 a1_gate.py --runs <run-name> [...]   # read other runs (no gate file is written)
    python3 a1_gate.py --no-write # read the registered smokes, write nothing

The gate passes only when all three smokes have finished (manifest return code 0) and every
smoke passes infrastructure errors, every mechanical bar and the write-order bar. scripts/
a1_grid.sh refuses to launch without a passing gate file. Reads results.json only.
"""
from __future__ import annotations

import ast
import collections
import datetime as dt
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SIM = ROOT / "tau2-bench" / "data" / "simulations"
MANIFESTS = ROOT / "results" / "calibration-manifests"
GATE_FILE = ROOT / "results" / "a1-smoke-gate.json"
MA, BUD, TERM = "transfer_testing_multi_agent", "transfer_testing_completion_budget", "transfer_testing_termination"

SMOKES = [  # the three cells with the most refused or invented orders across the families (CHANGELOG 2026-10-12)
    "smoke5-m1-telecom-gemini3flash-high-gpt52low-b4x-capb1x-otd-1trials-seed300",
    "smoke5-m1-retail-gpt5mini-high-gpt52low-b4x-capb1x-otd-1trials-seed300",
    "smoke5-m1-airline-gpt5nano-high-gpt52low-b4x-capb1x-otd-1trials-seed300",
]
MAX_CUT_CALL_SHARE, MAX_CUT_TOKEN_SHARE, MIN_AS_ISSUED = 0.05, 0.10, 0.90


def schema(domain: str) -> dict:
    src = (ROOT / "tau2-bench" / "src" / "tau2" / "domains" / domain / "tools.py").read_text()
    out = {}
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.FunctionDef):
            for d in n.decorator_list:
                if isinstance(d, ast.Call) and getattr(d.func, "id", "") == "is_tool":
                    kind = d.args[0].attr if d.args and isinstance(d.args[0], ast.Attribute) else "?"
                    out[n.name] = (kind, [a.arg for a in n.args.args if a.arg != "self"])
    return out


def _strip(n):
    return (n or "").split(".")[-1]


def _norm(v):
    return json.dumps(v, sort_keys=True).lower().replace(" ", "")


def classify(a: dict, sch: dict) -> str:
    """Same categories as the secondary audit (results/secondary-2026-09-26/orders.py)."""
    spec = a.get("content")
    if isinstance(spec, str):
        try:
            spec = json.loads(spec)
        except Exception:
            spec = None
    tcs = a.get("tool_calls") or []
    if not isinstance(spec, dict):
        return "unstructured_order"
    want = _strip(spec.get("tool"))
    if not tcs:
        return "valid_name_no_call" if want in sch else "invalid_name_refused"
    wargs = spec.get("arguments") if isinstance(spec.get("arguments"), dict) else {}
    got, gargs = _strip(tcs[0]["name"]), tcs[0].get("arguments") or {}
    if want not in sch:
        return "invalid_name_mapped_to_write" if got in sch and sch[got][0] == "WRITE" else "invalid_name_diverted"
    if got != want:
        return "valid_name_tool_changed_write" if got in sch and sch[got][0] == "WRITE" else "valid_name_diverted"
    keys = set(sch[want][1])
    shared = [k for k in keys if k in wargs and k in gargs]
    if any(_norm(wargs[k]) != _norm(gargs[k]) for k in shared):
        return "value_changed"
    if [k for k in wargs if k not in keys] or [k for k in gargs if k not in wargs]:
        return "schema_keys_corrected"
    return "as_issued"


def read(run: str) -> dict:
    path = SIM / run / "results.json"
    r = {"run": run, "exists": path.exists()}
    if not path.exists():
        r["error"] = f"missing {path}"
        return r
    man = MANIFESTS / f"{run}.json"
    r["manifest_rc"] = json.load(open(man)).get("return_code") if man.exists() else None
    d = json.load(open(path))
    sims = d["simulations"]
    domain = run.split("-")[2]
    sch = schema(domain)
    calls = cut = tok = cut_tok = dc_exh = dc_ord = jsn = cut_text = otc = exh = plan = plan_fail = 0
    tools_per_ep = []
    otd_flags = set()
    orders = collections.Counter()
    for s in sims:
        label, n_tools = "normal", 0
        seen = set()
        for m in s["messages"]:
            if m["role"] != "assistant":
                continue
            if m.get("tool_calls"):
                n_tools += len(m["tool_calls"])
            rd = m.get("raw_data") or {}
            if TERM in rd:
                label = rd[TERM]
            if MA not in rd:
                continue
            ma = rd[MA]
            otd_flags.add(ma.get("orchestrator_tool_definitions"))
            ev = [str(e) for e in (ma.get("events") or [])]
            otc += sum(1 for e in ev if e.startswith("orchestrator_returned_tool_call"))
            plan_fail += sum(1 for e in ev if e == "plan_parse_failed")
            comps = ma.get("components") or []
            n_cut = 0
            for c in comps:
                ct = (c.get("usage") or {}).get("completion_tokens", 0) or 0
                calls += 1
                tok += ct
                plan += c.get("call_name") == "m1_plan"
                if c.get("truncated"):
                    n_cut += 1
                    cut += 1
                    cut_tok += ct
            if n_cut >= 2:
                if rd.get(TERM) == "budget_exhausted":
                    dc_exh += 1
                else:
                    dc_ord += 1
            fb = any("fallback_text" in e for e in ev)
            text = (m.get("content") or "").strip()
            if text and not m.get("tool_calls"):
                if text.startswith("{") or text.startswith("```"):
                    jsn += 1
                elif n_cut and comps and comps[-1].get("truncated") and label != "budget_exhausted" and not fb:
                    cut_text += 1
            for a in ma.get("assignments") or []:
                if a.get("kind") != "write":
                    continue
                k = (json.dumps(a.get("content"), sort_keys=True), json.dumps(a.get("tool_calls"), sort_keys=True))
                if k in seen:
                    continue
                seen.add(k)
                orders[classify(a, sch)] += 1
        exh += label == "budget_exhausted"
        tools_per_ep.append(n_tools)
    n_orders = sum(orders.values())
    as_issued = orders["as_issued"] / n_orders if n_orders else None
    infra = sum(1 for s in sims if s.get("termination_reason") == "infrastructure_error")
    rewards = [float((s.get("reward_info") or {}).get("reward", 0) or 0) for s in sims]
    r.update(
        episodes=len(sims), infra=infra, calls=calls, cut_calls=cut, cut_call_share=(cut / calls if calls else 0.0),
        tokens=tok, cut_tokens=cut_tok, cut_token_share=(cut_tok / tok if tok else 0.0),
        double_cut_exhaustion=dc_exh, double_cut_normal=dc_ord, json_to_customer=jsn, cut_text_to_customer=cut_text,
        tool_calls_per_episode=(st.mean(tools_per_ep) if tools_per_ep else 0.0), exhausted=exh,
        plan_calls=plan, plan_parse_failed=plan_fail, orchestrator_tool_definitions=sorted(str(x) for x in otd_flags),
        dropped_orchestrator_tool_calls=otc, write_orders=dict(orders), write_orders_total=n_orders,
        write_orders_as_issued_share=as_issued, pass_count=sum(x >= 1 for x in rewards),
    )
    bars = {
        "infrastructure_errors": infra == 0,
        "calls_cut_at_cap": r["cut_call_share"] <= MAX_CUT_CALL_SHARE,
        "tokens_in_cut_calls": r["cut_token_share"] <= MAX_CUT_TOKEN_SHARE,
        "double_cut_turns": (dc_exh + dc_ord) == 0,
        "json_or_cut_text_to_customer": jsn == 0 and cut_text == 0,
        "write_orders_as_issued": (as_issued is not None and as_issued >= MIN_AS_ISSUED),
        "finished": r["manifest_rc"] == 0,
    }
    r["bars"] = bars
    r["pass"] = all(bars.values())
    return r


def show(r: dict) -> None:
    print(f"== {r['run']}")
    if not r.get("exists"):
        print(f"   missing: {r.get('error')}")
        return
    b = r["bars"]
    f = lambda ok: "PASS" if ok else "FAIL"
    print(f"   finished (manifest rc 0): {f(b['finished'])} (rc={r['manifest_rc']}); episodes {r['episodes']}; "
          f"orchestrator_tool_definitions seen: {r['orchestrator_tool_definitions']}")
    print(f"   1 [{f(b['infrastructure_errors'])}] infrastructure errors: {r['infra']} (bar 0)")
    print(f"   2 [{f(b['calls_cut_at_cap'])}] calls cut at the cap: {r['cut_calls']}/{r['calls']} = {r['cut_call_share']:.1%} (bar <= 5%)")
    print(f"     [{f(b['tokens_in_cut_calls'])}] tokens in cut calls: {r['cut_token_share']:.2%} (bar <= 10%)")
    print(f"     [{f(b['double_cut_turns'])}] turns with two cut calls: {r['double_cut_exhaustion'] + r['double_cut_normal']} "
          f"(exhaustion {r['double_cut_exhaustion']}, normal {r['double_cut_normal']}; bar 0)")
    print(f"     [{f(b['json_or_cut_text_to_customer'])}] JSON to customer {r['json_to_customer']}; cut text {r['cut_text_to_customer']} (bar 0)")
    print(f"     [info] tool calls per episode {r['tool_calls_per_episode']:.1f}; exhausted {r['exhausted']}/{r['episodes']}; "
          f"plan parse failures {r['plan_parse_failed']} of {r['plan_calls']} plan calls")
    share = r["write_orders_as_issued_share"]
    print(f"   3 [{f(b['write_orders_as_issued'])}] write orders executed as issued: {r['write_orders'].get('as_issued', 0)}/{r['write_orders_total']}"
          f" = {share:.0%} (bar >= 90%)" if share is not None else "   3 [FAIL] write orders executed as issued: no write order in the run")
    others = {k: v for k, v in r["write_orders"].items() if k != "as_issued"}
    if others:
        print(f"     other categories: {others}")
    print(f"   4 [info] orchestrator tool calls dropped: {r['dropped_orchestrator_tool_calls']}")
    print(f"   5 reward (read last, never gates): {r['pass_count']}/{r['episodes']} passed")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    write = "--no-write" not in argv
    runs = SMOKES
    if "--runs" in argv:
        runs = [a for a in argv[argv.index("--runs") + 1:] if not a.startswith("--")]
        write = False
    results = [read(r) for r in runs]
    for r in results:
        show(r)
    ok = all(r.get("pass") for r in results) and len(results) == len(SMOKES) and runs == SMOKES
    pooled_n = sum(r.get("write_orders_total", 0) for r in results if r.get("exists"))
    pooled_ok = sum(r.get("write_orders", {}).get("as_issued", 0) for r in results if r.get("exists"))
    if pooled_n:
        print(f"\npooled over the runs read: write orders as issued {pooled_ok}/{pooled_n} = {pooled_ok / pooled_n:.0%} (information only; the bar is per run)")
    if write:
        GATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        gate = dict(read_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), runs=results, **{"pass": ok},
                    rule="all three smokes finished and pass infrastructure errors, the mechanical G1 bars and the write-order bar (>= 90% as issued); reward never gates")
        json.dump(gate, open(GATE_FILE, "w"), indent=1, default=str)
        print(f"\ngate: {'PASS' if ok else 'FAIL'} -> {GATE_FILE.relative_to(ROOT)}")
    else:
        print(f"\ngate (not written): {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
