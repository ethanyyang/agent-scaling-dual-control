import os as _os, sys as _sys
_REPO = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
_HERE = _os.path.dirname(_os.path.abspath(__file__))
import json, os, sys, statistics, collections
ROOT = _REPO + "/"; H = ROOT + "results/secondary-2026-09-26/"
sys.path.insert(0, ROOT); sys.path.insert(0, _HERE)
from h1_extract import cells
from pairs import tok
V = {r["run"]: r for r in json.load(open(H + "validity.json"))}
O = json.load(open(H + "orders.json")); D = json.load(open(H + "decomp2.json")); H6 = json.load(open(H + "h6.json")); PW = json.load(open(H + "power12.json"))
BAD = ["invalid_name_refused", "invalid_name_diverted", "valid_name_diverted", "valid_name_no_call"]
L = []; P = L.append
P("# Secondary analyses and validity audit, 2026-09-26\n")
P("Scripts: `results/secondary-2026-09-26/validity.py`, `orders.py`, `decomp.py`, `h6.py`, `power12.py` (copies in this folder). Cells: the 12 H1 grid cells at k = 4 (plus telecom x qwen3.5-4b where stated). Seed 300; task-cluster bootstrap, 2,000 resamples.\n")
P("## 1. G1 validity table (M1 grid cells at k = 4)\n")
P("| cell | write orders | as issued | keys corrected by DB agent | invented tool name, mapped | refused or diverted | value changed | cut calls | cut tokens | double-cut turns (exhaustion / other) | JSON / cut text to customer | exhausted | median utilisation |")
P("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|")
rows = []
for fam, model, tier, d, s1p, m1p in cells():
    run = os.path.basename(os.path.dirname(m1p)); v = V[run]; c = collections.Counter(O[run]["counts"]); n = sum(c.values())
    bad = sum(c[k] for k in BAD)
    P(f'| {d} x {model} | {n} | {c["as_issued"]/n:.0%} | {c["schema_keys_corrected"]/n:.0%} | {c["invalid_name_mapped_to_write"]/n:.0%} | {bad/n:.0%} | {c["value_changed"]/n:.0%} | {v["cut_share"]:.1%} | {v["cut_tok_share"]:.1%} | {v["dc_exh"]} / {v["dc_ord"]} | {v["json"]} / {v["cut_text"]} | {v["exh"]}/150 | {v["util_med"]:.2f} |')
P("\n`as issued` = the executed call has the ordered tool and the ordered arguments (after dropping a `functions.` prefix). `refused or diverted` = the orchestrator's order named a tool that does not exist or used argument names the tool does not take, and the database agent made no call (refused and reported back) or called a different, non-write tool. Order classes are computed per unique order (the frozen checker logs an order twice, once when issued and once when closed, and leaves refused orders out of its denominator). Cut text uses the corrected check (a cut call whose output is still a complete JSON object is not cut text); the frozen checker's one flag on telecom x gemini-3-flash is its known false positive.\n")
P("## 2. Loss decomposition (exact, per episode against S1 on the same task)\n")
P("gain = mean over M1 episodes of (reward - S1 pass rate on that task). Split by whether the episode ended budget-exhausted, and by whether it contained at least one refused or diverted write order. Components sum to the gain.\n")
P("| cell | S1 | M1 | gain [95% CI] | exhausted episodes | finished episodes | episodes with a refused/diverted order | exhaustion share of loss |")
P("|---|---:|---:|---|---|---|---|---:|")
tot = collections.Counter()
for r in D:
    ex, fi, bd = r["ex"], r["fin"], r["bad"]
    sh = f'{ex[0]/r["gain"]:.0%}' if r["gain"] < 0 else "n/a"
    P(f'| {r["domain"]} x {r["model"]} | {r["S1"]:.1%} | {r["M1"]:.1%} | {r["gain"]*100:+.1f} [{r["gain_ci"][0]*100:+.1f}, {r["gain_ci"][1]*100:+.1f}] | {ex[0]*100:+.1f} [{ex[1]*100:+.1f}, {ex[2]*100:+.1f}] | {fi[0]*100:+.1f} [{fi[1]*100:+.1f}, {fi[2]*100:+.1f}] | {bd[0]*100:+.1f} [{bd[1]*100:+.1f}, {bd[2]*100:+.1f}] | {sh} |')
    if r["model"] != "qwen3.5-4b": tot["g"] += r["gain"]; tot["ex"] += ex[0]; tot["fi"] += fi[0]; tot["bd"] += bd[0]
P(f'\nMean over the 12 H1 cells: gain {tot["g"]/12*100:+.1f}; exhausted episodes {tot["ex"]/12*100:+.1f} ({tot["ex"]/tot["g"]:.0%} of the loss); finished episodes {tot["fi"]/12*100:+.1f}; episodes with a refused or diverted order {tot["bd"]/12*100:+.1f} ({tot["bd"]/tot["g"]:.0%}). Episode classes are outcomes of M1, not random assignments: read as accounting, not as causal effects.\n')
P("## 3. H7, spend, cost, per-task counts\n")
P("| cell | median utilisation | exhausted | completion tokens M1 / S1 (median) | agent USD S1 / M1 | end-to-end USD S1 / M1 | tasks M1 better / same / worse |")
P("|---|---:|---:|---:|---|---|---|")
meds = {}
for fam, model, tier, d, s1p, m1p in cells():
    a = [tok(x) for x in json.load(open(s1p))["simulations"]]; b = [tok(x) for x in json.load(open(m1p))["simulations"]]
    meds[(model, d)] = statistics.median(b) / statistics.median(a)
for r in D:
    cs, cm = r["cost_S1"], r["cost_M1"]
    P(f'| {r["domain"]} x {r["model"]} | {r["util_median"]:.2f} | {r["exhausted"]:.0%} | {meds[(r["model"], r["domain"])]:.1f} | ${cs[0]:.2f} / ${cm[0]:.2f} | ${sum(cs):.2f} / ${sum(cm):.2f} | {r["better"]} / {r["same"]} / {r["worse"]} |')
P("\n## 4. H6 (write share of S1 failures)\n")
for k, f in H6["fits"].items():
    ws = f["b_ws"]; P(f'- {k}: b_x {f["b_x"][0]:+.3f} [{f["b_x"][1]:+.3f}, {f["b_x"][2]:+.3f}]' + (f'; b_write_share {ws[0]:+.3f} [{ws[1]:+.3f}, {ws[2]:+.3f}]' if ws else "") + f'; permutation p (two-sided, within family) {f["perm_p_two_sided_tested_coef"]:.3f}; dof {f["dof"]}')
P("\nwrite share = (wrongful writes + wrong writes) / S1 failures; wrong write = a failing episode on a task that needs a write in which the agent wrote and the database check or a gold write action failed.\n")
P("| cell | S1 failures | WW | wrong write | write share | gain |\n|---|---:|---:|---:|---:|---:|")
for c in sorted([c for c in H6["cells"] if c.get("x") is not None], key=lambda c: c["write_share"]):
    P(f'| {c["domain"]} x {c["model"]} | {c["fails"]} | {c["ww"]} | {c["wa"]} | {c["write_share"]:.2f} | {c["gain"]*100:+.1f} |')
P("\n## 5. Power of the H1 test for the cells held\n")
P("Simulation with the observed LODO x, per-cell SEs and the primary estimator (family and domain FE, inverse-variance WLS, t CI, dof 7), 4,000 worlds per point; tau = between-cell SD beyond task sampling (power_sim.py assumed 0).\n")
P("| tau | b = 0 (false positive) | b = -0.2 | b = -0.3 | b = -0.5 | b = -1.0 |\n|---|---:|---:|---:|---:|---:|")
for t, row in PW.items():
    P(f'| {float(t):.2f} | {row["0.0"]:.2f} | {row["-0.2"]:.2f} | {row["-0.3"]:.2f} | {row["-0.5"]:.2f} | {row["-1.0"]:.2f} |')
open(H + "report.md", "w").write("\n".join(L) + "\n"); print("\n".join(L))
