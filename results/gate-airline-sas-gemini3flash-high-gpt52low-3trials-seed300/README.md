# Gate: airline SAS baseline, gemini-3-flash-preview (high) × gpt-5.2 user (low)

50-task airline `base` split, 3 trials per task (150 episodes), seed 300,
tau2-bench v1.0.1 commit `c3398666`.

## Result

- pass^1: 80.7%  (trials: 78.0%, 78.0%, 86.0%; std 4.6pp)
- pass^2: 76.0%  ·  pass^3: 74.0%
- Wilson 95% CI on pooled pass^1: [73.6%, 86.2%]
- Flaky tasks (inconsistent across trials): 7/50
- Position relative to the Kim et al. selection rule: **ABOVE 45%**, CI does
  not straddle. Rule predicts generic-MAS gain zero-to-negative for this cell.
- Recorded run cost: $8.52 total ($6.85 agent + $1.67 user), $0.0568/episode
- Zero infrastructure errors in the final 150 episodes

## Configuration

- Agent: `gemini/gemini-3-flash-preview`, `{"reasoning_effort": "high"}`.
  Raw responses record snapshot `gemini-3-flash-preview` for all 1,737 agent
  calls. No temperature was set (reasoning mode).
- User simulator: `gpt-5.2`, `{"reasoning_effort": "low"}`. Raw responses
  record snapshot `gpt-5.2-2025-12-11` (662 calls carry model metadata).
- Originally requested agent was `gemini-3-pro-preview`; the Gemini API has
  retired it (404, "use gemini-3.1-pro-preview"). The user chose
  `gemini-3-flash-preview` instead.
- Concurrency 10, max-retries 8, retry-delay 20s.

## Provenance

Input:

`tau2-bench/data/simulations/gate-airline-sas-gemini3flash-high-gpt52low-3trials-seed300/results.json`

Input SHA-256:

`e188ae2d1c160822a42cedfdac430c013ac3e3bff998e9d856c98613a0e38278`

Generated with:

```bash
python3 analyze_run.py \
  tau2-bench/data/simulations/gate-airline-sas-gemini3flash-high-gpt52low-3trials-seed300/results.json \
  --csv results/gate-airline-sas-gemini3flash-high-gpt52low-3trials-seed300/per_episode.csv \
  --report results/gate-airline-sas-gemini3flash-high-gpt52low-3trials-seed300/analysis.txt
```

Note: `analyze_run.py` was patched before this analysis to tolerate
`cached_tokens: null` in Gemini usage metadata (the pilot's OpenAI responses
always carried integers). The pilot numbers are unaffected by the patch.

## NL-assertion re-grade (full sample)

All 150 episodes re-graded with the official evaluator under
`ALL_WITH_NL_ASSERTIONS` (`nl_regrade.py`, judge gpt-4.1-2025-04-14 temp 0).
Airline's reward_basis is [DB, COMMUNICATE], so nl results are recorded but
do not enter the reward; all 150 regraded rewards match the originals exactly.
Full report: `nl_regrade_all150.json`.

| Quantity | Value |
|---|---|
| Assertion-level pass rate | 323/369 = **87.5%** |
| Episodes with all assertions met | 119/150 = 79.3% |
| … among reward-1.0 episodes | 109/121 = 90.1% (12 flagged — same 12 as `nl_assertion_screen.json`) |
| … among reward-0 episodes | 10/29 = 34.5% |
| Hypothetical pass^1 if nl entered the reward | 109/150 = **72.7%** (vs 80.7% official) |

Flagged in all 3 trials: tasks 2, 38 (passing) and 7, 32, 39, 44 (failing);
task 32 met 0/2 assertions in every trial. Judge flags are LLM judgments
pending human spot-check.

## Interpretation cautions

- **Not simulator-matched to the pilot.** The gpt-4.1-mini pilot used
  gpt-4.1-mini as the user simulator; this run uses gpt-5.2 (low). Per the
  documented simulator sensitivity (Quesma: +22.7% relative from a prompt
  change alone), the two airline rows are not directly comparable until one
  is rerun under a common simulator.
- Exploratory, not preregistered: ANALYSIS.md was not frozen before this run.
- Cached-token accounting: Gemini reports implicit cache hits differently
  from OpenAI; the 45% figure is not comparable to the pilot's 88%.
- The Wilson interval treats 150 episodes as independent; trials are nested
  within tasks.
- Cost is the cost attached to the final trajectories; billed cost can be
  higher due to retried calls (a handful of early free-tier 429s, plus any
  rate-limit retries during the run).
