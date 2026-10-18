#!/usr/bin/env python3
"""Analyze a tau2-bench results.json for the cost-matched SAS vs MAS study.

Usage:
    python analyze_run.py path/to/results.json
    python analyze_run.py path/to/results.json --csv per_episode.csv
    python analyze_run.py path/to/results.json --csv per_episode.csv --report analysis.txt

The pass^k calculation matches tau2-bench's official combinatorial estimator:
for a task with c successes in n trials, pass^k = C(c, k) / C(n, k).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import statistics as stats
from collections import defaultdict
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any


# Database-mutating (WRITE) tools per domain, read from tau2's own tags: every
# function decorated `@is_tool(ToolType.WRITE)` in src/tau2/domains/<domain>/tools.py
# at the pinned commit. The hard-coded airline set is kept only as a fallback
# and as a check that the parser agrees with it.
AIRLINE_WRITE_TOOLS_FALLBACK = {
    "book_reservation",
    "cancel_reservation",
    "send_certificate",
    "update_reservation_baggages",
    "update_reservation_flights",
    "update_reservation_passengers",
}


def write_tools_for_domain(domain: str) -> set[str] | None:
    """Return the agent-side WRITE tool names for a domain, parsed from tau2 source."""
    import ast

    tools_py = Path(__file__).resolve().parent / "tau2-bench" / "src" / "tau2" / "domains" / domain / "tools.py"
    if not tools_py.exists():
        return AIRLINE_WRITE_TOOLS_FALLBACK if domain == "airline" else None
    names: set[str] = set()
    for node in ast.walk(ast.parse(tools_py.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and getattr(dec.func, "id", None) == "is_tool":
                for arg in dec.args:
                    if isinstance(arg, ast.Attribute) and arg.attr == "WRITE":
                        names.add(node.name)
    if domain == "airline" and names != AIRLINE_WRITE_TOOLS_FALLBACK:
        print(f"  WARNING: parsed airline write tools {sorted(names)} differ from the recorded set")
    return names or None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results_json", type=Path, help="tau2-bench results.json")
    parser.add_argument("--csv", type=Path, help="write per-episode data to CSV")
    parser.add_argument("--report", type=Path, help="write the printed report to a text file")
    return parser.parse_args()


def load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return data


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def episode_tokens(simulation: dict[str, Any]) -> dict[str, int]:
    """Sum agent-side token usage recorded on assistant messages."""
    input_tokens = output_tokens = cached_tokens = agent_calls = 0
    for message in simulation.get("messages", []):
        if message.get("role") != "assistant":
            continue
        usage = message.get("usage") or {}
        if not usage:
            continue
        agent_calls += 1
        input_tokens += usage.get("prompt_tokens") or 0
        output_tokens += usage.get("completion_tokens") or 0
        raw_usage = (message.get("raw_data") or {}).get("usage") or {}
        prompt_details = raw_usage.get("prompt_tokens_details") or {}
        cached_tokens += prompt_details.get("cached_tokens") or 0
    return {
        "in": input_tokens,
        "out": output_tokens,
        "cached": cached_tokens,
        "agent_llm_calls": agent_calls,
    }


def episode_writes(simulation: dict[str, Any], write_tools: set[str]) -> int:
    """Count database-mutating tool calls made by the AGENT (telecom users also call tools)."""
    return sum(
        1
        for message in simulation.get("messages", [])
        if message.get("role") == "assistant"
        for tool_call in (message.get("tool_calls") or [])
        if tool_call.get("name") in write_tools
    )


def task_requires_write(task: dict[str, Any], write_tools: set[str]) -> bool:
    """Return whether the gold trajectory contains a database write."""
    actions = (task.get("evaluation_criteria") or {}).get("actions") or []
    return any(
        action.get("name") in write_tools and action.get("requestor", "assistant") == "assistant"
        for action in actions
    )


def wilson(successes: int, observations: int, z: float = 1.96) -> tuple[float, float]:
    if observations == 0:
        return (0.0, 0.0)
    proportion = successes / observations
    denominator = 1 + z * z / observations
    center = (proportion + z * z / (2 * observations)) / denominator
    half_width = (
        z
        * math.sqrt(
            proportion * (1 - proportion) / observations
            + z * z / (4 * observations * observations)
        )
        / denominator
    )
    return (max(0.0, center - half_width), min(1.0, center + half_width))


def pass_hat_k(num_trials: int, success_count: int, k: int) -> float:
    """Use the estimator implemented by tau2.metrics.agent_metrics.pass_hat_k."""
    if num_trials < k:
        raise ValueError(f"Number of trials {num_trials} is less than k={k}")
    return math.comb(success_count, k) / math.comb(num_trials, k)


def task_sort_key(task_id: Any) -> tuple[int, Any]:
    text = str(task_id)
    return (0, int(text)) if text.isdigit() else (1, text)


def analyze(data: dict[str, Any], source: Path, csv_out: Path | None) -> None:
    info = data.get("info", {})
    tasks = {task["id"]: task for task in data.get("tasks", [])}
    simulations = data.get("simulations", [])
    if not simulations:
        raise ValueError("The results file contains no simulations")

    environment_info = info.get("environment_info") or {}
    domain = environment_info.get("domain_name", "?")
    write_tools = write_tools_for_domain(domain)
    reward_bases = sorted({tuple((t.get("evaluation_criteria") or {}).get("reward_basis") or []) for t in data.get("tasks", [])})

    print("=" * 68)
    print("RUN METADATA")
    print("=" * 68)
    print(f"  source      : {source.resolve()}")
    print(f"  sha256      : {sha256(source)}")
    print(f"  commit      : {info.get('git_commit', '?')[:12]}")
    print(f"  domain      : {domain}")
    print(
        f"  agent llm   : {(info.get('agent_info') or {}).get('llm', '?')}  "
        f"args={(info.get('agent_info') or {}).get('llm_args')}"
    )
    print(
        f"  user  llm   : {(info.get('user_info') or {}).get('llm', '?')}  "
        f"args={(info.get('user_info') or {}).get('llm_args')}"
    )
    print(f"  num_trials  : {info.get('num_trials')}   seed: {info.get('seed')}")
    print(f"  tasks       : {len(tasks)}   simulations: {len(simulations)}")
    print(f"  reward basis: {reward_bases}")
    print(f"  write tools : {sorted(write_tools) if write_tools else 'none configured'}")

    by_trial: dict[int, list[float]] = defaultdict(list)
    by_task: dict[Any, list[float]] = defaultdict(list)
    for simulation in simulations:
        reward = (simulation.get("reward_info") or {}).get("reward", 0.0)
        by_trial[simulation.get("trial", 0)].append(reward)
        by_task[simulation.get("task_id")].append(reward)

    print()
    print("=" * 68)
    print("PASS RATE")
    print("=" * 68)
    trial_rates = []
    for trial in sorted(by_trial):
        rewards = by_trial[trial]
        successes = sum(reward >= 1.0 for reward in rewards)
        rate = successes / len(rewards)
        trial_rates.append(rate)
        print(f"  trial {trial + 1}: {rate:6.1%}   ({successes}/{len(rewards)})")

    if len(trial_rates) > 1:
        print(f"  mean    : {stats.mean(trial_rates):6.1%}  (std {stats.stdev(trial_rates):.1%})")
    total_successes = sum(
        reward >= 1.0 for rewards in by_trial.values() for reward in rewards
    )
    lower, upper = wilson(total_successes, len(simulations))
    print(
        "  95% CI on pooled pass^1 "
        f"(Wilson, n={len(simulations)} episodes): [{lower:.1%}, {upper:.1%}]"
    )

    max_k = min(len(rewards) for rewards in by_task.values())
    for k in range(1, max_k + 1):
        task_estimates = []
        for rewards in by_task.values():
            successes = sum(reward >= 1.0 for reward in rewards)
            task_estimates.append(pass_hat_k(len(rewards), successes, k))
        estimate = stats.mean(task_estimates)
        print(f"  pass^{k}   : {estimate:6.1%}   (official tau2 estimator)")

    flaky = [
        task_id
        for task_id, rewards in by_task.items()
        if len({reward >= 1.0 for reward in rewards}) > 1
    ]
    flaky.sort(key=task_sort_key)
    print(
        f"  flaky tasks (inconsistent across trials): {len(flaky)}/{len(by_task)}"
        f"  -> {flaky[:15]}{' ...' if len(flaky) > 15 else ''}"
    )

    print()
    print("=" * 68)
    print("FAILURE STRUCTURE  (exploratory passivity-confound check)")
    print("=" * 68)
    if write_tools is None:
        print(f"  skipped: no write-tool taxonomy is configured for domain {domain!r}")
    else:
        buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "pass": 0})
        wrongful: list[tuple[Any, Any, int]] = []
        inaction: list[tuple[Any, Any]] = []
        other: list[tuple[Any, Any, int]] = []
        for simulation in simulations:
            task_id = simulation.get("task_id")
            task = tasks.get(task_id, {})
            needs_write = task_requires_write(task, write_tools)
            key = "needs-write" if needs_write else "no-write (refuse/inform)"
            reward = (simulation.get("reward_info") or {}).get("reward", 0.0)
            buckets[key]["n"] += 1
            if reward >= 1.0:
                buckets[key]["pass"] += 1
                continue
            writes = episode_writes(simulation, write_tools)
            if not needs_write and writes > 0:
                wrongful.append((task_id, simulation.get("trial"), writes))
            elif needs_write and writes == 0:
                inaction.append((task_id, simulation.get("trial")))
            else:
                other.append((task_id, simulation.get("trial"), writes))

        for label, values in sorted(buckets.items()):
            print(
                f"  {label:26s} pass {values['pass']:4d}/{values['n']:<4d} = "
                f"{values['pass'] / max(values['n'], 1):6.1%}"
            )
        print()
        print(f"  FAILURES BY HEURISTIC TYPE (total {len(wrongful) + len(inaction) + len(other)}):")
        print(f"    wrongful write  (acted when gold has no write): {len(wrongful):4d}")
        print(f"    inaction        (no write when gold has write): {len(inaction):4d}")
        print(f"    other/incorrect write or communication       : {len(other):4d}")
        if wrongful:
            print(f"    wrongful-write examples: {wrongful[:8]}")
        if inaction:
            print(f"    inaction examples      : {inaction[:8]}")
        print("  Note: this is a heuristic taxonomy, not a causal failure annotation.")

    terminations: dict[str, int] = defaultdict(int)
    for simulation in simulations:
        terminations[simulation.get("termination_reason", "?")] += 1
    print()
    print(
        "  termination reasons: "
        + ", ".join(f"{key}={value}" for key, value in sorted(terminations.items()))
    )

    print()
    print("=" * 68)
    print("TOKEN ACCOUNTING & COST  (per episode)")
    print("=" * 68)
    rows: list[dict[str, Any]] = []
    total_input = total_output = total_cached = 0
    total_agent_cost = total_user_cost = 0.0
    for simulation in simulations:
        tokens = episode_tokens(simulation)
        agent_cost = simulation.get("agent_cost") or 0.0
        user_cost = simulation.get("user_cost") or 0.0
        total_input += tokens["in"]
        total_output += tokens["out"]
        total_cached += tokens["cached"]
        total_agent_cost += agent_cost
        total_user_cost += user_cost
        rows.append(
            {
                "task_id": simulation.get("task_id"),
                "trial": simulation.get("trial"),
                "reward": (simulation.get("reward_info") or {}).get("reward", 0.0),
                "input_tokens": tokens["in"],
                "output_tokens": tokens["out"],
                "cached_input_tokens": tokens["cached"],
                "agent_llm_calls": tokens["agent_llm_calls"],
                "writes": episode_writes(simulation, write_tools or set()),
                "agent_cost": agent_cost,
                "user_cost": user_cost,
                "duration_s": simulation.get("duration"),
                "termination": simulation.get("termination_reason"),
            }
        )

    episode_count = len(simulations)
    avg_agent_cost = total_agent_cost / episode_count
    avg_user_cost = total_user_cost / episode_count
    print(f"  agent input tokens : {total_input / episode_count:10,.0f}  (total {total_input:,})")
    print(
        f"    of which cached  : {total_cached / episode_count:10,.0f}  "
        f"({total_cached / max(total_input, 1):.0%} hit rate)"
    )
    print(f"  agent output tokens: {total_output / episode_count:10,.0f}  (total {total_output:,})")
    print(
        f"  agent LLM calls    : "
        f"{sum(row['agent_llm_calls'] for row in rows) / episode_count:10,.1f}"
    )
    print(f"  agent cost         : ${avg_agent_cost:9.5f}  (total ${total_agent_cost:.2f})")
    print(f"  user  cost         : ${avg_user_cost:9.5f}  (total ${total_user_cost:.2f})")
    print(f"  TOTAL cost/episode : ${avg_agent_cost + avg_user_cost:9.5f}")
    print()
    print("  >> Budget projection for 278 tasks x 3 trials x 4 systems")
    episodes_per_system = 278 * 3
    mas_systems = 3
    for multiplier, label in (
        (1.0, "if MAS agent cost == SAS"),
        (2.0, "if MAS agent cost is 2x SAS"),
        (3.0, "if MAS agent cost is 3x SAS"),
    ):
        projected = episodes_per_system * (
            avg_agent_cost
            + avg_user_cost
            + mas_systems * (multiplier * avg_agent_cost + avg_user_cost)
        )
        print(f"       {label:31s}: ~${projected:8.2f}")
    print("     Assumes one SAS plus three MAS systems and fixed user-simulator cost.")

    if csv_out:
        csv_out.parent.mkdir(parents=True, exist_ok=True)
        rows.sort(key=lambda row: (task_sort_key(row["task_id"]), row["trial"]))
        with csv_out.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file, fieldnames=list(rows[0].keys()), lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n  per-episode CSV written to {csv_out.resolve()}")

    print()
    print("=" * 68)
    print("THRESHOLD POSITIONING (Kim et al. ~45% selection rule)")
    print("=" * 68)
    mean_pass_1 = stats.mean(trial_rates)
    side = "ABOVE" if mean_pass_1 > 0.45 else "BELOW"
    print(f"  SAS pass^1 = {mean_pass_1:.1%}  ->  {side} the ~45% saturation threshold")
    print(
        "  Rule predicts generic MAS gain: "
        f"{'zero-to-negative' if mean_pass_1 > 0.45 else 'possibly positive'}"
    )
    print("  Treat this run as exploratory unless model snapshots and protocol were pre-registered.")


def main() -> None:
    args = parse_args()
    source = args.results_json.resolve()
    data = load(source)

    output = io.StringIO()
    with redirect_stdout(output):
        analyze(data, source, args.csv)
    report = output.getvalue()
    print(report, end="")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report, encoding="utf-8")
        print(f"Report written to {args.report.resolve()}")


if __name__ == "__main__":
    main()
