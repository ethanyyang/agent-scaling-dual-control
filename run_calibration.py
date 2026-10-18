#!/usr/bin/env python3
"""Launch the S1 calibration grid (ANALYSIS.md §3, §4.2), one tau2 run per cell.

Reads cells.json and task_subsets.json, refuses to start if the frozen inputs do
not match (base prompt hash vs the pinned tau2 source, task-id hashes), builds
one `tau2 run` command per (family, model, domain) cell, runs them sequentially
(tau2 parallelises simulations inside each run), and writes a manifest next to
each results file. Re-running a finished cell is a no-op: tau2 resumes on the
same --save-to name.

Usage:
  python run_calibration.py --dry-run                      # print all commands
  python run_calibration.py --only google                  # one family
  python run_calibration.py --only google/gemini-3-flash   # one model
  python run_calibration.py --only google/gemini-3-flash/airline
  python run_calibration.py --only google --max-concurrency 2
  python run_calibration.py --only google/gemini-3-flash/airline --user-sim gpt41   # R2 second simulator
Secrets are read by tau2 from tau2-bench/.env; nothing is passed on the command line.
"""
from __future__ import annotations

import argparse, ast, hashlib, json, os, shlex, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TAU2 = ROOT / "tau2-bench"
CELLS = ROOT / "cells.json"
SUBSETS = ROOT / "task_subsets.json"
BASE_PROMPT = ROOT / "prompts" / "base_system_prompt.md"
MANIFEST_DIR = ROOT / "results" / "calibration-manifests"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tau2_commit() -> str:
    return subprocess.check_output(["git", "-C", str(TAU2), "rev-parse", "--short", "HEAD"]).decode().strip()


def base_prompt_matches_source() -> tuple[bool, str, str]:
    """The file must equal AGENT_INSTRUCTION inside SYSTEM_PROMPT at the pinned commit."""
    src = (TAU2 / "src/tau2/agent/llm_agent.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    consts = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            v = node.value
            if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and v.func.attr == "strip" and isinstance(v.func.value, ast.Constant):
                consts[node.targets[0].id] = v.func.value.value.strip()
    template = consts["SYSTEM_PROMPT"].replace("{agent_instruction}", consts["AGENT_INSTRUCTION"])
    body = BASE_PROMPT.read_text(encoding="utf-8")
    body = body[body.index("-->") + 3:].strip() if body.startswith("<!--") else body.strip()
    return body == template, hashlib.sha256(template.encode()).hexdigest(), hashlib.sha256(body.encode()).hexdigest()


def check_frozen_inputs(cells: dict) -> None:
    ok, h_src, h_file = base_prompt_matches_source()
    if not ok:
        sys.exit(f"REFUSING TO RUN: prompts/base_system_prompt.md ({h_file[:16]}) != tau2 default prompt at pinned commit ({h_src[:16]}).")
    subs = json.load(open(SUBSETS))
    for dom in ("retail", "telecom"):
        ids = cells["domains"][dom]["task_ids"]
        h = hashlib.sha256("\n".join(ids).encode()).hexdigest()
        if h != subs["domains"][dom]["sha256_of_ids"] or h != cells["domains"][dom]["sha256"]:
            sys.exit(f"REFUSING TO RUN: {dom} task-id list does not match task_subsets.json.")
    if subs["root_seed"] != cells["seed"]:
        sys.exit("REFUSING TO RUN: seed mismatch between cells.json and task_subsets.json.")


def save_name(domain: str, model: dict, cells: dict) -> str:
    return f"calib-{domain}-s1-{model['short']}-{cells['user']['short']}-{cells['num_trials']}trials-seed{cells['seed']}"


def build_command(family: str, model: dict, domain: str, cells: dict, max_concurrency: int | None) -> list[str]:
    fam = cells["families"][family]
    cmd = ["uv", "run", "tau2", "run",
           "--domain", domain,
           "--agent", cells["agent"],
           "--agent-llm", model["litellm"],
           "--agent-llm-args", json.dumps(model["llm_args"]),
           "--user", cells["user"]["implementation"],
           "--user-llm", cells["user"]["llm"],
           "--user-llm-args", json.dumps(cells["user"]["llm_args"]),
           "--num-trials", str(cells["num_trials"]),
           "--seed", str(cells["seed"]),
           "--max-steps", str(cells["max_steps"]),
           "--max-errors", str(cells["max_errors"]),
           "--max-concurrency", str(max_concurrency or fam["max_concurrency"]),
           "--auto-resume",
           "--save-to", save_name(domain, model, cells)]
    ids = cells["domains"][domain]["task_ids"]
    if ids:
        cmd += ["--task-ids", *ids]
    return cmd


def infra_errors(results: Path) -> tuple[int, int]:
    """(episodes that ended in infrastructure_error, total episodes) for a results.json."""
    if not results.exists():
        return 0, 0
    sims = json.load(open(results)).get("simulations", [])
    return sum(1 for x in sims if x.get("termination_reason") == "infrastructure_error"), len(sims)


def cell_is_finished(done_manifest: Path, results: Path) -> bool:
    """Finished = manifest says rc 0 AND every episode has a real termination (tau2's
    resume re-runs infrastructure_error episodes, so a cell with any is not done)."""
    if not done_manifest.exists():
        return False
    m = json.loads(done_manifest.read_text())
    if m.get("return_code") != 0:
        return False
    if m.get("results_path"):  # admitted gate runs live under a different name (PROVENANCE.md)
        results = ROOT / m["results_path"]
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


STRAGGLER_FRACTION = 0.05  # up to this share of infrastructure_error episodes: continue, re-run them in a second pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="family, family/model, or family/model/domain")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-concurrency", type=int, default=None)
    ap.add_argument("--user-sim", default=None,
                    help="R2 only (ANALYSIS.md §1 R2): use cells.json user_alternatives[NAME] as the user simulator; the run name carries its short tag")
    args = ap.parse_args()

    cells = json.load(open(CELLS))
    check_frozen_inputs(cells)
    if args.user_sim:
        alts = cells.get("user_alternatives", {})
        if args.user_sim not in alts or args.user_sim.startswith("_"):
            sys.exit(f"--user-sim {args.user_sim!r}: not in cells.json user_alternatives")
        cells["user"] = alts[args.user_sim]
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    commit = tau2_commit()
    cells_hash = sha256_file(CELLS)
    _, _, prompt_hash = base_prompt_matches_source()

    # Pass 1 runs every cell; pass 2 re-runs only cells left with a few straggler
    # episodes (transient 429s), so one failed episode never idles the whole batch.
    todo = list(iter_cells(cells, args.only))
    for pass_no in (1, 2):
        stragglers = []
        if pass_no == 2 and not todo:
            break
        if pass_no == 2:
            print(f"== second pass: re-running {len(todo)} cell(s) with straggler episodes", flush=True)
        for family, model, domain in todo:
            name = save_name(domain, model, cells)
            cmd = build_command(family, model, domain, cells, args.max_concurrency)
            printable = " ".join(shlex.quote(c) for c in cmd)
            done_manifest = MANIFEST_DIR / f"{name}.json"
            results = TAU2 / "data" / "simulations" / name / "results.json"
            if cell_is_finished(done_manifest, results):
                print(f"== [{family}/{model['name']}/{domain}] already finished (manifest present), skipping", flush=True)
                continue
            bad, total = infra_errors(results)
            if bad:
                print(f"== [{family}/{model['name']}/{domain}] {bad}/{total} episodes ended in infrastructure_error; resuming to re-run them", flush=True)
            if args.dry_run:
                print(f"[{family}/{model['name']}/{domain}] {printable}\n")
                continue
            manifest = {
                "cell": {"family": family, "model": model["name"], "tier": model["tier"], "domain": domain},
                "snapshot": model["snapshot"], "litellm_model": model["litellm"], "agent": cells["agent"],
                "agent_llm_args": model["llm_args"], "user_llm": cells["user"]["llm"], "user_llm_args": cells["user"]["llm_args"],
                "seed": cells["seed"], "num_trials": cells["num_trials"], "max_steps": cells["max_steps"],
                "task_ids_sha256": cells["domains"][domain].get("sha256"), "tau2_commit": commit,
                "cells_json_sha256": cells_hash, "base_prompt_sha256": prompt_hash, "command": printable,
                "budget": "uncapped (S1 calibration, ANALYSIS.md §4.2)", "started_utc": datetime.now(timezone.utc).isoformat(),
            }
            print(f"== [{family}/{model['name']}/{domain}] -> {name}", flush=True)
            t0 = time.time()
            rc = subprocess.call(cmd, cwd=TAU2, env={**os.environ, "PYTHONUNBUFFERED": "1"}, stdin=subprocess.DEVNULL)
            manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
            manifest["wall_seconds"] = round(time.time() - t0, 1)
            bad, total = infra_errors(results)
            if rc == 0 and bad:
                rc = 2  # provider-side failures (quota, outages): the cell is not usable until they are re-run
            manifest["return_code"] = rc
            manifest["episodes"] = total
            manifest["infrastructure_errors"] = bad
            manifest["results_path"] = str(results.relative_to(ROOT)) if results.exists() else None
            manifest["results_sha256"] = sha256_file(results) if results.exists() else None
            (MANIFEST_DIR / f"{name}.json").write_text(json.dumps(manifest, indent=2))
            if rc != 0:
                why = f"{bad}/{total} episodes ended in infrastructure_error (see 'info.error' in results.json)" if bad else f"rc={rc}"
                if rc == 2 and total and bad / total <= STRAGGLER_FRACTION and pass_no == 1:
                    print(f"!! {why}; continuing, will re-run these episodes in a second pass", flush=True)
                    stragglers.append((family, model, domain))
                    continue
                print(f"!! cell failed ({why}); manifest written; stopping so the failure is looked at. Relaunch to resume.", flush=True)
                sys.exit(rc)
            print(f"== finished {name} in {manifest['wall_seconds'] / 60:.0f} min", flush=True)
        todo = stragglers
    print("done")


if __name__ == "__main__":
    main()
