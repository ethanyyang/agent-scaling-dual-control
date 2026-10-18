# Exploratory airline SAS baseline

This directory contains the derived analysis for the 50-task airline run with
three trials per task (150 episodes total).

## Result

- pass^1: 40.0%
- pass^2: 26.0%
- pass^3: 18.0%
- Trial pass rates: 34.0%, 48.0%, and 38.0%
- Recorded run cost: $1.646436 total, or $0.010976 per episode
- Position relative to the Kim et al. selection rule: below 45%

The pass^k values were independently checked against
`tau2.metrics.agent_metrics.compute_metrics` at tau2-bench commit
`c3398666e6559e3a063da3fc04b5acf7f941464e`.

## Provenance

Input:

`tau2-bench/data/simulations/exploratory-airline-sas-gpt41mini-full-3trials-seed300/results.json`

Input SHA-256:

`0e6a9bb1c33951e3ae51e0d1f32996d8f4d9adf18d9631119f244ba873ac3bd7`

The run metadata names the model alias `gpt-4.1-mini`. The raw response
metadata records `gpt-4.1-mini-2025-04-14` for all 1,571 agent calls and all
1,094 user-simulator calls. Both used temperature 0. The root seed was 300.

Generated with:

```bash
python3 analyze_run.py \
  tau2-bench/data/simulations/exploratory-airline-sas-gpt41mini-full-3trials-seed300/results.json \
  --csv results/exploratory-airline-sas-gpt41mini-full-3trials-seed300/per_episode.csv \
  --report results/exploratory-airline-sas-gpt41mini-full-3trials-seed300/analysis.txt
```

Artifacts:

- `analysis.txt`: human-readable run summary
- `per_episode.csv`: one row per episode for downstream analysis

The exact raw result is published as a compressed GitHub Release asset:

- [tau2-airline-sas-gpt41mini-3trials-seed300-results.json.gz](https://github.com/ethanyyang/transfer-testing/releases/download/pilot-airline-sas-gpt41mini-seed300/tau2-airline-sas-gpt41mini-3trials-seed300-results.json.gz)
- Compressed size: 1,176,855 bytes
- Compressed SHA-256:
  `8c1d1afc480a446983e8273cc59c44fdae7d8a6a98b6549e98bf4f51a2059761`

Decompressing that asset reproduces the input file whose checksum is recorded
above. The archive was made deterministically with `gzip -n -9`.

## NL-assertion re-grade (full sample)

All 150 episodes re-graded with the official evaluator under
`ALL_WITH_NL_ASSERTIONS` (`nl_regrade.py`, judge gpt-4.1-2025-04-14 temp 0),
mirroring the gate run's re-grade. Airline's reward_basis is
[DB, COMMUNICATE], so nl results are recorded but do not enter the reward;
all 150 regraded rewards match the originals exactly.
Full report: `nl_regrade_all150.json`.

| Quantity | Pilot (gpt-4.1-mini) | Gate (gemini-3-flash high) |
|---|---|---|
| Assertion-level pass rate | 207/369 = **56.1%** | 323/369 = 87.5% |
| Episodes with all assertions met | 55/150 = 36.7% | 119/150 = 79.3% |
| … among reward-1.0 episodes | 51/60 = 85.0% (9 flagged) | 109/121 = 90.1% (12 flagged) |
| … among reward-0 episodes | 4/90 = 4.4% | 10/29 = 34.5% |
| Hypothetical pass^1 if nl entered the reward | 51/150 = **34.0%** (vs 40.0% official) | 109/150 = 72.7% (vs 80.7%) |

Notable pass-flags (reward 1.0 but judge-unmet assertions): task 34 trial 0
("Agent should not make any changes"), task 0 trial 2 ("should refuse to
proceed with the cancellation"), task 45 trial 2 ("should not change PEP4E0
flight"), task 4 trials 1–2 (hallucinated-cancellation compensation — same
failure mode as the gate run's task 4). Judge flags are LLM judgments pending
human spot-check.

## Interpretation cautions

This is an exploratory baseline, not a preregistered confirmatory result. The
Wilson interval in `analysis.txt` treats the 150 episodes as independent; a
confirmatory analysis should account for repeated trials nested within tasks.
The failure categories are a heuristic based on whether the gold trajectory
contains a database write, not manually validated causal annotations.

The saved cost is the cost attached to the final 150 trajectories. Because the
run used retries after rate limiting, provider billing can be higher if failed
or discarded attempts were billed.
