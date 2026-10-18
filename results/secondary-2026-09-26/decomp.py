"""Per-cell loss decomposition, H7 utilisation, spend ratio, cost, per-task counts. Exploratory/secondary; reads results.json only."""
import os as _os, sys as _sys
_REPO = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
_HERE = _os.path.dirname(_os.path.abspath(__file__))
import json, os, sys, random, statistics, collections
sys.path.insert(0, _HERE)
import orders
ROOT = _REPO + "/"; sys.path.insert(0, ROOT)
from h1_extract import cells
TERM, BUD, MA = "transfer_testing_termination", "transfer_testing_completion_budget", "transfer_testing_multi_agent"
BAD = {"invalid_name_refused", "invalid_name_diverted", "valid_name_diverted", "valid_name_no_call"}
def rw(x): return (x.get("reward_info") or {}).get("reward", 0) or 0
def tok(x): return sum((q.get("usage") or {}).get("completion_tokens", 0) or 0 for q in x["messages"] if q["role"] == "assistant")
def cost(x): return (x.get("agent_cost") or 0), (x.get("user_cost") or 0)
def ep_info(s, sch):
    label = "normal"; spent = limit = None; seen = set(); bad = 0; nord = 0
    for m in s["messages"]:
        if m["role"] != "assistant": continue
        rd = m.get("raw_data") or {}
        if TERM in rd: label = rd[TERM]
        b = rd.get(BUD) or {}; spent, limit = b.get("spent", spent), b.get("limit", limit)
        ma = rd.get(MA)
        if not ma: continue
        for a in ma.get("assignments") or []:
            if a.get("kind") != "write": continue
            k = (json.dumps(a.get("content"), sort_keys=True), json.dumps(a.get("tool_calls"), sort_keys=True))
            if k in seen: continue
            seen.add(k); nord += 1; bad += orders.classify(a, sch) in BAD
    return dict(exh=label == "budget_exhausted", util=(spent / limit) if (spent is not None and limit) else None, bad=bad, orders=nord)
def boot_tasks(per_task, B=2000, seed=300):
    ts = sorted(per_task); random.seed(seed); out = []
    for _ in range(B):
        smp = random.choices(ts, k=len(ts)); out.append(sum(per_task[t] for t in smp) / len(ts))
    out.sort(); return out[int(0.025 * B)], out[int(0.975 * B) - 1]
res = []
for fam, model, tier, d, s1p, m1p in cells():
    sch = orders.schema(d)
    S1 = json.load(open(s1p))["simulations"]; M1 = json.load(open(m1p))["simulations"]
    s1t = collections.defaultdict(list)
    for x in S1: s1t[x["task_id"]].append(rw(x))
    s1m = {t: statistics.mean(v) for t, v in s1t.items()}
    N = len(M1); ntask = len(s1m)
    classes = ["EX_BAD", "EX_OK", "FIN_BAD", "FIN_OK"]
    contrib = {c: collections.defaultdict(float) for c in classes}; cnt = collections.Counter(); passes = collections.Counter(); s1on = collections.defaultdict(float)
    m1t = collections.defaultdict(list); utils = []; ntr = collections.Counter(x["task_id"] for x in M1)
    for x in M1:
        e = ep_info(x, sch); c = ("EX_" if e["exh"] else "FIN_") + ("BAD" if e["bad"] else "OK")
        t = x["task_id"]; dlt = rw(x) - s1m[t]
        for cc in classes: contrib[cc][t] += (dlt if cc == c else 0) / ntr[t]
        cnt[c] += 1; passes[c] += rw(x); s1on[c] += s1m[t]; m1t[t].append(rw(x))
        if e["util"] is not None: utils.append(e["util"])
    gain_t = {t: statistics.mean(m1t[t]) - s1m[t] for t in s1m}
    row = dict(family=fam, model=model, domain=d, S1=statistics.mean(s1m.values()), M1=statistics.mean(rw(x) for x in M1),
               gain=statistics.mean(gain_t.values()), gain_ci=boot_tasks(gain_t),
               util_median=statistics.median(utils), exhausted=sum(1 for c in cnt for _ in range(cnt[c]) if c.startswith("EX")) / N,
               tok_S1=statistics.mean(tok(x) for x in S1), tok_M1=statistics.mean(tok(x) for x in M1),
               cost_S1=[sum(cost(x)[0] for x in S1), sum(cost(x)[1] for x in S1)], cost_M1=[sum(cost(x)[0] for x in M1), sum(cost(x)[1] for x in M1)],
               better=sum(1 for v in gain_t.values() if v > 1e-9), same=sum(1 for v in gain_t.values() if abs(v) <= 1e-9), worse=sum(1 for v in gain_t.values() if v < -1e-9),
               gain_by_task=gain_t, cls={})
    for c in classes:
        per_task = {t: contrib[c][t] / ntask * ntask for t in s1m}  # per-task mean contribution
        tot = sum(per_task.values()) / ntask
        row.setdefault("cls_task", {})[c] = per_task
        row["cls"][c] = dict(n=cnt[c], pass_M1=passes[c] / cnt[c] if cnt[c] else None, pass_S1_same_tasks=s1on[c] / cnt[c] if cnt[c] else None,
                             contribution=tot, ci=boot_tasks(per_task))
    row["tok_ratio"] = row["tok_M1"] / row["tok_S1"]
    res.append(row); print(model, d, "done", flush=True)
json.dump(res, open(ROOT + "results/secondary-2026-09-26/decomp.json", "w"), indent=1)
