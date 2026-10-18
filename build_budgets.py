#!/usr/bin/env python3
"""Build budgets.json from the finished S1 calibration cells.

Reads every manifest in results/calibration-manifests/ with return_code 0,
runs the §4.2 calibration on its results file, and writes one entry per cell:
B_1x (P75), c (per-call P95), per-call median (a_min), w, S1 mean, hash.
run_m1.py refuses to run a cell that has no entry here.

Usage: python3 build_budgets.py            # writes budgets.json, prints a table
"""
from __future__ import annotations
import json
from pathlib import Path

from calibrate_budget import calibrate

ROOT = Path(__file__).resolve().parent
MANIFESTS = ROOT / "results" / "calibration-manifests"
OUT = ROOT / "budgets.json"


def main() -> None:
    budgets: dict[str, dict] = {}
    for mf in sorted(MANIFESTS.glob("calib-*.json")):
        m = json.loads(mf.read_text())
        if m.get("return_code") != 0 or not m.get("results_path"):
            continue
        cell = m["cell"]
        key = f"{cell['domain']} x {cell['model']}"
        results = ROOT / m["results_path"]
        if not results.exists():
            print(f"!! {key}: results file missing ({results})")
            continue
        cal = calibrate(results)
        if m.get("results_sha256") and cal["results_sha256"] != m["results_sha256"]:
            print(f"!! {key}: results file hash changed since the manifest was written; refusing to use it")
            continue
        b1x = cal["S1_P75_completion_per_episode (B_1x)"]
        median = cal["per_call_median"]
        budgets[key] = {
            "family": cell["family"], "model": cell["model"], "domain": cell["domain"],
            "B_1x": b1x, "c": cal["per_call_P95 (c)"], "per_call_median": median,
            "w": max(int(round(0.15 * b1x)), 2 * median), "a_min": median,
            "S1_mean": cal["S1_mean_completion_per_episode"], "episodes": cal["episodes"],
            "results_sha256": cal["results_sha256"], "results_path": m["results_path"],
            "admitted_gate_run": bool(m.get("admitted_gate_run", False)),
        }
    # Cells calibrated on another machine (results/teammate-*/): the results.json is not held here, so
    # use the calibrate_budget.py output that came with the run (same function, same fields), checked
    # against its run manifest by results hash. A local results file for the same cell always wins.
    cells_cfg = json.loads((ROOT / "cells.json").read_text())
    by_litellm = {m["litellm"]: (fam, m["name"]) for fam, f in cells_cfg["families"].items() for m in f["models"]}
    for d in sorted((ROOT / "results").glob("teammate-*")):
        for cf in sorted(d.glob("calib-*.calibration.json")):
            mf = cf.with_name(cf.name.replace(".calibration.json", ".manifest.json"))
            if not mf.exists():
                print(f"!! {cf.name}: no run manifest beside it; skipped")
                continue
            cal, m = json.loads(cf.read_text()), json.loads(mf.read_text())
            if m.get("return_code") != 0 or m.get("infrastructure_errors"):
                print(f"!! {cf.name}: run not clean (return_code {m.get('return_code')}, infra {m.get('infrastructure_errors')}); skipped")
                continue
            if cal["results_sha256"] != m.get("results_sha256"):
                print(f"!! {cf.name}: results hash differs from its manifest; skipped")
                continue
            family, name = by_litellm.get(m["model"], (None, None))
            if name is None:
                print(f"!! {cf.name}: model {m['model']} not in cells.json; skipped")
                continue
            key = f"{m['domain']} x {name}"
            if key in budgets:
                continue
            b1x, median = cal["S1_P75_completion_per_episode (B_1x)"], cal["per_call_median"]
            budgets[key] = {
                "family": family, "model": name, "domain": m["domain"],
                "B_1x": b1x, "c": cal["per_call_P95 (c)"], "per_call_median": median,
                "w": max(int(round(0.15 * b1x)), 2 * median), "a_min": median,
                "S1_mean": cal["S1_mean_completion_per_episode"], "episodes": cal["episodes"],
                "results_sha256": cal["results_sha256"], "results_path": None,
                "calibration_file": str(cf.relative_to(ROOT)),
                "source": "teammate run; results.json not held locally",
                "admitted_gate_run": False,
            }
    OUT.write_text(json.dumps({"_note": "Per-cell budget values from S1 calibration (ANALYSIS.md §4.2). Frozen with the plan.", "cells": budgets}, indent=2))
    print(f"{'cell':40s} {'B_1x':>7s} {'c':>6s} {'median':>7s} {'w':>6s} {'mean':>7s}")
    for k, v in budgets.items():
        print(f"{k:40s} {v['B_1x']:7d} {v['c']:6d} {v['per_call_median']:7d} {v['w']:6d} {v['S1_mean']:7.0f}")
    print(f"\n{len(budgets)} cells -> {OUT}")


if __name__ == "__main__":
    main()
