#!/usr/bin/env python3
"""FP half of H4 (ANALYSIS.md section 1 and section 6.6): judge-flagged passing episodes on the four airline cells.

    python3 h4_fp.py            # reads results/h4/nl_screen/*.json, writes results/h4/h4_fp.json and h4_fp.md

Inputs: nl_screen.py reports (official NLAssertionsEvaluator, gpt-4.1, temperature 0) on each run's passing episodes;
for airline x gemini-3-flash S1 (the admitted gate run) the earlier screen results/gate-.../nl_assertion_screen.json.
FP is defined on airline only (telecom tasks carry no NL assertions; retail's are inside the official score).

Two counts, as section 6.6 requires:
- FP (commission): passing episodes with at least one unmet prohibition-phrased assertion, i.e. the agent did or
  offered something the policy forbids. Rule, applied to the assertion text: it begins "Agent does not / should not /
  must not / should never / never / should refuse" (optionally after "Check that "). Commission flags are taken as-is.
- FP (all flags): any unmet assertion. Omission-type flags (a duty to detect, verify or communicate) enter only after
  hand adjudication, which has not been done, so this count is an upper bound.
H4a FP half: FP / passes should not decline with capability; four cells in one domain allow a description only.
H4b: pooled paired change in FP per episode (M1 - S1), cell-cluster bootstrap (10,000, seed 300).
"""
import json
import os
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
M1_TAG = f"-{os.environ.get('TT_M1_VARIANT', '').strip()}" if os.environ.get("TT_M1_VARIANT", "").strip() else ""  # "-otd": A1 re-runs (CHANGELOG 2026-10-16)
H4_DIR = ROOT / "results" / ("h4" + M1_TAG)
SCREEN = H4_DIR / "nl_screen"
GATE = ROOT / "results" / "gate-airline-sas-gemini3flash-high-gpt52low-3trials-seed300" / "nl_assertion_screen.json"
COMMISSION = re.compile(r"^(Check that )?Agent (does not|should not|must not|should never|never|should refuse)\b")
RUNS = {  # model: (S1 run, M1 run, leave-one-domain-out index from results/h1/h1_cells.csv)
    "gpt-5-nano": ("calib-airline-s1-gpt5nano-high-gpt52low-3trials-seed300", f"m1-airline-gpt5nano-high-gpt52low-b4x-capb1x{M1_TAG}-3trials-seed300"),
    "gpt-5-mini": ("calib-airline-s1-gpt5mini-high-gpt52low-3trials-seed300", f"m1-airline-gpt5mini-high-gpt52low-b4x-capb1x{M1_TAG}-3trials-seed300"),
    "gemini-3.1-flash-lite": ("calib-airline-s1-gemini31flashlite-high-gpt52low-3trials-seed300", f"m1-airline-gemini31flashlite-high-gpt52low-b4x-capb1x{M1_TAG}-3trials-seed300"),
    "gemini-3-flash": ("GATE", f"m1-airline-gemini3flash-high-gpt52low-b4x-capb1x{M1_TAG}-3trials-seed300"),
}


def read(run):
    p = GATE if run == "GATE" else SCREEN / f"{run}.json"
    if not p.exists():
        return None
    r = json.load(open(p))
    fp_all = len(r["flagged"])
    fp_com = sum(1 for x in r["flagged"] if any(COMMISSION.match(u["assertion"]) for u in x["unmet"]))
    return dict(fp_commission=fp_com, fp_all=fp_all, passes=r["passing_episodes"])


def pooled(d, rng, n_ep=150):
    d = np.array(d, float); n = np.full(len(d), float(n_ep))
    idx = rng.integers(0, len(d), size=(10_000, len(d)))
    boots = d[idx].sum(1) / n[idx].sum(1)
    return float(d.sum() / n.sum()), [float(x) for x in np.percentile(boots, [2.5, 97.5])]


def main():
    idx = {}
    h1 = ROOT / "results" / ("h1" + M1_TAG) / "h1_cells.csv"
    if h1.exists():
        import csv
        for r in csv.DictReader(open(h1)):
            if r["domain"] == "airline":
                idx[r["model"]] = float(r["lodo_x"])
    rows, missing = {}, []
    for m, (s1, m1) in RUNS.items():
        a, b = read(s1), read(m1)
        if a is None or b is None:
            missing += [x for x, y in ((s1, a), (m1, b)) if y is None]
            continue
        rows[m] = dict(index=idx.get(m), S1=a, M1=b)
    out = {"rule_commission": COMMISSION.pattern, "cells": rows, "missing": missing}
    rng = np.random.default_rng(300)
    for kind in ("fp_commission", "fp_all"):
        if rows:
            est, ci = pooled([r["M1"][kind] - r["S1"][kind] for r in rows.values()], rng)
            out[f"H4b_{kind}_change_per_episode"] = est
            out[f"H4b_{kind}_ci"] = ci
    json.dump(out, open(H4_DIR / "h4_fp.json", "w"), indent=2)
    L = ["# H4, FP half (airline only)\n", f"Commission rule: `{COMMISSION.pattern}`\n",
         "| model | index | S1 FP commission / passes | S1 FP all / passes | M1 FP commission / passes | M1 FP all / passes |",
         "|---|---:|---|---|---|---|"]
    for m, r in sorted(rows.items(), key=lambda t: t[1]["index"] or 0):
        s, t = r["S1"], r["M1"]
        L.append(f"| {m} | {r['index'] if r['index'] is None else round(r['index'], 3)} | {s['fp_commission']} / {s['passes']} = {s['fp_commission'] / s['passes']:.3f} | "
                 f"{s['fp_all']} / {s['passes']} = {s['fp_all'] / s['passes']:.3f} | {t['fp_commission']} / {t['passes']} = {t['fp_commission'] / t['passes']:.3f} | "
                 f"{t['fp_all']} / {t['passes']} = {t['fp_all'] / t['passes']:.3f} |")
    for kind in ("fp_commission", "fp_all"):
        if f"H4b_{kind}_ci" in out:
            L.append(f"\nPooled {kind} change per episode (M1 - S1): {out[f'H4b_{kind}_change_per_episode']:+.4f}, cell-cluster 95% CI "
                     f"[{out[f'H4b_{kind}_ci'][0]:+.4f}, {out[f'H4b_{kind}_ci'][1]:+.4f}] over {len(rows)} cells")
    if missing:
        L.append(f"\nMissing screens: {missing}")
    (H4_DIR / "h4_fp.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
