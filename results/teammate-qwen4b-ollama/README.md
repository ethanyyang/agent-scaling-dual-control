# Teammate run: qwen3.5:4b on local Ollama, S1, all three domains

Filed 24 Sep 2026. Source: `raw/runner.stdout.log`, the stdout of the teammate's runner (machine path `~/Projects/transfer-testing-main`, results folder there `results/qwen-local-s1-calibration/`). SHA-256 of the log: `0cd325f6914661587a694edb4103e0cf2de22b50a304f005c0c9ff6a79321216`. Timestamps in the log run from 2026-09-20 22:23 to 2026-09-23 23:24 (teammate's local clock).

## What is here

| Folder | Save name on the teammate's machine | Status |
|---|---|---|
| `airline/` | `s1-airline-ollama-qwen35-4b-32k-temp0-gpt52low-3trials-seed300` | finished: 144 evaluated, 6 infrastructure errors |
| `retail/` | `s1-retail-ollama-qwen35-4b-32k-temp0-gpt52low-3trials-seed300` | finished: 142 evaluated, 8 infrastructure errors (a first attempt ended with all 150 as infrastructure errors and was restarted from zero) |
| `telecom/` | `s1-telecom-ollama-qwen35-4b-32k-temp0-gpt52low-3trials-seed300` | partial: 22 of 150 when the log ends (a first attempt ended with all 150 as infrastructure errors) |

Each folder has `episodes.csv` (one row per finished episode: task, trial, reward, termination, duration, simulator cost, line in the log) and `summary.json`. `summary.json` at the top holds all three.

These rows are parsed from the "Simulation Overview" panels in the log. They are not tau2 `results.json` files: there are no messages, no token counts and no per-call records. So no budget (`B_1x`, `c`) can be computed from them, and nothing here can feed `build_budgets.py`.

## Configuration visible in the log

- Agent `llm_agent` on `ollama_chat/qwen3.5:4b` (litellm's native Ollama chat route). Simulator `gpt-5.2-2025-12-11`. 3 trials, max steps 200, max errors 10, concurrency 1.
- The save names say `32k` (context length) and `temp0` (temperature 0). litellm request timeout 600 s (visible in the timeout errors).
- Task sets match the registered subsets (all 50 airline tasks; the registered 50 retail and 50 telecom ids).
- Not visible in the log: reasoning or thinking setting, `max_tokens`, Ollama version, model digest or quantization.

Differences from the registered `qwen3.5-4b` cell (ANALYSIS.md §3, PROVENANCE.md, `cells.json` family `qwen`): route `ollama_chat/` in place of `openai/` on Ollama's OpenAI-compatible endpoint; context 32k in place of 131,072; temperature 0 in place of the model's shipped defaults; request timeout 600 s in place of 3,600 s; `reasoning_effort: high` not confirmed.

## Results (S1 pass^1 over evaluated episodes; task-cluster bootstrap, 10,000 draws, seed 300, same procedure as `fill_cell.py`)

| Domain | Evaluated | pass^1 | 95% CI | AGENT_ERROR | Pass rate among `user_stop` episodes | Minutes per episode |
|---|---:|---:|---|---:|---:|---:|
| airline | 144 | 39.7% | [29.0, 50.7] | 69 (48%) | 84% (57 of 68) | 9.2 |
| retail | 142 | 36.3% | [27.0, 46.0] | 64 (45%) | 71% (51 of 72) | 7.8 |
| telecom (partial) | 22 | 59.1% | [36.4, 77.3] | 9 (41%) | 100% (13 of 13) | 6.0 |

The two finished pass^1 values agree with tau2's own printed summary (0.397 and 0.363).

## Caveat: read before using any of these numbers

Between 41% and 48% of episodes end in `AGENT_ERROR`, and every one of them scores 0. The episodes that end normally pass at 71% to 100%. The registered telecom cell, same model, run on the OpenAI-compatible route with 131k context, had no `AGENT_ERROR` in 150 episodes and scored 94.7%. So the low pass^1 here most likely comes from the serving setup, not from the model. The log does not print the error text, so the exact cause is not visible here; the `info` field of each simulation in the teammate's `results.json` files would show it.

Not entered in ANALYSIS.md. The airline and retail rows for `qwen3.5-4b` stay blank: these runs use a different stack from the registered cell, and S1 and M1 of a cell must share one stack.
