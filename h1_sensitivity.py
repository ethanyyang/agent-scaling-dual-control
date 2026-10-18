#!/usr/bin/env python3
"""H1 diagnostics and the pre-specified sensitivity that adds the three G1-failing qwen3.5-9b cells.

    python3 h1_sensitivity.py results/h1/per_episode.csv results/h1/m1_qwen9b_per_episode.csv

Diagnostics: overdispersion of the primary fit (sigma^2 = weighted residual variance; 1 means the cells scatter
around the line only as much as task sampling allows), per-cell residuals, leave-one-cell-out slopes.
Sensitivity: the 12 primary cells plus airline, retail and telecom x qwen3.5-9b. The 9b S1 per-episode files are
not held (collaborator run), so each 9b gain variance is approximated: airline from the collaborator's paired
task-cluster CI; retail and telecom as var(M1 per-task means)/50 + SE(S1)^2 with SE(S1) from the S1 task-cluster
CI in ANALYSIS.md section 5. This ignores the positive S1-M1 covariance over tasks, so it overstates the variance
and down-weights these cells. Output: results/h1/h1_sensitivity.json and .md next to the input.
"""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import h1_analysis as H  # noqa: E402

S1_9B = {"airline": (0.793, 0.713, 0.867), "retail": (0.760, 0.667, 0.847), "telecom": (0.953, 0.913, 0.987)}  # pass^1, CI (section 5)
AIRLINE_9B_PAIRED = (-0.180, -0.287, -0.067)  # collaborator's paired gain and CI (CHANGELOG 2026-09-25)


def main():
    per_ep = Path(sys.argv[1]); m1_9b = Path(sys.argv[2]); outdir = per_ep.parent
    cells = H.load(per_ep)
    keys_all = sorted(cells, key=lambda k: (cells[k]["family"], cells[k]["tier"], k[0], H.DOMAINS.index(k[1])))
    base = {k: dict(zip(("s1", "m1", "gain", "var"), H.cell_stats(cells[k]["S1"], cells[k]["M1"]))) for k in keys_all}
    s1 = {k: base[k]["s1"] for k in keys_all}
    xl = H.lodo_x(s1, keys_all)
    keys_p = [k for k, x in zip(keys_all, xl) if not np.isnan(x)]
    fam_levels = ["OpenAI", "Google"]
    x = np.array([xl[keys_all.index(k)] for k in keys_p]); y = np.array([base[k]["gain"] for k in keys_p])
    v = np.array([base[k]["var"] for k in keys_p])
    fam = np.array([cells[k]["family"] for k in keys_p]); dom = np.array([k[1] for k in keys_p])

    X = H.design(x, fam, dom, fam_levels); w = 1 / v
    beta, cov, dof = H.wls(X, y, w)
    resid = y - X @ beta
    sigma2 = float((w * resid ** 2).sum() / dof)
    out = {"primary_overdispersion_sigma2": sigma2,
           "primary_residuals": {f"{d} x {m}": float(r) for (m, d), r in zip(keys_p, resid)},
           "unweighted_residual_sd": float(np.sqrt((resid ** 2).sum() / dof)),
           "median_sampling_se": float(np.median(np.sqrt(v)))}
    # leave-one-cell-out slopes
    loo = {}
    for i, (m, d) in enumerate(keys_p):
        keep = np.arange(len(y)) != i
        f = H.fit(x[keep], y[keep], v[keep], fam[keep], dom[keep], fam_levels)
        loo[f"{d} x {m}"] = [f["slope"], f["lo"], f["hi"]]
    out["leave_one_cell_out"] = loo

    # sensitivity with the 9b cells
    m1 = defaultdict(lambda: defaultdict(list))
    for r in csv.DictReader(open(m1_9b)):
        m1[r["domain"]][r["task_id"]].append(float(r["reward"]))
    add_x, add_y, add_v = [], [], []
    for d in H.DOMAINS:
        tm = np.array([np.mean(v_) for v_ in m1[d].values()])
        m1_pass = float(np.mean([r for v_ in m1[d].values() for r in v_]))
        if d == "airline":
            g, lo, hi = AIRLINE_9B_PAIRED; var = ((hi - lo) / (2 * 1.96)) ** 2
        else:
            p, lo, hi = S1_9B[d]; g = m1_pass - p
            var = tm.var(ddof=1) / len(tm) + ((hi - lo) / (2 * 1.96)) ** 2
        others = [S1_9B[d2][0] for d2 in H.DOMAINS if d2 != d]
        add_x.append(np.mean(others)); add_y.append(g); add_v.append(var)
    xs = np.concatenate([x, add_x]); ys = np.concatenate([y, add_y]); vs = np.concatenate([v, add_v])
    fs = np.concatenate([fam, ["Qwen"] * 3]); ds = np.concatenate([dom, H.DOMAINS])
    fl = ["OpenAI", "Google", "Qwen"]
    f = H.fit(xs, ys, vs, fs, ds, fl)
    p_two, p_one = H.permutation_p(xs, ys, vs, fs, ds, fl, np.random.default_rng(H.SEED))
    out["sensitivity_with_9b"] = dict(n=len(ys), dof=f["dof"], slope=f["slope"], ci=[f["lo"], f["hi"]],
                                      perm_p_two_sided=p_two, perm_p_one_sided_negative=p_one, x0=f["x0"],
                                      qwen9b_cells={d: dict(x=float(a), gain=float(b), se=float(math.sqrt(c)))
                                                    for d, a, b, c in zip(H.DOMAINS, add_x, add_y, add_v)})
    json.dump(out, open(outdir / "h1_sensitivity.json", "w"), indent=2)
    L = ["# H1 diagnostics and sensitivity\n",
         f"Primary fit overdispersion sigma^2 = {sigma2:.1f} (1 = cells scatter only as much as task sampling allows).",
         f"Unweighted residual SD {out['unweighted_residual_sd']:.3f} against a median per-cell sampling SE of {out['median_sampling_se']:.3f}.\n",
         "Residuals (gain minus fitted, pass^1 fraction):\n"]
    L += [f"- {k}: {r:+.3f}" for k, r in out["primary_residuals"].items()]
    L += ["\nLeave-one-cell-out slope [95% CI]:\n"]
    L += [f"- without {k}: {s:+.3f} [{lo:+.3f}, {hi:+.3f}]" for k, (s, lo, hi) in loo.items()]
    S = out["sensitivity_with_9b"]
    L += [f"\nSensitivity adding the three qwen3.5-9b cells (n = {S['n']}, dof {S['dof']}): slope {S['slope']:+.3f}, 95% CI [{S['ci'][0]:+.3f}, {S['ci'][1]:+.3f}], permutation p two-sided {S['perm_p_two_sided']:.4f}, one-sided {S['perm_p_one_sided_negative']:.4f}",
          "9b cells used: " + "; ".join(f"{d}: x {c['x']:.3f}, gain {c['gain']:+.3f}, SE {c['se']:.3f}" for d, c in S["qwen9b_cells"].items())]
    (outdir / "h1_sensitivity.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
