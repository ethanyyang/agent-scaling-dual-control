#!/usr/bin/env python3
"""H1 confirmatory analysis, as specified in ANALYSIS.md section 1 (and section 1.1).

    python3 h1_analysis.py [results/h1/per_episode.csv]

Input: per_episode.csv from h1_extract.py (13 valid cells x S1 and M1 x 150 episodes).
Output: results/h1/h1_results.json, results/h1/h1_cells.csv, results/h1/h1_report.md.

Specification followed (ANALYSIS.md section 1):
- unit: one (domain x model) cell; gain = M1 - S1 on per-task mean reward, averaged over tasks (= pass^1 difference);
- primary x: leave-one-domain-out capability index = the model's mean S1 pass^1 on the other two domains;
- weighted least squares of gain on x with family and domain fixed effects, weights = 1 / task-cluster variance
  of gain (var of the per-task paired difference / n_tasks), the same estimator as power_sim.py;
- supported if the slope is negative with a 95% CI excluding zero; confirmatory p by permutation of gain across
  cells within family (10,000 permutations; each cell's gain moves with its own variance);
- crossing x0 = -intercept / slope at the mean fixed effect, task-cluster bootstrap CI (tasks resampled within
  each cell, fit and crossing recomputed, 10,000 replicates); readings: transfers if the x0 CI covers 45%,
  shifts if the slope is negative and the x0 CI excludes 45%, no crossing if the slope CI covers zero;
- robustness forms beside the primary: (a) split seeds, x = the cell's S1 pass^1 from trial 0, gain from trials
  1-2; (b) logit gain on the LODO x; (c) relative gain on the LODO x; naive same-episode x reported
  descriptively; family-by-x interaction reported.
Cells without a leave-one-domain-out index (telecom x qwen3.5-4b: its other domains were not run) enter the
split-seed and naive forms only. Seed 300 throughout.
"""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

try:
    from scipy import stats as _st

    def t975(dof):
        return float(_st.t.ppf(0.975, dof))
except ImportError:  # pure-Python fallback: invert the Student-t CDF by bisection
    def _betacf(a, b, x, it=300, eps=3e-14):
        qab, qap, qam = a + b, a + 1, a - 1
        c, d = 1.0, 1 - qab * x / qap
        d = 1 / (d if abs(d) > 1e-300 else 1e-300); h = d
        for m in range(1, it + 1):
            m2 = 2 * m
            aa = m * (b - m) * x / ((qam + m2) * (a + m2))
            d = 1 + aa * d; d = 1 / (d if abs(d) > 1e-300 else 1e-300)
            c = 1 + aa / c if abs(c) > 1e-300 else 1e300
            h *= d * c
            aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
            d = 1 + aa * d; d = 1 / (d if abs(d) > 1e-300 else 1e-300)
            c = 1 + aa / c if abs(c) > 1e-300 else 1e300
            de = d * c; h *= de
            if abs(de - 1) < eps:
                break
        return h

    def _ibeta(a, b, x):
        if x <= 0 or x >= 1:
            return 0.0 if x <= 0 else 1.0
        lb = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
        if x < (a + 1) / (a + b + 2):
            return math.exp(lb) * _betacf(a, b, x) / a
        return 1 - math.exp(lb) * _betacf(b, a, 1 - x) / b

    def _tcdf(t, dof):
        p = 0.5 * _ibeta(dof / 2, 0.5, dof / (dof + t * t))
        return 1 - p if t > 0 else p

    def t975(dof):
        lo, hi = 0.0, 100.0
        for _ in range(200):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if _tcdf(mid, dof) < 0.975 else (lo, mid)
        return (lo + hi) / 2

SEED = 300
N_PERM = 10_000
N_BOOT = 10_000
N_BOOT_VAR = 2_000
DOMAINS = ["airline", "retail", "telecom"]
THRESH = 0.45


# ---------------------------------------------------------------- data
def load(path):
    per = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))  # (model, domain) -> cond -> task -> [(trial, r)]
    meta = {}
    for r in csv.DictReader(open(path)):
        key = (r["model"], r["domain"])
        meta[key] = (r["family"], r["tier"])
        per[key][r["condition"]][r["task_id"]].append((int(r["trial"]), float(r["reward"])))
    cells = {}
    for key, conds in per.items():
        tasks = sorted(set(conds["S1"]) & set(conds["M1"]))
        assert len(tasks) == len(conds["S1"]) == len(conds["M1"]), key
        def mat(c):
            m = np.zeros((len(tasks), 3))
            for i, t in enumerate(tasks):
                for trial, rew in conds[c][t]:
                    m[i, trial] = rew
            return m
        cells[key] = dict(family=meta[key][0], tier=meta[key][1], model=key[0], domain=key[1],
                          tasks=tasks, S1=mat("S1"), M1=mat("M1"))
    return cells


def cell_stats(s1, m1):
    """s1, m1: tasks x trials matrices. Returns S1 pass^1, M1 pass^1, gain, task-cluster var of gain."""
    s = s1.mean(1); m = m1.mean(1); d = m - s
    n = len(d)
    return s.mean(), m.mean(), d.mean(), max(d.var(ddof=1) / n, 1e-6)


# ---------------------------------------------------------------- estimator (power_sim.wls_slope plus domain FE)
def design(x, fam, dom, fam_levels, interaction=False):
    cols = [np.ones_like(x), x]
    cols += [(fam == f).astype(float) for f in fam_levels[1:]]
    cols += [(dom == d).astype(float) for d in DOMAINS[1:] if (dom == d).any()]
    if interaction:
        cols += [x * (fam == f).astype(float) for f in fam_levels[1:]]
    return np.column_stack(cols)


def wls(X, y, w):
    XtW = X.T * w
    A = XtW @ X
    beta = np.linalg.solve(A, XtW @ y)
    resid = y - X @ beta
    dof = len(y) - X.shape[1]
    sigma2 = (w * resid ** 2).sum() / dof
    cov = sigma2 * np.linalg.inv(A)
    return beta, cov, dof


def mean_effect_intercept(beta, fam_levels, dom_present):
    """Intercept at the mean fixed effect: average over family levels and domain levels (baselines = 0)."""
    nf = len(fam_levels) - 1
    fam_eff = np.concatenate([[0.0], beta[2:2 + nf]])
    dom_eff = np.concatenate([[0.0], beta[2 + nf:2 + nf + len(dom_present) - 1]])
    return beta[0] + fam_eff.mean() + dom_eff.mean()


def fit(x, y, v, fam, dom, fam_levels, interaction=False):
    X = design(x, fam, dom, fam_levels, interaction)
    beta, cov, dof = wls(X, y, 1.0 / v)
    t = t975(dof)
    se = math.sqrt(cov[1, 1])
    dom_present = [d for d in DOMAINS if (dom == d).any()]
    a_bar = mean_effect_intercept(beta, fam_levels, dom_present)
    return dict(beta=beta, cov=cov, dof=dof, slope=beta[1], se=se, lo=beta[1] - t * se, hi=beta[1] + t * se,
                a_bar=a_bar, x0=(-a_bar / beta[1]) if beta[1] != 0 else float("nan"), tcrit=t)


def permutation_p(x, y, v, fam, dom, fam_levels, rng, n=N_PERM):
    obs = fit(x, y, v, fam, dom, fam_levels)["slope"]
    idx_by_fam = {f: np.where(fam == f)[0] for f in fam_levels}
    ge_two = le_one = 0
    for _ in range(n):
        perm = np.arange(len(y))
        for f, idx in idx_by_fam.items():
            perm[idx] = rng.permutation(idx)
        b = fit(x, y[perm], v[perm], fam, dom, fam_levels)["slope"]
        ge_two += abs(b) >= abs(obs) - 1e-12
        le_one += b <= obs + 1e-12
    return (1 + ge_two) / (1 + n), (1 + le_one) / (1 + n)


# ---------------------------------------------------------------- forms
def lodo_x(s1_by_cell, keys):
    xs = []
    for (m, d) in keys:
        others = [s1_by_cell[(m, d2)] for d2 in DOMAINS if d2 != d and (m, d2) in s1_by_cell]
        xs.append(np.mean(others) if len(others) == 2 else np.nan)
    return np.array(xs)


def boot_var(fn, s1, m1, rng, n=N_BOOT_VAR):
    k = len(s1)
    vals = []
    for _ in range(n):
        i = rng.integers(0, k, k)
        vals.append(fn(s1[i], m1[i]))
    return float(np.var(vals, ddof=1))


def logit(p, eps=0.5 / 150):
    p = min(max(p, eps), 1 - eps)
    return math.log(p / (1 - p))


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("results/h1/per_episode.csv")
    outdir = path.parent
    cells = load(path)
    rng = np.random.default_rng(SEED)

    keys_all = sorted(cells, key=lambda k: (cells[k]["family"], cells[k]["tier"], k[0], DOMAINS.index(k[1])))
    base = {}
    for k in keys_all:
        c = cells[k]
        s, m, g, v = cell_stats(c["S1"], c["M1"])
        base[k] = dict(s1=s, m1=m, gain=g, var=v)
    s1_by_cell = {k: base[k]["s1"] for k in keys_all}
    xl = lodo_x(s1_by_cell, keys_all)
    keys_p = [k for k, x in zip(keys_all, xl) if not np.isnan(x)]          # primary: cells with a LODO index
    fam_levels = sorted({cells[k]["family"] for k in keys_p}, key=lambda f: ["OpenAI", "Google", "Qwen"].index(f))

    def arrays(keys, xs, ys, vs):
        fam = np.array([cells[k]["family"] for k in keys]); dom = np.array([k[1] for k in keys])
        return np.array(xs, float), np.array(ys, float), np.array(vs, float), fam, dom

    res = {"spec": "ANALYSIS.md section 1; see module docstring", "seed": SEED, "n_perm": N_PERM, "n_boot": N_BOOT,
           "cells_primary": [f"{d} x {m}" for m, d in keys_p]}

    # ---- primary
    x = np.array([xl[keys_all.index(k)] for k in keys_p]); y = np.array([base[k]["gain"] for k in keys_p])
    v = np.array([base[k]["var"] for k in keys_p])
    X_, Y_, V_, fam, dom = arrays(keys_p, x, y, v)
    prim = fit(X_, Y_, V_, fam, dom, fam_levels)
    p_two, p_one = permutation_p(X_, Y_, V_, fam, dom, fam_levels, rng)

    # ---- task-cluster bootstrap of the slope and crossing
    rngb = np.random.default_rng(SEED)
    boot_slopes, boot_x0, boot_line = [], [], []
    grid = np.linspace(0.30, 1.0, 71)
    for _ in range(N_BOOT):
        bb = {}
        for k in keys_all:
            c = cells[k]; n = len(c["tasks"]); i = rngb.integers(0, n, n)
            bb[k] = cell_stats(c["S1"][i], c["M1"][i])
        s1b = {k: bb[k][0] for k in keys_all}
        xb = lodo_x(s1b, keys_p)
        yb = np.array([bb[k][2] for k in keys_p]); vb = np.array([bb[k][3] for k in keys_p])
        f = fit(xb, yb, vb, fam, dom, fam_levels)
        boot_slopes.append(f["slope"]); boot_x0.append(f["x0"])
        boot_line.append(f["a_bar"] + f["slope"] * grid)
    boot_slopes = np.array(boot_slopes); boot_x0 = np.array(boot_x0); boot_line = np.array(boot_line)
    x0_lo, x0_hi = np.percentile(boot_x0, [2.5, 97.5])
    sl_lo_b, sl_hi_b = np.percentile(boot_slopes, [2.5, 97.5])
    line_lo, line_hi = np.percentile(boot_line, [2.5, 97.5], axis=0)

    supported = prim["hi"] < 0 and p_two < 0.05
    if prim["lo"] <= 0 <= prim["hi"]:
        reading = "no crossing (slope CI covers zero)"
    elif prim["slope"] < 0 and x0_lo <= THRESH <= x0_hi:
        reading = "transfers (x0 CI covers 45%)"
    elif prim["slope"] < 0:
        reading = "shifts " + ("below" if x0_hi < THRESH else "above") + " 45% (x0 CI excludes 45%)"
    else:
        reading = "positive slope (outside the pre-specified readings)"
    res["primary"] = dict(n_cells=len(keys_p), dof=prim["dof"], slope=prim["slope"], se=prim["se"],
                          ci=[prim["lo"], prim["hi"]], ci_boot=[float(sl_lo_b), float(sl_hi_b)],
                          perm_p_two_sided=p_two, perm_p_one_sided_negative=p_one,
                          intercept_at_mean_effect=prim["a_bar"], x0=prim["x0"], x0_ci_boot=[float(x0_lo), float(x0_hi)],
                          h1_supported=bool(supported), crossing_reading=reading,
                          coefficients=dict(zip(["intercept", "x"] + [f"family_{f}" for f in fam_levels[1:]] +
                                                [f"domain_{d}" for d in DOMAINS[1:]], map(float, prim["beta"]))))

    # ---- family-by-x interaction
    fi = fit(X_, Y_, V_, fam, dom, fam_levels, interaction=True)
    ti = t975(fi["dof"]); b_int = fi["beta"][-1]; se_int = math.sqrt(fi["cov"][-1, -1])
    res["family_by_x"] = dict(term=f"x*family_{fam_levels[1]}", coef=float(b_int), ci=[b_int - ti * se_int, b_int + ti * se_int],
                              dof=fi["dof"], slope_reference_family=float(fi["beta"][1]),
                              slope_other_family=float(fi["beta"][1] + b_int))

    # ---- robustness forms
    rngv = np.random.default_rng(SEED)
    forms = {}
    # (a) split seeds, x from trial 0, gain from trials 1-2
    for label, keys in (("split_seed_12", keys_p), ("split_seed_13", keys_all)):
        xs, ys, vs = [], [], []
        for k in keys:
            c = cells[k]
            xs.append(c["S1"][:, 0].mean())
            _, _, g, vv = cell_stats(c["S1"][:, 1:], c["M1"][:, 1:])
            ys.append(g); vs.append(vv)
        a = arrays(keys, xs, ys, vs); fl = sorted({cells[k]["family"] for k in keys}, key=lambda f: ["OpenAI", "Google", "Qwen"].index(f))
        f = fit(*a, fl)
        forms[label] = dict(n=len(keys), slope=f["slope"], ci=[f["lo"], f["hi"]], dof=f["dof"])
    # (b) logit gain, (c) relative gain, both on the LODO x
    def g_logit(s1, m1): return logit(m1.mean()) - logit(s1.mean())
    def g_rel(s1, m1): return (m1.mean() - s1.mean()) / max(s1.mean(), 1e-6)
    for label, fn in (("logit_gain", g_logit), ("relative_gain", g_rel)):
        ys = [fn(cells[k]["S1"], cells[k]["M1"]) for k in keys_p]
        vs = [boot_var(fn, cells[k]["S1"], cells[k]["M1"], rngv) for k in keys_p]
        f = fit(X_, np.array(ys), np.array(vs), fam, dom, fam_levels)
        forms[label] = dict(n=len(keys_p), slope=f["slope"], ci=[f["lo"], f["hi"]], dof=f["dof"],
                            note="slope in logit units per unit of x" if label == "logit_gain" else "slope in relative-gain units per unit of x")
    # naive, descriptive only
    for label, keys in (("naive_12", keys_p), ("naive_13", keys_all)):
        a = arrays(keys, [base[k]["s1"] for k in keys], [base[k]["gain"] for k in keys], [base[k]["var"] for k in keys])
        fl = sorted({cells[k]["family"] for k in keys}, key=lambda f: ["OpenAI", "Google", "Qwen"].index(f))
        f = fit(*a, fl)
        forms[label] = dict(n=len(keys), slope=f["slope"], ci=[f["lo"], f["hi"]], dof=f["dof"],
                            note="descriptive only: x shares episodes with gain (19 to 28% false-positive rate in power_sim.py)")
    res["robustness"] = forms

    # ---- per-cell table
    rows = []
    for k in keys_all:
        c = cells[k]; b = base[k]
        rows.append(dict(family=c["family"], model=k[0], tier=c["tier"], domain=k[1], s1=b["s1"], m1=b["m1"],
                         gain=b["gain"], se=math.sqrt(b["var"]), lodo_x=float(xl[keys_all.index(k)]),
                         in_primary=k in keys_p))
    res["cells"] = rows
    with open(outdir / "h1_cells.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    np.savez(outdir / "h1_boot.npz", grid=grid, line_lo=line_lo, line_hi=line_hi, boot_slopes=boot_slopes, boot_x0=boot_x0)
    json.dump(res, open(outdir / "h1_results.json", "w"), indent=2, default=float)

    # ---- report
    P = res["primary"]
    L = []
    L.append("# H1 results (ANALYSIS.md section 1)\n")
    L.append(f"Primary fit: {P['n_cells']} cells, WLS with family and domain fixed effects, inverse task-cluster variance weights, dof {P['dof']}.\n")
    L.append(f"- slope b = {P['slope']:+.3f}, 95% CI [{P['ci'][0]:+.3f}, {P['ci'][1]:+.3f}] (t); bootstrap CI [{P['ci_boot'][0]:+.3f}, {P['ci_boot'][1]:+.3f}]")
    L.append(f"- permutation p (within family, {N_PERM}): two-sided {P['perm_p_two_sided']:.4f}; one-sided (negative) {P['perm_p_one_sided_negative']:.4f}")
    L.append(f"- H1 supported (slope < 0, CI excludes 0, permutation p < 0.05): {P['h1_supported']}")
    L.append(f"- crossing x0 = {P['x0']:.3f}, task-cluster bootstrap 95% CI [{P['x0_ci_boot'][0]:.3f}, {P['x0_ci_boot'][1]:.3f}]; reading: {P['crossing_reading']}")
    L.append(f"- intercept at the mean fixed effect {P['intercept_at_mean_effect']:+.3f}; coefficients {json.dumps({k: round(v, 4) for k, v in P['coefficients'].items()})}")
    FI = res["family_by_x"]
    L.append(f"\nFamily-by-x interaction ({FI['term']}): {FI['coef']:+.3f}, 95% CI [{FI['ci'][0]:+.3f}, {FI['ci'][1]:+.3f}], dof {FI['dof']}; slope OpenAI {FI['slope_reference_family']:+.3f}, Google {FI['slope_other_family']:+.3f}\n")
    L.append("Robustness forms:\n")
    for k2, f in forms.items():
        L.append(f"- {k2} (n={f['n']}, dof {f['dof']}): slope {f['slope']:+.3f}, 95% CI [{f['ci'][0]:+.3f}, {f['ci'][1]:+.3f}]" + (f"  ({f['note']})" if 'note' in f else ""))
    L.append("\nCells (pass^1 as fractions):\n")
    L.append("| family | model | domain | S1 | M1 | gain | SE | LODO x | primary |")
    L.append("|---|---|---|---:|---:|---:|---:|---:|---|")
    for r in rows:
        L.append(f"| {r['family']} | {r['model']} | {r['domain']} | {r['s1']:.3f} | {r['m1']:.3f} | {r['gain']:+.3f} | {r['se']:.3f} | {r['lodo_x']:.3f} | {r['in_primary']} |")
    (outdir / "h1_report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
