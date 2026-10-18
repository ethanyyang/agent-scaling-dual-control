"""H6 (ANALYSIS.md 1.2): does the write share of S1 failures predict gain beyond x? gain = a + b1 x + b2 write_share + domain effects,
inverse-variance weights as in H1, permutation p within family (10,000, gain moves with its variance as in h1_analysis.py)."""
import os as _os, sys as _sys
_REPO = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
_HERE = _os.path.dirname(_os.path.abspath(__file__))
import json, os, sys, csv, collections, numpy as np
ROOT = _REPO + "/"; sys.path.insert(0, ROOT)
from h1_extract import cells
from analyze_run import episode_writes, task_requires_write, write_tools_for_domain
def t975(dof):
    from scipy import stats; return float(stats.t.ppf(0.975, dof))
try: t975(7)
except Exception:
    T = {5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228}; t975 = lambda d: T[d]
rows = []
for fam, model, tier, d, s1p, m1p in cells():
    wt = write_tools_for_domain(d)
    S1 = json.load(open(s1p)); M1 = json.load(open(m1p))["simulations"]
    tasks = {t["id"]: t for t in S1["tasks"]}
    fails = ww = wa = 0; s1t = collections.defaultdict(list); m1t = collections.defaultdict(list)
    for s in S1["simulations"]:
        ri = s.get("reward_info") or {}; r = ri.get("reward", 0) or 0; s1t[s["task_id"]].append(r)
        if r >= 1: continue
        fails += 1
        nw = task_requires_write(tasks[s["task_id"]], wt); wr = episode_writes(s, wt)
        if not nw and wr > 0: ww += 1; continue
        if nw and wr > 0:
            dbm = (ri.get("db_check") or {}).get("db_match")
            wmis = any((a.get("tool_type") == "write" and not a.get("action_match")) for a in (ri.get("action_checks") or []))
            if dbm is False or wmis: wa += 1
    for s in M1: m1t[s["task_id"]].append((s.get("reward_info") or {}).get("reward", 0) or 0)
    g = np.array([np.mean(m1t[t]) - np.mean(s1t[t]) for t in sorted(s1t)])
    rows.append(dict(family=fam, model=model, domain=d, s1=np.mean([np.mean(v) for v in s1t.values()]), gain=g.mean(), var=g.var(ddof=1) / len(g),
                     fails=fails, ww=ww, wa=wa, write_share=(ww + wa) / fails if fails else 0.0))
s1 = {(r["model"], r["domain"]): r["s1"] for r in rows}
for r in rows:
    o = [s1.get((r["model"], dd)) for dd in ("airline", "retail", "telecom") if dd != r["domain"]]
    r["x"] = float(np.mean(o)) if all(v is not None for v in o) else None
C = [r for r in rows if r["x"] is not None]
def X_of(C, with_ws=True, fam_fe=False):
    cols = [np.ones(len(C)), [c["x"] for c in C]]
    if with_ws: cols.append([c["write_share"] for c in C])
    if fam_fe: cols.append([c["family"] == "Google" for c in C])
    cols += [[c["domain"] == "retail" for c in C], [c["domain"] == "telecom" for c in C]]
    return np.column_stack(cols).astype(float)
def wls(X, y, w):
    A = (X.T * w) @ X; b = np.linalg.solve(A, (X.T * w) @ y); res = y - X @ b; dof = len(y) - X.shape[1]
    s2 = (w * res ** 2).sum() / dof; return b, np.sqrt(np.diag(s2 * np.linalg.inv(A))), dof
y = np.array([c["gain"] for c in C]); v = np.array([c["var"] for c in C])
out = {}
for name, ws, ff in (("joint", True, False), ("x_only", False, False), ("joint_familyFE", True, True)):
    X = X_of(C, ws, ff); b, se, dof = wls(X, y, 1 / v); t = t975(dof)
    rng = np.random.default_rng(300); idx = {f: [i for i, c in enumerate(C) if c["family"] == f] for f in ("OpenAI", "Google")}
    k = 2 if ws else 1; cnt = 0
    for _ in range(10000):
        perm = np.arange(len(C))
        for f, ii in idx.items(): perm[ii] = np.array(ii)[rng.permutation(len(ii))]
        bp, _, _ = wls(X, y[perm], 1 / v[perm])
        if abs(bp[k]) >= abs(b[k]) - 1e-12: cnt += 1
    out[name] = dict(dof=dof, b_x=[b[1], b[1] - t * se[1], b[1] + t * se[1]],
                     b_ws=([b[2], b[2] - t * se[2], b[2] + t * se[2]] if ws else None), perm_p_two_sided_tested_coef=cnt / 10000)
print(json.dumps(out, indent=1))
for c in sorted(C, key=lambda c: c["write_share"]):
    print(f'{c["model"]:22s} {c["domain"]:8s} x {c["x"]:.3f} fails {c["fails"]:3d} WW {c["ww"]:3d} WA {c["wa"]:3d} share {c["write_share"]:.3f} gain {c["gain"]:+.3f}')
json.dump(dict(fits=out, cells=rows), open(ROOT + "results/secondary-2026-09-26/h6.json", "w"), indent=1, default=float)
