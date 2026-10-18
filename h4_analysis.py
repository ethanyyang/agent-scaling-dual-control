#!/usr/bin/env python3
"""H4 analysis (ANALYSIS.md section 1), log-based parts: H4a on WW / failures and H4b on WW, IN, BX.

    python3 h4_analysis.py [results/h4/taxonomy_per_episode.csv]

Specification followed:
- H4a (S1 only): WW / failures regressed on the leave-one-domain-out capability index with family and domain fixed
  effects, weights = number of failing episodes (as in power_sim.py run_h4a); supported if the slope is negative with
  a within-family permutation p < 0.05 (10,000 permutations). FP / passes (the other half of H4a) needs the judge pass
  and is not computed here.
- H4b (S1 vs M1 within cells): paired difference in the WW count per cell, episodes as the unit and the cell as the
  cluster, pooled across the valid cells; CI by cluster bootstrap over cells (10,000, seed 300). The changes in IN, BX
  and OTHER are always reported beside it (FP pending the judge pass). Reading grid (fixed in advance):
  WW down with IN + BX flat -> a failure class repaired; WW down with IN + BX up by a comparable amount -> one class
  traded for another; WW unchanged -> the architecture did not act on the failures it targets.
Output: results/h4/h4_results.json and h4_report.md next to the input.
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import h1_analysis as H  # noqa: E402  (same estimator, permutation and LODO index as H1)

SEED = 300
N_BOOT = 10_000
CATS = ["PASS", "WW", "BX", "IN", "OTHER"]


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("results/h4/taxonomy_per_episode.csv")
    outdir = path.parent
    per = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    meta, nowrite = {}, defaultdict(set)
    for r in csv.DictReader(open(path)):
        k = (r["model"], r["domain"])
        meta[k] = r["family"]
        c = per[k][r["condition"]]
        c[r["category"]] += 1
        c["N"] += 1
        c["IN_incl_BX"] += int(r["inaction_incl_bx"])
        if r["needs_write"] == "0":
            nowrite[r["domain"]].add(r["task_id"])
    keys = sorted(per, key=lambda k: (meta[k], k[0], H.DOMAINS.index(k[1])))
    out = {"spec": "ANALYSIS.md section 1 (H4a WW half, H4b); see module docstring",
           "no_write_tasks_per_domain": {d: len(v) for d, v in nowrite.items()}}

    # ---------------- H4a: WW / failures on the LODO index (S1 cells)
    s1_pass = {k: per[k]["S1"]["PASS"] / per[k]["S1"]["N"] for k in keys}
    xl = H.lodo_x(s1_pass, keys)
    kp = [k for k, x in zip(keys, xl) if not np.isnan(x)]
    x = np.array([xl[keys.index(k)] for k in kp])
    fails = np.array([per[k]["S1"]["N"] - per[k]["S1"]["PASS"] for k in kp], float)
    ww = np.array([per[k]["S1"]["WW"] for k in kp], float)
    y = ww / fails
    v = 1.0 / fails                                      # weights = failing episodes
    fam = np.array([meta[k] for k in kp]); dom = np.array([k[1] for k in kp])
    fl = ["OpenAI", "Google"]
    f = H.fit(x, y, v, fam, dom, fl)
    p2, p1 = H.permutation_p(x, y, v, fam, dom, fl, np.random.default_rng(SEED))
    out["H4a_ww"] = dict(n_cells=len(kp), dof=f["dof"], slope=f["slope"], ci=[f["lo"], f["hi"]],
                         perm_p_two_sided=p2, perm_p_one_sided_negative=p1,
                         supported=bool(f["slope"] < 0 and p2 < 0.05 and f["hi"] < 0),
                         pooled_rate_by_domain={d: float(ww[dom == d].sum() / fails[dom == d].sum()) for d in H.DOMAINS},
                         cells={f"{d} x {m}": dict(x=float(xx), ww=int(a), failures=int(b), rate=float(a / b))
                                for (m, d), xx, a, b in zip(kp, x, ww, fails)})
    out["H4a_fp"] = "pending: needs the NL-assertion judge pass; FP is defined on airline only (telecom tasks carry no NL assertions; retail's are inside the official score)"

    # ---------------- H4b: paired changes, pooled over valid cells, cell-cluster bootstrap
    rng = np.random.default_rng(SEED)
    measures = ["WW", "IN", "BX", "IN_incl_BX", "OTHER", "PASS"]
    diff = {m: np.array([per[k]["M1"].get(m, 0) - per[k]["S1"].get(m, 0) for k in keys], float) for m in measures}
    n = np.array([per[k]["S1"]["N"] for k in keys], float)
    assert all(per[k]["S1"]["N"] == per[k]["M1"]["N"] for k in keys)
    idx = rng.integers(0, len(keys), size=(N_BOOT, len(keys)))
    h4b = {}
    for m in measures:
        est = diff[m].sum() / n.sum()
        boots = diff[m][idx].sum(1) / n[idx].sum(1)
        lo, hi = np.percentile(boots, [2.5, 97.5])
        h4b[m] = dict(pooled_change_per_episode=float(est), ci=[float(lo), float(hi)],
                      s1_total=int(sum(per[k]["S1"].get(m, 0) for k in keys)),
                      m1_total=int(sum(per[k]["M1"].get(m, 0) for k in keys)),
                      cells_down=int((diff[m] < 0).sum()), cells_up=int((diff[m] > 0).sum()))
    ww_ci = h4b["WW"]["ci"]
    if ww_ci[0] <= 0 <= ww_ci[1]:
        reading = "WW unchanged: the architecture did not act on the failures it targets"
    elif h4b["WW"]["pooled_change_per_episode"] < 0:
        inbx = h4b["IN"]["pooled_change_per_episode"] + h4b["BX"]["pooled_change_per_episode"]
        reading = ("WW down with IN + BX up by a comparable amount: one failure class traded for another"
                   if inbx >= abs(h4b["WW"]["pooled_change_per_episode"]) else "WW down with IN + BX flat: a failure class repaired")
    else:
        reading = "WW up (outside the pre-specified grid)"
    out["H4b"] = dict(n_cells=len(keys), episodes_per_condition=int(n.sum()), changes=h4b, reading=reading,
                      supported=bool(h4b["WW"]["ci"][1] < 0), fp="pending (judge pass; airline only)")
    out["cells"] = {f"{d} x {m}": {c: {cat: per[(m, d)][c].get(cat, 0) for cat in CATS + ["N"]} for c in ("S1", "M1")}
                    for (m, d) in keys}
    json.dump(out, open(outdir / "h4_results.json", "w"), indent=2, default=float)

    A = out["H4a_ww"]; B = out["H4b"]
    L = ["# H4 results, log-based parts (ANALYSIS.md section 1)\n",
         f"Tasks whose gold trajectory has no write (where WW is possible), per domain: {out['no_write_tasks_per_domain']}\n",
         f"## H4a, WW / failures on the leave-one-domain-out index (S1, {A['n_cells']} cells, dof {A['dof']})\n",
         f"- slope {A['slope']:+.3f}, 95% CI [{A['ci'][0]:+.3f}, {A['ci'][1]:+.3f}]; permutation p two-sided {A['perm_p_two_sided']:.4f}, one-sided {A['perm_p_one_sided_negative']:.4f}; supported: {A['supported']}",
         f"- pooled WW / failures by domain: " + ", ".join(f"{d} {r:.3f}" for d, r in A["pooled_rate_by_domain"].items()),
         "- FP / passes: " + out["H4a_fp"] + "\n",
         "| cell | index | WW | failures | WW / failures |", "|---|---:|---:|---:|---:|"]
    L += [f"| {k} | {c['x']:.3f} | {c['ww']} | {c['failures']} | {c['rate']:.3f} |" for k, c in A["cells"].items()]
    L += [f"\n## H4b, paired change M1 - S1, pooled over {B['n_cells']} valid cells ({B['episodes_per_condition']} episodes per condition), cell-cluster bootstrap\n",
          "| measure | S1 total | M1 total | change per episode | 95% CI | cells down / up |", "|---|---:|---:|---:|---|---|"]
    for m, c in B["changes"].items():
        L.append(f"| {m} | {c['s1_total']} | {c['m1_total']} | {c['pooled_change_per_episode']:+.4f} | [{c['ci'][0]:+.4f}, {c['ci'][1]:+.4f}] | {c['cells_down']} / {c['cells_up']} |")
    L += [f"\nReading (pre-specified grid): {B['reading']}. H4b supported (WW CI below zero): {B['supported']}. FP change: {B['fp']}.\n",
          "## Per cell (counts out of 150)\n", "| cell | S1 PASS/WW/BX/IN/OTHER | M1 PASS/WW/BX/IN/OTHER |", "|---|---|---|"]
    for k, c in out["cells"].items():
        L.append(f"| {k} | " + " / ".join(str(c['S1'][x]) for x in CATS) + " | " + " / ".join(str(c['M1'][x]) for x in CATS) + " |")
    (outdir / "h4_report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
