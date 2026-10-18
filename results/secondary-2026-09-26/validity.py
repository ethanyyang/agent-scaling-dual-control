"""G1 validity table (ANALYSIS.md section 1, G1). One row per M1/S2 run. Diagnostic; reads results.json only."""
import os as _os, sys as _sys
_REPO = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
_HERE = _os.path.dirname(_os.path.abspath(__file__))
import json, ast, statistics, sys, os
S = _REPO + "/tau2-bench/data/simulations/"
MA, BUD, TERM = "transfer_testing_multi_agent", "transfer_testing_completion_budget", "transfer_testing_termination"

def parses(txt):
    if not isinstance(txt, str): return isinstance(txt, (dict, list))
    t = txt.strip()
    if t.startswith("```"):
        t = t.strip("`"); t = t[4:] if t.startswith("json") else t
    for f in (json.loads, ast.literal_eval):
        try:
            if isinstance(f(t), dict): return True
        except Exception: pass
    return False

def run(name):
    sims = json.load(open(S + name + "/results.json"))["simulations"]
    r = dict(run=name, eps=len(sims), infra=0, calls=0, cut=0, tok=0, cut_tok=0, runaway=0, runaway_tok=0,
             dc_exh=0, dc_ord=0, json=0, cut_text=0, cut_text_old=0, holding=0, w_true=0, w_false=0, w_none=0,
             plan_calls=0, plan_fail=0, adv_eps=0, exh=0, util=[], reward=0.0)
    for s in sims:
        if s.get("termination_reason") == "infrastructure_error": r["infra"] += 1
        r["reward"] += (s.get("reward_info") or {}).get("reward", 0) or 0
        label = "normal"; spent = limit = None; adv = False
        for m in s["messages"]:
            if m["role"] != "assistant": continue
            rd = m.get("raw_data") or {}
            if TERM in rd: label = rd[TERM]
            b = rd.get(BUD) or {}
            spent, limit = b.get("spent", spent), b.get("limit", limit)
            if MA not in rd: continue
            ma = rd[MA]; comps = ma.get("components") or []; ev = [str(e) for e in (ma.get("events") or [])]
            n_cut = 0
            for c in comps:
                ct = (c.get("usage") or {}).get("completion_tokens", 0) or 0
                r["calls"] += 1; r["tok"] += ct
                if c.get("call_name") in ("m1_plan", "s2_plan"): r["plan_calls"] += 1
                if c.get("call_name") == "m1_advisor": adv = True
                mx = c.get("max_tokens_sent")
                if mx and ct > mx: r["runaway"] += 1; r["runaway_tok"] += ct
                if c.get("truncated"): n_cut += 1; r["cut"] += 1; r["cut_tok"] += ct
            r["plan_fail"] += sum(1 for e in ev if e == "plan_parse_failed")
            if n_cut >= 2:
                if rd.get(TERM) == "budget_exhausted": r["dc_exh"] += 1
                else: r["dc_ord"] += 1
            fb = any("fallback_text" in e for e in ev)
            if fb: r["holding"] += 1
            for i, a in enumerate(ma.get("assignments") or []):
                if a.get("kind") != "write": continue
                v = a.get("executed_as_issued")
                r["w_true" if v is True else "w_false" if v is False else "w_none"] += 1
            text = (m.get("content") or "").strip()
            if text and not m.get("tool_calls"):
                if text.startswith("{") or text.startswith("```"): r["json"] += 1
                elif n_cut and comps and comps[-1].get("truncated") and label != "budget_exhausted" and not fb:
                    r["cut_text_old"] += 1
                    if not parses(comps[-1].get("output")): r["cut_text"] += 1
        r["adv_eps"] += adv; r["exh"] += label == "budget_exhausted"
        if spent is not None and limit: r["util"].append(spent / limit)
    r["util_med"] = statistics.median(r["util"]) if r["util"] else None; del r["util"]
    r["pass1"] = r["reward"] / r["eps"]
    w = r["w_true"] + r["w_false"]
    r["write_exec"] = r["w_true"] / w if w else None
    r["cut_share"] = r["cut"] / r["calls"] if r["calls"] else 0
    r["cut_tok_share"] = r["cut_tok"] / r["tok"] if r["tok"] else 0
    r["cut_tok_share_norunaway"] = r["cut_tok"] / (r["tok"] - r["runaway_tok"]) if r["tok"] > r["runaway_tok"] else 0
    base = (r["write_exec"] is None or r["write_exec"] >= 0.9) and r["cut_share"] <= 0.05 and r["cut_tok_share"] <= 0.10 \
        and r["json"] == 0 and r["cut_text"] == 0 and r["infra"] == 0
    r["valid_strict"] = base and r["dc_exh"] + r["dc_ord"] == 0
    r["valid_amend_b"] = base and r["dc_ord"] == 0
    return r

if __name__ == "__main__":
    out = []
    for n in sys.argv[1:]:
        try:
            out.append(run(n)); print(n, "ok", flush=True)
        except Exception as e:
            print(n, "ERROR", e, flush=True)
    json.dump(out, open(_REPO + "/results/secondary-2026-09-26/validity.json", "w"), indent=1)
