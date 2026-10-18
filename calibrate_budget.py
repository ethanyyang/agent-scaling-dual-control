#!/usr/bin/env python3
"""Compute the §4.2 calibration values for one S1 results.json.

Per episode: sum of agent completion tokens (hidden reasoning included, as the
provider reports it). Per call: agent completion tokens per LLM call.
Outputs S1 mean, P75 (= B_1x), 0.5x, 2x, per-call P95 (= c), per-call median
(feeds a_min and w in docs/budget-protocol.md), reasoning-token coverage, and
the SHA-256 of the results file, as JSON. Uses numpy-free percentiles
(nearest-rank on the sorted list) so the numbers are reproducible by hand.

Usage: python calibrate_budget.py tau2-bench/data/simulations/<run>/results.json
Importable: `from calibrate_budget import calibrate`.
"""
from __future__ import annotations
import hashlib, json, statistics, sys
from pathlib import Path


def pct(values: list[int], p: float) -> int:
    xs = sorted(values)
    k = max(1, int(round(p / 100 * len(xs))))          # nearest-rank
    return xs[min(k, len(xs)) - 1]


def calibrate(path: str | Path) -> dict:
    p = Path(path)
    d = json.load(open(p))
    per_episode, per_call = [], []
    calls = calls_with_details = 0
    for sim in d["simulations"]:
        ep = 0
        for m in sim["messages"]:
            if m.get("role") != "assistant" or not m.get("usage"):
                continue
            c = int(m["usage"].get("completion_tokens") or 0)
            ep += c
            per_call.append(c)
            calls += 1
            det = ((m.get("raw_data") or {}).get("usage") or {}).get("completion_tokens_details") or {}
            if det.get("reasoning_tokens") is not None:
                calls_with_details += 1
        per_episode.append(ep)
    b1x = pct(per_episode, 75)
    return {
        "results_file": str(p), "results_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        "episodes": len(per_episode), "agent_calls": calls,
        "calls_with_reasoning_details": calls_with_details,
        "S1_mean_completion_per_episode": round(statistics.mean(per_episode), 1),
        "S1_P75_completion_per_episode (B_1x)": b1x,
        "B_0.5x": b1x // 2, "B_2x": b1x * 2,
        "S1_max_completion_per_episode": max(per_episode),
        "share_of_episodes_above_B_1x": round(sum(e > b1x for e in per_episode) / len(per_episode), 3),
        "per_call_median": pct(per_call, 50), "per_call_P95 (c)": pct(per_call, 95), "per_call_max": max(per_call),
    }


if __name__ == "__main__":
    print(json.dumps(calibrate(sys.argv[1]), indent=2))
