#!/usr/bin/env python3
"""Post-hoc nl_assertion screen over passing episodes of a tau2 results.json.

Uses the benchmark's own NLAssertionsEvaluator (official prompt, gpt-4.1
judge at temperature 0) which the v1.0.1 grading pipeline does not run.
Flags reward==1.0 episodes containing assertions the judge marks unmet.

Run with the tau2-bench venv:
  tau2-bench/.venv/bin/python nl_screen.py <results.json> --out <report.json>
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tau2.data_model.simulation import Results
from tau2.evaluator.evaluator_nl_assertions import NLAssertionsEvaluator


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results_json", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

    results = Results.load(args.results_json)
    tasks = {t.id: t for t in results.tasks}
    passing = [
        s
        for s in results.simulations
        if s.reward_info is not None and s.reward_info.reward == 1.0
    ]
    print(f"{len(passing)} passing episodes to screen")

    def screen(sim):
        task = tasks[sim.task_id]
        # ponytail: crude 30s-sleep backoff around tau2's own retry; enough
        # for the org's 30k TPM gpt-4.1 limit at 2 workers
        for attempt in range(10):
            try:
                checks = NLAssertionsEvaluator.evaluate_nl_assertions(
                    sim.messages, task.evaluation_criteria.nl_assertions
                )
                return sim, checks
            except Exception as exc:
                if attempt == 9:
                    raise
                print(f"retry task {sim.task_id} trial {sim.trial}: {type(exc).__name__}")
                time.sleep(30)

    flagged = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for sim, checks in pool.map(screen, passing):
            unmet = [c for c in checks if not c.met]
            if unmet:
                flagged.append(
                    {
                        "task_id": sim.task_id,
                        "trial": sim.trial,
                        "unmet": [
                            {"assertion": c.nl_assertion, "reasoning": c.justification}
                            for c in unmet
                        ],
                    }
                )
                print(f"FLAG task {sim.task_id} trial {sim.trial}: {len(unmet)} unmet")

    report = {
        "source": str(args.results_json),
        "judge": "official NLAssertionsEvaluator (tau2 v1.0.1 defaults)",
        "passing_episodes": len(passing),
        "flagged_episodes": len(flagged),
        "flagged": flagged,
    }
    args.out.write_text(json.dumps(report, indent=2))
    print(
        f"{len(flagged)}/{len(passing)} passing episodes flagged -> {args.out}"
    )


if __name__ == "__main__":
    main()
