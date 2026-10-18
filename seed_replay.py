#!/usr/bin/env python3
"""Seed replay test: M1 (as built), retail x qwen3.5-4b-oct26, trial-2 anomaly.

Background (ANALYSIS.md CHANGELOG, 2026-10-14 and 2026-10-15). In trial 2 (seed 361454) the
orchestrator's plan and forced-message calls ran into long hidden reasoning, often cut at the
per-call cap with no visible output; trials 0 and 1 (seeds 626729, 373753) did not. tau2 writes
the trial seed into llm_args, so every agent call in a trial reaches Ollama with the same
sampling seed. The user simulator receives the same trial seed, so trial-2 customer messages
may differ as well. A third candidate is the state of the Ollama server during trial 2.

This script rebuilds the FIRST orchestrator plan call of an episode exactly as M1 builds it
(same agent code, budget, base prompt, greeting, and the customer's first message taken from
the recorded trajectory) and sends it under several seeds. Two factors:
  prompt source: the customer's first message from trial 1 or from trial 2 (same task);
  seed: 361454 (trial 2), 373753 (trial 1), or none.
Tasks: every task whose trial-2 first plan call was cut at the cap ("cut" tasks), plus
N_CONTROL control tasks whose trial-2 first plan call was not cut.

Reading rule (fixed before the run; CHANGELOG 2026-10-15). k = number of cut tasks,
hi = ceil(2k/3), lo = max(1, k // 6). Counts are first-plan cuts on the cut tasks, first repeat:
  seed explanation supported:   trial-2 prompts under seed 361454 cut >= hi AND
                                trial-2 prompts with no seed cut <= lo;
  prompt explanation supported: trial-2 prompts cut >= hi under every seed condition
                                (none included) AND trial-1 prompts cut <= lo under every one;
  neither reproduced:           trial-2 prompts cut <= lo under 361454 and under no seed
                                (server state during trial 2 becomes the leading explanation);
  anything else:                inconclusive.
Repeats under the same seed also test determinism (identical reply hash).
The replay reads no reward, and its outcome does not change how the cell is reported
(pooled over all three trials as registered, per trial as a secondary view).

Run from tau2-bench on the Mac, on a freshly restarted server, with nothing else running:
  bash ../ollama/stop_ollama.sh && bash ../ollama/serve_only.sh   # must not print WRONG BUILD
  uv run python ../seed_replay.py --dry-run    # rebuild the prompts, check them, no model calls
  uv run python ../seed_replay.py              # the test (about 120 calls, 1 to 2 hours)
Output: results/seed-replay-2026-10-15/calls.jsonl (resumable) and summary.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics as st
import sys
import time
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
try:  # same as run_m1.py
    from dotenv import load_dotenv

    load_dotenv(ROOT / "tau2-bench" / ".env")
except Exception:
    pass

from tau2.data_model.message import UserMessage  # noqa: E402
from tau2.orchestrator.orchestrator import DEFAULT_FIRST_AGENT_MESSAGE  # noqa: E402
from tau2.runner.build import build_environment  # noqa: E402

import m1_agent  # noqa: E402
from budget_layer import BudgetConfig, load_base_prompt_template, sha256_text  # noqa: E402
from m1_agent import DEFAULT_READ_CALL_LIMIT, TurnLog, make_m1_factory  # noqa: E402

RUN = "m1-retail-qwen35-4b-q4-oct26-ollama-gpt52low-b4x-capb1x-3trials-seed300"
RESULTS = ROOT / "tau2-bench" / "data" / "simulations" / RUN / "results.json"
MANIFEST = ROOT / "results" / "calibration-manifests" / f"{RUN}.json"
OUT = ROOT / "results" / "seed-replay-2026-10-15"
MA = "transfer_testing_multi_agent"
BUDGET_KEY = "retail x qwen3.5-4b-oct26"
MODEL_NAME = "qwen3.5-4b-oct26"
N_CONTROL = 4


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def first_user_and_plan(sim: dict) -> tuple[str, dict]:
    user = next(m for m in sim["messages"] if m["role"] == "user")
    for m in sim["messages"]:
        rd = m.get("raw_data") or {}
        for c in (rd.get(MA) or {}).get("components", []):
            if c["call_name"] == "m1_plan":
                return user.get("content") or "", c
    raise ValueError(f"no plan call in task {sim['task_id']} trial {sim['trial']}")


def select_tasks(by: dict, tasks: list[str]) -> tuple[list[str], list[str]]:
    cut, rest = [], []
    for t in tasks:
        _, plan = first_user_and_plan(by[(t, 2)])
        (cut if plan.get("truncated") else rest).append(t)
    tok = {t: first_user_and_plan(by[(t, 2)])[1]["usage"]["completion_tokens"] for t in rest}
    med = st.median(tok.values())
    control = sorted(rest, key=lambda t: (abs(tok[t] - med), int(t)))[:N_CONTROL]
    return cut, sorted(control, key=int)


def usage_of(c: dict) -> dict:
    u = c.get("usage") or {}
    return u if isinstance(u, dict) else getattr(u, "model_dump", lambda: {})()


def build(args):
    sims = json.load(open(RESULTS))["simulations"]
    by = {(s["task_id"], s["trial"]): s for s in sims}
    seeds = {s["trial"]: s["seed"] for s in sims}
    tasks = sorted({s["task_id"] for s in sims}, key=int)
    cut, control = select_tasks(by, tasks)

    manifest = json.load(open(MANIFEST))
    budgets = json.load(open(ROOT / "budgets.json"))
    b = budgets.get("cells", budgets)[BUDGET_KEY]  # budgets.json keeps the cells under "cells"
    cfg = BudgetConfig.from_calibration(b["B_1x"], b["c"], b["per_call_median"], multiplier=4.0, cap_rule="b1x")
    assert cfg.limit == manifest["budget"]["limit"] and cfg.per_call_cap == manifest["budget"]["per_call_cap"], "budget differs from the run"
    prompt_hash = sha256_text(load_base_prompt_template())
    assert prompt_hash == manifest["base_prompt_sha256"], "base prompt differs from the run"
    assert manifest["orchestrator_tool_definitions"] is False and manifest["read_call_limit"] == DEFAULT_READ_CALL_LIMIT
    factory = make_m1_factory(cfg, prompt_hash, DEFAULT_READ_CALL_LIMIT, 1.0, False)
    cells = json.load(open(ROOT / "cells.json"))
    model = next(m for m in cells["families"]["qwen"]["models"] if m["name"] == MODEL_NAME)
    assert model["llm_args"] == manifest["agent_llm_args"], "llm_args differ from the run"
    env = build_environment("retail")
    conds = [seeds[2], seeds[1], None]
    return dict(by=by, seeds=seeds, cut=cut, control=control, factory=factory, model=model,
                tools=env.get_tools(), policy=env.get_policy(), conds=conds)


def one_plan_call(ctx: dict, seed, user_text: str):
    llm_args = deepcopy(ctx["model"]["llm_args"])
    if seed is not None:
        llm_args["seed"] = seed  # what tau2's set_seed does for the whole trial
    agent = ctx["factory"](tools=ctx["tools"], domain_policy=ctx["policy"], llm=ctx["model"]["litellm"], llm_args=llm_args)
    state = agent.get_init_state(message_history=[deepcopy(DEFAULT_FIRST_AGENT_MESSAGE)])
    state.messages.append(UserMessage(role="user", content=user_text))  # as _generate_next_message does
    state.turn_index += 1
    turn = TurnLog()
    t0 = time.time()
    agent._orchestrator_plan(state, turn, None)  # the first plan call of the episode, note None
    return turn, time.time() - t0


def dry_run(ctx: dict) -> None:
    """Rebuild every prompt without calling the model: report size, hash and the cap sent."""
    seen = []
    real = m1_agent.metered_generate

    def capture(**kw):
        from tau2.data_model.message import AssistantMessage
        seen.append(kw)
        return AssistantMessage(role="assistant", content="{}", raw_data={"transfer_testing_call": {
            "truncated": False, "finish_reason": "stop", "max_tokens_sent": kw["budget"].allowance(kw.get("per_call_cap"))}})

    m1_agent.metered_generate = capture
    try:
        print(f"cut tasks {ctx['cut']}  control tasks {ctx['control']}  seeds {ctx['conds']}")
        for t in ctx["cut"] + ctx["control"]:
            for src in (1, 2):
                text, plan = first_user_and_plan(ctx["by"][(t, src)])
                seen.clear()
                turn, _ = one_plan_call(ctx, ctx["seeds"][src], text)
                kw = seen[0]
                prompt = "\n".join(str(m.content) for m in kw["messages"])
                u = usage_of(plan)
                print(f"task {t:>4} src t{src}: prompt {len(prompt):6d} chars sha {sha(prompt)} | cap sent "
                      f"{turn.components[0]['max_tokens_sent']} (run {plan.get('max_tokens_sent')}) | run prompt_tokens "
                      f"{u.get('prompt_tokens')} completion {u.get('completion_tokens')} cut {plan.get('truncated')} | seed in args "
                      f"{kw['llm_args'].get('seed')}")
    finally:
        m1_agent.metered_generate = real


def plan_calls(ctx: dict, reps_seeded: int, reps_none: int) -> list[dict]:
    jobs = []
    for rep in range(max(reps_seeded, reps_none)):
        batch = []
        for t in ctx["cut"] + ctx["control"]:
            for src in (1, 2):
                for seed in ctx["conds"]:
                    if rep < (reps_none if seed is None else reps_seeded):
                        batch.append(dict(task=t, group="cut" if t in ctx["cut"] else "control", src=src, seed=seed, rep=rep))
        random.Random(300 + rep).shuffle(batch)  # interleave conditions so drift over time hits all of them
        jobs += batch
    return jobs


def key(j: dict) -> str:
    return f"{j['task']}|{j['src']}|{j['seed']}|{j['rep']}"


def run(ctx: dict, reps_seeded: int, reps_none: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "calls.jsonl"
    done = {key(json.loads(line)) for line in open(path)} if path.exists() else set()
    jobs = plan_calls(ctx, reps_seeded, reps_none)
    print(f"{len(jobs)} calls planned, {len(done)} already done", flush=True)
    for i, j in enumerate(jobs):
        if key(j) in done:
            continue
        text, plan = first_user_and_plan(ctx["by"][(j["task"], j["src"])])
        turn, secs = one_plan_call(ctx, j["seed"], text)
        c = turn.components[0]
        u = usage_of(c)
        reply = turn.replies[0]
        rec = dict(j, prompt_tokens=u.get("prompt_tokens"), completion_tokens=u.get("completion_tokens"),
                   truncated=bool(c["truncated"]), finish_reason=c["finish_reason"], empty=not c["output"],
                   reply_sha=sha(json.dumps([reply.content, getattr(reply, "reasoning_content", None)], default=str)),
                   n_calls=len(turn.components), seconds=round(secs, 1),
                   run_prompt_tokens=usage_of(plan).get("prompt_tokens"),
                   run_completion_tokens=usage_of(plan).get("completion_tokens"), run_truncated=plan.get("truncated"))
        with open(path, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"[{i + 1}/{len(jobs)}] task {j['task']} src t{j['src']} seed {j['seed']} rep {j['rep']}: "
              f"{rec['completion_tokens']} tokens{' CUT' if rec['truncated'] else ''}{' EMPTY' if rec['empty'] else ''} "
              f"({secs:.0f}s; prompt {rec['prompt_tokens']} vs run {rec['run_prompt_tokens']})", flush=True)
    summarize(ctx)


def summarize(ctx: dict) -> dict:
    recs = [json.loads(line) for line in open(OUT / "calls.jsonl")]
    s2, s1 = ctx["seeds"][2], ctx["seeds"][1]
    k = len(ctx["cut"])
    hi, lo = math.ceil(2 * k / 3), max(1, k // 6)

    def sel(**f):
        return [r for r in recs if all(r[a] == b for a, b in f.items())]

    def cuts(**f):
        return sum(r["truncated"] for r in sel(rep=0, group="cut", **f))

    table = []
    for src in (1, 2):
        for seed in ctx["conds"]:
            for group in ("cut", "control"):
                rs = sel(src=src, seed=seed, group=group)
                if rs:
                    table.append(dict(src=src, seed=seed, group=group, n=len(rs),
                                      median_tokens=st.median(r["completion_tokens"] or 0 for r in rs),
                                      cut=sum(r["truncated"] for r in rs), empty=sum(r["empty"] for r in rs)))
    pairs = {}
    for r in recs:
        if r["seed"] is not None:
            pairs.setdefault((r["task"], r["src"], r["seed"]), []).append(r["reply_sha"])
    full = [v for v in pairs.values() if len(v) >= 2]
    identical = sum(len(set(v)) == 1 for v in full)
    prompt_mismatch = sum(r["prompt_tokens"] != r["run_prompt_tokens"] for r in recs)

    c = dict(t2_seed2=cuts(src=2, seed=s2), t2_seed1=cuts(src=2, seed=s1), t2_none=cuts(src=2, seed=None),
             t1_seed2=cuts(src=1, seed=s2), t1_seed1=cuts(src=1, seed=s1), t1_none=cuts(src=1, seed=None))
    if c["t2_seed2"] >= hi and c["t2_none"] <= lo:
        verdict = "seed explanation supported"
    elif min(c["t2_seed2"], c["t2_seed1"], c["t2_none"]) >= hi and max(c["t1_seed2"], c["t1_seed1"], c["t1_none"]) <= lo:
        verdict = "prompt explanation supported"
    elif c["t2_seed2"] <= lo and c["t2_none"] <= lo:
        verdict = "neither reproduced (server state during trial 2 is the leading explanation)"
    else:
        verdict = "inconclusive"
    out = dict(run=RUN, cut_tasks=ctx["cut"], control_tasks=ctx["control"], k=k, hi=hi, lo=lo,
               first_repeat_cuts_on_cut_tasks=c, verdict=verdict, table=table,
               determinism=dict(seeded_pairs=len(full), identical=identical),
               prompt_token_mismatches_vs_run=prompt_mismatch, calls=len(recs))
    json.dump(out, open(OUT / "summary.json", "w"), indent=1)
    print(json.dumps(out, indent=1))
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="rebuild the prompts and check them; no model calls")
    ap.add_argument("--reps-seeded", type=int, default=2)
    ap.add_argument("--reps-none", type=int, default=2)
    ap.add_argument("--summary", action="store_true", help="only re-summarize calls.jsonl")
    a = ap.parse_args(argv)
    ctx = build(a)
    if a.summary:
        summarize(ctx)
    elif a.dry_run:
        dry_run(ctx)
    else:
        run(ctx, a.reps_seeded, a.reps_none)


if __name__ == "__main__":
    main()
