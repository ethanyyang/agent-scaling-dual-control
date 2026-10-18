#!/usr/bin/env python3
"""Full re-grade of a tau2 results.json under ALL_WITH_NL_ASSERTIONS.

Calls the official evaluate_simulation with the same arguments the official
re-grading script (tau2.scripts.evaluate_trajectories) uses, for EVERY
episode, so nl_assertion checks are recorded for the full sample — including
failing episodes the nl_screen.py pass skipped. For airline (reward_basis
[DB, COMMUNICATE]) the nl results do not enter the reward, so the regraded
reward doubles as a consistency check against the original.

Run with the tau2-bench venv:
  tau2-bench/.venv/bin/python nl_regrade.py <results.json> --out <report.json>
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tau2.data_model.simulation import Results
from tau2.evaluator.evaluator import EvaluationType, evaluate_simulation
from tau2.scripts.evaluate_trajectories import (
    _build_eval_env_kwargs,
    get_communication_mode,
    is_solo_mode,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results_json", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

    results = Results.load(args.results_json)
    domain = results.info.environment_info.domain_name
    solo_mode = is_solo_mode(results)
    tasks = {t.id: t for t in results.tasks}
    print(f"{len(results.simulations)} episodes to re-grade ({domain})")

    def regrade(sim):
        task = tasks[sim.task_id]
        # ponytail: same crude 30s-sleep backoff as nl_screen.py; enough for
        # the org's 30k TPM gpt-4.1 judge limit at 2 workers
        for attempt in range(10):
            try:
                reward_info = evaluate_simulation(
                    domain=domain,
                    task=task,
                    simulation=sim,
                    evaluation_type=EvaluationType.ALL_WITH_NL_ASSERTIONS,
                    solo_mode=solo_mode,
                    mode=get_communication_mode(results, sim),
                    env_kwargs=_build_eval_env_kwargs(domain, task),
                    strict_replay=False,
                )
                return sim, reward_info
            except Exception as exc:
                if attempt == 9:
                    raise
                print(f"retry task {sim.task_id} trial {sim.trial}: {type(exc).__name__}")
                time.sleep(30)

    episodes = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for sim, ri in pool.map(regrade, results.simulations):
            checks = ri.nl_assertions or []
            unmet = [c for c in checks if not c.met]
            episodes.append(
                {
                    "task_id": sim.task_id,
                    "trial": sim.trial,
                    "original_reward": sim.reward_info.reward,
                    "regraded_reward": ri.reward,
                    "nl_total": len(checks),
                    "nl_met": len(checks) - len(unmet),
                    "unmet": [
                        {"assertion": c.nl_assertion, "reasoning": c.justification}
                        for c in unmet
                    ],
                }
            )
            tag = f"task {sim.task_id} trial {sim.trial}"
            if unmet:
                print(f"FLAG {tag}: {len(unmet)}/{len(checks)} unmet")
            else:
                print(f"ok   {tag}")

    n = len(episodes)
    nl_clean = sum(1 for e in episodes if e["nl_met"] == e["nl_total"])
    total_asserts = sum(e["nl_total"] for e in episodes)
    met_asserts = sum(e["nl_met"] for e in episodes)
    passing = [e for e in episodes if e["original_reward"] == 1.0]
    failing = [e for e in episodes if e["original_reward"] != 1.0]
    reward_mismatches = [
        {k: e[k] for k in ("task_id", "trial", "original_reward", "regraded_reward")}
        for e in episodes
        if e["regraded_reward"] != e["original_reward"]
    ]

    report = {
        "source": str(args.results_json),
        "evaluation_type": "all_with_nl_assertions",
        "judge": "official NLAssertionsEvaluator (tau2 v1.0.1 defaults)",
        "episodes": n,
        "nl_clean_episodes": nl_clean,
        "assertions_total": total_asserts,
        "assertions_met": met_asserts,
        "nl_clean_among_passing": sum(
            1 for e in passing if e["nl_met"] == e["nl_total"]
        ),
        "passing_episodes": len(passing),
        "nl_clean_among_failing": sum(
            1 for e in failing if e["nl_met"] == e["nl_total"]
        ),
        "failing_episodes": len(failing),
        "reward_mismatches": reward_mismatches,
        "per_episode": episodes,
    }
    args.out.write_text(json.dumps(report, indent=2))
    print(
        f"\nnl-clean episodes: {nl_clean}/{n}"
        f"  |  assertions met: {met_asserts}/{total_asserts}"
        f"  |  reward mismatches vs original: {len(reward_mismatches)}"
        f"\n-> {args.out}"
    )


if __name__ == "__main__":
    main()
