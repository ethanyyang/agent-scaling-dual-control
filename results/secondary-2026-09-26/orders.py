"""Write-order audit for M1 runs: separates the orchestrator's schema guesses from database-agent misexecution."""
import os as _os, sys as _sys
_REPO = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
_HERE = _os.path.dirname(_os.path.abspath(__file__))
import ast, json, os, sys, collections
ROOT = _REPO + "/"
S = ROOT + "tau2-bench/data/simulations/"
def schema(domain):
    src = open(ROOT + f"tau2-bench/src/tau2/domains/{domain}/tools.py").read()
    out = {}
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.FunctionDef):
            for d in n.decorator_list:
                if isinstance(d, ast.Call) and getattr(d.func, "id", "") == "is_tool":
                    kind = d.args[0].attr if d.args and isinstance(d.args[0], ast.Attribute) else "?"
                    out[n.name] = (kind, [a.arg for a in n.args.args if a.arg != "self"])
    return out
def strip(n): return (n or "").split(".")[-1]
def norm(v): return json.dumps(v, sort_keys=True).lower().replace(" ", "")
def classify(a, sch):
    spec = a.get("content")
    if isinstance(spec, str):
        try: spec = json.loads(spec)
        except Exception: spec = None
    tcs = a.get("tool_calls") or []
    if not isinstance(spec, dict): return "unstructured_order"
    want0 = strip(spec.get("tool"))
    if not tcs: return "valid_name_no_call" if want0 in sch else "invalid_name_refused"
    want, wargs = strip(spec.get("tool")), spec.get("arguments") if isinstance(spec.get("arguments"), dict) else {}
    got, gargs = strip(tcs[0]["name"]), tcs[0].get("arguments") or {}
    if want not in sch:
        if got in sch and sch[got][0] == "WRITE": return "invalid_name_mapped_to_write"
        return "invalid_name_diverted"
    if got != want:
        return "valid_name_tool_changed_write" if got in sch and sch[got][0] == "WRITE" else "valid_name_diverted"
    keys = set(sch[want][1])
    shared = [k for k in keys if k in wargs and k in gargs]
    if any(norm(wargs[k]) != norm(gargs[k]) for k in shared): return "value_changed"
    extra = [k for k in wargs if k not in keys]
    missing = [k for k in gargs if k not in wargs]
    if extra or missing: return "schema_keys_corrected"
    return "as_issued"
def audit(run, domain):
    sch = schema(domain)
    sims = json.load(open(S + run + "/results.json"))["simulations"]
    c = collections.Counter(); ep = []
    for si, s in enumerate(sims):
        seen = set(); cats = []
        for m in s["messages"]:
            ma = (m.get("raw_data") or {}).get("transfer_testing_multi_agent")
            if not ma: continue
            for a in ma.get("assignments") or []:
                if a.get("kind") != "write": continue
                k = (json.dumps(a.get("content"), sort_keys=True), json.dumps(a.get("tool_calls"), sort_keys=True))
                if k in seen: continue
                seen.add(k); cat = classify(a, sch); c[cat] += 1; cats.append(cat)
        r = (s.get("reward_info") or {}).get("reward", 0) or 0
        ep.append((s["task_id"], r, cats))
    return c, ep
if __name__ == "__main__":
    res = {}
    for run in sys.argv[1:]:
        dom = run.split("-")[1]
        c, ep = audit(run, dom)
        res[run] = dict(counts=c, episodes=ep)
        n = sum(c.values()); print(run, n, dict(c.most_common()), flush=True)
    json.dump(res, open(ROOT + "results/secondary-2026-09-26/orders.json", "w"))
