#!/usr/bin/env python3
"""Extract per-episode rewards for the H1 analysis (ANALYSIS.md section 1) into results/h1/per_episode.csv.

    python3 h1_extract.py

Cells: the 13 valid grid cells of the cost-bounded arm (k = 4, c = B_1x, r = 4). S1 is the uncapped
calibration run of each cell (airline x gemini-3-flash: the admitted gate run). Reward is read exactly as
cell_report.py reads it (missing reward_info counts as 0). No file is modified.

Variant (CHANGELOG 2026-10-16): with the environment variable TT_M1_VARIANT=otd the M1 runs are the A1
re-runs (orchestrator with tool definitions; run names carry -otd), the output goes to results/h1-otd/,
and the local Qwen cell is the October-build pair (local-telecom-s1 with m1-telecom-qwen35-4b-q4-oct26
-otd), included only when TT_INCLUDE_QWEN=1, because it is a labelled cell outside the primary fit.
Without the variable, behaviour is unchanged (the as-built grid, results/h1/).
    python3 h1_extract.py --list   # print the cells and whether their files exist; writes nothing
"""
import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SIM = ROOT / "tau2-bench" / "data" / "simulations"
VARIANT = os.environ.get("TT_M1_VARIANT", "").strip()      # "" = M1 as built; "otd" = the A1 re-runs
M1_TAG = f"-{VARIANT}" if VARIANT else ""
OUT = ROOT / "results" / ("h1" + M1_TAG)
INCLUDE_QWEN = (not VARIANT) or os.environ.get("TT_INCLUDE_QWEN") == "1"

MODELS = [  # family, model, tier, short name used in run folders
    ("OpenAI", "gpt-5-nano", "low", "gpt5nano-high"),
    ("OpenAI", "gpt-5-mini", "mid", "gpt5mini-high"),
    ("Google", "gemini-3.1-flash-lite", "low", "gemini31flashlite-high"),
    ("Google", "gemini-3-flash", "mid", "gemini3flash-high"),
]
DOMAINS = ["airline", "retail", "telecom"]


def s1_path(short, domain):
    if short == "gemini3flash-high" and domain == "airline":
        return SIM / "gate-airline-sas-gemini3flash-high-gpt52low-3trials-seed300" / "results.json"
    return SIM / f"calib-{domain}-s1-{short}-gpt52low-3trials-seed300" / "results.json"


def m1_path(short, domain):
    return SIM / f"m1-{domain}-{short}-gpt52low-b4x-capb1x{M1_TAG}-3trials-seed300" / "results.json"


def cells():
    for fam, model, tier, short in MODELS:
        for d in DOMAINS:
            yield fam, model, tier, d, s1_path(short, d), m1_path(short, d)
    if not INCLUDE_QWEN:
        return
    if VARIANT:  # October-build pair: S1 and M1 on the same build (CHANGELOG 2026-10-16)
        yield ("Qwen", "qwen3.5-4b-oct26", "low", "telecom",
               SIM / "local-telecom-s1-qwen35-4b-q4-ollama-gpt52low-3trials-seed300" / "results.json",
               SIM / f"m1-telecom-qwen35-4b-q4-oct26-ollama-gpt52low-b4x-capb1x{M1_TAG}-3trials-seed300" / "results.json")
        return
    q = "qwen35-4b-q4-ollama"
    yield ("Qwen", "qwen3.5-4b", "low", "telecom",
           SIM / f"calib-telecom-s1-{q}-gpt52low-3trials-seed300" / "results.json",
           SIM / f"m1-telecom-{q}-gpt52low-b4x-capb1x-3trials-seed300" / "results.json")


def rows(path):
    sims = json.load(open(path))["simulations"]
    for x in sims:
        term = str(x.get("termination_reason"))
        yield str(x["task_id"]), int(x.get("trial", 0)), float((x.get("reward_info") or {}).get("reward", 0) or 0), term


def main():
    if "--list" in sys.argv:
        for fam, model, tier, d, s1, m1 in cells():
            print(f"{model:24s} {d:8s} S1 {'ok     ' if s1.exists() else 'MISSING'} {s1.parent.name}")
            print(f"{'':24s} {'':8s} M1 {'ok     ' if m1.exists() else 'MISSING'} {m1.parent.name}")
        print(f"variant: {VARIANT or 'as built'}; output folder: {OUT.relative_to(ROOT)}")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "per_episode.csv"
    n_infra = 0
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["family", "model", "tier", "domain", "condition", "task_id", "trial", "reward", "termination"])
        for fam, model, tier, d, s1, m1 in cells():
            for cond, p in (("S1", s1), ("M1", m1)):
                if not p.exists():
                    sys.exit(f"missing {p}")
                k = 0
                for tid, trial, r, term in rows(p):
                    if "infrastructure" in term:
                        n_infra += 1
                    w.writerow([fam, model, tier, d, cond, tid, trial, r, term])
                    k += 1
                print(f"{model:24s} {d:8s} {cond}  {k} episodes  {p.parent.name}", flush=True)
    print(f"wrote {out}; infrastructure_error episodes: {n_infra}")


if __name__ == "__main__":
    main()
