#!/usr/bin/env python3
"""Pilot: S1 episodes on tau2-bench with the local Ollama model as the agent.

    python3 ollama/run_local_s1.py                       # qwen3.5-4b, telecom, first 5 tasks, 1 trial
    python3 ollama/run_local_s1.py --size 2b --domain airline --tasks 10
    python3 ollama/run_local_s1.py --tasks 10            # extend (finished episodes are kept)
    python3 ollama/run_local_s1.py --tasks 50 --trials 3 # the full cell size (days on this Mac)
    python3 ollama/run_local_s1.py --report-only         # print the summary of what exists

It builds the tau2 command with run_calibration.build_command, so the customer simulator,
seed, step limits and task subset are the ones in cells.json. It does NOT edit cells.json,
writes no calibration manifest, and saves under a `pilot-local-` name, so build_budgets.py
and fill_cell.py never see these episodes. Same task order as `run_m1.py --smoke N`.
"""
import argparse
import copy
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import run_calibration as rc  # noqa: E402

SIZES = ["0.8b", "2b", "4b", "9b"]
PRECISIONS = ["q4", "bf16"]


def variant(size, prec):
    return {"ollama_name": f"tt-qwen3.5-{size}:{prec}", "short": f"qwen35-{size}-{prec}-ollama"}


MAX_TOKENS = 32768  # loop guard. Hosted routes have a provider-side output limit; the local route has none.


def llm_args():
    return {
        "api_base": "http://127.0.0.1:11434/v1",
        "api_key": "ollama",
        "timeout": 3600,
        "max_tokens": MAX_TOKENS,
        "extra_body": {"reasoning_effort": "high"},
    }


def preflight(ollama_name):
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as r:
            names = [m.get("name") for m in json.load(r).get("models", [])]
    except Exception as e:  # noqa: BLE001
        sys.exit(f"Ollama server is not reachable on 127.0.0.1:11434 ({e}). Run: bash ollama/deploy_qwen35_4b.sh")
    if ollama_name not in names:
        sys.exit(f"Model {ollama_name} is not on the server (found: {names}). Run: bash ollama/deploy_qwen35.sh <size> [q4|bf16]")
    env = (HERE / "serve.env").read_text().strip() if (HERE / "serve.env").exists() else "unknown"
    print(f"ollama ok | model {ollama_name} | server settings: {env}", flush=True)


def serve_log_stats(offset):
    """Tokens the server actually read and wrote since `offset` bytes into serve.log."""
    p = HERE / "serve.log"
    if not p.exists():
        return None
    with open(p, "rb") as f:
        f.seek(offset)
        text = f.read().decode(errors="replace")
    pe = re.findall(r"prompt eval time =\s*([\d.]+) ms /\s*(\d+) tokens", text)
    ge = re.findall(r"(?<!prompt) eval time =\s*([\d.]+) ms /\s*(\d+) tokens", text)
    return {
        "calls": len(pe),
        "prompt_tokens_processed": sum(int(n) for _, n in pe),
        "prompt_seconds": round(sum(float(ms) for ms, _ in pe) / 1000, 1),
        "generated_tokens": sum(int(n) for _, n in ge),
        "generation_seconds": round(sum(float(ms) for ms, _ in ge) / 1000, 1),
        "truncated_prompts": len(re.findall(r"truncated = [1-9]", text)),
    }


def report(results_path, ctx, serve_stats=None):
    if not results_path.exists():
        print("no results.json yet")
        return
    d = json.load(open(results_path))
    sims = d.get("simulations", [])
    rows, ends = [], {}
    for s in sims:
        calls = [m for m in s.get("messages", []) if m.get("role") == "assistant" and m.get("usage")]
        comp = sum((m["usage"].get("completion_tokens") or 0) for m in calls)
        prm = sum((m["usage"].get("prompt_tokens") or 0) for m in calls)
        peak = max(((m["usage"].get("prompt_tokens") or 0) + (m["usage"].get("completion_tokens") or 0) for m in calls), default=0)
        big = max(((m["usage"].get("completion_tokens") or 0) for m in calls), default=0)
        reward = (s.get("reward_info") or {}).get("reward")
        end = str(s.get("termination_reason"))
        ends[end] = ends.get(end, 0) + 1
        rows.append({"task": str(s.get("task_id"))[:58], "reward": reward, "end": end.split(".")[-1], "calls": len(calls),
                     "completion": comp, "prompt_sum": prm, "peak_ctx": peak, "max_call": big,
                     "minutes": round((s.get("duration") or 0) / 60, 1)})
    print(f"\n{'task':60s}{'rew':>4s}{'end':>18s}{'calls':>6s}{'out tok':>9s}{'max call':>9s}{'peak ctx':>9s}{'min':>7s}")
    for r in rows:
        print(f"{r['task']:60s}{str(r['reward']):>4s}{r['end']:>18s}{r['calls']:>6d}{r['completion']:>9d}{r['max_call']:>9d}{r['peak_ctx']:>9d}{r['minutes']:>7.1f}")
    n = len(rows)
    if not n:
        return
    ok = [r["reward"] for r in rows if r["reward"] is not None]
    mean_out = sum(r["completion"] for r in rows) / n
    mean_min = sum(r["minutes"] for r in rows) / n
    print(f"\nepisodes {n} | passed {sum(1 for x in ok if x and x >= 1)} | endings {ends}")
    print(f"mean output tokens per episode {mean_out:,.0f} | mean minutes per episode {mean_min:.1f} "
          f"| 150 episodes one after another = about {150 * mean_min / 60:.0f} hours")
    hit_guard = sum(1 for r in rows if r["max_call"] >= MAX_TOKENS - 8)
    near_ctx = sum(1 for r in rows if ctx and r["peak_ctx"] >= 0.95 * ctx)
    print(f"episodes with a call at the {MAX_TOKENS}-token guard: {hit_guard} | episodes within 5% of the context limit ({ctx}): {near_ctx}")
    if serve_stats:
        asked = sum(r["prompt_sum"] for r in rows)
        print(f"server this run: {json.dumps(serve_stats)}")
        if asked and serve_stats.get("prompt_tokens_processed"):
            print(f"prompt tokens re-read by the server / prompt tokens sent: {serve_stats['prompt_tokens_processed'] / asked:.2f} "
                  f"(near 1.0 = no prompt caching between calls)")
    print("Five or ten tasks cannot estimate pass^1. Read the health numbers, then decide on the full cell.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", default="telecom", choices=["airline", "retail", "telecom"])
    ap.add_argument("--size", default="4b", choices=SIZES)
    ap.add_argument("--variant", default="q4", choices=PRECISIONS)
    ap.add_argument("--tasks", type=int, default=5, help="first N task ids of the domain subset")
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--concurrency", type=int, default=1, help="Ollama serves qwen35 one request at a time, so 1 is the honest setting")
    ap.add_argument("--full", action="store_true",
                    help="the full cell, same size as every calibration cell: all 50 tasks of the domain subset x num_trials from cells.json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args()

    v = variant(a.size, a.variant)
    cells = copy.deepcopy(json.load(open(rc.CELLS)))
    rc.check_frozen_inputs(cells)
    if a.full:
        a.trials = cells["num_trials"]
        a.tasks = len(cells["domains"][a.domain].get("task_ids") or []) or 50
    cells["num_trials"] = a.trials
    model = {"name": f"qwen3.5-{a.size}", "tier": "local-pilot", "litellm": "openai/" + v["ollama_name"],
             "snapshot": v["ollama_name"], "llm_args": llm_args(), "short": v["short"]}
    cells["families"]["qwen-local"] = {"max_concurrency": a.concurrency, "models": [model]}
    ids = cells["domains"][a.domain].get("task_ids")
    if ids:
        cells["domains"][a.domain]["task_ids"] = ids[: a.tasks]

    cmd = rc.build_command("qwen-local", model, a.domain, cells, a.concurrency)
    prefix = "local" if a.full else "pilot-local"
    name = f"{prefix}-{a.domain}-s1-{v['short']}-{cells['user']['short']}-{a.trials}trials-seed{cells['seed']}"
    cmd[cmd.index("--save-to") + 1] = name
    if not ids and not a.full:
        cmd += ["--num-tasks", str(a.tasks)]
    results = rc.TAU2 / "data" / "simulations" / name / "results.json"
    ctx = None
    if (HERE / "serve.env").exists():
        m = re.search(r"CTX=(\d+)", (HERE / "serve.env").read_text())
        ctx = int(m.group(1)) if m else None

    if a.report_only:
        report(results, ctx)
        return
    printable = " ".join(shlex.quote(c) for c in cmd)
    if a.dry_run:
        print(printable)
        return
    preflight(v["ollama_name"])

    offset = (HERE / "serve.log").stat().st_size if (HERE / "serve.log").exists() else 0
    man_dir = HERE / "pilot-manifests"
    man_dir.mkdir(exist_ok=True)
    manifest = {"name": name, "domain": a.domain, "tasks": a.tasks, "trials": a.trials, "concurrency": a.concurrency,
                "litellm_model": model["litellm"], "agent_llm_args": model["llm_args"], "command": printable,
                "tau2_commit": rc.tau2_commit(), "cells_json_sha256": rc.sha256_file(rc.CELLS),
                "provenance_file": (f"ollama/provenance-{a.size}-{a.variant}.txt"
                                    if (HERE / f"provenance-{a.size}-{a.variant}.txt").exists() else f"ollama/provenance-{a.variant}.txt"),
                "serve_env": (HERE / "serve.env").read_text().strip() if (HERE / "serve.env").exists() else None,
                "started_utc": datetime.now(timezone.utc).isoformat(),
                "note": "pilot, not a calibration cell; not in cells.json; not read by build_budgets.py or fill_cell.py"}
    print(f"== pilot -> {name}\n{printable}\n", flush=True)
    t0 = time.time()
    code = subprocess.call(cmd, cwd=rc.TAU2, env={**os.environ, "PYTHONUNBUFFERED": "1"}, stdin=subprocess.DEVNULL)
    manifest.update({"finished_utc": datetime.now(timezone.utc).isoformat(), "wall_seconds": round(time.time() - t0, 1),
                     "return_code": code, "serve_log_stats": serve_log_stats(offset)})
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (man_dir / f"{name}-{stamp}.json").write_text(json.dumps(manifest, indent=2))
    print(f"\n== finished in {manifest['wall_seconds'] / 60:.0f} min, return code {code}", flush=True)
    report(results, ctx, manifest["serve_log_stats"])


if __name__ == "__main__":
    main()
