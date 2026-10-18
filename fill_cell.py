#!/usr/bin/env python3
"""Fill the §4.2 and §5 rows in ANALYSIS.md for one finished S1 calibration cell.
Usage: python3 fill_cell.py <domain> <model-name-as-in-ANALYSIS> <results.json>
Prints the summary; edits ANALYSIS.md only if both rows are still blank."""
import json, sys, subprocess, collections, random
dom, model, path = sys.argv[1], sys.argv[2], sys.argv[3]
out = json.loads(subprocess.check_output([sys.executable, "calibrate_budget.py", path]))
d = json.load(open(path)); sims = d["simulations"]
by = collections.defaultdict(list)
for s in sims: by[s["task_id"]].append(s["reward_info"]["reward"])
pm = {t: sum(v)/len(v) for t, v in by.items()}; tasks = list(pm)
random.seed(300); bs = []
for _ in range(10000):
    smp = [pm[random.choice(tasks)] for _ in tasks]; bs.append(sum(smp)/len(smp))
bs.sort(); lo, hi = bs[250], bs[9749]; p1 = sum(pm.values())/len(pm)
straddle = "no" if (hi < 0.45 or lo > 0.45) else "yes"
pred = "M1 > S1" if hi < 0.45 else ("M1 < S1" if lo > 0.45 else "—")
cnt = collections.Counter(round(sum(v)) for v in by.values())
flaky = sum(1 for v in by.values() if 0 < sum(v) < 3)
trials = collections.defaultdict(list)
for s in sims: trials[s["trial"]].append(s["reward_info"]["reward"])
cost = sum(s["agent_cost"] + s["user_cost"] for s in sims) / len(sims)
print(f"{dom} x {model}: pass^1 {p1*100:.1f}% CI [{lo*100:.1f}, {hi*100:.1f}] {'clearly below' if hi<0.45 else 'clearly above' if lo>0.45 else 'straddles'} | trials {[round(sum(v)/len(v)*100) for k,v in sorted(trials.items())]} | per-task 0..3: {[cnt.get(k,0) for k in range(4)]} | flaky {flaky}/{len(by)} | B_1x {out['S1_P75_completion_per_episode (B_1x)']} c {out['per_call_P95 (c)']} mean {out['S1_mean_completion_per_episode']:.0f} | cost/ep ${cost:.4f} | hash {out['results_sha256'][:12]}")
p = "ANALYSIS.md"; s = open(p, encoding="utf-8").read()
r42_old = f"| {dom} x {model} | ____ | ____ | ____ | ____ | ____ | ____ |"
r42_new = (f"| {dom} x {model} | `{out['results_sha256'][:12]}…` | {out['S1_mean_completion_per_episode']:.0f} | "
           f"**{out['S1_P75_completion_per_episode (B_1x)']}** | {out['B_0.5x']} | {out['B_2x']} | {out['per_call_P95 (c)']} |")
r5_old = f"| {dom} x {model} | ____ | ____ | ____ | ____ |"
r5_new = f"| {dom} x {model} | {p1*100:.1f}% | [{lo*100:.1f}%, {hi*100:.1f}%] | {straddle} | {pred} |"
# the §5 pattern is a prefix of the §4.2 pattern, so replace the longer one first
if s.count(r42_old) == 1 and s.count(r5_old) == 2:
    s = s.replace(r42_old, r42_new)
    assert s.count(r5_old) == 1
    s = s.replace(r5_old, r5_new); open(p, "w", encoding="utf-8").write(s); print("  -> ANALYSIS.md rows filled")
else:
    print("  -> rows not blank (already filled?), ANALYSIS.md untouched")
