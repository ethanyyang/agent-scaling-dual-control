# Secondary analyses and validity audit, 2026-09-26

Scripts: `~/work/validity.py`, `orders.py`, `decomp.py`, `h6.py`, `power12.py` (copies in this folder). Cells: the 12 H1 grid cells at k = 4 (plus telecom x qwen3.5-4b where stated). Seed 300; task-cluster bootstrap, 2,000 resamples.

## 1. G1 validity table (M1 grid cells at k = 4)

| cell | write orders | as issued | keys corrected by DB agent | invented tool name, mapped | refused or diverted | value changed | cut calls | cut tokens | double-cut turns (exhaustion / other) | JSON / cut text to customer | exhausted | median utilisation |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|
| airline x gpt-5-nano | 265 | 16% | 41% | 26% | 14% | 3% | 0.3% | 0.3% | 0 / 0 | 0 / 0 | 35/150 | 0.50 |
| retail x gpt-5-nano | 198 | 10% | 22% | 57% | 9% | 2% | 0.4% | 0.5% | 0 / 0 | 0 / 0 | 24/150 | 0.63 |
| telecom x gpt-5-nano | 276 | 20% | 32% | 13% | 33% | 1% | 0.3% | 0.5% | 0 / 0 | 0 / 0 | 23/150 | 0.54 |
| airline x gpt-5-mini | 324 | 31% | 20% | 0% | 48% | 1% | 0.9% | 0.9% | 0 / 0 | 0 / 0 | 51/150 | 0.83 |
| retail x gpt-5-mini | 337 | 39% | 3% | 0% | 58% | 0% | 1.3% | 1.4% | 0 / 0 | 0 / 0 | 65/150 | 0.90 |
| telecom x gpt-5-mini | 346 | 41% | 7% | 1% | 52% | 0% | 0.5% | 0.5% | 0 / 0 | 0 / 0 | 27/150 | 0.70 |
| airline x gemini-3.1-flash-lite | 182 | 13% | 36% | 2% | 46% | 3% | 1.8% | 2.5% | 0 / 0 | 0 / 0 | 46/150 | 0.71 |
| retail x gemini-3.1-flash-lite | 142 | 13% | 12% | 46% | 28% | 1% | 3.5% | 6.7% | 2 / 0 | 0 / 0 | 87/150 | 1.00 |
| telecom x gemini-3.1-flash-lite | 212 | 15% | 29% | 1% | 50% | 4% | 1.8% | 2.0% | 0 / 0 | 0 / 0 | 67/150 | 0.96 |
| airline x gemini-3-flash | 98 | 41% | 12% | 0% | 44% | 3% | 1.9% | 3.0% | 1 / 0 | 0 / 0 | 76/150 | 1.00 |
| retail x gemini-3-flash | 54 | 19% | 7% | 52% | 22% | 0% | 3.3% | 5.8% | 1 / 0 | 0 / 0 | 101/150 | 1.00 |
| telecom x gemini-3-flash | 192 | 29% | 5% | 0% | 64% | 3% | 1.7% | 1.5% | 0 / 0 | 0 / 0 | 102/150 | 1.00 |
| telecom x qwen3.5-4b | 118 | 9% | 21% | 31% | 37% | 0% | 2.3% | 8.0% | 0 / 0 | 0 / 0 | 94/150 | 1.00 |

`as issued` = the executed call has the ordered tool and the ordered arguments (after dropping a `functions.` prefix). `refused or diverted` = the orchestrator's order named a tool that does not exist or used argument names the tool does not take, and the database agent made no call (refused and reported back) or called a different, non-write tool. Order classes are computed per unique order (the frozen checker logs an order twice, once when issued and once when closed, and leaves refused orders out of its denominator). Cut text uses the corrected check (a cut call whose output is still a complete JSON object is not cut text); the frozen checker's one flag on telecom x gemini-3-flash is its known false positive.

## 2. Loss decomposition (exact, per episode against S1 on the same task)

gain = mean over M1 episodes of (reward - S1 pass rate on that task). Split by whether the episode ended budget-exhausted, and by whether it contained at least one refused or diverted write order. Components sum to the gain.

| cell | S1 | M1 | gain [95% CI] | exhausted episodes | finished episodes | episodes with a refused/diverted order | exhaustion share of loss |
|---|---:|---:|---|---|---|---|---:|
| airline x gpt-5-nano | 42.7% | 45.3% | +2.7 [-6.7, +12.7] | +2.0 [-0.2, +4.7] | +0.7 [-8.2, +9.8] | +0.0 [-4.0, +4.2] | n/a |
| retail x gpt-5-nano | 68.0% | 44.7% | -23.3 [-32.7, -13.3] | -6.2 [-11.1, -2.0] | -17.1 [-25.3, -8.9] | -3.1 [-6.0, -0.4] | 27% |
| telecom x gpt-5-nano | 32.7% | 19.3% | -13.3 [-20.7, -6.0] | -3.6 [-6.4, -1.3] | -9.8 [-16.9, -3.6] | -3.1 [-7.1, +0.7] | 27% |
| airline x gpt-5-mini | 74.7% | 58.0% | -16.7 [-27.3, -6.7] | -11.8 [-19.6, -4.9] | -4.9 [-10.9, +0.4] | -12.2 [-21.6, -4.0] | 71% |
| retail x gpt-5-mini | 76.0% | 48.0% | -28.0 [-40.0, -17.3] | -22.9 [-32.9, -13.8] | -5.1 [-10.7, +0.2] | -20.7 [-31.3, -10.4] | 82% |
| telecom x gpt-5-mini | 77.3% | 66.0% | -11.3 [-18.7, -4.0] | -8.7 [-12.9, -4.9] | -2.7 [-8.9, +3.6] | -5.6 [-12.0, +1.1] | 76% |
| airline x gemini-3.1-flash-lite | 78.7% | 62.7% | -16.0 [-24.0, -8.0] | -11.8 [-18.2, -5.6] | -4.2 [-9.1, -0.7] | -14.9 [-22.7, -7.3] | 74% |
| retail x gemini-3.1-flash-lite | 77.3% | 41.3% | -36.0 [-47.3, -24.0] | -32.2 [-42.7, -22.0] | -3.8 [-8.7, +0.9] | -10.7 [-15.8, -5.8] | 90% |
| telecom x gemini-3.1-flash-lite | 34.0% | 12.0% | -22.0 [-30.7, -12.7] | -13.1 [-20.4, -6.9] | -8.9 [-15.1, -2.7] | -12.2 [-19.1, -6.0] | 60% |
| airline x gemini-3-flash | 80.7% | 55.3% | -25.3 [-36.7, -14.0] | -17.6 [-26.9, -8.4] | -7.8 [-13.3, -2.7] | -9.8 [-16.4, -4.0] | 69% |
| retail x gemini-3-flash | 80.0% | 25.3% | -54.7 [-66.0, -44.0] | -48.7 [-59.3, -38.0] | -6.0 [-10.4, -2.0] | -4.0 [-7.1, -1.3] | 89% |
| telecom x gemini-3-flash | 91.3% | 10.7% | -80.7 [-87.3, -73.3] | -60.7 [-68.9, -52.2] | -20.0 [-26.2, -14.0] | -45.1 [-54.9, -35.3] | 75% |
| telecom x qwen3.5-4b | 94.7% | 23.3% | -71.3 [-80.0, -62.7] | -56.2 [-65.6, -47.6] | -15.1 [-21.8, -8.7] | -19.8 [-25.6, -14.7] | 79% |

Mean over the 12 H1 cells: gain -27.1; exhausted episodes -19.6 (72% of the loss); finished episodes -7.5; episodes with a refused or diverted order -11.8 (44%). Episode classes are outcomes of M1, not random assignments: read as accounting, not as causal effects.

## 3. H7, spend, cost, per-task counts

| cell | median utilisation | exhausted | completion tokens M1 / S1 (median) | agent USD S1 / M1 | end-to-end USD S1 / M1 | tasks M1 better / same / worse |
|---|---:|---:|---:|---|---|---|
| airline x gpt-5-nano | 0.50 | 23% | 2.9 | $2.56 / $7.34 | $4.66 / $9.15 | 13 / 26 / 11 |
| retail x gpt-5-nano | 0.63 | 16% | 3.1 | $1.88 / $5.83 | $3.74 / $7.49 | 2 / 23 / 25 |
| telecom x gpt-5-nano | 0.54 | 15% | 2.8 | $4.40 / $10.79 | $8.71 / $12.57 | 3 / 28 / 19 |
| airline x gpt-5-mini | 0.83 | 34% | 5.2 | $6.65 / $25.82 | $8.77 / $27.54 | 6 / 27 / 17 |
| retail x gpt-5-mini | 0.90 | 43% | 4.9 | $4.79 / $19.14 | $6.82 / $20.83 | 5 / 19 / 26 |
| telecom x gpt-5-mini | 0.70 | 18% | 4.2 | $8.53 / $28.77 | $16.94 / $34.45 | 5 / 25 / 20 |
| airline x gemini-3.1-flash-lite | 0.71 | 31% | 4.1 | $2.76 / $6.39 | $4.53 / $8.10 | 0 / 36 / 14 |
| retail x gemini-3.1-flash-lite | 1.00 | 58% | 5.2 | $2.61 / $5.98 | $4.21 / $7.37 | 3 / 20 / 27 |
| telecom x gemini-3.1-flash-lite | 0.96 | 45% | 5.8 | $3.24 / $8.26 | $5.53 / $9.53 | 4 / 23 / 23 |
| airline x gemini-3-flash | 1.00 | 51% | 6.1 | $6.85 / $17.88 | $8.52 / $19.43 | 2 / 30 / 18 |
| retail x gemini-3-flash | 1.00 | 67% | 5.1 | $4.78 / $12.84 | $6.36 / $14.01 | 0 / 15 / 35 |
| telecom x gemini-3-flash | 1.00 | 68% | 5.4 | $9.47 / $27.53 | $14.29 / $29.47 | 0 / 1 / 49 |
| telecom x qwen3.5-4b | 1.00 | 63% | 5.3 | $0.00 / $0.00 | $5.09 / $4.16 | 0 / 4 / 46 |

## 4. H6 (write share of S1 failures)

- joint: b_x -0.750 [-1.966, +0.466]; b_write_share -0.557 [-2.207, +1.094]; permutation p (two-sided, within family) 0.545; dof 7
- x_only: b_x -0.816 [-1.959, +0.326]; permutation p (two-sided, within family) 0.145; dof 8
- joint_familyFE: b_x -0.274 [-1.354, +0.805]; b_write_share -0.781 [-2.113, +0.551]; permutation p (two-sided, within family) 0.173; dof 6

write share = (wrongful writes + wrong writes) / S1 failures; wrong write = a failing episode on a task that needs a write in which the agent wrote and the database check or a gold write action failed.

| cell | S1 failures | WW | wrong write | write share | gain |
|---|---:|---:|---:|---:|---:|
| telecom x gpt-5-nano | 101 | 12 | 43 | 0.54 | -13.3 |
| airline x gemini-3-flash | 29 | 2 | 14 | 0.55 | -25.3 |
| airline x gemini-3.1-flash-lite | 32 | 0 | 18 | 0.56 | -16.0 |
| telecom x gemini-3.1-flash-lite | 99 | 0 | 56 | 0.57 | -22.0 |
| airline x gpt-5-mini | 38 | 5 | 17 | 0.58 | -16.7 |
| retail x gemini-3.1-flash-lite | 34 | 1 | 20 | 0.62 | -36.0 |
| retail x gpt-5-nano | 48 | 0 | 31 | 0.65 | -23.3 |
| telecom x gpt-5-mini | 34 | 1 | 22 | 0.68 | -11.3 |
| retail x gemini-3-flash | 30 | 0 | 21 | 0.70 | -54.7 |
| telecom x gemini-3-flash | 13 | 2 | 8 | 0.77 | -80.7 |
| retail x gpt-5-mini | 36 | 0 | 28 | 0.78 | -28.0 |
| airline x gpt-5-nano | 86 | 28 | 48 | 0.88 | +2.7 |

## 5. Power of the H1 test for the cells held

Simulation with the observed LODO x, per-cell SEs and the primary estimator (family and domain FE, inverse-variance WLS, t CI, dof 7), 4,000 worlds per point; tau = between-cell SD beyond task sampling (power_sim.py assumed 0).

| tau | b = 0 (false positive) | b = -0.2 | b = -0.3 | b = -0.5 | b = -1.0 |
|---|---:|---:|---:|---:|---:|
| 0.00 | 0.03 | 0.36 | 0.67 | 0.98 | 1.00 |
| 0.10 | 0.02 | 0.10 | 0.18 | 0.41 | 0.93 |
| 0.20 | 0.02 | 0.05 | 0.08 | 0.16 | 0.46 |
