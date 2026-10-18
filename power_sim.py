#!/usr/bin/env python3
"""Pre-registered power simulation for ANALYSIS.md H1 (slope) and H4a (blind share).

No API calls. Inputs are measured quantities only:
  * task-level heterogeneity (beta-binomial concentration) fitted to the pilot and
    gate per_episode.csv files (50 tasks x 3 trials each);
  * the planned design: 27 cells (9 models x 3 domains), N tasks, K seeds;
  * assumed cell baselines (documented, adjustable; used only to place cells on
    the x-axis).

Two "worlds" are simulated per scenario:
  * H1 true: gain(baseline) = b * (baseline - 0.45), b < 0
  * H1 null: b = 0
Each world is simulated R times; the pre-registered analysis (inverse-variance
weighted least squares of gain on baseline with family dummies) is run on each
fake dataset; power = fraction of worlds in which the slope's 95% CI excludes
zero on the negative side. Also reported: false-positive rate under the null,
the per-cell sign-match accuracy distribution (secondary), a replica of Kim et
al.'s 16-cell / n=20 / 1-run validation, and H4a power.

Usage: python3 power_sim.py [--reps 500] [--seed 1]
"""
from __future__ import annotations
import argparse, csv, collections, math, json
import numpy as np

# ----------------------------------------------------------------------------
# 1. Fit task heterogeneity (beta-binomial concentration kappa) from real runs
# ----------------------------------------------------------------------------
def load_counts(path, trials=3):
    rows = list(csv.DictReader(open(path)))
    per = collections.defaultdict(float)
    for r in rows:
        per[r["task_id"]] += float(r["reward"])
    return np.array([per[k] for k in per]), trials

def betabinom_loglik(counts, n, mean, kappa):
    a, b = mean * kappa, (1 - mean) * kappa
    from math import lgamma
    ll = 0.0
    for k in counts:
        ll += (lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1)
               + lgamma(k + a) + lgamma(n - k + b) - lgamma(n + a + b)
               + lgamma(a + b) - lgamma(a) - lgamma(b))
    return ll

def fit_kappa(counts, n):
    mean = counts.mean() / n
    grid = np.exp(np.linspace(np.log(0.2), np.log(50), 200))
    lls = [betabinom_loglik(counts, n, mean, k) for k in grid]
    return mean, float(grid[int(np.argmax(lls))])

# ----------------------------------------------------------------------------
# 2. Design: 27 cells with assumed baselines (x-axis placement only)
# ----------------------------------------------------------------------------
FAMILIES = {
    "openai": ["gpt-5.4-nano", "gpt-5.4-mini", "gpt-5.4"],
    "google": ["gemini-3.1-flash-lite", "gemini-3-flash", "gemini-3.1-pro"],
    "qwen":   ["qwen3.5-4b", "qwen3.5-9b", "qwen3.5-27b"],
}
# assumed S1 baselines (airline, retail, telecom). Documented guesses; only the
# spread matters for power. gemini-3-flash airline is measured (0.807).
BASELINES = {
    "qwen3.5-4b":            (0.22, 0.35, 0.30),
    "qwen3.5-9b":            (0.32, 0.48, 0.42),
    "qwen3.5-27b":           (0.42, 0.60, 0.55),
    "gpt-5.4-nano":          (0.35, 0.50, 0.45),
    "gpt-5.4-mini":          (0.55, 0.70, 0.72),
    "gpt-5.4":               (0.78, 0.82, 0.90),
    "gemini-3.1-flash-lite": (0.40, 0.55, 0.50),
    "gemini-3-flash":        (0.807, 0.77, 0.91),
    "gemini-3.1-pro":        (0.80, 0.76, 0.91),
}
DOMAINS = ["airline", "retail", "telecom"]

def cells(families=FAMILIES):
    out = []
    for fam, models in families.items():
        for m in models:
            for d, p in zip(DOMAINS, BASELINES[m]):
                out.append((fam, m, d, p))
    return out

# ----------------------------------------------------------------------------
# 3. Simulate one fake dataset and run the pre-registered analysis
# ----------------------------------------------------------------------------
def simulate_cell(rng, p, gain_true, n_tasks, k_seeds, kappa, arch_sd=0.05):
    a, b = p * kappa, (1 - p) * kappa
    task_p = rng.beta(a, b, size=n_tasks)                      # S1 per-task pass prob
    m1_p = np.clip(task_p + gain_true + rng.normal(0, arch_sd, n_tasks), 0, 1)
    s1 = rng.binomial(k_seeds, task_p) / k_seeds               # per-task mean reward
    m1 = rng.binomial(k_seeds, m1_p) / k_seeds
    d = m1 - s1
    gain_hat = d.mean()
    var_hat = d.var(ddof=1) / n_tasks                          # task-cluster variance
    base_hat = s1.mean()
    return base_hat, gain_hat, max(var_hat, 1e-6)

def wls_slope(x, y, w, fam_idx, n_fam):
    # design: intercept, x, family dummies (drop first)
    X = np.column_stack([np.ones_like(x), x] + [(fam_idx == j).astype(float) for j in range(1, n_fam)])
    W = np.diag(w)
    XtW = X.T @ W
    beta = np.linalg.solve(XtW @ X, XtW @ y)
    resid = y - X @ beta
    dof = len(y) - X.shape[1]
    sigma2 = (w * resid**2).sum() / dof
    cov = sigma2 * np.linalg.inv(XtW @ X)
    se = math.sqrt(cov[1, 1])
    # t critical
    from statistics import NormalDist
    tcrit = 2.0 if dof > 25 else {10:2.23, 15:2.13, 20:2.09}.get(dof, 2.1)
    return beta[1], se, tcrit, dof

def run_world(rng, b_slope, n_tasks, k_seeds, kappa, families, a_int=0.0, xmode="naive"):
    """xmode: 'naive' = x is this cell's S1 baseline (shares noise with gain);
              'loo'   = x is the model's mean S1 baseline on the OTHER two domains;
              'split' = x from seed 0 of S1, gain from remaining seeds vs M1."""
    cs = cells(families)
    fam_names = list(families.keys())
    per = {}
    for fam, m, d, p in cs:
        gain_true = a_int + b_slope * (p - 0.45)
        a, b = p * kappa, (1 - p) * kappa
        task_p = rng.beta(a, b, size=n_tasks)
        m1_p = np.clip(task_p + gain_true + rng.normal(0, 0.05, n_tasks), 0, 1)
        s1_all = rng.binomial(1, task_p[:, None].repeat(k_seeds, 1))   # tasks x seeds
        m1_all = rng.binomial(1, m1_p[:, None].repeat(k_seeds, 1))
        if xmode == "split" and k_seeds >= 2:
            s1_x = s1_all[:, 0].mean()
            s1 = s1_all[:, 1:].mean(1); m1 = m1_all[:, 1:].mean(1)
        else:
            s1_x = s1_all.mean()
            s1 = s1_all.mean(1); m1 = m1_all.mean(1)
        dd = m1 - s1
        per[(m, d)] = dict(fam=fam, base=s1_all.mean(), x=s1_x, gain=dd.mean(),
                           var=max(dd.var(ddof=1) / n_tasks, 1e-6))
    xs, ys, ws, fi, signs = [], [], [], [], []
    informative = 0
    for (m, d), r in per.items():
        if xmode == "loo":
            others = [per[(m, d2)]["base"] for d2 in DOMAINS if d2 != d]
            x = float(np.mean(others))
        else:
            x = r["x"]
        xs.append(x); ys.append(r["gain"]); ws.append(1 / r["var"]); fi.append(fam_names.index(r["fam"]))
        signs.append((r["gain"] > 0) == (r["base"] < 0.45))
        if abs(r["gain"]) > 1.96 * math.sqrt(r["var"]): informative += 1
    slope, se, tcrit, dof = wls_slope(np.array(xs), np.array(ys), np.array(ws), np.array(fi), len(fam_names))
    reject_neg = (slope + tcrit * se) < 0
    return reject_neg, np.mean(signs), informative / len(cs)

# ----------------------------------------------------------------------------
# 4. H4a: blind share FP/(FP+WW) vs baseline
# ----------------------------------------------------------------------------
def run_h4a(rng, n_tasks, k_seeds, kappa, families, true_effect=True):
    """H4a as RATES: f_ww = WW / failing episodes declines with baseline (anchors .41 @ .40, .07 @ .81);
    f_fp = FP / passing episodes does not decline (~.12). The raw share FP/(FP+WW) is NOT used:
    it rises mechanically with the pass rate even when both rates are constant."""
    xs, ys, ws = [], [], []
    for fam, m, d, p in cells(families):
        n_ep = n_tasks * k_seeds
        a, b = p * kappa, (1 - p) * kappa
        task_p = rng.beta(a, b, size=n_tasks)
        passes = int(rng.binomial(k_seeds, task_p).sum()); fails = n_ep - passes
        if fails < 5: continue
        f_ww = (0.41 + (p - 0.40) * (0.07 - 0.41) / (0.81 - 0.40)) if true_effect else 0.25
        f_ww = float(np.clip(f_ww, 0.02, 0.6))
        ww = rng.binomial(fails, f_ww)
        xs.append(passes / n_ep); ys.append(ww / fails); ws.append(fails)
    x, y, w = map(np.array, (xs, ys, ws))
    X = np.column_stack([np.ones_like(x), x]); W = np.diag(w)
    beta = np.linalg.solve(X.T @ W @ X, X.T @ W @ y)
    resid = y - X @ beta; dof = len(y) - 2
    sigma2 = (w * resid**2).sum() / dof
    se = math.sqrt((sigma2 * np.linalg.inv(X.T @ W @ X))[1, 1])
    return (beta[1] + 2.0 * se) < 0    # negative slope: wrongful-write share of failures declines

# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=500)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)

    pilot = "results/exploratory-airline-sas-gpt41mini-full-3trials-seed300/per_episode.csv"
    gate = "results/gate-airline-sas-gemini3flash-high-gpt52low-3trials-seed300/per_episode.csv"
    kappas = {}
    for name, path in [("pilot", pilot), ("gate", gate)]:
        try:
            c, n = load_counts(path)
            mean, kappa = fit_kappa(c, n)
            kappas[name] = (mean, kappa)
        except Exception as e:
            kappas[name] = None
    print("Task-heterogeneity fit (beta-binomial):")
    for k, v in kappas.items():
        print(f"  {k}: mean={v[0]:.3f} kappa={v[1]:.2f}" if v else f"  {k}: unavailable")
    kappa = float(np.mean([v[1] for v in kappas.values() if v])) if any(kappas.values()) else 1.0
    print(f"  using kappa={kappa:.2f} (smaller = more task heterogeneity)\n")

    scenarios = [
        ("27 cells, 50 tasks, 3 seeds (pre-registered)", FAMILIES, 50, 3),
        ("27 cells, 50 tasks, 5 seeds", FAMILIES, 50, 5),
        ("18 cells (drop qwen), 50 tasks, 3 seeds", {k: v for k, v in FAMILIES.items() if k != "qwen"}, 50, 3),
        ("27 cells, 114-task full splits, 3 seeds", FAMILIES, 114, 3),
    ]
    slopes = [0.0, -0.10, -0.20, -0.30, -0.40]
    for xmode in ["naive", "split", "loo"]:
      print(f"H1 slope test, x-axis = {xmode}: power (fraction of worlds where slope CI excludes 0, negative side)")
      print(f"  {'scenario':50s} " + " ".join(f"b={b:+.2f}" for b in slopes) + "   sign-acc@b=-0.3  informative-cells@b=-0.3")
      R = args.reps
      for label, fams, n_tasks, k in scenarios:
        row = []
        sign_acc = inf = None
        for b in slopes:
            res = [run_world(rng, b, n_tasks, k, kappa, fams, xmode=xmode) for _ in range(R)]
            row.append(np.mean([r[0] for r in res]))
            if b == -0.30:
                sign_acc = np.mean([r[1] for r in res]); inf = np.mean([r[2] for r in res])
        print(f"  {label:50s} " + " ".join(f"{p:6.2f} " for p in row) + f"      {sign_acc:5.2f}            {inf:5.2f}")
      print("  (column b=+0.00 is the false-positive rate; target <= 0.05)\n")

    # Kim replica: 16 cells, 20 tasks, 1 run, baselines spread 0.15-0.85
    print("Replica of Kim et al. validation (16 cells, 20 tasks, 1 run), true b=-0.30:")
    accs = []
    for _ in range(R):
        ok = []
        for i in range(16):
            p = rng.uniform(0.15, 0.85)
            g = -0.30 * (p - 0.45)
            a, bb = p * kappa, (1 - p) * kappa
            tp = rng.beta(a, bb, 20); mp = np.clip(tp + g + rng.normal(0, 0.05, 20), 0, 1)
            s1 = rng.binomial(1, tp).mean(); m1 = rng.binomial(1, mp).mean()
            ok.append(((m1 - s1) > 0) == (s1 < 0.45))
        accs.append(np.mean(ok))
    accs = np.array(accs)
    print(f"  expected sign-match accuracy = {accs.mean():.2f}; P(accuracy >= 15/16) = {(accs >= 15/16).mean():.2f}")
    print("  under NULL (b=0):", end=" ")
    accs0 = []
    for _ in range(R):
        ok = []
        for i in range(16):
            p = rng.uniform(0.15, 0.85)
            a, bb = p * kappa, (1 - p) * kappa
            tp = rng.beta(a, bb, 20); mp = np.clip(tp + rng.normal(0, 0.05, 20), 0, 1)
            s1 = rng.binomial(1, tp).mean(); m1 = rng.binomial(1, mp).mean()
            ok.append(((m1 - s1) > 0) == (s1 < 0.45))
        accs0.append(np.mean(ok))
    accs0 = np.array(accs0)
    print(f"expected accuracy = {accs0.mean():.2f}; P(>= 15/16) = {(accs0 >= 15/16).mean():.2f}\n")

    print("H4a wrongful-write-rate test (WW/failures vs baseline; 27 cells, 50 tasks, 3 seeds):")
    pw = np.mean([run_h4a(rng, 50, 3, kappa, FAMILIES, True) for _ in range(R)])
    fp = np.mean([run_h4a(rng, 50, 3, kappa, FAMILIES, False) for _ in range(R)])
    print(f"  power (effect as in §0 anchors) = {pw:.2f}; false-positive rate = {fp:.2f}")

if __name__ == "__main__":
    main()
