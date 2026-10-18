# Provenance

## Environment

- date: 2026-08-15T05:07:02Z
- tau2-bench commit: `c3398666e6559e3a063da3fc04b5acf7f941464e` (v1.0.1)
- python: Python 3.13.3
- uv: uv 0.12.5 (210d1f678 2026-08-14 aarch64-apple-darwin)

Never `git pull` the benchmark mid-project; results from other versions are
not comparable.

## Reproduction Gate — PASSED

Run: `results/gate-airline-sas-gemini3flash-high-gpt52low-3trials-seed300/`

Our airline SAS run reproduces the published taubench.com leaderboard entry
for the same agent/user-simulator configuration to within ~2pp on pass^1,
well inside our Wilson 95% CI [73.6%, 86.2%].

| Metric | This run | taubench.com submission |
|---|---|---|
| pass^1 | 80.7% | 82.5% |
| pass^2 | 76.0% | 76.3% |
| pass^3 | 74.0% | 72.0% |

### Reference entry (taubench.com)

- Agent: `vertex_ai/gemini-3-flash-preview`, `reasoning_effort: high`
- User simulator: gpt-5.2, `reasoning_effort: low`
- Evaluation date: 2026-03-02
- Bench version: 1.0.1
- 4 trials, seed 123

### This run

- Agent: `gemini/gemini-3-flash-preview` (AI Studio API), `reasoning_effort: high`;
  snapshot `gemini-3-flash-preview`
- User simulator: gpt-5.2 (`gpt-5.2-2025-12-11`), `reasoning_effort: low`
- Run date: 2026-08-27
- Bench version: 1.0.1, commit `c3398666`
- 3 trials, seed 300
- Input SHA-256:
  `e188ae2d1c160822a42cedfdac430c013ac3e3bff998e9d856c98613a0e38278`

### Known differences (accepted)

- **Trial count and seed differ**: 3 trials / seed 300 here vs 4 trials /
  seed 123 in the reference. pass^3 is the deepest directly comparable
  estimator; the reference's pass^k values additionally average over a 4th
  trial.
- Provider route differs (AI Studio `gemini/` here vs `vertex_ai/` in the
  reference); the recorded model snapshot name is identical.
- Reference evaluation date is 2026-03-02 vs 2026-08-27 here; any silent
  server-side model drift over that window is not controlled.

## Evaluator Integrity — PASSED (2026-08-27)

Verbatim outputs, run in `tau2-bench/`:

```
$ git status --porcelain
 M uv.lock
$ git diff HEAD --stat -- src/tau2/evaluator/ data/tau2/domains/
$ git rev-parse HEAD
c3398666e6559e3a063da3fc04b5acf7f941464e
```

- The HEAD commit equals the pinned commit in the Environment section.
- The evaluator and domain-data diff is empty; all benchmark source is
  unmodified.
- The single dirty file is `uv.lock`, a one-line metadata change produced by
  `uv sync` when the editable install was repointed to this checkout
  (records tau2 `1.0.0` → `1.0.1`; touches no code):

```
$ git diff HEAD -- uv.lock
-version = "1.0.0"
+version = "1.0.1"
```

- Our own analysis code does not import, wrap, or monkey-patch the
  evaluator: `grep -rn "evaluator|monkey|patch|setattr"` over
  `analyze_run.py`, `canonical_refit.py`, and `setup.sh` returns nothing.
  `analyze_run.py` has no tau2 import at all — it reads rewards already
  written to `results.json` by the official runner and reimplements only the
  pass^k estimator, which was independently checked against
  `tau2.metrics.agent_metrics.compute_metrics` at the pinned commit (see the
  pilot run README).

## NL-Assertion Re-grade (2026-08-27)

Both baseline runs re-graded post-hoc with the official evaluator under
`EvaluationType.ALL_WITH_NL_ASSERTIONS`, via `nl_regrade.py` (thin wrapper
calling `tau2.evaluator.evaluator.evaluate_simulation` with the same arguments
as the official `tau2.scripts.evaluate_trajectories`, `strict_replay=False`,
plus rate-limit backoff). No episodes were re-run.

- **Judge pin:** `gpt-4.1-2025-04-14`, temperature 0
  (`DEFAULT_LLM_NL_ASSERTIONS` in `src/tau2/config.py` at commit `c3398666`).
- **Reward invariance:** airline `reward_basis` is [DB, COMMUNICATE], so NL
  results are recorded but do not enter the reward. All 300 regraded rewards
  (150 per run) match the originals exactly (`reward_mismatches: []`).
- **Judge stability:** the full-population regrade of the gate run flagged
  exactly the same 12/121 passing episodes as the earlier passing-only screen
  (`nl_assertion_screen.json`) — zero disagreement between independent runs.
- **Task-set identity:** both results files embed the same 50 task ids with
  byte-identical `nl_assertion` lists (123 assertions; 369 checks per run).

| Quantity | Pilot (gpt-4.1-mini) | Gate (gemini-3-flash high) |
|---|---|---|
| Assertion-level pass rate | 207/369 = 56.1% | 323/369 = 87.5% |
| Episodes with all assertions met | 55/150 | 119/150 |
| … among reward-1.0 episodes | 51/60 (9 flagged) | 109/121 (12 flagged) |
| Counterfactual pass^1 if NL entered reward | 34.0% (official 40.0%) | 72.7% (official 80.7%) |

Reports: `nl_regrade_all150.json` in each run's results directory. Judge
flags are LLM judgments; the human spot-check protocol is in ANALYSIS.md §6.6.

## Instrumentation Check — PASSED (2026-08-27)

Run checked: the reproduction gate run above (window 10:08–10:29 local).

### Thinking-token visibility

litellm's normalized `completion_tokens` INCLUDES thinking tokens for both
providers. All 1,614 Gemini agent calls carrying `completion_tokens_details`
satisfy `reasoning_tokens + text_tokens == completion_tokens` exactly
(698,493 reasoning + 144,363 text; zero mismatches). gpt-5.2 likewise
(10,466 reasoning inside 59,538 completion). Caveat: 123 agent calls (7%)
have no details block, so 10,169 output tokens (1.2%) cannot be split into
reasoning vs text; a reasoning-only meter undercounts by at most that.

### Cached-input accounting

`prompt_tokens` is raw (cached included); `prompt_tokens_details.cached_tokens`
verifies as `cached + text = prompt` per call. Recorded costs are already
cache-discounted: recomputing as
`(input − cached) × uncached_rate + cached × cached_rate + output × output_rate`
reproduces the recorded totals to the cent for both providers
(Gemini $0.50/$0.05/$3.00 per Mtok → $6.8481; gpt-5.2 $1.75/$0.175/$14.00
→ $1.6669). Flat input pricing would give $9.7610 for the agent, so any
USD meter must carry all three rates per model.

### Billing cross-check

Recorded (gate run + the one successful smoke episode) vs provider consoles,
same day:

| Provider | Recorded | Billed | Gap |
|---|---|---|---|
| Google (Gemini agent) | $6.8699 | $6.86 | −0.1% (console rounding) |
| OpenAI (gpt-5.2 user sim) | $1.6745 | $1.69 | +0.9% |

Token totals recorded for the gate run: Gemini 7,930,781 uncached input +
6,473,055 cached + 853,025 output; gpt-5.2 463,014 uncached + 131,968 cached
+ 59,538 output. The two failed smoke attempts (404 retired model, free-tier
429) recorded $0 and are, as expected, not visibly billed. The +0.9% OpenAI
gap is consistent with user-simulator calls in the failed smokes and/or
discarded mid-run retries; below the ~2–3% concern level. Billing ≥ recorded
holds; discarded-retry volume is negligible for this run.

## Task subsets and root seed (frozen 2026-09-18)

Root seed: **300** (tau2 `--seed` on every run for agent and user simulator; also the shuffle seed below).
Rule: retail and telecom use the first 50 ids of the `base` split after one `random.Random(300).shuffle` of the ids in the order stored in `split_tasks.json` at commit c339866; airline uses the full `base` split. Machine-readable copy with the same ids: `task_subsets.json`.

### airline: 50 of 50 base tasks, SHA-256 of the id list `696d5a08a964eb1ead4e24cd4fc1cb942bb2daab78e4a51b1d47d4cb75186d0f`

All 50 base ids: 0, 1, 3, 4, 5, 7, 9, 10, 11, 12, 14, 15, 17, 20, 21, 23, 27, 28, 33, 34, 36, 38, 39, 40, 41, 42, 43, 46, 47, 49, 2, 6, 8, 13, 16, 18, 19, 22, 24, 25, 26, 29, 30, 31, 32, 35, 37, 44, 45, 48

### retail: 50 of 114 base tasks, SHA-256 of the id list `5047ad30fdc1fda10416047a19473c72b43e3c42cfd56d5076354d27c6207b64`

Ids (shuffled order, as run): 13, 31, 18, 112, 53, 59, 69, 106, 19, 38, 84, 64, 109, 68, 91, 74, 56, 87, 17, 92, 23, 24, 44, 108, 41, 54, 9, 104, 75, 101, 93, 60, 36, 47, 8, 80, 21, 3, 16, 82, 89, 1, 6, 94, 51, 63, 65, 39, 26, 30

### telecom: 50 of 114 base tasks, SHA-256 of the id list `f9c34039b7c81f91a58f5ad7cc63f4af74d1922fe69e0b13a05af61891418f1e`

Ids (shuffled order, as run; telecom ids are long compositional strings):

- `[mms_issue]airplane_mode_on|bad_network_preference|break_apn_mms_setting|break_app_both_permissions|data_mode_off|data_usage_exceeded|user_abroad_roaming_enabled_off[PERSONA:None]`
- `[mms_issue]bad_wifi_calling|break_apn_mms_setting|unseat_sim_card|user_abroad_roaming_enabled_off[PERSONA:Easy]`
- `[mms_issue]airplane_mode_on|bad_network_preference|break_app_storage_permission|data_mode_off|user_abroad_roaming_enabled_off[PERSONA:Easy]`
- `[service_issue]contract_end_suspension|lock_sim_card_pin[PERSONA:Hard]`
- `[mobile_data_issue]airplane_mode_on|bad_network_preference|data_mode_off|data_saver_mode_on[PERSONA:Hard]`
- `[mobile_data_issue]airplane_mode_on|bad_network_preference|bad_vpn|data_saver_mode_on|user_abroad_roaming_disabled_on[PERSONA:Easy]`
- `[mobile_data_issue]airplane_mode_on|bad_network_preference|data_saver_mode_on|data_usage_exceeded|user_abroad_roaming_disabled_off[PERSONA:None]`
- `[service_issue]airplane_mode_on|overdue_bill_suspension|unseat_sim_card[PERSONA:Easy]`
- `[mms_issue]airplane_mode_on|bad_network_preference|data_usage_exceeded[PERSONA:None]`
- `[mms_issue]bad_network_preference|break_app_both_permissions[PERSONA:Easy]`
- `[mobile_data_issue]bad_network_preference|data_saver_mode_on|data_usage_exceeded[PERSONA:Hard]`
- `[mobile_data_issue]bad_vpn|data_mode_off|data_usage_exceeded|user_abroad_roaming_disabled_off[PERSONA:None]`
- `[service_issue]break_apn_settings|lock_sim_card_pin|overdue_bill_suspension|unseat_sim_card[PERSONA:Easy]`
- `[service_issue]airplane_mode_on|break_apn_settings|contract_end_suspension|lock_sim_card_pin[PERSONA:None]`
- `[mobile_data_issue]data_saver_mode_on|data_usage_exceeded[PERSONA:Easy]`
- `[service_issue]airplane_mode_on|break_apn_settings|lock_sim_card_pin|unseat_sim_card[PERSONA:None]`
- `[mobile_data_issue]airplane_mode_on|data_saver_mode_on|user_abroad_roaming_disabled_on[PERSONA:None]`
- `[mobile_data_issue]bad_vpn|data_saver_mode_on|user_abroad_roaming_disabled_on[PERSONA:None]`
- `[mms_issue]airplane_mode_on|bad_network_preference|break_app_both_permissions|data_usage_exceeded|unseat_sim_card|user_abroad_roaming_disabled_on[PERSONA:Hard]`
- `[mobile_data_issue]data_usage_exceeded|user_abroad_roaming_enabled_off[PERSONA:Easy]`
- `[mms_issue]bad_network_preference|bad_wifi_calling|break_app_sms_permission|data_mode_off|unseat_sim_card|user_abroad_roaming_enabled_off[PERSONA:Hard]`
- `[mms_issue]bad_network_preference|break_app_sms_permission|data_mode_off|data_usage_exceeded|user_abroad_roaming_enabled_off[PERSONA:None]`
- `[mms_issue]break_app_sms_permission|data_usage_exceeded|user_abroad_roaming_disabled_on[PERSONA:None]`
- `[service_issue]contract_end_suspension|unseat_sim_card[PERSONA:Hard]`
- `[mms_issue]break_app_both_permissions|data_usage_exceeded[PERSONA:Hard]`
- `[mobile_data_issue]airplane_mode_on|bad_network_preference|bad_vpn|data_mode_off|data_saver_mode_on|user_abroad_roaming_disabled_off[PERSONA:Hard]`
- `[mms_issue]airplane_mode_on|bad_network_preference|bad_wifi_calling|break_apn_mms_setting|break_app_sms_permission|data_mode_off|data_usage_exceeded|unseat_sim_card|user_abroad_roaming_disabled_on[PERSONA:None]`
- `[service_issue]airplane_mode_on|lock_sim_card_pin|overdue_bill_suspension|unseat_sim_card[PERSONA:Easy]`
- `[mobile_data_issue]airplane_mode_on|data_mode_off[PERSONA:None]`
- `[service_issue]break_apn_settings|lock_sim_card_pin[PERSONA:None]`
- `[service_issue]airplane_mode_on|break_apn_settings[PERSONA:Hard]`
- `[mobile_data_issue]bad_network_preference|bad_vpn|data_mode_off|data_saver_mode_on|data_usage_exceeded|user_abroad_roaming_enabled_off[PERSONA:Easy]`
- `[mms_issue]bad_network_preference|bad_wifi_calling|break_app_sms_permission|data_mode_off|data_usage_exceeded|unseat_sim_card|user_abroad_roaming_enabled_off[PERSONA:Easy]`
- `[mms_issue]break_app_storage_permission|unseat_sim_card|user_abroad_roaming_disabled_on[PERSONA:Easy]`
- `[mms_issue]airplane_mode_on|bad_network_preference|bad_wifi_calling|break_app_storage_permission|data_mode_off|data_usage_exceeded|unseat_sim_card|user_abroad_roaming_enabled_off[PERSONA:Hard]`
- `[mobile_data_issue]bad_network_preference|bad_vpn|data_usage_exceeded|user_abroad_roaming_disabled_off[PERSONA:Easy]`
- `[mms_issue]bad_network_preference|bad_wifi_calling|break_app_both_permissions|data_usage_exceeded|unseat_sim_card|user_abroad_roaming_disabled_off[PERSONA:None]`
- `[mms_issue]airplane_mode_on|bad_network_preference|bad_wifi_calling|break_apn_mms_setting|break_app_storage_permission|data_mode_off|data_usage_exceeded|unseat_sim_card[PERSONA:Easy]`
- `[mms_issue]airplane_mode_on|bad_network_preference|break_apn_mms_setting|data_usage_exceeded[PERSONA:Hard]`
- `[mobile_data_issue]bad_network_preference|bad_vpn|user_abroad_roaming_enabled_off[PERSONA:Easy]`
- `[mobile_data_issue]data_mode_off|data_usage_exceeded|user_abroad_roaming_disabled_off[PERSONA:Hard]`
- `[mms_issue]airplane_mode_on|bad_network_preference|bad_wifi_calling|break_apn_mms_setting|break_app_both_permissions|data_mode_off|data_usage_exceeded|unseat_sim_card|user_abroad_roaming_disabled_on[PERSONA:Hard]`
- `[mms_issue]airplane_mode_on|bad_network_preference|bad_wifi_calling|break_apn_mms_setting|break_app_storage_permission|data_usage_exceeded|unseat_sim_card|user_abroad_roaming_disabled_off[PERSONA:Easy]`
- `[service_issue]airplane_mode_on|overdue_bill_suspension[PERSONA:None]`
- `[mobile_data_issue]airplane_mode_on|bad_network_preference|bad_vpn|data_mode_off|data_saver_mode_on|data_usage_exceeded|user_abroad_roaming_enabled_off[PERSONA:Easy]`
- `[mobile_data_issue]airplane_mode_on|bad_network_preference|data_mode_off|data_saver_mode_on|data_usage_exceeded|user_abroad_roaming_disabled_on[PERSONA:None]`
- `[mobile_data_issue]data_saver_mode_on|user_abroad_roaming_enabled_off[PERSONA:Easy]`
- `[mms_issue]bad_network_preference|break_app_sms_permission|user_abroad_roaming_disabled_on[PERSONA:Hard]`
- `[mms_issue]airplane_mode_on|bad_wifi_calling|break_app_both_permissions|data_mode_off|data_usage_exceeded|unseat_sim_card|user_abroad_roaming_enabled_off[PERSONA:None]`
- `[mms_issue]bad_wifi_calling|break_apn_mms_setting|data_mode_off|data_usage_exceeded|unseat_sim_card[PERSONA:None]`


## M1 role blocks (frozen 2026-09-21)

SHA-256 of the files in `prompts/roles/` at the freeze (the runner records the same digests in every M1 manifest under `role_block_sha256`):

- `m1_orchestrator.md`: `1a26e997efe8928865330dd5ecc5409964402842aeac666239108e04b545e000`
- `m1_database_agent.md`: `367b9355faf9a0063ddaee28303e4e951ff1a032261556d5b379d2f1a76fffc8`
- `m1_advisor.md`: `a350bd2cec205373fcf25403ed7606eb54b9a877b35bb0f9ebcfc3641dc06186`

Base prompt template (`prompts/base_system_prompt.md`, comment header stripped): `825bb492ecd9062046cc7de0050b31ae7887e3577b66b149883728e71a193da7`. Archived drafts: `prompts/roles/archive/m1_orchestrator_v5.md`.

## S2 role block (frozen 2026-09-26, ANALYSIS.md §8.2)

`prompts/roles/s2_single_agent.md` v2, file SHA-256 `1345572de1dc2d86c76ca4d3c4b58a53403d2bb377d923c8dba41437207444f9`; block as sent (comment header stripped) `ba0af7c798387e5d6958949ac91caafe5b28f99dde6c7aadc26de211988e5973`. v1 (block as sent `dbb2e3aa4e13336ca8e7708cb022b1b87e576455bfe517fe9d54144e23e34e01`) ran only in the first smoke (`smoke5v1-s2-*`); v2 ran in the second smoke (`smoke5-s2-*`). The runner records the file digest in every S2 manifest under `role_block_sha256`.


## Qwen family (ladder changed 2026-09-22)

Two dense rungs; see ANALYSIS.md section 3 and the CHANGELOG entry of 2026-09-22.

### qwen3.5-4b, low rung, local Ollama

- Machine: Apple M4 Pro, 48 GB, macOS 26.6.2. Ollama 0.34.2 (Homebrew), started with `OLLAMA_CONTEXT_LENGTH=131072 OLLAMA_NUM_PARALLEL=4 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_KEEP_ALIVE=-1`; the `qwen35` architecture is served one request at a time regardless of `OLLAMA_NUM_PARALLEL`.
- Model: `qwen3.5:4b` from the Ollama library, digest `2a654d98e6fb`, architecture `qwen35`, 4.7B parameters, quantization Q4_K_M, model context length 262144; pinned name `tt-qwen3.5-4b:q4` (digest `668eab7d518c`) created from `ollama/Modelfile.q4` with `PARAMETER num_ctx 131072` and no sampling parameters, so the shipped defaults apply (temperature 1, top_p 0.95, top_k 20, presence_penalty 1.5). Full `ollama show` output in `ollama/provenance-q4.txt`.
- Route: litellm `openai/tt-qwen3.5-4b:q4`, `api_base http://127.0.0.1:11434/v1`, `timeout 3600`, `max_tokens 32768` (loop guard; the budget layer lowers it per call in M1), `extra_body {"reasoning_effort": "high"}`. Thinking on (Ollama default for this model); thinking tokens counted in `usage.completion_tokens`; the thinking trace is returned in a separate field and never reaches the customer. Checks in `ollama/check-q4.json` (thinking, tools, 53k-token prompt arrives whole, model fully on GPU).
- Deviations from the 2026-09-18 text: engine Ollama in place of vLLM; precision Q4_K_M in place of BF16; no Hugging Face revision pin (the Ollama digest is the pin).
- S1 calibration: `calib-telecom-s1-qwen35-4b-q4-ollama-gpt52low-3trials-seed300`, results SHA-256 `37957ae5a52222a744c6363a762b43b602545ad5e0ed81f65a6e5bd42f5024c5`, 150 episodes, 0 infrastructure errors after two episodes were re-run (an Ollama tool-call parse rejection returned as HTTP 500, and one empty reply). Airline and retail S1 not yet run.
- Cost: recorded as 0 by litellm (no price entry); local compute only.

### qwen3.5-9b, mid rung, OpenRouter (teammate run)

- Route: litellm `openrouter/qwen/qwen3.5-9b`; the served provider, build and precision behind OpenRouter's routing are not pinned. Agent args `{"temperature": 0.0, "reasoning": {"effort": "high"}}`; simulator `gpt-5.2-2025-12-11` with `{"temperature": 0.0, "reasoning_effort": "low"}`.
- Agent: `BudgetedS1Agent` in uncapped calibration mode (same prompt, loop and tools as the stock `llm_agent`; no allowance line), not the stock agent used by the other calibration cells. `max_concurrency` 4. Base prompt SHA-256 `825bb492ecd9062046cc7de0050b31ae7887e3577b66b149883728e71a193da7` and tau2 commit `c3398666` match this repository.
- Files: `results/teammate-qwen9b/` (three `.calibration.json`, three `.manifest.json`, `summary.json`, `summary2.json`). Results SHA-256: airline `856e06c713a63373c591a56dbaa7e6014c7628f67c60bf0d83e6f6625043ba46`, retail `ce1270aa0d73f7a58552fbb1565d5947a59c9fe0c7490afe1f0e7de69be94221`, telecom `f1fbe345418fe4cf04a5b9b6a106baa94aeb0e6445b92e30fff034c605b4b3d5`. The results files themselves have not been received; pass^1 values in ANALYSIS.md section 5 are teammate-computed from `summary2.json` until they are.
- Deviations from the other calibration cells: OpenRouter route; BudgetedS1Agent in place of `llm_agent`; explicit `temperature 0.0`; different manifest schema; airline and retail manifests record a relaunch over finished results, so their timestamps are not run durations.
