#!/usr/bin/env python3
"""Calibration entry for the local October-build cell telecom x qwen3.5-4b-oct26, from its own S1 run.

Same procedure as the retail x qwen3.5-4b-oct26 entry of 2026-10-12: calibrate_budget.calibrate over the
evaluated episodes only (infrastructure-error episodes carry no agent calls and would pull B_1x down), on a
filtered copy written under results/, never under tau2-bench/data/simulations. c is the per-call P95 as
stored for every cell; run_m1.py's b1x cap rule uses B_1x at run time. w = 15% of B_1x, a_min = per-call median.

    python3 a1_qwen_budget.py            # print the entry
    python3 a1_qwen_budget.py --write    # add it to budgets.json (refuses if the key exists)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from calibrate_budget import calibrate  # noqa: E402

RUN = "local-telecom-s1-qwen35-4b-q4-ollama-gpt52low-3trials-seed300"
KEY = "telecom x qwen3.5-4b-oct26"
SRC = ROOT / "tau2-bench" / "data" / "simulations" / RUN / "results.json"
OUT_DIR = ROOT / "results" / "m1-telecom-4b-oct26"


def main() -> None:
    if not SRC.exists():
        sys.exit(f"S1 run not found: {SRC} (run: python3 ollama/run_local_s1.py --domain telecom --full)")
    d = json.load(open(SRC))
    keep = [s for s in d["simulations"] if s.get("termination_reason") != "infrastructure_error"]
    dropped = len(d["simulations"]) - len(keep)
    if len(d["simulations"]) < 150:
        sys.exit(f"S1 run has {len(d['simulations'])} episodes; the cell is 150. Not finished.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    filt = OUT_DIR / "s1-evaluated-episodes.json"
    json.dump({**d, "simulations": keep}, open(filt, "w"))
    cal = calibrate(filt)
    full = calibrate(SRC)
    b1x = cal["S1_P75_completion_per_episode (B_1x)"]
    entry = {
        "family": "qwen-local", "model": "qwen3.5-4b-oct26", "domain": "telecom",
        "B_1x": b1x, "c": cal["per_call_P95 (c)"], "per_call_median": cal["per_call_median"],
        "w": int(round(0.15 * b1x)), "a_min": cal["per_call_median"],
        "S1_mean": cal["S1_mean_completion_per_episode"], "episodes": cal["episodes"],
        "results_sha256": full["results_sha256"],
        "results_path": str(SRC.relative_to(ROOT)), "admitted_gate_run": False,
        "_source": (f"written by a1_qwen_budget.py: calibrate_budget.py over the {cal['episodes']} evaluated episodes "
                    f"({dropped} infrastructure-error episodes excluded; results_sha256 is of the full file); "
                    "build_budgets.py does not produce this entry and drops it on a rebuild"),
    }
    print(json.dumps(entry, indent=1))
    print(f"(full file, no filter: B_1x {full['S1_P75_completion_per_episode (B_1x)']}, episodes {full['episodes']})")
    if "--write" in sys.argv:
        bp = ROOT / "budgets.json"
        b = json.load(open(bp))
        if KEY in b["cells"]:
            sys.exit(f"{KEY} already in budgets.json; not overwritten")
        b["cells"][KEY] = entry
        json.dump(b, open(bp, "w"), indent=2)
        print(f"added '{KEY}' to budgets.json")


if __name__ == "__main__":
    main()
