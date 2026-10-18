#!/usr/bin/env python3
"""Run budgeted cells (M1, or S1 under a cap) through tau2's Python API.

Why not `tau2 run`: the CLI cannot pass a per-cell budget to a custom agent.
This runner registers one agent factory per cell, closed over that cell's
BudgetConfig (from budgets.json, i.e. the §4.2 values), and calls tau2's
batch runner with the same settings as run_calibration.py (seed 300, task
subsets, simulator, max_steps, auto-resume). Results land under
tau2-bench/data/simulations/<name>/results.json with a manifest beside the
calibration ones.

Run from the tau2 environment so its dependencies resolve:
  cd tau2-bench && uv run python ../run_m1.py --condition m1 --only google/gemini-3.1-flash-lite/telecom
Options:
  --condition m1|s1|s2     s1 = the stock agent under the cap (G1 / R1 comparators); s2 = strong single agent (§8.2)
  --budget-mult k          ceiling multiple on B_1x: 4 (Kim-regime arm, default) or 1 (matched arm, R1 cells)
  --cap-rule b1x|p95       per-call cap: b1x (default, c = B_1x) or p95 (superseded)
  --num-trials N           default from cells.json (3); G1 uses 5
  --only family[/model[/domain]]
  --dry-run                print what would run
  --max-concurrency N
  --smoke N                pilot on the first N tasks only (saved as smoke<N>-..., never counted as the cell)
  --user-sim NAME          R2 only: replace the user simulator by cells.json user_alternatives[NAME] (e.g. gpt41)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
TAU2 = ROOT / "tau2-bench"
MANIFEST_DIR = ROOT / "results" / "calibration-manifests"

try:  # tau2 reads its keys from tau2-bench/.env; load it when running from elsewhere
    from dotenv import load_dotenv

    load_dotenv(TAU2 / ".env")
except Exception:
    pass

from tau2.data_model.simulation import TextRunConfig  # noqa: E402
from tau2.registry import registry  # noqa: E402
from tau2.runner.batch import run_domain  # noqa: E402
from tau2.runner.helpers import get_tasks  # noqa: E402
from tau2.utils.utils import DATA_DIR  # noqa: E402

from budget_layer import BudgetConfig, load_base_prompt_template, sha256_text  # noqa: E402
from m1_agent import DEFAULT_READ_CALL_LIMIT, make_m1_factory  # noqa: E402
from s1_agent import make_s1_factory  # noqa: E402
from s2_agent import make_s2_factory  # noqa: E402


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tau2_commit() -> str:
    return subprocess.check_output(["git", "-C", str(TAU2), "rev-parse", "--short", "HEAD"]).decode().strip()


def infra_errors(results: Path) -> tuple[int, int]:
    """(episodes that ended in infrastructure_error, total episodes) for a results.json."""
    if not results.exists():
        return 0, 0
    sims = json.load(open(results)).get("simulations", [])
    return sum(1 for x in sims if x.get("termination_reason") == "infrastructure_error"), len(sims)


def cell_is_finished(done_manifest: Path, results: Path) -> bool:
    """Finished = manifest rc 0 AND no episode ended in infrastructure_error (quota,
    outages). tau2's --auto-resume re-runs exactly those episodes on the next launch."""
    if not done_manifest.exists() or json.loads(done_manifest.read_text()).get("return_code") != 0:
        return False
    bad, total = infra_errors(results)
    return total > 0 and bad == 0


def iter_cells(cells: dict, only: str | None):
    parts = only.split("/") if only else []
    for family, fam in cells["families"].items():
        if parts and parts[0] != family:
            continue
        for model in fam["models"]:
            if len(parts) > 1 and parts[1] != model["name"]:
                continue
            for domain in cells["domains"]:
                if len(parts) > 2 and parts[2] != domain:
                    continue
                yield family, model, domain


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", choices=["m1", "s1", "s2"], required=True)
    ap.add_argument("--budget-mult", type=float, default=4.0,
                    help="ceiling multiple k on B_1x; 4 = Kim-regime arm (default, CHANGELOG 2026-09-21); 1 = matched arm (R1 cells)")
    ap.add_argument("--num-trials", type=int, default=None)
    ap.add_argument("--only")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-concurrency", type=int, default=None)
    ap.add_argument("--read-call-limit", type=int, default=DEFAULT_READ_CALL_LIMIT)
    ap.add_argument("--cap-rule", choices=["p95", "b1x"], default="b1x",
                    help="per-call cap c: b1x = B_1x (runaway guard, ANALYSIS.md CHANGELOG 2026-09-21, default); p95 = S1 per-call P95 (superseded)")
    ap.add_argument("--orch-cap-mult", type=float, default=1.0,
                    help="per-call cap for M1 orchestrator/advisor calls as a multiple of c (database agent keeps c)")
    ap.add_argument("--uncapped", action="store_true",
                    help="uncapped arm (§8 addendum 2026-09-24): no episode ceiling, per-call guard c kept; --budget-mult is ignored")
    ap.add_argument("--smoke", type=int, default=None, metavar="N",
                    help="pilot: first N task ids of the subset only; results saved under smoke-* names, never as the cell")
    ap.add_argument("--orch-tool-defs", action="store_true",
                    help="M1 only, G1 write-order fix A1 (CHANGELOG 2026-10-12): orchestrator calls carry the tool definitions with tool_choice 'none'; run names carry -otd. Off = M1 as built (v6)")
    ap.add_argument("--user-sim", default=None,
                    help="R2 only (ANALYSIS.md §1 R2): use cells.json user_alternatives[NAME] as the user simulator; the run name carries its short tag")
    args = ap.parse_args()

    cells = json.load(open(ROOT / "cells.json"))
    if args.user_sim:
        alts = cells.get("user_alternatives", {})
        if args.user_sim not in alts or args.user_sim.startswith("_"):
            sys.exit(f"--user-sim {args.user_sim!r}: not in cells.json user_alternatives")
        cells["user"] = alts[args.user_sim]
    budgets_path = ROOT / "budgets.json"
    if not budgets_path.exists():
        sys.exit("budgets.json missing: run build_budgets.py after the S1 calibration cells")
    budgets = json.load(open(budgets_path))["cells"]
    prompt_hash = sha256_text(load_base_prompt_template())
    role_hashes = {p.stem: sha256_file(p) for p in (ROOT / "prompts" / "roles").glob("*.md")}
    commit = tau2_commit()
    num_trials = args.num_trials or cells["num_trials"]
    mult_tag = (
        ("uncapped" if args.uncapped else f"b{args.budget_mult:g}x")
        + f"-cap{args.cap_rule}"
        + (f"-oc{args.orch_cap_mult:g}x" if args.condition == "m1" and args.orch_cap_mult != 1.0 else "")
        # read-call limit r (docs/budget-protocol.md): names without a tag are r = 4, the build default.
        + (f"-rc{args.read_call_limit}" if args.condition == "m1" and args.read_call_limit != DEFAULT_READ_CALL_LIMIT else "")
        # G1 write-order fix A1: names without -otd are M1 as built (orchestrator without tool definitions).
        + ("-otd" if args.condition == "m1" and args.orch_tool_defs else "")
    )
    if args.orch_tool_defs and args.condition != "m1":
        sys.exit("--orch-tool-defs applies to --condition m1 only")
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    STOP_FILE = ROOT / "STOP_M1"

    for family, model, domain in iter_cells(cells, args.only):
        key = f"{domain} x {model['name']}"
        if STOP_FILE.exists():
            # `touch STOP_M1` in the folder: finish the running cell, start no new one.
            print(f"== stop file {STOP_FILE.name} found; not starting [{key}]. Remove the file to relaunch.", flush=True)
            break
        if key not in budgets:
            print(f"== [{key}] no calibration entry in budgets.json; skipping", flush=True)
            continue
        b = budgets[key]
        if args.uncapped:
            cfg = BudgetConfig.uncapped_with_guard(b["B_1x"], b["c"], b["per_call_median"], cap_rule=args.cap_rule)
        else:
            cfg = BudgetConfig.from_calibration(b["B_1x"], b["c"], b["per_call_median"], multiplier=args.budget_mult, cap_rule=args.cap_rule)
        name = f"{args.condition}-{domain}-{model['short']}-{cells['user']['short']}-{mult_tag}-{num_trials}trials-seed{cells['seed']}"
        if args.smoke:
            name = f"smoke{args.smoke}-{name}"
        agent_name = f"{args.condition}_{model['short']}_{domain}_{mult_tag}".replace(".", "_").replace("-", "_")
        done_manifest = MANIFEST_DIR / f"{name}.json"
        save_path = DATA_DIR / "simulations" / name / "results.json"
        if cell_is_finished(done_manifest, save_path):
            print(f"== [{key}] already finished ({name}), skipping", flush=True)
            continue
        bad, total = infra_errors(save_path)
        if bad:
            print(f"== [{key}] {bad}/{total} episodes ended in infrastructure_error; resuming to re-run them", flush=True)
        summary = f"{key} | {args.condition} | B={cfg.limit} c={cfg.per_call_cap}{' orch_c=' + str(int(round(cfg.per_call_cap * args.orch_cap_mult))) if args.condition == 'm1' and args.orch_cap_mult != 1.0 else ''} w={cfg.wrapup_threshold} a_min={cfg.min_call_allowance} | trials={num_trials}{' | SMOKE ' + str(args.smoke) + ' tasks' if args.smoke else ''} -> {name}"
        if args.dry_run:
            print("[dry-run]", summary)
            continue
        print("==", summary, flush=True)

        if args.condition == "m1":
            factory = make_m1_factory(cfg, prompt_hash, args.read_call_limit, args.orch_cap_mult, args.orch_tool_defs)
        elif args.condition == "s2":
            factory = make_s2_factory(cfg, prompt_hash)
        else:
            factory = make_s1_factory(cfg, prompt_hash)
        if registry.get_agent_factory(agent_name) is None:
            registry.register_agent_factory(factory, agent_name)

        task_ids = cells["domains"][domain]["task_ids"]
        if task_ids is None:
            # airline runs the full base split (cells.json has no id list); take tau2's own order,
            # exactly what run_calibration.py runs when it omits --task-ids.
            task_ids = [t.id for t in get_tasks(domain)]
        if args.smoke:
            task_ids = task_ids[: args.smoke]
        # Same fields run_calibration.py passes to `tau2 run`; run_domain() is what the CLI calls,
        # so the save layout (data/simulations/<name>/results.json) and resume behaviour match.
        config = TextRunConfig(
            domain=domain,
            agent=agent_name,
            user=cells["user"]["implementation"],
            llm_agent=model["litellm"],
            llm_args_agent=model["llm_args"],
            llm_user=cells["user"]["llm"],
            llm_args_user=cells["user"]["llm_args"],
            task_ids=task_ids,
            num_trials=num_trials,
            max_steps=cells["max_steps"],
            max_errors=cells["max_errors"],
            max_concurrency=args.max_concurrency or cells["families"][family]["max_concurrency"],
            seed=cells["seed"],
            auto_resume=True,
            save_to=name,
        )
        manifest = {
            "cell": {"family": family, "model": model["name"], "tier": model["tier"], "domain": domain},
            "condition": args.condition, "budget": cfg.to_dict(), "budget_multiplier": None if args.uncapped else args.budget_mult, "arm": "uncapped" if args.uncapped else "cost-bounded",
            "calibration_source": {"results_sha256": b["results_sha256"], "B_1x": b["B_1x"], "c": b["c"], "per_call_median": b["per_call_median"]},
            "read_call_limit": args.read_call_limit if args.condition == "m1" else None,
            "orchestrator_tool_definitions": bool(args.orch_tool_defs) if args.condition == "m1" else None,
            "orchestrator_cap_mult": args.orch_cap_mult if args.condition == "m1" else None,
            "cap_rule": args.cap_rule,
            "smoke": args.smoke, "task_ids_used": len(task_ids),
            "snapshot": model["snapshot"], "litellm_model": model["litellm"], "agent": agent_name,
            "agent_llm_args": model["llm_args"], "user_llm": cells["user"]["llm"], "user_llm_args": cells["user"]["llm_args"],
            "seed": cells["seed"], "num_trials": num_trials, "max_steps": cells["max_steps"],
            "task_ids_sha256": cells["domains"][domain].get("sha256"), "tau2_commit": commit,
            "base_prompt_sha256": prompt_hash, "role_block_sha256": role_hashes,
            "started_utc": datetime.now(timezone.utc).isoformat(),
        }
        t0 = time.time()
        rc = 0
        try:
            run_domain(config)
        except Exception as exc:  # record and stop; the next launch resumes
            rc = 1
            manifest["error"] = f"{type(exc).__name__}: {exc}"
        manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
        manifest["wall_seconds"] = round(time.time() - t0, 1)
        bad, total = infra_errors(save_path)
        if rc == 0 and bad:
            rc = 2  # provider-side failures: not a usable cell until re-run
            manifest["error"] = f"{bad}/{total} episodes ended in infrastructure_error (see info.error in results.json)"
        manifest["return_code"] = rc
        manifest["episodes"] = total
        manifest["infrastructure_errors"] = bad
        manifest["results_path"] = (
            str(save_path.relative_to(ROOT)) if save_path.exists() and save_path.is_relative_to(ROOT)
            else (str(save_path) if save_path.exists() else None)
        )
        manifest["results_sha256"] = sha256_file(save_path) if save_path.exists() else None
        done_manifest.write_text(json.dumps(manifest, indent=2))
        if rc != 0:
            print(f"!! cell failed: {manifest.get('error')}; manifest written; stopping. Relaunch to resume.", flush=True)
            sys.exit(rc)
        print(f"== finished {name} in {manifest['wall_seconds'] / 60:.0f} min", flush=True)
    print("done")


if __name__ == "__main__":
    main()
