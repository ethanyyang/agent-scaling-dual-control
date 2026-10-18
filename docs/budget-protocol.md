# Budget protocol — implementation guidance for ANALYSIS.md §4

**Status:** implemented, pre-freeze (2026-09-19). This document maps every rule in
ANALYSIS.md §4 to the mechanism that satisfies it, and lists the tests that prove
it. It is frozen together with ANALYSIS.md (SHA-256 recorded in §4.6). Before the
freeze this file is edited freely; after the freeze it changes only via the
ANALYSIS.md CHANGELOG.

ANALYSIS.md says *what must be true*. This file says *how it is made true*.
PROVENANCE.md records the code commit that *did* it.

Implementation (repository root):

| File | Role |
|---|---|
| `completion_budget.py` | The ledger: `CompletionTokenBudget.reserve / commit / release / snapshot`, `BudgetExhausted` |
| `budget_layer.py` | Shared by S1 and M1: `BudgetConfig` (`uncapped()`, `from_calibration()`), `EpisodeBudget`, `metered_generate()` (the only path to the provider), prompt loading with hash checks, wrap-up and exhaustion helpers |
| `s1_agent.py` | `BudgetedS1Agent`: tau2's stock `LLMAgent` loop with the meter; uncapped for calibration, capped for G1 / R1 |
| `m1_agent.py` | `M1Agent`: orchestrator (no tools) + database agent (all tools) + policy advisor (reasoning only), one shared ledger |
| `run_m1.py` | Runner for capped cells through tau2's `run_domain()` (per-cell budget from `budgets.json`) |
| `s2_agent.py` | `S2Agent` (ANALYSIS.md §2, §8.2): the strong single agent. One context; each turn is a plan call without tools (ledgers, quoted policy check, draft) and an act call with native tools (review the draft, revise if needed, act). Same budget layer and values as M1; `run_m1.py --condition s2` |
| `build_budgets.py` | Writes `budgets.json` (B_1x, c, median, w, a_min per cell) from the calibration manifests |
| `tests/` | 60 tests on 2026-09-25 (27 at the 2026-09-19 freeze, §5); run with `cd tau2-bench && uv run python -m pytest ../tests -q` |

The earlier reference implementation (`budgeted_llm_agent.py`, `budgeted_multi_agent.py`
on branch `test/glm46-airline`, dce0a24) is superseded and no longer used.

---

## 1. Definitions

| Symbol | Meaning | Source |
|---|---|---|
| `B_1x(d, m)` | Episode ceiling for cell (domain d, model m): P75 of S1 calibration episode completion tokens | §4.2 |
| `c(d, m)` | Per-call cap. **Frozen rule (CHANGELOG 2026-09-21): `c = B_1x`**, a runaway guard that touches 0 to 1% of S1 calibration episodes; the original S1 per-call P95 cut 75% of orchestrator plan calls in the pilot. Same c for every component and both arms; it never scales with k | §4.2 |
| `w(d, m)` | Wrap-up threshold: remaining allowance at which the wrap-up notice is injected. **Frozen value: `w = max(0.15 * B_1x, 2 * median S1 per-call completion tokens)`** | §4.3 |
| `a_min(d, m)` | Minimum call allowance below which no further LLM call is attempted. **Frozen rule: `a_min = median S1 per-call completion tokens` for the cell** | §4.3 |
| `completion_tokens` | litellm `usage.completion_tokens`, verified to include hidden reasoning for Gemini and gpt-5.2 (ANALYSIS.md §0) | §4.1 |
| `r` | Maximum tool calls the M1/M2 database agent may make inside one read assignment before it must report back (was written `k` until 2026-09-22; renamed because `k` is also the ceiling multiple below). **Frozen value for the grid: `r = 4`**, set at build time (2026-09-19) with the reason "a goal-level lookup in these domains needs one to three calls; four bounds runaway loops without forcing a report after every call". Checked against the S1 calibration episodes only on 2026-09-22: single agents chain 5 to 7 tool calls before replying (median longest run on telecom: flash-lite 5, 3-flash 7, P90 6 and 10), and `r = 4` was reached on 17 to 51% of read orders in the Gemini M1 cells (orders that used all four calls). Sensitivity run at `r = 25` (Kim et al.'s per-agent iteration ceiling) on two cells, CHANGELOG 2026-09-22. Write assignments are always one call | §2 |

| `k` | Ceiling multiple for the Kim-regime arm: `B = k x B_1x` for S1 and M1 alike. **Frozen value: `k = 4`**, the smallest multiple that leaves S1 unconstrained (largest S1 calibration episode 3.85 x B_1x over 16 cells); the pre-registered 10% exhaustion criterion was not met at 4x or 5x because M1's spend expands with the ceiling (pilot table in the CHANGELOG). Exhaustion and utilisation are reported per cell. The matched arm runs at k = 1 on the R1 cells | CHANGELOG 2026-09-21 |

All four budget values are computed once per cell by `build_budgets.py`
(`BudgetConfig.from_calibration(B_1x, c, median, multiplier)`), recorded in the
§4.2 table and in `budgets.json`, and written into every run manifest.
`--budget-mult` sets k (default 4; 1 for the matched arm); it scales `B_1x` and `w` only; `c` and `a_min` are unchanged.

`--uncapped` (ANALYSIS.md §8.1, 2026-09-24): no ceiling `B`, no wrap-up `w`, no allowance line; `c = B_1x` kept as the per-call guard; the orchestrator's budget paragraph is removed. Used only for the uncapped arm.

`--condition s2` (ANALYSIS.md §8.2, 2026-09-25): the same `BudgetConfig` as M1 in the same arm (`k x B_1x`, `c = B_1x` on every call, `w`, `a_min`). Each turn costs two calls: plan (tools shown with `tool_choice` "none", so it sees the act call's context) and act (tools, `tool_choice` "auto"); after the wrap-up notice a turn is one call with no tools and no plan, as in S1 (R5); a truncated or empty act call is never executed and one closing call without tools follows, as in S1 (R6); an unparsable plan is retried once (not when cut at `c` and not once `w` is crossed), then the act call runs without a plan; an act reply that is JSON text is never sent (a message drafted inside it is used, else the act call is repeated once with the tools and a reminder, and a second JSON reply becomes the message inside it or M1's holding line; changed 2026-09-25 after the first smoke, where the closing call carried the wrap-up notice). No read-call limit applies (S2 has no database agent, like S1).


## 2. Rule → mechanism mapping

| # | ANALYSIS.md §4 rule | Mechanism | Status |
|---|---|---|---|
| R1 | One ledger per episode, shared by every component | `EpisodeBudget` lives in the agent state (`S1State.budget`, `M1State.budget`, `S2State.budget`), created in `get_init_state()`, so one ledger per simulation; every provider call goes through `metered_generate()`, which does `reserve → completion → commit` (or `release` on exception) | implemented; `test_calls_share_one_episode_budget`, `test_turn_usage_sums_every_component` |
| R2 | Parallel workers cannot each spend the full remainder | Reservations are taken before dispatch and bounded by the remainder; M1 has no parallel workers (components run in sequence), so R2 reduces to R1 | implemented; `test_parallel_reservations_never_exceed_remaining` |
| R3 | Per-call output limit ≤ reservation **and ≤ `c`** | `max_tokens = min(reservation, c, configured max_tokens)` with `c = B_1x` (`--cap-rule b1x`, default); the uncapped calibration config sends no `max_tokens`; below `a_min` no call is attempted | implemented; `test_per_call_cap_bounds_max_tokens_and_ledger_is_charged`, `test_remaining_below_cap_shrinks_the_allowance` |
| R4 | Wrap-up notice when remaining < `w` | `EpisodeBudget.needs_wrapup()` fires once per episode; the notice (`prompts/budget_wrapup_notice.md`) is appended to the single system message of every later call (one system message, because some providers reject or merge a second one); `wrapup_triggered=true` in the snapshot | implemented; `test_s1_wrapup_notice_injected_once_then_tools_withheld`, `test_wrapup_forces_a_customer_message` |
| R5 | Remainder must go to a final user-facing turn or stop | After wrap-up S1 gets no tools; M1's orchestrator is told "Only a customer message is allowed now; do not issue assignments", and an assignment issued anyway is refused and replaced by a forced customer message | implemented; same tests as R4 |
| R6 | Truncated calls recorded; truncated tool calls never executed | Usage is committed **before** tool-call parsing, so a call cut mid-arguments is still charged; `finish_reason == "length"` or an unparsable arguments string marks the reply truncated, drops its tool calls, and counts in `truncated_calls`; S1 then makes one closing customer-facing call without tools (or stops if below `a_min`); in M1 a truncated database-agent call closes the assignment with a "truncated" deviation report and returns control to the orchestrator, and a truncated (unparsable) plan is retried once and then replaced by a forced customer message | implemented; `test_truncated_tool_call_is_charged_and_never_executed`, `test_s1_truncated_tool_call_becomes_a_closing_message` |
| R7 | `budget_exhausted` label, distinct from `inaction` | `exhausted_before_call()` (remaining < `a_min`, or the ledger raises `BudgetExhausted`) emits the fixed exhaustion message with `raw_data["transfer_testing_termination"] = "budget_exhausted"`; `is_stop()` returns true on it, so tau2 ends the episode with `termination_reason = agent_stop`. `analyze_run.py` must branch on the label before coding `inaction` | agents implemented; `test_s1_exhaustion_message_is_labelled_and_stops`, `test_exhaustion_stops_the_episode_with_the_label`, `test_s1_exhaustion_ends_the_episode_inside_tau2`. **Analyzer branch still to add** |
| R8 | Provider overrun recorded as infra protocol violation | `overrun = max(0, actual − reservation)` committed and surfaced in the snapshot | implemented; `test_exhaustion_raises_and_overrun_is_recorded` |
| R9 | Utilisation and rates reported per condition | Every agent message carries the snapshot (`spent`, `remaining`, `n_calls`, `truncated_calls`, `wrapup_triggered`, `overrun`), so utilisation, wrap-up, exhaustion, truncation and overrun rates are computable from `results.json` | data recorded; **`analyze_run.py` reporting still to add** (it currently counts M1 turns, not component calls: use `raw_data.transfer_testing_multi_agent.llm_calls`) |
| R10 | Base prompt injection | `render_base_prompt()` loads `prompts/base_system_prompt.md`, checks its SHA-256 against the value recorded in §2 when one is passed, and fills `{domain_policy}`; S1 uses it verbatim; M1 appends a role block per component (`prompts/roles/m1_*.md`, HTML comment header stripped) | implemented; `test_base_prompt_matches_tau2_default_and_hash_check_bites` |
| R11 | M1 routing: while a read assignment is open, tool results go to the database agent; a report (or reaching `r`) returns control to the orchestrator; every write assignment is one call whose executed tool name and arguments are logged next to the order; the act call is skipped when no advisor question was asked | `M1Agent`: `Assignment` state with `calls_made`; forced report (no tools) at `r`; write orders checked (`exact`, `exact_after_type_normalisation`, `argument_mismatch`, `tool_mismatch`) and logged as `executed_as_issued`; a write attempted inside a read assignment is blocked and logged; plan→act only after an advisor question | implemented; `test_read_assignment_routes_tool_results_to_database_agent_then_reports`, `test_write_assignment_is_checked_against_the_order`, `test_write_misexecution_is_logged`, `test_read_call_limit_forces_a_report`, `test_write_inside_read_assignment_is_blocked`, `test_advisor_is_consulted_then_act_call_decides`, `test_m1_runs_a_mock_task_end_to_end` |

## 3. Snapshot schema (`raw_data["transfer_testing_completion_budget"]`, attached to every agent message)

```
{
  "limit": int | null,          # B_1x (null = uncapped calibration)
  "spent": int,                 # committed completion tokens so far (all components)
  "reserved": int,              # outstanding reservations at snapshot time
  "remaining": int | null,
  "exhausted": bool,
  "overrun": int,
  "per_call_cap": int | null,   # c
  "wrapup_threshold": int | null,
  "min_call_allowance": int,    # a_min
  "wrapup_triggered": bool,
  "n_calls": int,               # provider calls so far in the episode
  "truncated_calls": int
}
```

Per call, `raw_data["transfer_testing_call"]` records the component, call name,
reservation, `max_tokens` sent, tokens used, `finish_reason` and whether the call
was truncated. `raw_data["transfer_testing_termination"]` ∈ {`"normal"`,
`"budget_exhausted"`} on every agent message. `raw_data["usage"]` is the
litellm-shaped usage (with `completion_tokens_details.reasoning_tokens` and
`prompt_tokens_details.cached_tokens`) that `analyze_run.py` and
`calibrate_budget.py` read; for M1 it is the sum over the turn's component calls.

M1 and S2 additionally write `raw_data["transfer_testing_multi_agent"]` on every
turn: `llm_calls`, `components` (one entry per provider call), `assignments`
(kind, text or order, calls made, report, `executed_as_issued`, `order_check`),
`advisor` exchanges, `plans`, `events`, the task and progress ledgers, and the
open assignment if the turn ended inside a read. S2 writes the same fields with
`architecture: "S2"`, empty `assignments` and `advisor`, and a `review` record
(the plan's draft and the outcome: `kept`, `revised_arguments`, `revised_tool`,
`reworded`, `revised_to_message`, `revised_to_tool_call`, `no_draft`, or, for turns
that were not reviews, `forced_closing`, `wrapup_after_plan`, `wrapup_turn`).

## 4. Exhaustion path (exact behaviour)

1. Before any call: if `remaining < a_min` → emit the fixed exhaustion message
   (`budget_layer.DEFAULT_EXHAUSTED_MESSAGE`, hashed in every manifest under
   `budget.exhausted_message_sha256`), set `exhausted=true`,
   `transfer_testing_termination="budget_exhausted"`, stop.
2. Else if `remaining < w` and not yet `wrapup_triggered` → append the wrap-up
   notice to the system message, set `wrapup_triggered=true`, proceed to a
   user-facing call with `max_tokens = min(remaining, c)` and no tools.
3. Else → normal call with `max_tokens = min(reservation, c, configured_max)`.

Exhausted episodes are scored by the official evaluator exactly like any
other episode.

## 5. Tests (all green on 2026-09-19 against tau2-bench c339866, 27 tests)

`tests/test_completion_budget.py` (ledger), `tests/test_budget_layer.py`
(cap, metering on truncation, release on exception, usage details, base prompt
hash, S1 wrap-up / exhaustion / truncation), `tests/test_m1_agent.py` (M1 turn
loop: plan→message, read routing and report, write order check and
misexecution, `k` limit, write-in-read blocked, advisor, unparsable plan,
wrap-up, exhaustion, usage sums), `tests/test_tau2_integration.py` (M1 and
capped S1 inside tau2's real runner on the mock domain, offline: tool execution,
ACTION reward, stop handling, metadata in `results.json`).

Added 2026-09-25 for S2 (§8.2): `tests/test_s2_agent.py` (plan call with the tools shown and
`tool_choice` "none", act call with the tools, one context; review outcomes; unparsable, truncated
and tool-calling plans; truncated act; JSON act replies never sent and retried once; a second JSON reply
becomes the holding line; the `functions.` prefix on drafted tool names; no plan retry past `w`; wrap-up turn; exhaustion; flat drafts; the
allowance paragraph removed only without a ceiling) and one S2 episode in
`tests/test_tau2_integration.py`; S1 and M1 requests are checked to keep `tool_choice` "auto".
60 tests pass (58 on first build; 2 more after the first smoke).

Still to add before the freeze: `test_taxonomy_separates_exhaustion_from_inaction`
(`analyze_run.py` branch, R7/R9).

## 6. Pre-freeze checklist

- [x] R3 per-call cap
- [x] R4/R5 wrap-up notice and final-turn rule
- [x] R6 truncation handling
- [x] R7 termination label (agents)
- [ ] R7/R9 `analyze_run.py`: taxonomy branch on the label; utilisation, wrap-up, exhaustion, truncation rates; M1 call count from `llm_calls`
- [x] R10 base-prompt injection with hash check
- [x] R11 M1 routing
- [x] `a_min` and `w` per cell from calibration (no flat constants)
- [ ] Provider checks before the first M1 cell: `max_tokens` bounds reasoning tokens on Gemini (`thinking_level: high`) and Model Studio (`enable_thinking`); tools accepted alongside thinking; one system message accepted
- [ ] Role blocks frozen and their SHA-256 recorded in ANALYSIS.md §2 (currently DRAFT v4 / v2 / v4)
- [ ] M2 (gating checker) not built; M2 role block and R2 for its verifier remain open

## 7. Frozen values (from `budgets.json`, built 2026-09-19 from the six finished Gemini cells)

| Cell | `B_1x` | `c` | median | `w` | `a_min` |
|---|---:|---:|---:|---:|---:|
| airline x gemini-3.1-flash-lite | 6159 | 1662 | 309 | 924 | 309 |
| airline x gemini-3-flash | 6672 | 1813 | 238 | 1001 | 238 |
| retail x gemini-3.1-flash-lite | 4186 | 949 | 216 | 628 | 216 |
| retail x gemini-3-flash | 4161 | 1072 | 203 | 624 | 203 |
| telecom x gemini-3.1-flash-lite | 7123 | 1326 | 352 | 1068 | 352 |
| telecom x gemini-3-flash | 8954 | 1355 | 302 | 1343 | 302 |

gemini-3.1-pro, the OpenAI family and the Qwen ladder are added by re-running
`build_budgets.py` once their calibration cells finish with zero
`infrastructure_error` episodes.

Base prompt template (`prompts/base_system_prompt.md`, comment header stripped):
SHA-256 `825bb492ecd9062046cc7de0050b31ae7887e3577b66b149883728e71a193da7`.
Wrap-up notice text (`prompts/budget_wrapup_notice.md`, as loaded): SHA-256
`f48a23bee3300d0afd2fa6cbdbe7c77f6e069c10b3082572c7cee8a47feacb21`.
Exhaustion message text: SHA-256
`f550c541217dd85534417b4d8262b66ab29ae723c289c9ce9009e1ecdc1e7089`.
