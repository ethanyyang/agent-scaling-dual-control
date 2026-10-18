#!/usr/bin/env python3
"""Fill the §4.2 PILOT block in ANALYSIS.md for one finished S1 pilot cell (GPT-5 ladder decision).

Same numbers and rules as fill_cell.py (calibrate_budget.py for the budget values; pass^1 with a
task-cluster bootstrap CI, 10,000 resamples, seed 300). It touches only the pilot row and the
pilot pass^1 sentence, never the 27 registered rows or §5.

Usage: python3 fill_pilot_cell.py <domain> <model> <results.json> [--analysis ANALYSIS.md]
Refuses to write if any episode ended in infrastructure_error or the episode count is not 150.
"""
import collections, json, random, sys
from calibrate_budget import calibrate

args = [a for a in sys.argv[1:] if not a.startswith("--")]
dom, model, path = args[0], args[1], args[2]
target = sys.argv[sys.argv.index("--analysis") + 1] if "--analysis" in sys.argv else "ANALYSIS.md"

out = calibrate(path)
sims = json.load(open(path))["simulations"]
terms = collections.Counter(s["termination_reason"] for s in sims)
by = collections.defaultdict(list)
for s in sims:
    by[s["task_id"]].append(s["reward_info"]["reward"])
pm = {t: sum(v) / len(v) for t, v in by.items()}
tasks = list(pm)
random.seed(300)
bs = sorted(sum(pm[random.choice(tasks)] for _ in tasks) / len(tasks) for _ in range(10000))
lo, hi, p1 = bs[250], bs[9749], sum(pm.values()) / len(pm)
where = "clearly below 45%" if hi < 0.45 else "clearly above 45%" if lo > 0.45 else "straddles 45%"
trials = collections.defaultdict(list)
for s in sims:
    trials[s["trial"]].append(s["reward_info"]["reward"])
cost = sum((s.get("agent_cost") or 0) + (s.get("user_cost") or 0) for s in sims) / len(sims)
print(f"{dom} x {model}: pass^1 {p1*100:.1f}% CI [{lo*100:.1f}, {hi*100:.1f}] ({where}) | episodes {len(sims)} tasks {len(by)} "
      f"terminations {dict(terms)} | per-trial {[round(sum(v)/len(v)*100) for _, v in sorted(trials.items())]} | "
      f"B_1x {out['S1_P75_completion_per_episode (B_1x)']} c {out['per_call_P95 (c)']} mean {out['S1_mean_completion_per_episode']:.0f} "
      f"per-call median {out['per_call_median']} | cost/episode ${cost:.4f} | hash {out['results_sha256'][:12]}")

if terms.get("infrastructure_error") or len(sims) != 150 or len(by) != 50:
    sys.exit("  -> NOT WRITTEN: the cell is incomplete or has infrastructure errors; relaunch run_calibration.py to resume.")

s = open(target, encoding="utf-8").read()
row_old = f"| {dom} x {model} | ____ | ____ | ____ | ____ | ____ | ____ |"
row_new = (f"| {dom} x {model} | `{out['results_sha256'][:12]}…` | {out['S1_mean_completion_per_episode']:.0f} | "
           f"**{out['S1_P75_completion_per_episode (B_1x)']}** | {out['B_0.5x']} | {out['B_2x']} | {out['per_call_P95 (c)']} |")
sent_old = f"{dom} x {model} ____"
sent_new = f"{dom} x {model} {p1*100:.1f}% [{lo*100:.1f}%, {hi*100:.1f}%], {where}"
if s.count(row_old) != 1 or s.count(sent_old) != 1:
    sys.exit("  -> NOT WRITTEN: pilot row or pass^1 placeholder not found exactly once (already filled?).")
s = s.replace(row_old, row_new).replace(sent_old, sent_new)
open(target, "w", encoding="utf-8").write(s)
print(f"  -> {target}: pilot row and pass^1 filled")
