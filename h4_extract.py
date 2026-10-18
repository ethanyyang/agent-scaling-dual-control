#!/usr/bin/env python3
"""Per-episode failure taxonomy for H4 (ANALYSIS.md section 1 and section 6), for the 13 valid grid cells, S1 and M1.

    python3 h4_extract.py        # writes results/h4/taxonomy_per_episode.csv

Uses analyze_run.py's own definitions so the taxonomy matches the section 0 anchors:
- write tools: tau2's @is_tool(ToolType.WRITE) tags per domain (write_tools_for_domain);
- a task "needs a write" if its gold actions contain an assistant-side write (task_requires_write);
- writes: agent-side tool calls to write tools in the trajectory (episode_writes). For M1 these are the database
  agent's executed calls, which tau2 records as the agent's turns; blocked or truncated calls never appear.
Categories for failing episodes (reward < 1), in this order:
  WW    wrongful write: the gold trajectory has no write and the agent wrote (primary-visible);
  BX    budget exhausted (the episode carries the transfer_testing_termination = budget_exhausted label);
  IN    inaction: the gold trajectory needs a write and the agent made none;
  OTHER any other failure (a wrong write on a write task, or a communication failure).
BX is applied before IN, as the budget protocol requires (R7); IN including BX is also written out.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from analyze_run import episode_writes, task_requires_write, write_tools_for_domain  # noqa: E402
from h1_extract import M1_TAG, cells  # noqa: E402  (same cells and run folders as H1; TT_M1_VARIANT=otd for the A1 re-runs)

OUT = ROOT / "results" / ("h4" + M1_TAG)


def exhausted(sim):
    return any(((m.get("raw_data") or {}).get("transfer_testing_termination") == "budget_exhausted")
               for m in sim.get("messages", []) if m.get("role") == "assistant")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "taxonomy_per_episode.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["family", "model", "tier", "domain", "condition", "task_id", "trial", "reward", "needs_write",
                    "writes", "exhausted", "category", "inaction_incl_bx"])
        for fam, model, tier, d, s1, m1 in cells():
            wt = write_tools_for_domain(d)
            if not wt:
                sys.exit(f"no write tools parsed for {d}")
            for cond, p in (("S1", s1), ("M1", m1)):
                data = json.load(open(p))
                tasks = {t["id"]: t for t in data.get("tasks", [])}
                counts = {}
                for s in data["simulations"]:
                    task = tasks.get(s["task_id"], {})
                    nw = task_requires_write(task, wt)
                    wr = episode_writes(s, wt)
                    r = float((s.get("reward_info") or {}).get("reward", 0) or 0)
                    bx = exhausted(s)
                    if r >= 1:
                        cat = "PASS"
                    elif (not nw) and wr > 0:
                        cat = "WW"
                    elif bx:
                        cat = "BX"
                    elif nw and wr == 0:
                        cat = "IN"
                    else:
                        cat = "OTHER"
                    inbx = int(r < 1 and nw and wr == 0)
                    counts[cat] = counts.get(cat, 0) + 1
                    w.writerow([fam, model, tier, d, cond, s["task_id"], s.get("trial", 0), r, int(nw), wr, int(bx), cat, inbx])
                print(f"{model:24s} {d:8s} {cond}  {counts}", flush=True)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
