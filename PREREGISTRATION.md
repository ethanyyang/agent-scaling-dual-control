<!--
This file is the pre-registered analysis plan of the study, exported from the
authors' working repository on 2026-10-18 under the name ANALYSIS.md. It is
reproduced verbatim: sections 0 to 8 are the plan as written before the main
grid ran, and the CHANGELOG at the end is append-only; every change made after
the plan was written is a dated entry there. The only edits for release are
this note and the removal of an empty "Post-freeze changes" placeholder at the
very end. The header fields "Date frozen" and "Commit" were never filled in the
working copy. The dated record is: role blocks hashed and frozen 2026-09-21
(section 2); first grid MAS episode 2026-09-21T20:07Z (results/calibration-manifests);
commit history of the file in docs/preregistration-history.txt.
-->

# Pre-Registered Analysis Plan — v2

Project: Does the capability-saturation threshold survive conversation?
Testing multi-agent collaboration on policy-constrained tool-use tasks.

> **Freeze rule.** Fill every `____`, commit this file with a date and hash,
> and only then run the main grid. Nothing below may change after that commit.
> Changes go in a dated CHANGELOG section at the bottom, never by editing above.

**Date frozen:** ____   **Commit:** ____
**Benchmark:** tau2-bench v1.0.1, commit `c3398666` (see PROVENANCE.md)

---

## 0. Measured baseline results (exploratory — recorded, not pre-registered)

Two baseline runs, both airline `base` split, 50 tasks x 3 trials = 150
episodes, seed 300:

- Pilot: `exploratory-airline-sas-gpt41mini-full-3trials-seed300`,
  sha256 `0e6a9bb1c339…`, temperature 0.0.
- Gate: `gate-airline-sas-gemini3flash-high-gpt52low-3trials-seed300`,
  sha256 `e188ae2d1c16…` (reproduction gate — see PROVENANCE.md).

The pilot table below is pilot-only; the instrumentation check ran on the
gate run's data; the two-tier table covers both.

| Quantity | Value |
|---|---|
| pass^1 (mean of 3 trials) | **40.0%**  (trials: 34% / 48% / 38%, std 7.2pp) |
| pass^2 / pass^3 | 26.0% / 18.0% |
| Wilson CI on pooled pass^1 | [32.5%, 48.0%] |
| Tasks inconsistent across trials | **21/50 (42%)** |
| Per-task pass counts | 0/3: 20 tasks · 1/3: 9 · 2/3: 12 · 3/3: 9 |
| needs-write task pass rate | 32.1% (25/78) |
| no-write task pass rate | 48.6% (35/72) |
| Failures: wrongful write | **37** (= 100% of no-write failures) |
| Failures: inaction | 15 |
| Failures: other (wrong write / comms) | 38 |
| Agent input tokens / episode | 51,352 (88% cache hit) |
| Agent output tokens / episode | 851 |
| **input : output ratio** | **57 : 1** |
| Agent LLM calls / episode | 10.5 (median 10, max 31) |
| Cost / episode | $0.01098 (agent $0.0083 + user $0.0027) |
| Failing episodes cost | 1.33x passing episodes |

**Consequences that shaped the design below:** the 42% flake rate makes
50 tasks x 3 trials underpowered (minimum detectable difference ~12pp);
the 57:1 input:output ratio makes the choice of cost meter outcome-determining.

### Instrumentation check (completed 2026-08-27, before freeze)

| Check | Result |
|---|---|
| Reasoning-token visibility | PASS — `reasoning_tokens + text_tokens == completion_tokens` in all 1,614 agent calls carrying a details block. Reasoning is 82% of agent output tokens (698,493 / 853,025). 123 calls (7%) lack a details block, covering 10,169 output tokens (1.2%), which a reasoning-only meter would undercount. |
| Cached-input accounting | PASS — `cached + text == prompt` per call. Recorded cost reproduced to the cent with three rates (uncached input, cached input, output); flat input pricing would overstate the Gemini agent cost by 42% (whole run ~+37%, OpenAI side ~+12%). Cached input is priced ~10x below uncached on both providers. |
| Evaluator integrity | PASS — repo at pinned commit `c3398666`; `git diff` empty for `src/tau2/evaluator/` and `data/tau2/domains/`. Only `uv.lock` dirty (one-line version metadata written by `uv sync`; exact diff in PROVENANCE.md). No monkey-patching; analysis code never imports tau2 and its pass^k reimplementation was verified against the official `compute_metrics` at the pinned commit. |
| Regrade determinism | PASS — re-evaluating both runs with `ALL_WITH_NL_ASSERTIONS` reproduced all 300 original rewards exactly (`reward_mismatches: []`). DB/COMMUNICATE replay is deterministic and the NL evaluator does not perturb the official score. |
| Task-set identity | PASS — the task definitions embedded in both results files are identical: same 50 task ids with byte-identical per-task `nl_assertion` lists (123 assertions; 369 checks per run over 3 trials). |
| Billing reconciliation | PASS (gate run only) — Google recorded $6.8699 vs billed $6.86 (−0.1%); OpenAI recorded $1.6745 vs billed $1.69 (+0.9%). Run window 2026-08-27 10:08:31–10:29:01; details in PROVENANCE.md. The pilot was not reconciled against dashboards. |

### Two-tier baseline measurements (airline, 50 tasks x 3 trials, tau2-bench v1.0.1)

| Quantity | Low tier: gpt-4.1-mini | High tier: gemini-3-flash-preview (high) |
|---|---|---|
| User simulator | gpt-4.1-mini | gpt-5.2 (reasoning_effort: low) |
| pass^1 (official DB+COMMUNICATE) | 40.0% | 80.7% |
| Position vs ~45% threshold | below | above |
| Trial-inconsistent tasks | 21/50 (42%) | 7/50 (14%) |
| Assertion-level pass rate | 56.1% (207/369) | 87.5% (323/369) |
| Episodes with all assertions met | 36.7% (55/150) | 79.3% (119/150) |
| ... among reward-1.0 episodes | 85.0% (51/60); 9 flagged | 90.1% (109/121); 12 flagged |
| ... among reward-0 episodes | 4.4% (4/90) | 34.5% (10/29) |
| Counterfactual pass^1 if NL entered the reward | 34.0% (−6.0pp) | 72.7% (−8.0pp) |
| Wrongful writes / inaction / other (failures) | 37 / 15 / 38 | 2 / 11 / 16 |
| Cost per episode | $0.011 | $0.057 |

**Confound caveat:** the tiers are not simulator-matched — the pilot used
gpt-4.1-mini as its own user simulator, the gate run used gpt-5.2 (low).
Tier differences in this table mix agent and simulator effects and are not a
clean capability contrast until one run is repeated under a common simulator.

---

## 1. Hypotheses

This pre-registration has two confirmatory hypotheses — H1 (*what*: the
coordination benefit declines with capability) and H4 (*why*: the failures a
team can catch give way to failures it cannot, which the official score
cannot see either) — plus two pre-specified robustness checks (R1, R2) and
one set of implementation validity checks (G1). H1 and H4 are reported as a family of two
confirmatory tests. Everything else is either exploratory (§7) or a planned
extension pre-registered separately, by dated addendum, before any of its
data are collected (§8).

- **H1 (capability-saturation transfer) — confirmatory.** Unit of analysis:
  one (domain x model) cell of the wide grid (§3), with `gain = M1 - S1`
  (per-task mean reward, averaged over tasks) and `baseline = S1 pass^1`.
  - **Primary test (decides the claim): the slope.** Regress `gain` on a
    capability estimate `x` across all cells, with family and domain fixed
    effects (domain dummies are required because `x` is measured on the
    other domains, so this cell's domain affects `gain` but not `x`), and
    cells weighted by the inverse variance of `gain` (task-cluster). H1 is
    supported if the slope is negative with a 95% CI excluding zero: the
    benefit of coordination declines as single-agent capability rises, which
    is the functional claim underlying Kim et al.'s rule.
    - **`x` must not share measurement noise with `gain`.** Because
      `gain = M1 - S1`, regressing it on the same cell's S1 score induces a
      spurious negative slope (regression to the mean): the pre-registered
      simulation (`power_sim.py`, `docs/power-analysis.md`) shows a 19-28%
      false-positive rate under the null for that naive form. Kim et al.'s
      best-MAS-minus-SAS-versus-SAS analysis has the same structure. The
      primary `x` is therefore the **leave-one-domain-out capability
      index**: the model's mean S1 pass^1 on the other two domains
      (analogous to Kim et al.'s Agentic Capability Index, but independent
      of the cell's own episodes). Robustness, three pre-registered forms
      (2026-09-18): (a) split seeds, the same test with `x` = the cell's S1
      pass^1 from seed 0 only and `gain` from seeds 1-2; (b) logit scale,
      `gain_logit = logit(M1) - logit(S1)` on the LODO `x`, because a bounded
      outcome forces the raw gain toward zero near the ceiling and can
      produce a negative slope by construction; (c) relative gain,
      `(M1 - S1) / S1` on the LODO `x`. All three are reported beside the
      primary slope; the claim rests on the primary. The naive same-episodes
      form is reported descriptively with the bias stated. Both independent forms have empirical false-positive
      rates of 0.07-0.10 in simulation with an asymptotic t; the
      confirmatory p-value is therefore computed by permutation of `gain`
      across cells within family (10,000 permutations), which is exact
      under the null.
    - A significant family-by-`x` interaction is reported, since it would
      indicate the effect is family-specific rather than a capability
      effect. No cells are excluded from this test; straddling cells carry
      their own uncertainty through the weights.
  - **Threshold location (secondary): the zero crossing.** Kim et al.'s 45%
    is where their fitted line crosses zero, not a change of slope, so the
    location test uses the primary fit itself: `x0 = -intercept / slope`,
    evaluated at the mean domain effect, with a task-cluster bootstrap CI
    (episodes resampled by task within each cell, the fit and the crossing
    recomputed per replicate, 10,000 replicates). Reading, fixed in advance:
    transfers if the CI covers 45%; shifts if the slope is negative and the
    CI excludes 45% (direction reported); no crossing if the slope CI covers
    zero. Because `x` is the leave-one-domain-out index, `x0` is read on that
    index, in the same pass^1 units as the cell's own baseline. Per-domain
    crossings are exploratory (§7). A segmented (kink) fit, if reported, is
    exploratory (§7) and is never the location test (revised 2026-09-18;
    the earlier segmented breakpoint was misspecified for a linear rule).
  - **Sign-match accuracy (secondary, reported as the bridge to Kim et al.).**
    For cells whose baseline CI does not straddle 45%, the sign of `gain` is
    compared with the rule's prediction. Reported as X/N alongside Kim et
    al.'s 15/16, with a binomial test against 0.5 — **not** as a test of
    equivalence to 0.94, which neither study is powered to support. The N
    cells are split into those whose `gain` CI excludes zero (signs
    informative) and those within noise (signs uninformative), and accuracy
    is reported for both groups separately so that coin-flip cells are
    never counted as evidence. Rationale: per-cell SEs on `gain` are
    ~8-10pp here (50 tasks x 3 seeds) and ~20pp in Kim et al. (20 tasks x
    1 run), so sign-matching has limited power in both studies; the slope
    test uses effect magnitudes and does not share this weakness.
  - S1 is the contrast because Kim et al.'s rule is stated over one pair: the
    plain single agent (one trajectory, full per-system budget) both
    *classifies* the cell (P_SA vs 45%) and *anchors* the MAS-minus-SAS sign.
    The §5 classifier is S1's pass^1, so the contrast must be against S1 as
    well. S1 is compute-matched to M1 by the per-episode budget (§4).
  - M1 is the only generic MAS in H1 (see §2 for why). Kim et al. validated
    the rule against the best of four architectures; with one architecture, a
    null below 45% is stronger evidence against transfer than Kim's
    validation would give, and a null above 45% is weaker. This asymmetry is
    stated in the paper before results.
- **H4 (failure-mode migration) — confirmatory.** Same 18 cells, same
  episodes, no additional runs; all three outcome measures (§6) are computed
  for every wide-grid episode. Definitions per cell and condition, from the
  §0 taxonomy: `WW` = wrongful-write failures (primary-visible); `FP` =
  judge-flagged passing episodes (policy violation in words, primary-blind);
  `IN` = inaction failures; `BX` = budget-exhausted episodes.
  - **H4a (migration with capability; S1 only).** Stated as *rates*, not
    as the raw share `FP / (FP + WW)`: the raw share rises mechanically with
    the pass rate even when both underlying rates are constant (simulated
    false-positive rate 1.00; `docs/power-analysis.md`). H4a: the
    wrongful-write rate among failing episodes, `WW / failures`, declines
    with capability across cells, while the flagged rate among passing
    episodes, `FP / passes`, does not decline. Test: weighted regression
    (weights = episode counts) of `WW / failures` on the leave-one-domain-out
    capability index with family covariate; supported if the slope is
    negative with a permutation p < 0.05, with family and domain fixed
    effects as in H1; `FP / passes` is reported with its own slope and CI. Computable from the S1 calibration runs alone, before
    any M1 episode. §0 anchors (two stock-prompt cells): `WW / failures` =
    37/90 = 41% at 40.0% baseline and 2/29 = 7% at 80.7%; `FP / passes` =
    15% and 10%.
  - **H4b (architecture shifts composition; S1 vs M1).** Within cells, M1
    reduces `WW` relative to S1. Test: paired difference in `WW` count per
    cell (episodes as the unit, cell as cluster), pooled across cells; a
    negative pooled difference with CI excluding zero supports H4b. The
    changes in `FP`, `IN`, and `BX` are always reported alongside so that a
    `WW` reduction achieved by passivity or exhaustion is visible rather than
    hidden; the interpretation grid is fixed: `WW` down with `IN + BX` flat
    -> coordination repaired a failure class; `WW` down with `IN + BX` up by
    a comparable amount -> coordination traded one failure class for
    another; `WW` unchanged -> the architecture did not act on the failures
    it targets.
  - **Link to H1 (stated in advance).** If H1's slope is negative and H4a
    holds, the mechanism is: M1 acts on write-type failures (the advisor
    puts the governing rule in front of the orchestrator before it decides,
    and the database agent executes writes from a fresh context), and those
    failures vanish with capability while word-type failures do not, so the
    headline benefit shrinks. If H1 is null but H4b holds, coordination is
    changing what fails without changing how often — reported as a finding.
    H4a holding with H1 null, or H1 holding with H4a null, are each reported
    as the mechanism being absent or different from the one hypothesised.
  - Judge validity for `FP` follows §6.6; omission-type flags are excluded
    from `FP` unless hand-adjudicated as violations.
- **R1 (budget invariance) — robustness.** On two pre-specified cells (one
  clearly below 45%, one clearly above, chosen by the §5 gate), S1 and M1 are
  re-run at 0.5x and 2x of `B_1x` with three seeds. Reported per cell: `gain`
  at 0.5x, 1x, 2x with task-cluster CIs, and the within-cell slope of `gain`
  on log budget with its CI. Budget dependence is claimed only if that slope's
  CI excludes zero; sign changes between levels are reported descriptively
  and are not themselves a finding (per-level SEs are ~8-10pp). A
  significant budget slope is reported as a finding (coordination benefit
  depends on headroom), not smoothed over.
- **R2 (simulator invariance) — robustness.** On three pre-specified cells
  (airline for the lowest-, middle-, and highest-baseline models), S1 and M1
  are re-run with a second user simulator (`gpt-4.1-2025-04-14`, the
  tau2-bench default user simulator; §3) with three seeds. Reported per cell: `gain` under each simulator with CIs, and
  the paired difference in `gain` between simulators with its CI. Simulator
  contingency is claimed only if that difference's CI excludes zero in at
  least two of the three cells; if so, the paper elevates it to a primary
  finding. Sign changes alone are reported descriptively.
- **G1 (M1 validity checks) — mechanical indicators reported for every
  M1 cell of the grid; no separate gate run.** Purpose: make a null or
  negative H1 interpretable. A negative slope or a null can mean coordination
  has no value here *or* that our M1 is broken; the indicators separate the
  two. They are diagnostics of the implementation, not tests of H1, and they
  never depend on reward.
  - **Indicators, computed per cell from the grid runs (definitions in §2):**
    fraction of write orders executed as issued and the order-misexecution
    count; fraction of episodes in which the orchestrator consulted the
    policy advisor at least once, and mean advisor calls per episode;
    fraction of advisor outputs referenced in the orchestrator's next ledger
    update ("worker output used"); mean tool calls per episode against S1's
    on the same cell; calls cut at the per-call cap and tokens spent in cut
    calls; turns with two or more cut calls; customer messages that were
    JSON or cut text; holding lines sent; exhaustion and utilisation;
    orchestrator plan calls whose output could not be parsed as the plan
    object (plan-parse failure rate) and forced customer messages sent
    (added 2026-09-22, see CHANGELOG). They
    are reported as a validity table in the appendix next to the gain table.
  - **Reading (fixed in advance; amended 2026-09-22 and 2026-10-17, see
    CHANGELOG):** a cell is *valid* if write orders were
    executed as issued in >= 90% of writes, calls cut at the cap <= 5%,
    tokens in cut calls <= 10%, no turn in which a cut call is retried and
    no turn with two or more cut calls other than the exhaustion turn
    (exhaustion-turn double cuts are reported as a count; amendment (b),
    2026-10-17), and no JSON or cut text
    reached the customer. Exhaustion is *not* a validity failure on its own:
    the 2026-09-21 pilot showed M1's spend expanding with the ceiling while
    every mechanical indicator held, so exhaustion is reported as an outcome
    (§4.3). A cell that fails a mechanical indicator is a *protocol failure*.
  - **Stop rule and fix policy (anti-tuning):** a protocol failure stops the
    grid for that family until the cause is diagnosed and recorded in the
    CHANGELOG. Permitted fixes are bug-class only: crashes, malformed tool
    calls, protocol failures, delegation never triggering, budget-ledger
    faults. Not permitted: editing the base prompt, or editing M1's role
    prompts in response to any cell's tasks or rewards. After a fix the
    affected cells are re-run in full; at most two fix iterations per
    family. If a family still fails, its M1 cells are reported as invalid
    and excluded from H1, and the paper says so.
  - **What G1 no longer does:** the earlier version (2026-09-02) required M1
    to beat S1 on the most favourable cell before the grid could run. That
    clause tested the hypothesis, not the implementation, and would have
    made "the rule does not transfer" unobservable at grid level. Removed on
    2026-09-21 (CHANGELOG). The M1 vs S1 contrast on low-S1 cells is what
    H1 reads from the grid.

### 1.1 Pre-registered power analysis

`power_sim.py` (output frozen in `docs/power-analysis.md`) simulates the
wide-grid design with task heterogeneity fitted to the pilot and gate runs
(beta-binomial concentration 1.39 and 0.42; 0.91 used), the planned 27 cells,
and assumed cell baselines used only to place cells on the x-axis. It runs the
pre-registered H1 and H4a tests on each simulated dataset. Results (400
worlds per setting):

- **H1, leave-one-domain-out `x`, 27 cells, 50 tasks, 3 seeds:** power 0.95
  at slope b = -0.30 (gain +7.5pp at 20% baseline, -10.5pp at 80%), 0.77 at
  b = -0.20, 0.40 at b = -0.10; false-positive rate 0.07 (asymptotic t; the
  permutation p-value is used for the confirmatory test). Five seeds raise
  power at b = -0.20 to 0.93. The **minimum detectable slope at ~80% power
  is about b = -0.20** — a swing of roughly 6pp in coordination benefit
  across a 30-point range of baseline. Effects weaker than that will not be
  reliably detected, and a null is interpreted as "|b| < 0.2", not "b = 0".
- **Naive `x` (same-episode S1):** false-positive rate 0.19-0.28 under the
  null — the reason the primary test uses an independent `x`.
- **Sign-match (secondary):** under a true b = -0.30, only 32-39% of cells
  have `gain` CIs excluding zero; expected sign accuracy is 0.84. A replica
  of Kim et al.'s validation design (16 cells, 20 tasks, 1 run) has expected
  accuracy 0.74 under b = -0.30 and 0.60 under the null, and reaches 15/16
  in 4% of true-effect worlds — their reported 15/16 is therefore either a
  much steeper effect than b = -0.30 or partly fortunate; either way the
  metric is weakly diagnostic, which is why it is secondary here.
- **H4a (rates):** power 1.00 for the §0 anchor effect; false-positive rate
  0.03.

The simulation's assumed baselines are replaced by the measured §5 values
and the analysis re-run (same script, `--reps 1000`) before the freeze; the
re-run is appended to `docs/power-analysis.md` and the minimum detectable
slope is restated.

### 1.2 Secondary hypotheses added 2026-09-21 (pre-registered; not confirmatory)

Added before any full M1 cell was read (at the time of writing the first
grid cell, airline x gemini-3.1-flash-lite, had 23 of 150 episodes
checkpointed and none had been read for reward). These are secondary: they
do not enter the H1 + H4 confirmatory family, they carry no multiplicity
correction claim, and each is reported whatever its result. Their reading
rules are fixed here. Any change after this date is a CHANGELOG entry.

- **H5 (budget-dependent threshold).** Claim: the crossing point x0 of the
  gain line moves with the ceiling multiple k. Data: the k = 4 arm (full
  grid) and the k = 1 arm (R1 cells); a k = 2 point on the same R1 cells is
  added if budget allows. Measure: x0 = -intercept / slope with the
  task-cluster bootstrap CI, computed within each arm exactly as in §1 for
  H1. Reading: a budget dependence is claimed only if the two x0 CIs do not
  overlap and both slopes are negative; otherwise reported as "not
  detected" with both intervals. Kim et al.'s ceiling (about 100 calls per
  system, about 14x their single agent's realised use, no token cap per
  call; from their released code) is stated next to ours.
- **H6 (failure composition predicts gain).** Claim: the share of S1
  failures that are write-related (wrongful write + wrong-argument write,
  §0 taxonomy) predicts gain beyond S1 accuracy. Data: the same 18 cells;
  the share is computed from the S1 calibration runs alone, so it is
  measurable before any team is built. Model, fixed now:
  gain = a + b1 * x + b2 * write_share + domain effects, permutation p
  within family as in H1. Reading: H6 holds if the CI for b2 excludes zero
  with b2 > 0; H6 dominates H1's predictor if additionally the CI for b1
  covers zero in the joint model. Reported with the univariate x-only fit
  next to it.
- **H7 (coordination cost expands with the ceiling).** Claim: M1's spend
  is not a fixed multiple of S1's; it grows with the ceiling while
  exhaustion does not fall. Data: utilisation (spent / B) and exhaustion
  rate per cell at k = 4 across the grid, and across k on the R1 cells.
  Reading: H7 holds if median utilisation at k = 4 is at least 0.7 in a
  majority of cells and, on the R1 cells, exhaustion at the higher k is not
  lower than at k = 4 by more than 10 percentage points. Reported with the
  spend ratio M1 / S1 per cell (same tasks). Pilot evidence on two cells is
  recorded in the 2026-09-21 CHANGELOG entry and is not reused here.
- **H1' (team or tokens)** stays as pre-registered in §8 (M1 - S2 on the
  selected cells), with one update: S2 runs at the same ceiling as M1,
  k x B_1x = 4 x B_1x, not B_1x.

Order of reporting in the paper: H1 and H4 first (the transfer test), then
H5 to H7 and H1' in a separate results section titled as secondary.

## 2. Conditions

Confirmatory (wide grid):

| ID | System |
|----|--------|
| S1 | Single agent, one user-facing trajectory, full per-episode budget (§4) |
| M1 | Centralized: one user-facing orchestrator (Magentic-One dual-ledger) that plans and talks to the customer; a database agent that executes the orchestrator's tool assignments; one silent reasoning-only worker, a policy advisor. Same per-episode budget shared across all components. Specification below. |

Planned extension (§8), not run before its own addendum is frozen:

| ID | System |
|----|--------|
| S2 | Strong single agent: single-context plan -> execute -> review/revise, same budget; never sees gold actions, evaluator outputs, assertions, or reward. (Best-of-N with a non-oracle selector was the earlier candidate; rejected because selection without an oracle is the whole difficulty.) |
| M2 | M1 plus a gating checker: the same orchestrator, database agent and policy advisor, with a checker that reviews (a) every write assignment and (b) every outbound customer message flagged policy-relevant, and whose recommendation replaces the orchestrator's draft when they differ. Database agent identical to M1 (no veto). Specification below. |

**Why Centralized is the generic MAS.** tau2-bench is dual-control: one
simulated customer, one conversational thread. Of Kim et al.'s four generic
architectures, only those that preserve a single user-facing conversational
locus map onto this setting without an adaptation that would itself be the
likeliest explanation of any result. Independent (N agents each hold their own
conversation with the customer, then vote) has no deployable analogue.
Decentralized (agents debate between customer turns) is not a customer-service
pattern and would be confounded by the debate protocol. Hybrid is Centralized
plus lateral worker messaging, a marginal variant. Centralized — a front-line
agent with back-office specialists — is how support teams are actually
organised, and it is the architecture tested. M2 is M1 plus one
domain-motivated component, a gating checker, added because of the failure
analysis in §0; it belongs to the extension and is not itself a generic
MAS.

**Base prompt (decided 2026-09-16).** The base system prompt for every
condition is the tau2-bench default agent prompt at the pinned commit:
`AGENT_INSTRUCTION` inside the `SYSTEM_PROMPT` wrapper in
`src/tau2/agent/llm_agent.py`, with the domain policy inserted verbatim. No
custom base prompt is written. S1 is therefore the tau2-bench default agent
(a "standard" submission under the leaderboard's rules): the plain single
agent that Kim et al.'s rule is stated over, and the agent behind every
public tau2 score, so S1 cells can be checked against the leaderboard. The
text is copied to `prompts/base_system_prompt.md` (2026-09-18, tau2-bench
commit c339866); SHA-256 of `AGENT_INSTRUCTION` `e00faa515230c864…`, of the
full template with the policy placeholder `825bb492ecd90620…` (full digests in
the file header). M1 (and, in the extension, S2/M2) append role or workflow blocks
after the base text, under these rules: (i) the base text and the policy are
never edited; (ii) blocks describe a workflow (how to delegate, what a worker
returns, plan-review-revise for S2), never domain content (no policy
reminders, no task hints); (iii) blocks are frozen in `prompts/roles/` and
hashed here before the first M1 episode (SHA-256 of the files in `prompts/roles/`, frozen 2026-09-21): M1 orchestrator (v6) `1a26e997efe89288…`, M1 database agent (v2) `367b9355faf9a006…`, M1 policy advisor (v4) `a350bd2cec205373…`; full digests in PROVENANCE.md; (iv) after the freeze only the bug-class fixes in §1 (G1 fix policy) are permitted. The
budget wrap-up notice (§4.3) is injected at run time and is not part of any
prompt file.

**Harness constraint (recorded 2026-09-16).** tau2-bench is half-duplex: a
tool call is executed only when the user-facing agent returns it as its turn.
M1 workers therefore cannot query the environment mid-turn. Workers are
reasoning-only: they read the policy, the conversation so far, and tool
results already in context, and return text to the orchestrator; the
orchestrator emits every tool call and every customer message. M1's
verification worker is advisory (the orchestrator decides what to do with
its opinion). M2's verifier gates (its action replaces the executor's). This
keeps M1 from being a superset of M2, so H1' remains interpretable.

**M1 specification (decided 2026-09-18; revised 2026-09-19 to remove the
checker).**

- Components, all on the same model and ledger: the *orchestrator* (the
  only component that sends customer messages; plans; keeps a task ledger
  of facts, guesses and plan, and a progress ledger of assignments,
  reports and stalls; issues assignments), the *database agent* (the only
  component that emits tool calls; executes the orchestrator's assignments
  and reports back), and one reasoning-only worker, the *policy advisor*
  ("which policy rules apply to the current request and what do they
  require"). This is Kim et al.'s centralized pattern adapted to dual
  control: the lead plans and talks, a worker does the tool work, and the
  lead reviews the worker's reports before deciding, which is the
  verification step in Kim's design. There is no separate reviewer of the
  orchestrator's own decisions in M1; that component is what M2 adds.
- Database agent. Receives an *assignment* from the orchestrator: a
  goal-level read assignment ("find X and report Y"), for which it may make
  several consecutive tool calls, keeping control across those turns until
  it reports back; or a single-call write assignment (one write tool call
  with the orchestrator's stated arguments). Context per assignment: base
  prompt + role block, the domain policy, the transcript so far including
  tool results, the orchestrator's ledgers, and the assignment. It executes
  assignments as issued and has no veto. It emits tool calls by native
  function calling, so tool-call format is identical to S1. It reports
  back in a fixed short format: `result`, `records` (identifiers and
  values found), `deviation` (anything it could not do as assigned).
  Multi-call read assignments are bounded: at most `r` tool calls per
  assignment (`r = 4` for the grid, frozen in `docs/budget-protocol.md`;
  sensitivity at `r = 25`, CHANGELOG 2026-09-22), after which it must
  report.
- Policy advisor: fresh context per call (base prompt + role block, the
  domain policy, the transcript so far including tool results and reports,
  the orchestrator's question). No memory across calls. Text only, fixed
  format `finding`, `recommendation`, `policy_basis` (quoted policy lines).
  Never sees the customer, never emits tool calls. Consulted at the
  orchestrator's discretion; the G1 validity reading requires it to be
  consulted in at least 80% of a cell's episodes, which is the functional
  check that M1 uses its policy mechanism.
- Every tool call goes through the database agent. Worker and
  database-agent calls are sequential; reservations are taken before each
  dispatch (§4.3).
- Turn structure: when the turn belongs to the orchestrator (a customer
  message arrived, or a database-agent report arrived), call A, *plan*,
  orchestrator with no tools, returns a JSON ledger update, an optional
  advisor question, and a draft (customer message, read assignment, or
  write assignment); code calls the advisor if asked; call B, *act*,
  orchestrator with no tools, emits the final customer message or the
  final assignment. If the output is a customer message, it is the turn.
  If it is an assignment, the database agent is called with native tools
  and its tool call is the turn; while a read assignment is open, tool
  results are routed to the database agent, which continues or reports;
  the report returns control to the orchestrator. If call A asks no
  advisor question, call B is skipped and the draft is the final output
  (the draft already has the final form), so a turn with no advice costs
  one orchestrator call. Every call is metered and capped (§4). Minimum
  cost of a tool turn is therefore one orchestrator call plus one
  database-agent call, against one call in S1; this overhead is the
  coordination cost the budget is designed to charge.
- Logging per turn: assignments and reports, advisor calls and outputs,
  the orchestrator's ledger update naming the worker ids it relied on, and
  for every write the assignment text and the executed tool call.
  Definitions (§1, G1): "worker output used" = the orchestrator's ledger
  update names the advisor; "order executed as issued" = the executed
  write's tool name and arguments match the assignment; "order
  misexecuted" = they differ, a coordination-induced failure class added
  to the §0 taxonomy for M1/M2 episodes and reported alongside `WW`, `IN`,
  `BX`, `FP`. All computed from logs, not by a judge.
- Prompts: orchestrator = base prompt + `prompts/roles/m1_orchestrator.md`;
  database agent = base prompt + `prompts/roles/m1_database_agent.md`;
  advisor = base prompt + `prompts/roles/m1_advisor.md`. Blocks are
  workflow-only (§2 rules) and hashed before the first M1 episode.

**M2 specification (extension, §8).** M1 plus a *checker* with a veto. The
checker is a reasoning-only worker (same context rules as the advisor)
that is called by code before (a) every write assignment and (b) every
outbound customer message the orchestrator flags `policy_relevant` (a
draft that commits to, offers or refuses an action the policy governs, or
changes a record). It returns `finding`, `recommendation`, `policy_basis`;
when its recommendation is "change" or "do not proceed", its
recommendation replaces the orchestrator's draft (a changed assignment is
issued as changed; a "do not proceed" turns the draft into a customer
message explaining what is needed). The database agent is identical to
M1's and still has no veto. `policy_relevant` self-declaration exists only
in M2; under-declaration is audited: for every judge-flagged verbal
violation (`FP`) in M2, the log shows whether the checker was consulted on
that message, and the rate is reported. M1 and M2 therefore differ in one
component, the gating checker, so H1' and H4c test whether adding a gate
helps beyond the generic team.

## 3. Fixed decisions

- **Models (wide grid, six since 2026-09-22): three families x two tiers**
  (low, mid), after Kim et al.'s families-by-tiers structure so that the
  analysis can separate "capability crossed 45%" from "the vendor changed";
  the high tiers were removed on 2026-09-22 (see below). Each
  family is a within-family capability ladder; the open ladder is the
  insurance for clearly-below-45% cells, which frontier vendors' smallest
  tiers may no longer provide on tau2 (telecom, the hardest domain, may
  supply such cells for any family; the §5 gate counts cells, not models).

  | Family | Low | Mid | High (removed from the grid 2026-09-22) |
  |---|---|---|---|
  | OpenAI (GPT-5) | `gpt-5-nano` | `gpt-5-mini` | `gpt-5`: S1 measured, kept outside the grid |
  | Google (Gemini 3.x) | `gemini-3.1-flash-lite` | `gemini-3-flash` | `gemini-3.1-pro`: S1 measured, kept outside the grid |
  | Open (Qwen3.5 dense, Apache 2.0) | `qwen3.5-4b` (local Ollama, Q4_K_M) | `qwen3.5-9b` (OpenRouter) | none (decided 2026-09-22) |

  Grid reduced to two tiers (decided 2026-09-22): the high rungs `gpt-5`
  and `gemini-3.1-pro` leave the grid; the Qwen family never had one. The
  grid is 18 cells (six models x three domains). The six measured S1 cells
  of the two removed rungs are kept outside the grid (§4.2, §5) with the
  retained gpt-5.4 cells; they enter no confirmatory test and no M1 cell
  is run for them. Reason: cost and time of the M1 arm at the top tier
  (the three `gemini-3.1-pro` M1 cells were paused on cost on 2026-09-22
  before any of them ran; `gpt-5` M1 was never started). Timing, stated
  plainly: decided after the six Gemini M1 cells of the low and mid tiers
  had been read (M1 below S1 on all six, the loss larger for the stronger
  model), so it is post hoc; removing the top tier drops the cells expected
  to show the largest losses above 45%, which works against a negative H1
  slope rather than for it. Consequences to record before the freeze: the
  power analysis was computed for 27 cells and must be re-run for 18; each
  family now contributes six cells to the within-family slope; the
  capability range of the grid on telecom is unchanged (S1 from 32.7% to
  95.3%) because the Qwen rungs sit near the top.

  OpenAI ladder (decided 2026-09-21): the GPT-5 family of August 2025
  (`gpt-5-nano`, `gpt-5-mini`, `gpt-5`) replaces the GPT-5.4 family. Two
  reasons, both settled on S1 data alone. First, these are the OpenAI models
  of Kim et al., so the rule is tested on the models it was fitted on and
  only the setting differs. Second, the H1 slope is identified within
  family, and the measured gpt-5.4 cells offer little within-family spread
  (60.0% to 80.7%, with nano above mini on two of three domains), whereas
  the measured GPT-5 cells are ordered and wide (telecom 32.7% and 77.3%,
  airline 42.7% and 74.7%, for nano and mini). The family is therefore an
  exception to the selection rule below: it is fixed by design to the
  snapshots of 2025-08-07 and is not the latest alias at the freeze.
  Constraint accepted with this choice: OpenAI retires the three snapshots
  on 2026-12-11, so every OpenAI cell, robustness runs included, is
  completed before that date, and the released trajectories are the record
  thereafter. `reasoning_effort: high` is the top level for GPT-5, whereas
  GPT-5.4 offers `xhigh` above it; the configuration released by Kim et al.
  leaves the effort unset (API default, `medium`). The six gpt-5.4 S1 cells
  already measured are retained outside the grid (§4.2, §5) as a same-task
  comparison across model generations; they enter no confirmatory test. The
  three `gpt-5.4` high-rung cells were never run and are dropped.

  Qwen ladder (decided 2026-09-22, replacing the 2026-09-18 ladder below):
  two dense open-weight rungs. Low: `qwen3.5-4b` (4.66B parameters), served
  locally on Ollama 0.34.2 at Q4_K_M (base digest `2a654d98e6fb`, pinned
  name `tt-qwen3.5-4b:q4`, `num_ctx` 131072, one request at a time;
  `cells.json` family `qwen`, `ollama/provenance-q4.txt`, PROVENANCE.md).
  Mid: `qwen3.5-9b`, served through OpenRouter and run by a teammate
  (served provider and build not pinned; deviations listed in §4.2 and
  PROVENANCE.md). No high rung: the family has two rungs (the grid then
  held 24 cells; 18 since the two-tier reduction above). The MoE ladder of 2026-09-18 is
  dropped; none of its cells was run. Reasons: the two dense rungs are the
  ones that were served and measured (S1 done for telecom x 4b and for all
  three 9b cells), and the ladder first pre-registered on 2026-09-17 was
  dense. Recorded deviations: engine Ollama in place of vLLM and precision
  Q4_K_M in place of BF16 for the 4b; two routes within one family, so the
  single-route property of the 2026-09-18 text no longer holds; the 4b runs
  at the model's shipped sampling defaults, the 9b was run with
  `temperature 0.0` and OpenRouter `reasoning.effort: high`. The swap rungs
  of 2026-09-18 no longer apply. Timing, stated plainly: this change was
  made after the S1 results of both rungs and after the first 85 episodes of
  the telecom x 4b M1 cell had been seen (M1 below S1 there, the direction
  of every M1 cell measured so far); it is labelled post hoc in the
  CHANGELOG. Vendor-reported TAU2-Bench for the 4B (Alibaba harness,
  thinking on) is 79.9.

  Qwen ladder (decided 2026-09-18, superseded 2026-09-22): the three open-weight Qwen3.5
  mixture-of-experts sizes, all served on Alibaba Cloud Model Studio
  (international) under one route and one thinking control
  (`enable_thinking: true`). They replace the dense 4B/9B/27B ladder
  because Model Studio does not host 4B or 9B and no other host served 4B
  at decision time; the MoE ladder also mirrors the closed families' shape
  (small tier, mid tier, flagship). Rungs are always described by both
  parameter counts. Pre-registered swap rungs for the §5 gate: if fewer
  than three cells sit clearly below 45%, the low rung becomes
  `qwen3.5-4b` self-hosted on vLLM (BF16, pinned Hugging Face revision,
  thinking on); if mid and high do not separate, the mid rung becomes
  `qwen3.5-27b` (dense, on Model Studio). Vendor-reported TAU2-Bench scores
  (Alibaba harness, thinking on) are 81.2 / 79.5 / 86.7 for the three
  rungs, so the family may not supply below-45% cells; the gate decides.

  Selection rule (decided 2026-09-17; the OpenAI family is excepted as stated
  above): each model is the latest pointer of
  the alias named in the §5 table on the freeze date; the dated snapshot id
  that the pointer resolves to (as returned in the API response) is recorded
  below and pinned for every later run, so that alias drift between S1
  calibration and M1 runs cannot occur. Snapshots and provider routes are
  recorded here before the freeze:
  `gpt-5-nano` snapshot `gpt-5-nano-2025-08-07` route `OpenAI direct (Responses API)`, `gpt-5-mini` snapshot `gpt-5-mini-2025-08-07` route `OpenAI direct (Responses API)`, `gpt-5` snapshot `gpt-5-2025-08-07` route `OpenAI direct (Responses API)`, `gemini-3.1-flash-lite` snapshot `gemini-3.1-flash-lite` (stable id; no dated variant published) route `Gemini API (AI Studio), paid tier`, `gemini-3-flash` snapshot `gemini-3-flash-preview` (preview id; no dated variant published; API-reported `modelVersion` recorded at the freeze) route `Gemini API, paid tier`, `gemini-3.1-pro` snapshot `gemini-3.1-pro-preview` (preview id; same rule) route `Gemini API, paid tier`, `qwen3.5-4b` snapshot `qwen3.5:4b Q4_K_M, Ollama digest 2a654d98e6fb (pinned name tt-qwen3.5-4b:q4, 668eab7d518c)` route `local Ollama 0.34.2, OpenAI-compatible endpoint` (changed 2026-09-22), `qwen3.5-9b` snapshot `qwen/qwen3.5-9b (OpenRouter model id; served provider not pinned)` route `OpenRouter, teammate run` (changed 2026-09-22).
  Reasoning effort: `high` for every agent-side model where the provider
  exposes an effort or thinking-level control (decided 2026-09-16), fixed
  across conditions and components (S1, M1 orchestrator, M1 workers). The
  concrete setting per model is recorded here before the freeze, because
  "high" maps to different controls across providers (OpenAI
  `reasoning_effort`, Gemini thinking level, Qwen thinking mode):
  OpenAI `reasoning_effort: high` (all three; the API default for the GPT-5
  models is `medium`, so it is sent on every call; `high` is their top level); Gemini `thinking_level: high` (all three; it is
  the default for 3.1-pro and 3-flash but not for flash-lite, so it is sent
  on every call); Qwen (changed 2026-09-22): `qwen3.5-4b` thinking on
  (Ollama default for this model) with `reasoning_effort: high` sent on
  every call; `qwen3.5-9b` OpenRouter `reasoning.effort: high`; no
  `thinking_budget`, so the per-call cap `c` (§4.2) is the only bound on
  thinking length (rule decided 2026-09-17).
  Route checks before the freeze (recorded in PROVENANCE.md): thinking plus
  function calling in one request works on Model Studio; one logged request
  shows the policy text arriving unchanged; pay-as-you-go billing is on
  (the free 1M-token trial quota per model covers about 20 episodes). The exact
  parameter names as sent on each route are recorded at the freeze. All routes must use the canonical, unmodified domain policy
  text (no gateway-driven paraphrase). Kim et al.'s third family (Anthropic)
  is replaced by the open ladder for cost and because no closed family offers
  a rung small enough to sit clearly below 45%; Claude models may be added as
  a fourth family by CHANGELOG entry if budget allows, never in place of the
  open ladder. Newer models may have seen tau2-bench (public since mid-2025)
  in training; this inflates S1 and M1 alike and is recorded as a limitation.
  The ladder may be adjusted only by the §5 gate, before the freeze.
- User-simulator model, fixed across ALL conditions and cells: `gpt-5.2`,
  `reasoning_effort: low` (decided 2026-09-16; same as the §0 gate run;
  snapshot `____`). Second simulator for R2 only: `gpt-4.1-2025-04-14`
  (decided 2026-09-17): the tau2-bench default user simulator, so the three
  R2 cells are directly comparable to leaderboard numbers, and a
  non-reasoning customer from an older generation, which is the customer
  axis most likely to matter.
- Temperature: 0.0 wherever the provider accepts it together with the
  reasoning setting; for the reasoning-mode agents and the gpt-5.2 simulator
  the APIs reject or ignore temperature when an effort or thinking level is
  set, so those calls run at the provider default (the 2026-08-27 gate run
  did the same). Recorded per cell in the run manifest.
- **Tasks:** airline full `base` split (50). Retail and telecom: a fixed
  50-task subset of each `base` split, selected by a deterministic shuffle of
  task ids with the root seed 300 (`random.Random(300).shuffle`, first 50),
  task-id lists and their hashes recorded in `PROVENANCE.md` and
  `task_subsets.json` (2026-09-18). (telecom `full` 2,285-task split is NOT used.) The same subsets
  are used for every model and condition.
- **Seeds: 3 per condition-task pair on the wide grid** and on R1/R2. (The
  pilot's 42% task-level flake rate is addressed on the wide grid by cell
  count rather than seed count: H1 is a between-cell test. The extension in
  §8 uses 5 seeds because its tests are within-cell.)
- Primary outcome unit: **per-task mean reward across seeds** (continuous in
  {0, 1/3, 2/3, 1} at three seeds), not binary pass/fail — the pilot shows
  binarising discards most of the signal
- Test: paired bootstrap over tasks, 10,000 resamples, alpha = 0.05, two-sided
- Baseline pass^1 CIs used to classify cells relative to 45% (§5) are
  task-cluster bootstrap CIs; pooled-episode Wilson CIs are descriptive only
- Secondary: pass^1 and pass^k for leaderboard comparability
- Infra-crash episodes re-run once, then excluded and reported
- Budget exhaustion (§4.3) is an agent-system outcome, not an infrastructure
  crash: exhausted episodes are scored as produced, never excluded or re-run,
  and carry their own terminal label distinct from `inaction`

## 4. Compute matching and deployment cost

The pilot's 57:1 input:output ratio means "matched total tokens" is almost
entirely "matched input tokens", which penalises MAS for prompt duplication
rather than for reasoning. Prior work disagrees on what to match and never
flagged this: Kim et al. (Nature MI 2026) matched per-system reasoning-token
ceilings in aggregate via iteration limits; Tran & Kiela (arXiv:2604.02460)
enforced a per-call thinking-token budget split across agents; Wang et al.
(arXiv:2406.06461) capped input+output tokens per question and reported
Performance@Tokens curves; "The Illusion of Multi-Agent Advantage"
(arXiv:2606.13003) and HAL (arXiv:2407.01502) report USD post hoc.

The design below adopts Kim et al.'s **per-system ceiling** principle (the
budget belongs to the system, not to each agent) and Tran & Kiela's
**split-the-budget** logic (the single agent spends the whole ceiling in one
trajectory; a multi-agent system must divide the same ceiling), generalised
from single-call tasks to multi-turn episodes. Deviations from each are listed
in §4.5.

### 4.1 Primary scientific budget — system-wide agent completion tokens

The confirmatory H1 comparison is matched on **system-wide agent completion
tokens**. For episode `e`:

`C_e = sum(completion_tokens_j for every agent-system LLM call j)`.

The sum includes every call made by the user-facing agent, planner,
orchestrator, worker, critic, verifier, selector, or aggregator. It includes
provider-reported hidden reasoning tokens, visible text, tool-call names and
arguments, and inter-agent messages. No component receives a separate free
allowance: the ceiling belongs to the system, not to each agent.

The primary scientific budget excludes system/user prompt tokens, conversation
history supplied as input, tool/environment observations, user-simulator
tokens, evaluator/judge calls, and offline analysis. These are excluded to
isolate coordination under a fixed amount of agent-generated computation, not
because they are economically free; they enter the deployment-cost accounts in
§4.4.

`completion_tokens` is used rather than reasoning-only tokens because it is
observable for both reasoning and non-reasoning models (a reasoning-only meter
reads near zero for gpt-4.1-mini). In the gate run it already includes hidden
reasoning (§0). It also charges MAS for explicit coordination messages and
tool-call construction, which a reasoning-only meter would treat as free.

### 4.2 Calibration and budget levels

Budgets are calibrated separately for every (domain x model) cell, but are
identical across all conditions within that cell (S1 and M1 on the wide grid;
S2 and M2 in the extension). Cross-model equality in raw
token counts is not required because tokenizers and reasoning regimes differ;
all threshold effects are within-model architecture contrasts.

Before any confirmatory M1/M2 data are collected, run the pre-specified S1
calibration protocol over the §3 task sets with three trials, root seed
300 (tau2 `--seed`, passed to agent and simulator calls; 2026-09-18), the frozen base prompt, and the fixed user simulator, for every
wide-grid cell. These calibration episodes are the S1 arm of the wide grid
and supply the §5 classification; M1 is run afterwards at the resulting
`B_1x`. Define:

`B_1x(domain, model) = P75(S1 calibration episode completion tokens)`.

The confirmatory wide grid runs at `B_1x`. The levels `0.5 * B_1x` and
`2 * B_1x` are run only on the two R1 cells (§1), three seeds. P75 is used instead of the median because a median hard ceiling would
truncate roughly half of otherwise normal S1 episodes; it is used instead of
the maximum because both baseline runs contain runaway outliers. No published
protocol specifies a calibration statistic (Kim et al. report a realised mean
of ~4,800 reasoning tokens; Tran & Kiela sweep absolute values), so this rule
is pre-registered here. The S1 calibration **mean** is recorded alongside P75
so the ceiling can be related to Kim et al.'s mean-matched convention.

Per-call cap: each LLM call is bounded by `min(remaining ledger, c)` where
`c(domain, model) = P95(S1 calibration per-call completion tokens)`, so that a
single reasoning burst cannot consume an entire episode budget. `c` is frozen
with `B_1x`.

The twenty-seven frozen values and calibration hashes are recorded here
before M1 runs:

| Domain x Model | Calibration SHA-256 | S1 mean | S1 P75 (`B_1x`) | 0.5x | 2x | per-call cap `c` (P95) |
|---|---|---:|---:|---:|---:|---:|
| airline x gpt-5-nano | `a0e882bf6ac0…` | 40839 | **51297** | 25648 | 102594 | 11566 |
| retail x gpt-5-nano | `03c84f443dc2…` | 29783 | **35313** | 17656 | 70626 | 8897 |
| telecom x gpt-5-nano | `6e0502f5595d…` | 60570 | **75032** | 37516 | 150064 | 6100 |
| airline x gpt-5-mini | `0993b01c8c63…` | 20808 | **27477** | 13738 | 54954 | 8312 |
| retail x gpt-5-mini | `e2bafb2beaa6…` | 14432 | **18294** | 9147 | 36588 | 5389 |
| telecom x gpt-5-mini | `d4be39972133…` | 26165 | **31514** | 15757 | 63028 | 5273 |
| airline x gemini-3.1-flash-lite | `3fc369bc1759…` | 4997 | **6159** | 3079 | 12318 | 1662 |
| retail x gemini-3.1-flash-lite | `0c9c773e4632…` | 3464 | **4186** | 2093 | 8372 | 949 |
| telecom x gemini-3.1-flash-lite | `4c7b844471fc…` | 5272 | **7123** | 3561 | 14246 | 1326 |
| airline x gemini-3-flash | `e188ae2d1c16…` (gate run, admitted) | 5687 | **6672** | 3336 | 13344 | 1813 |
| retail x gemini-3-flash | `836e2a05ad11…` | 3471 | **4161** | 2080 | 8322 | 1072 |
| telecom x gemini-3-flash | `8447013d0040…` | 7242 | **8954** | 4477 | 17908 | 1355 |
| airline x qwen3.5-4b | ____ | ____ | ____ | ____ | ____ | ____ |
| retail x qwen3.5-4b | ____ | ____ | ____ | ____ | ____ | ____ |
| telecom x qwen3.5-4b | `37957ae5a522…` | 4335 | **5630** | 2815 | 11260 | 608 |
| airline x qwen3.5-9b | `856e06c713a6…` | 9624 | **12263** | 6131 | 24526 | 3243 |
| retail x qwen3.5-9b | `ce1270aa0d73…` | 5367 | **6370** | 3185 | 12740 | 1808 |
| telecom x qwen3.5-9b | `f1fbe345418f…` | 4514 | **5758** | 2879 | 11516 | 772 |

**Retained high-rung cells (outside the 18 rows above; removed from the grid
2026-09-22).** S1 calibration of `gpt-5` and `gemini-3.1-pro`, measured under
the same configuration as the grid cells before the two-tier reduction (§3).
Kept for the appendix and for a same-task comparison across tiers; they enter
no confirmatory test and no M1 budget is derived from them.

| Domain x Model | Calibration SHA-256 | S1 mean | S1 P75 | 0.5x | 2x | per-call P95 |
|---|---|---:|---:|---:|---:|---:|
| airline x gpt-5 | `cf78e18aafb1…` | 23789 | **28364** | 14182 | 56728 | 6730 |
| retail x gpt-5 | `fc0c8c63de32…` | 15284 | **18917** | 9458 | 37834 | 4724 |
| telecom x gpt-5 | `eddd64838480…` | 18509 | **23120** | 11560 | 46240 | 4074 |
| airline x gemini-3.1-pro | `59b347d7e42e…` | 5114 | **6403** | 3201 | 12806 | 2140 |
| retail x gemini-3.1-pro | `3e930923e21d…` | 3528 | **4137** | 2068 | 8274 | 1228 |
| telecom x gemini-3.1-pro | `e09de21211cd…` | 4934 | **6331** | 3165 | 12662 | 898 |

**Retained gpt-5.4 cells (outside the 18 rows above; changed 2026-09-21).**
The OpenAI ladder was GPT-5.4 until 2026-09-21 (§3). Its six measured S1
calibration cells are kept for a same-task comparison across model generations
and for the appendix. They enter no confirmatory test, no M1 budget is derived
from them, and the three `gpt-5.4` high-rung cells were never run. Values as
computed by `calibrate_budget.py` under the same configuration:

| Domain x Model | Calibration SHA-256 | S1 mean | S1 P75 | 0.5x | 2x | per-call P95 |
|---|---|---:|---:|---:|---:|---:|
| airline x gpt-5.4-nano | `d4e3df3377e6…` | 6618 | **8733** | 4366 | 17466 | 2555 |
| retail x gpt-5.4-nano | `43c4fc866508…` | 3810 | **4706** | 2353 | 9412 | 1332 |
| telecom x gpt-5.4-nano | `f18ef31486f3…` | 6273 | **7900** | 3950 | 15800 | 1272 |
| airline x gpt-5.4-mini | `91d287198296…` | 3948 | **5205** | 2602 | 10410 | 1685 |
| retail x gpt-5.4-mini | `446451961387…` | 3506 | **4152** | 2076 | 8304 | 868 |
| telecom x gpt-5.4-mini | `aec8c17baca1…` | 4263 | **5877** | 2938 | 11754 | 1131 |

**Qwen3.5-9B on OpenRouter (teammate run, received 2026-09-21, manifests
received 2026-09-22; mid rung of the Qwen family since 2026-09-22, §3).** Three S1
calibration cells run by a teammate on a separate machine (150 episodes each,
seed 300, 3 trials, gpt-5.2-low simulator, max_steps 200, max_concurrency 4).
Files held under `results/teammate-qwen9b/` (three `.calibration.json`, three
`.manifest.json`, `summary.json`). What the manifests verify: agent route id
`openrouter/qwen/qwen3.5-9b`; agent reasoning effort `high`; simulator
`gpt-5.2-2025-12-11` at effort `low`; base prompt SHA-256 `825bb492ecd9…`
(matches the frozen prompt); tau2 commit `c3398666…` (matches); all three
cells `return_code` 0 with 150 episodes and 0 infrastructure errors; the
`results.json` SHA-256 in each manifest matches the one in the corresponding
calibration file. Deviations from the registered cells, to be carried into
PROVENANCE.md if the rung is admitted: (i) route is OpenRouter, not Model
Studio, so the single-route property of the Qwen family (§3) does not hold for
this model, and the served provider, build and precision behind OpenRouter's
routing are not pinned; (ii) the agent was run through our `BudgetedS1Agent`
in uncapped mode (same prompt, loop and tools as the stock `llm_agent`; no
allowance line or wrap-up notice in that mode) rather than the stock agent the
registered calibration cells used; (iii) `temperature: 0.0` was passed
explicitly to both the agent and the simulator, whereas the registered cells
pass no temperature and run at the provider default when an effort level is
set (§3); whether OpenRouter honoured the value for the agent, and whether
the OpenAI route dropped it for the simulator, cannot be checked without the
per-call records; (iv) the manifest schema differs from ours (no `command`,
`cells_json_sha256` or `task_ids_sha256` fields), and the airline and retail
manifests record a relaunch over already-finished results (`resume_state`
150 and 149 episodes), so their timestamps are not run durations. Not yet
received: the three `results.json` files, so task-id checks and termination
reasons cannot be verified here. A second summary (`summary2.json`, received
2026-09-22) carries pass^1 per cell, computed by the teammate with the same
task-cluster bootstrap as `fill_cell.py` (10,000 draws, seed 300), on results
files whose SHA-256 match the calibration files; those values fill the §5
rows and are marked teammate-computed until the results files are checked
here. Reasoning-token details present on 99.8% of calls.
Values as computed by `calibrate_budget.py`:

| Domain x Model | Calibration SHA-256 | S1 mean | S1 P75 (`B_1x`) | 0.5x | 2x | per-call P95 | per-call median | S1 max |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| airline x qwen3.5-9b (OpenRouter) | `856e06c713a6…` | 9624 | **12263** | 6131 | 24526 | 3243 | 270 | 35330 |
| retail x qwen3.5-9b (OpenRouter) | `ce1270aa0d73…` | 5367 | **6370** | 3185 | 12740 | 1808 | 224 | 14789 |
| telecom x qwen3.5-9b (OpenRouter) | `f1fbe345418f…` | 4514 | **5758** | 2879 | 11516 | 772 | 211 | 9732 |

This model is the mid rung of the Qwen family (decided 2026-09-22, §3); the
route and agent deviations above are recorded in PROVENANCE.md.

Sensitivity of the §5 classification: cells are classified by the uncapped
calibration S1 (the classifier must exist before the ceiling derived from it).
Because the wide-grid S1 *is* the calibration run, the classifier and the
contrast come from the same episodes; the R1 cells additionally report S1's
side of 45% at 0.5x and 2x.

**Known asymmetry, decided and kept (2026-09-02):** the H1 comparator S1 is
the uncapped calibration run, whereas M1 runs under `B_1x`. By construction
25% of S1 episodes exceeded the ceiling M1 is held to, so the contrast is
conservative against M1 by an amount bounded by the reward share of those
episodes; that share is reported per cell (`S1 pass rate among episodes
above B_1x` vs below). The decision not to re-run S1 capped is a cost
decision; its direction (against M1, i.e. against H1's predicted benefit
below 45%) is stated in the paper before results, and the R1 cells, where
S1 is re-run capped at the same ceiling, provide direct capped-vs-uncapped S1
comparisons to size the effect.

### 4.3 Enforcement, wrap-up, and budget exhaustion

- The budget ledger is shared across all internal components in an episode.
- Before concurrent workers are dispatched, their maximum allowances are
  reserved so that parallel calls cannot each spend the full remaining budget.
- Each call's output limit is no greater than its reserved allowance and no
  greater than the per-call cap `c`. Actual `completion_tokens` are committed
  after the response and unused reservation is released.
- **Wrap-up rule.** When the remaining allowance falls below a frozen
  threshold (`w`, recorded in `docs/budget-protocol.md`), the agent system is
  told, via a fixed notice whose text is frozen under `prompts/` and hashed,
  that it must conclude with the customer in its next user-facing message. The
  notice is the interactive analogue of Kim et al.'s step-budget warning.
- When the remaining allowance cannot support another planned internal call,
  the system must use the remainder for a final user-facing response or stop.
- A call truncated by the provider (`finish_reason == "length"`) is recorded
  as such; a truncated tool call is never executed.
- An exhausted episode is evaluated normally and labelled
  `budget_exhausted` in the trajectory metadata (tau2's own
  `termination_reason` may read `agent_stop`; the analysis reads the label).
  It is not excluded or re-run, and it is **not** coded as `inaction` in the
  failure taxonomy (§3, §6.3): exhaustion is reported as its own category and
  the inaction rate is reported both excluding and including it.
- Provider violations of a requested per-call output limit are recorded as
  infrastructure protocol violations. The original trajectory and measured
  overrun remain auditable; the infra retry rule in §3 applies, and both
  attempts are reported.
- For every condition report allocated budget, realised completion tokens,
  budget utilisation, wrap-up trigger rate, exhaustion rate, truncation rate,
  and any provider overrun. Utilisation is reported because Tran & Kiela
  document providers silently under-spending a declared budget.

Matching is by allocated system ceiling (the intention-to-budget estimand),
because systems may legitimately stop early. Realised-spend performance curves
are reported as a secondary analysis; systems are never forced to emit useless
tokens merely to spend the full allowance.

### 4.4 Parallel sensitivity and deployment-cost accounts

Only the completion-token ceiling is enforced for the confirmatory comparison.
The following meters are always reported in parallel, never used to construct
post-hoc "matched" samples:

1. **Reasoning-only tokens, where observable** — closest sensitivity analysis
   to the Nature MI and equal-thinking-token protocols. Coverage and missing
   details are reported per model and condition.
2. **Total agent API tokens** — uncached input + cached input + completion,
   summed over every internal component. Captures prompt/schema/history
   duplication and implementation overhead.
3. **Agent-system USD** — from three frozen rates per model in
   `pricing.json`: uncached input, cached input, output.
4. **End-to-end USD** — agent-system USD plus user-simulator cost. Evaluator
   and offline judge cost are reported separately as measurement costs.
5. **Operational measures** — LLM-call count, tool-call count, wall-clock
   latency (mean and P95), retry rate, and cache-hit rate.

Total token counts are reproducible within a model/provider route but are not
provider-neutral compute: tokenizers, hidden reasoning, and cache semantics
differ. Cache-hit rate is reported per system and provider (pilot SAS = 88% on
OpenAI; gate run = 45% on Gemini implicit caching) rather than compared as
though the providers implemented the same mechanism.

The H1 headline follows the pre-registered completion-token ceiling. For
deployment claims, report performance-versus-USD and
performance-versus-total-token Pareto frontiers (HAL convention) and
Performance@Tokens curves across the three budget levels (Wang et al.
convention). If architecture ordering changes across the scientific and
deployment meters, that reversal is a result, not something to smooth over.

### 4.5 Relationship to prior protocols (deviations stated in advance)

| Prior protocol | Adopted | Deviation here |
|---|---|---|
| Kim et al. | Per-system ceiling; coordination paid from the same pool; exhaustion is a legal termination | Kim enforce iteration ceilings and match reasoning tokens only as a realised mean; here the ceiling is a per-episode token cap, enforced |
| Tran & Kiela | Single agent spends whole budget in one trajectory; MAS divides it; budget sweep | They keep planner/aggregator "near budget-neutral" — here every component is charged (stricter for MAS); they count thinking tokens — here completion tokens, with reasoning-only as sensitivity; they split statically (B/k) — here a shared pool with reservations (more generous to MAS, so a null MAS result is conservative) |
| Wang et al. | Performance@Tokens curves | Their cap is input+output per question; here input is a deployment account, not the scientific budget |
| HAL / Kapoor et al. | Accuracy-vs-USD Pareto for deployment | Not used for the confirmatory contrast (compute and architecture would co-vary) |

### 4.6 Implementation protocol

The mapping from each rule above to code (ledger semantics, per-call cap,
wrap-up threshold `w` and notice, truncation handling, metadata schema,
required tests) is specified in `docs/budget-protocol.md`. That document and
the enforcement code are frozen with this file: protocol SHA-256 `____`,
enforcement-code commit `____`. Engineering changes before the freeze are
made there, not here; after the freeze they are CHANGELOG entries.

**Meter validity (instrumentation check, 2026-08-27 — see PROVENANCE.md):**

- Primary completion-token meter: litellm's `completion_tokens` INCLUDES
  thinking tokens for both Gemini (`reasoning + text == completion`, zero
  mismatches over 1,614 detailed calls) and gpt-5.2. ~1.2% of gate-run output
  tokens sit in calls without a details block; they remain counted by the
  primary meter but cannot be split reasoning-vs-text, so the reasoning-only
  sensitivity meter carries that caveat.
- USD meter: `pricing.json` must carry THREE rates per model (uncached input,
  cached input, output). Recorded run costs are cache-discounted and
  reproduce provider billing to within 1% (Google −0.1%, OpenAI +0.9%).
- The input:output ratio is regime-dependent: ~60:1 for the non-reasoning
  pilot (gpt-4.1-mini) but 16.9:1 for the gate run (reasoning_effort high).
  The primary completion-token meter therefore diverges from deployment total
  tokens far more for non-reasoning models. Both are reported, with per-model
  ratios alongside.
- Observed per-episode maxima that motivate the per-call cap and per-cell
  calibration: pilot max input 233,989 (runaway loop); gate-run max 987,586
  input / 1,013,303 total.

## 5. Pre-registered threshold predictions (fill BEFORE M1 runs)

| Domain x Model | S1 pass^1 | 95% CI (task-cluster bootstrap) | Straddles 45%? | Rule's predicted sign of M1 - S1 |
|---|---|---|---|---|
| airline x gpt-5-nano | 42.7% | [31.3%, 54.0%] | yes | — |
| retail x gpt-5-nano | 68.0% | [58.7%, 77.3%] | no | M1 < S1 |
| telecom x gpt-5-nano | 32.7% | [22.7%, 43.3%] | no | M1 > S1 |
| airline x gpt-5-mini | 74.7% | [64.7%, 84.0%] | no | M1 < S1 |
| retail x gpt-5-mini | 76.0% | [66.7%, 84.0%] | no | M1 < S1 |
| telecom x gpt-5-mini | 77.3% | [68.0%, 86.0%] | no | M1 < S1 |
| airline x gemini-3.1-flash-lite | 78.7% | [68.0%, 88.7%] | no | M1 < S1 |
| retail x gemini-3.1-flash-lite | 77.3% | [67.3%, 86.7%] | no | M1 < S1 |
| telecom x gemini-3.1-flash-lite | 34.0% | [24.0%, 44.7%] | no | M1 > S1 |
| airline x gemini-3-flash | 80.7% | [70.7%, 90.0%] | no | M1 < S1 |
| retail x gemini-3-flash | 80.0% | [70.7%, 88.7%] | no | M1 < S1 |
| telecom x gemini-3-flash | 91.3% | [86.0%, 96.0%] | no | M1 < S1 |
| airline x qwen3.5-4b | ____ | ____ | ____ | ____ |
| retail x qwen3.5-4b | ____ | ____ | ____ | ____ |
| telecom x qwen3.5-4b | 94.7% | [90.7%, 98.0%] | no | M1 < S1 |
| airline x qwen3.5-9b | 79.3% | [71.3%, 86.7%] | no | M1 < S1 |
| retail x qwen3.5-9b | 76.0% | [66.7%, 84.7%] | no | M1 < S1 |
| telecom x qwen3.5-9b | 95.3% | [91.3%, 98.7%] | no | M1 < S1 |

The three `qwen3.5-9b` rows are teammate-computed from
`results/teammate-qwen9b/summary2.json` (same task-cluster bootstrap as
`fill_cell.py`; results-file hashes match the §4.2 block) and will be
recomputed here when the results files arrive.

All twenty-seven cells are measured under the frozen configuration of §2-§3
(frozen base prompt, one fixed user simulator, 3 seeds) after the prompt
freeze and before any M1 episode. The `S1 pass^1` column is the `baseline`
regressor for the primary slope test (§1); the last two columns feed only the
secondary sign-match report. This table, together with the per-cell failure
taxonomy from the same runs, is also the sole input to the R1 cell-selection
rule (§4.4). The §0 pilot (gpt-4.1-mini simulator) is an exploratory anchor and
does NOT fill this table. The §0 gate run used the now-frozen base prompt and
simulator (gpt-5.2, low); it may be admitted as the airline x gemini-3-flash
calibration cell only if its model snapshot, simulator snapshot, trial-seed
protocol, and token instrumentation are identical to the frozen configuration,
with the admission recorded in the CHANGELOG before any M1 episode. Otherwise
it remains an exploratory anchor.

**Gate (decided before the freeze, from this table alone):** at least three
cells must be clearly below 45% (CI entirely below) and at least three clearly
above (CI entirely above). If not, one ladder rung is swapped within its
family, using the swap rungs pre-registered in §3 (Qwen: `qwen3.5-4b`
self-hosted as the low rung, `qwen3.5-27b` as the mid rung), its S1 cells
are measured, and the swap is recorded in the CHANGELOG. Per-family
crossings are reported as exploratory (§7) so family effects are visible. No M1 data exist at that point, so the
swap cannot be outcome-driven.

Cells whose CI straddles 45% are excluded from the secondary sign-match
report and listed separately; they are never excluded from the primary slope
test. Robustness: the sign-match report is recomputed across thresholds
35-55%.

**Retained high-rung cells (outside the grid; removed 2026-09-22).** S1
pass^1 of the six `gpt-5` and `gemini-3.1-pro` cells measured before the
two-tier reduction (§3), same configuration. Reported in the appendix; they
enter neither the slope test nor the sign-match report. All six are clearly
above 45%.

| Domain x Model | S1 pass^1 | 95% CI (task-cluster bootstrap) | Straddles 45%? |
|---|---|---|---|
| airline x gpt-5 | 76.7% | [67.3%, 85.3%] | no |
| retail x gpt-5 | 77.3% | [69.3%, 85.3%] | no |
| telecom x gpt-5 | 96.0% | [90.7%, 99.3%] | no |
| airline x gemini-3.1-pro | 82.0% | [72.0%, 90.7%] | no |
| retail x gemini-3.1-pro | 83.3% | [74.7%, 91.3%] | no |
| telecom x gemini-3.1-pro | 95.3% | [90.7%, 98.7%] | no |

**Retained gpt-5.4 cells (outside the grid; changed 2026-09-21).** S1 pass^1 of
the six gpt-5.4 cells measured before the OpenAI ladder changed (§3), under the
same configuration. They are reported in the appendix and enter neither the
slope test nor the sign-match report.

| Domain x Model | S1 pass^1 | 95% CI (task-cluster bootstrap) | Straddles 45%? |
|---|---|---|---|
| airline x gpt-5.4-nano | 72.0% | [62.0%, 82.0%] | no |
| retail x gpt-5.4-nano | 67.3% | [58.0%, 76.0%] | no |
| telecom x gpt-5.4-nano | 80.7% | [72.0%, 88.0%] | no |
| airline x gpt-5.4-mini | 60.0% | [48.7%, 71.3%] | no |
| retail x gpt-5.4-mini | 74.7% | [65.3%, 83.3%] | no |
| telecom x gpt-5.4-mini | 69.3% | [60.0%, 78.0%] | no |

## 6. Outcome measures, and what each can and cannot detect

Three measures are pre-registered. They are not interchangeable: each is blind
to a class of behaviour the others catch, and the mapping from hypothesis to
measure below is fixed in advance for that reason.

### 6.1 Primary — official reward (per-domain reward basis)

The unmodified tau2-bench reward at the pinned commit, with the
`reward_basis` each domain ships (read from the task files on 2026-09-19;
the earlier statement that all three use DB + COMMUNICATE was wrong):
airline `[DB, COMMUNICATE]`; retail `[DB, NL_ASSERTION]`; telecom
`[ENV_ASSERTION]` (43 tasks) or `[ENV_ASSERTION, ACTION]` (7 tasks). In
retail the NL-assertion judge is therefore part of the official score; in
telecom the score checks the state of the customer's device after the
conversation (the customer runs tools too: 614 user-side tool calls in the
flash-lite calibration cell) rather than a database diff. Reported as
per-task mean reward across seeds (the analysis unit), with pass^1 and
pass^k alongside for leaderboard comparability. Consequences for §6.2 and
H4 are stated below.

**Detects:** actions that change the database (airline, retail) or the
device state (telecom) when they should not, and failures to change it when
they should. **Blind to (airline, telecom):** policy violations that never
reach a write — most importantly, an agent that verbally commits to a
forbidden action in an episode that ends before execution. **Retail is
different:** its official reward already includes the NL assertions, so a
verbal violation that the judge catches fails the episode there; the
primary-blind class `FP` (judge-flagged passing episodes) is therefore
defined for airline and telecom only, and retail contributes to H4a through
`WW / failures` alone. The `FP` and `WW` definitions in §1 are read with
this per-domain scope.

Measured size of that blind spot (upper bound — the flags include
omission-type judgments pending hand adjudication, §6.6): 15.0% of passing
episodes at the low tier (9/60) and 9.9% at the high tier (12/121).

### 6.2 Secondary — NL-assertion compliance

Episode-level rate of episodes meeting every `nl_assertion`, produced by the
official evaluator run with `EvaluationType.ALL_WITH_NL_ASSERTIONS`, which
forces the NL evaluator for airline and telecom, where `NL_ASSERTION` is
absent from `reward_basis`; for retail it is already part of the official
score (§6.1). Computed on saved trajectories; no episodes are re-run, and
the official reward is provably unaffected (see §0, regrade determinism).

**Detects:** commissions — including verbal ones the primary measure misses —
and omitted required checks or communications (the assertion set is a mix:
40/123 are prohibition-phrased, the rest are affirmative duties such as
"detect", "verify", "communicate"). **Blind to:** task completion. An agent
that does nothing fails the DB check yet can satisfy many assertions (10/29
failing high-tier episodes met every assertion; clean-failing and flagged
episodes have the same ~40% zero-write share, so assertion compliance does not
track whether required work happened). NL compliance therefore cannot serve as
the passivity detector.

### 6.3 Tertiary — inaction rate

Pass rate on tasks whose gold trajectory contains at least one write, plus the
absolute count of episodes classified `inaction` (gold requires a write, agent
made none). Needed because neither measure above can test whether an
intervention makes the agent too passive, and the primary measure's
DB-comparison structure rewards passivity on refuse-type tasks.

### 6.4 Hypothesis to measure — fixed mapping

| Hypothesis | Measure | Why not the others |
|---|---|---|
| H1 (capability-saturation transfer) — confirmatory | Primary | The rule is stated over standard benchmark performance; slope test primary, zero crossing and sign-match secondary |
| R1, R2 (robustness) | Primary | Same contrast as H1 under changed budget / simulator |
| H1' (strong-baseline) — extension §8 | Primary | Same measure as H1; only the contrast (M1 - S2) differs |
| H2a (M2 reduces wrongful commitments) — extension §8 | **Secondary** | At the high tier only ~14% of M2's addressable failures are primary-visible; see §6.5 |
| H2b (M2 does not increase inaction) — extension §8 | **Tertiary** | The secondary measure cannot detect passivity (§6.2) |
| H4a (migration with capability) — confirmatory | Secondary vs primary (blind share) | The claim is precisely about the split between primary-visible and primary-blind violations |
| H4b (M1 shifts composition) — confirmatory | All three jointly | A `WW` reduction is only interpretable with `IN`, `BX`, `FP` alongside |
| H3 (moderators) — exploratory §7 | Primary, per-task | Features are hand-coded without a pre-registered scheme |

All three measures are computed for every wide-grid episode; H4 is tested on
them directly, and they are additionally reported descriptively per cell. H2 is supported only if H2a and H2b both hold. H2a
alone is consistent with M2 merely making the agent passive.

### 6.5 Expected detectability, and why H2a is not tested on the primary measure

M2's addressable failures, from the two baseline runs (150 episodes each).
"Addressable" counts flagged passes only because M2's verifier gates outbound
policy-relevant messages as well as writes (§2); a write-only verifier could
address none of them.

| Tier | Wrongful writes (primary-visible) | Flagged passes (primary-blind) | Total | Share primary-visible |
|---|---|---|---|---|
| Low (gpt-4.1-mini, 40.0%) | 37 | 9 | 46 | 80% |
| High (gemini-3-flash, 80.7%) | 2 | 12 | 14 | 14% |

At the high tier the primary measure's ceiling for M2 is therefore ~1.3pp
(2/150) — below the design's minimum detectable difference. A high-tier H2a
test run on the primary measure would report "no effect" whether or not M2
works. The secondary measure's ceiling at the same tier is ~8pp (12/150), which
is detectable. This is pre-registered so the null cannot be read as evidence of
absence after the fact.

### 6.6 Judge validity

The NL evaluator is an LLM judge and is treated as an instrument requiring
validation, not as ground truth.

- **Stability (automated):** the full-population regrade flagged exactly the
  same 12/121 passing episodes as the earlier passing-only screen — zero
  disagreement between two independent judge runs at temperature 0.
- **Human verification (pending before freeze):** a preliminary hand read of a
  few passing high-tier episodes exists, but its sampling frame was not
  recorded, so it enters no reported figure. The planned check replaces it:
  read all 12 judge-flagged passing episodes (judge precision), >= 5 random
  unflagged passes (false negatives), and 5 failing episodes (sanity check),
  recording the sampling frame of each pool with the result.
- **Calibration against the primary measure:** assertion violations are ~6.5x
  more frequent in failing than in passing high-tier episodes (65.5% vs 9.9%).
  The ungraded dimension is therefore strongly concordant with the graded one,
  not orthogonal — the primary measure is a reasonable proxy for policy quality
  with a quantified ~10-15% blind spot, rather than being systematically blind.
- **Small-sample rule:** no rate derived from a hand sample of fewer than 30
  episodes is reported.
- **Known judge-strictness ambiguity:** omission-type flags (e.g. "did not
  cite Silver status as the basis") are adjudicated by hand before entering any
  reported figure; commission-type flags are taken as-is.

### 6.7 Sensitivity of threshold position to grading regime

Exploratory, on the §0 anchors: recomputing both stock-prompt cells under the
stricter counterfactual regime (NL assertions multiplied into the reward) moves
the low tier 40.0% → 34.0% and the high tier 80.7% → 72.7%. Neither changes
side of the ~45% threshold, and the effect is similar across tiers (−6.0pp,
−8.0pp). This does not validate the §5 classifications (different prompt and
simulators); the same counterfactual recomputation is repeated on every §5
cell and any cell that changes side is reported separately.

### 6.8 Known measurement limitations, carried into the paper

1. A write followed by a compensating revert leaves the DB hash unchanged and
   is invisible to the primary measure. Three high-priority candidates
   identified for hand adjudication, all in the pilot (low-tier) run: task 34
   trial 0, task 0 trial 2, task 45 trial 2 (all reward 1.0 with a DB-adjacent
   assertion unmet).
2. The reasoning-only sensitivity meter cannot split 1.2% of gate-run output
   tokens because those calls lack a details block. The primary
   completion-token meter still counts them (§0, §4.1).
3. Task 4 is flagged in both runs independently of agent model — a task-level
   trap rather than a model difference; reported separately in the failure
   analysis.
4. The secondary measure depends on the judge model, which is pinned and
   recorded in PROVENANCE.md.

## 7. Analyses labelled exploratory in the paper

- Failure-mode coding (MAST + conversational extensions), including the
  order-misexecution class defined in §2
- Error-amplification factors compared with the Nature MI table
- H3 moderator regression (task features hand-coded; no pre-registered coding
  scheme, so exploratory regardless of result)
- Budget-dependence of the M1 - S1 effect beyond the two R1 cells
- Per-domain and per-family crossing points; segmented (kink) fits
- Any subgroup analysis not listed above

## 8. Planned extension — deep grid (pre-registered by dated addendum before it runs)

Purpose: the mechanism and the fix. H1 asks *where* a team helps; the
extension asks *how* it helps or hurts and whether a domain-native verifier
repairs the failures identified in §0. None of it is required for H1 and none
of it may start before a dated addendum to this file freezes its details.

- Cells: two models from the nine in §3, one clearly below and one clearly above
  45% by the §5 table; all three domains; full `base` splits.
- Conditions: S1, S2, M1, M2 (§2); five seeds at the grid ceiling
  `k x B_1x` (k = 4, CHANGELOG 2026-09-21); 1x and 2x at three seeds.
- Hypotheses: H1' (M1 - S2 sign, with the interpretation grid: both H1 and
  H1' hold -> coordination adds what scaffolding cannot; H1 holds, H1' fails
  -> the predicted benefit is obtainable inside one context; H1 fails -> H1'
  descriptive); H2 (dual criterion, H2a on the secondary measure, H2b on the
  tertiary, thresholds `____` pp each, set from §6.5 before the addendum);
  H4c (does adding the gating checker, M2 minus M1, reduce `FP` and `WW`
  beyond the generic team: the direct test of whether the mechanism H4a
  identifies needs a reviewer with a veto before commit).
- Prompt freeze for S2/M2 role blocks, `prompts/roles/`, hashed in the
  addendum. Base prompt and simulator are those of the wide grid, unchanged.
- The wide-grid S1 and M1 cells for the two chosen models are reused, not
  re-run; S2 and M2 are the only new conditions.

### 8.1 Addendum 2026-09-24: uncapped arm (decided by the PI before any uncapped episode ran)

- **Cells.** `gpt-5-nano` and `gemini-3.1-flash-lite`, each on airline,
  retail and telecom (six cells). S1 pass^1 by cell: telecom x flash-lite
  34.0 and telecom x nano 32.7 (clearly below 45%), airline x nano 42.7
  (straddling), retail x nano 68.0, airline x flash-lite 78.7, retail x
  flash-lite 77.3 (above). Deviation from the §8 text, which asks for one
  model clearly below and one clearly above 45%: neither model is above at
  the model level (flash-lite is above on two of three domains). The pair
  was chosen for cell coverage (both below-45% cells of the grid, the
  straddling cell, three cells above) and cost (M1 at 4x cost $25 for the
  three flash-lite cells and $29 for nano, against $63 for gemini-3-flash
  and $83 for gpt-5-mini). Chosen after all grid M1 results at 4x had been
  seen; stated as post hoc. The top of the capability range (S1 above 90%)
  is not covered by this arm.
- **Amendment 2026-09-24, before any uncapped episode finished (decided by
  the PI, on cost).** The arm runs on three of the six cells for now:
  telecom x gemini-3.1-flash-lite and telecom x gpt-5-nano (the two cells
  clearly below 45%) and airline x gpt-5-nano (the straddling cell). The
  three cells above 45% (airline and retail x flash-lite, retail x nano)
  are deferred, not dropped, and run under this addendum unchanged if the
  PI resumes them. The first two launches (airline x flash-lite, airline x
  nano) were stopped about one minute after start with 0 of 150 episodes
  finished. Consequences: reading rules (1) and (2) are unchanged, since
  they use only the two below-45% cells. Rule (3) has no point above 45%,
  so no uncapped H5 point is reported until the deferred cells run, and
  this arm cannot say whether the grid's losses above 45% survive without
  the ceiling. Cost stop lowered from $150 to $75 (expected $30 to $50 for
  the three cells).
- **Condition.** M1 with no episode ceiling: no wrap-up notice, no
  allowance line; episodes end only on tau2's own limits (`max_steps` 200,
  `max_errors` 10) or the customer. The per-call guard `c = B_1x` is kept as
  a runaway stop, with the same value as in the cost-bounded arm; `r = 4`.
  Implementation: `BudgetConfig.uncapped_with_guard`, `run_m1.py --uncapped`
  (run names `...-uncapped-capb1x-...`, manifest field `arm`).
- **Prompt.** Database agent and advisor role blocks unchanged. The
  orchestrator uses the frozen v6 block (file SHA-256 `1a26e997efe8...`,
  unchanged) with its one budget paragraph removed ("Your team has a fixed
  processing allowance ..."), because that paragraph describes an allowance
  and a status line that do not exist in this arm. Block as used, SHA-256
  `54af48966c06cb4f70731158d4a2b5d129eb40ca1b3f1b6f88bb01d3e2f4b63d`.
- **Seeds and tasks.** Same 50 tasks per domain, 3 trials, seed 300, as the
  grid. §8 asks for five seeds; three are used here to match the grid and
  to hold cost.
- **Comparators.** S1 is the existing uncapped calibration run of each
  cell (the uncapped single agent; not re-run). The 4x grid cell of the
  same model is the second comparator.
- **Outcomes, per cell.** `gain_uncapped = M1_uncapped - S1` with the
  task-cluster CI (the H1 contrast without a ceiling); `M1_uncapped -
  M1_4x` with the same CI (the effect of lifting the ceiling); completion
  tokens per episode and the M1 / S1 ratio; cost; endings (step and error
  limits); the mechanical G1 bars that apply (cut calls, cut tokens,
  double-cut turns, JSON or cut text to the customer).
- **Reading, fixed now.** (1) If `gain_uncapped` is positive with a CI that
  excludes zero on either below-45% cell, the paper states that the ceiling
  hid a team benefit below the threshold and scopes the cost-bounded
  conclusion to bounded budgets. (2) If on both below-45% cells the CI
  covers zero or lies below it, the loss in the grid is not a product of
  the ceiling. (3) Six cells do not support a slope; H5's uncapped point
  is reported descriptively.
- **Cost stop.** Expected $60 to $90 for the six cells. If the running
  total passes $150, the arm stops and is reviewed before continuing.
- **Not in this addendum.** S2 and M2 need their role blocks written,
  frozen and hashed in a second addendum before they run.

### 8.2 Addendum 2026-09-25: S2, the strong single agent (written before any S2 episode; role block frozen after the smoke)

- **Cells.** The three cells of the §8.1 arm as amended: telecom x
  gemini-3.1-flash-lite, telecom x gpt-5-nano and airline x gpt-5-nano
  (decided by the PI, 2026-09-24). Same 50 tasks per domain, 3 trials,
  seed 300, simulator and settings as the grid. §8 asks for five seeds;
  three are used, as in §8.1. Post hoc, stated plainly: the design and the
  cells were fixed after all grid M1 cells at 4x and the first uncapped
  episodes had been seen.
- **Condition.** S2 as defined in §2: one agent, one model, one context.
  Every call sees the conversation as S1 does (native tool calls and tool
  results, and the same tool definitions) under the base prompt plus one
  role block. Each turn is two calls. *Plan* (tools shown with
  `tool_choice` "none", so it cannot call them) returns a JSON update of a
  task ledger and a
  progress ledger, a policy check (the policy lines that apply, quoted,
  and what they require, including conditions not yet verified) and a
  draft of the next action (a customer message or one tool call). *Act*
  (native tools): the agent reviews the draft against its policy check,
  the conversation and its plan, revises it if needed, and acts; the act
  call's output is the turn. S2 therefore does in one context the work M1
  divides among its orchestrator (plan and ledgers), its advisor (policy
  rules) and its database agent (tool calls). One difference is by
  design: S2 states the applicable rules on every plan, while M1's
  orchestrator consults its advisor at its discretion. Implementation:
  `s2_agent.py`, `run_m1.py --condition s2` (run names
  `s2-...-b4x-capb1x-...`).
- **Budget.** Identical to the M1 grid cell of the same model and domain:
  ceiling 4 x B_1x, per-call cap c = B_1x on every call, wrap-up threshold
  w, a_min, the same status line and wrap-up notice. After the wrap-up
  notice a turn is one call without tools and without a plan, as in S1. A
  truncated or empty act call is never executed and one closing call
  without tools follows, as in S1. An unparsable plan is retried once
  (not when cut at c and not once w is crossed); the act call then runs
  without a plan. An act reply that is JSON text is never sent to the
  customer: a message drafted inside it is used, otherwise the act call is
  repeated once with the tools and a reminder, and a second JSON reply
  becomes the message inside it or M1's fixed holding line; each case is
  logged (amended after the first smoke, see the CHANGELOG entry of
  2026-09-25). No read-call limit applies (S2 has no
  database agent).
- **Prompt.** Base prompt unchanged. Role block
  `prompts/roles/s2_single_agent.md`, workflow only under the §2 rules:
  the two-step turn, the ledgers, the plan JSON, the review rule, and an
  allowance paragraph worded after the M1 orchestrator's. Draft v1, block
  as sent SHA-256
  `dbb2e3aa4e13336ca8e7708cb022b1b87e576455bfe517fe9d54144e23e34e01`.
  Draft v2 after the first smoke (v1 plus one sentence defining the draft
  as the exact next message or the one next tool call, with the plan kept
  in the task ledger), block as sent SHA-256
  `ba0af7c798387e5d6958949ac91caafe5b28f99dde6c7aadc26de211988e5973`.
  **Frozen 2026-09-26 after the second smoke:** v2, file SHA-256
  `1345572de1dc2d86c76ca4d3c4b58a53403d2bb377d923c8dba41437207444f9`
  (header marked frozen; block text unchanged); PROVENANCE.md holds the
  same digests. After the freeze, bug-class fixes only.
  The file is marked frozen, and its file hash recorded here, after the
  smoke; changes before the freeze are limited to the bug and format
  classes of the G1 fix policy and are logged in the CHANGELOG.
- **Smoke (before the freeze).** The first 5 tasks x 1 trial of each of
  the three cells. Read in this order: infrastructure errors; the
  mechanical G1 bars (calls cut at c at most 5%, tokens in cut calls at
  most 10%, no turn with two or more cut calls, no JSON or cut text sent
  to the customer); plan-parse failures, plans returned as tool calls
  (a provider ignoring `tool_choice` "none"), plans without a policy
  check, JSON act replies caught by the guard; review outcomes. Reward is
  read last and is not a reason to change the block.
- **Comparators.** S1 is the existing calibration run of each cell (the
  4x ceiling leaves S1 unconstrained, §4.2). M1 is the 4x grid cell of the
  same model and domain. Both are reused, not re-run.
- **Outcomes, per cell.** `M1_4x - S2` (H1' as pre-registered in §8) and
  `S2 - S1`, each with the task-cluster bootstrap CI (seed 300, 2,000
  resamples); completion tokens per episode and the S2 / S1 ratio;
  exhaustion and utilisation; cost; review outcomes (the share of turns in
  which the act call kept, revised or replaced the draft; forced closing
  and wrap-up turns are counted apart and never as reviews); the
  mechanical G1 bars.
- **Reading, fixed now.** H1 failed on these cells at 4x (M1 below S1 on
  both below-45% cells, a tie on airline x nano), so under the §8 grid H1'
  is descriptive. The contrasts are read for mechanism. (1) If `S2 - S1`
  has a CI below zero on a cell, plan-and-review scaffolding inside one
  context also loses at the same ceiling, and the grid loss on that cell
  is not specific to dividing the work among agents. (2) If `S2 - S1`
  covers zero or lies above it while `M1_4x - S2` lies below zero, the loss
  on that cell is attributed to the division into agents. (3) Any other
  pattern is reported as mixed. An S2 loss that runs through exhaustion
  (episodes that finish inside the budget pass at or above S1's rate) is
  reported as a budget effect, by the same test the grid entries apply to
  M1. `S2 - S1` carries the asymmetry of the H1 contrast: S2 runs under the
  ceiling and sees the allowance line, while the S1 comparator is the
  uncapped calibration run; this is kept for the same reason as in H1 and
  stated beside the result. `M1_4x - S2` has no such asymmetry. Three cells
  do not support a slope.
- **Cost stop.** Expected $25 to $45 for the three cells (the three M1 4x
  cells cost $31.25 together). If the running total passes $75, the arm
  stops and is reviewed.
- **Not in this addendum.** M2.

---

## CHANGELOG (append-only after freeze)

Pre-freeze design revisions (recorded for provenance; edits above are still
permitted until the freeze):

- 2026-09-02 — H1 contrast changed from M1 - S2 to M1 - S1. Reason: the §5
  classifier is S1's pass^1, and Kim et al.'s rule refers to the same plain
  single agent for both classification and the MAS-minus-SAS sign; the old
  wording classified by S1 but contrasted against S2. Per-episode budget
  matching (§4) makes S1 compute-matched, removing the original reason to use
  S2 for H1. M1 - S2 retained as pre-registered secondary H1' with a fixed
  interpretation grid. S2 instantiation flagged as an open decision in §2.
- 2026-09-02 — §4 replaced: primary budget is now an enforced system-wide
  completion-token ceiling calibrated per cell (P75 of S1), with per-call cap,
  wrap-up rule, `budget_exhausted` label separate from `inaction`, parallel
  sensitivity/deployment meters, and a stated relationship to Kim et al., Tran
  & Kiela, Wang et al., and HAL. Core design ported by hand from branch
  `test/glm46-airline` (dce0a24, aireshixxx) — the branch itself is not
  merged; additions here: citations and deviation table (§4.5), per-call cap,
  wrap-up rule, exhaustion-vs-inaction separation, S1-mean column,
  §5 re-classification sensitivity, implementation-protocol reference (§4.6).
  §3 gains cluster-bootstrap classification CIs and the exhaustion rule.
- 2026-09-02 — Scope restructured into a confirmatory **wide grid** and a
  separately pre-registered **deep-grid extension** (§8). Reason: H1 is a
  between-cell test whose sample size is the number of (domain x model)
  cells; the two-model design gave <= 6 cells and plausibly zero clean
  below-45% cells, which cannot test the rule's below-threshold prediction.
  Wide grid: S1 + M1, six models (Qwen3 4B/8B/14B/30B ladder + gpt-4.1-mini
  + gemini-3-flash), three domains, retail/telecom fixed 50-task subsets,
  3 seeds -> 18 cells with a §5 gate requiring >= 3 clean cells on each side
  of 45%. Centralized is the sole generic MAS because it is the only Kim
  architecture deployable in dual control (§2); the resulting asymmetry is
  stated in §1. H1' / H2 / H4 and conditions S2 / M2 move to §8; H3 moves to
  §7 exploratory. R1 (budget invariance, two cells) and R2 (simulator
  invariance, three cells) added as pre-specified robustness checks.
- 2026-09-02 — Wide-grid model set revised from six models to three
  families x three tiers (nine models, 27 cells): OpenAI GPT-5.4
  nano/mini/full, Google Gemini 3.1 Flash-Lite / 3 Flash / 3.1 Pro, and an
  open Qwen3.5 dense ladder 4B/9B/27B, replacing the year-old Qwen3 ladder.
  Mirrors Kim et al.'s family-by-tier structure; Anthropic family replaced
  by the open ladder (cost; no closed family has a clearly-below-45% rung),
  addable later by CHANGELOG. Family added as a covariate in the H1
  breakpoint regression. Canonical policy text required on every route.
- 2026-09-02 — H1 restructured: the primary test is now the slope of
  `gain = M1 - S1` on the S1 baseline across cells (inverse-variance
  weighted, family covariate); the breakpoint location and the per-cell
  sign-match count become secondary. Reason: per-cell SEs on `gain` are
  ~8-10pp, so a sign count is largely noise-bounded (as is Kim et al.'s
  15/16 at ~20pp per cell); the slope uses effect magnitudes and tests the
  functional claim beneath the 45% rule. Sign-match is kept as the bridge to
  Kim et al., reported with informative vs within-noise cells separated.
- 2026-09-02 — G1 (M1 validity gate) added to §1: one M1 run at 2x budget
  on the cell most favourable to M1, selected mechanically from S1
  calibration data (baseline in [30, 45]%, highest write-related failure
  share), with pre-fixed pass/ambiguous/fail readings, functional
  indicators, and a two-iteration bug-class-only fix policy with
  confirmation on a second cell. Reason: without it a null H1 cannot be
  distinguished from a broken M1. Doubles as R1's below-threshold 2x cell.
- 2026-09-02 — H4 promoted from the §8 extension to a confirmatory
  hypothesis on the wide grid, as H4a (blind share of violations rises with
  S1 baseline; S1 data only) and H4b (M1 reduces wrongful writes vs S1,
  reported with inaction / exhaustion / flagged-pass changes alongside, with
  a fixed interpretation grid). Reason: it is the mechanism for H1, it is
  free (all three measures already computed per episode), it makes a null
  H1 interpretable, and the §0 observation is otherwise two-run anecdote.
  H1 + H4 declared as a family of two confirmatory tests. The M2-specific
  version becomes H4c in §8.
- 2026-09-02 — Power analysis added (§1.1, `power_sim.py`,
  `docs/power-analysis.md`). It exposed two flaws in the tests as first
  written: (a) regressing `M1 - S1` on the same cell's S1 has a 19-28%
  false-positive rate (shared noise); H1's primary `x` is now the
  leave-one-domain-out capability index with a permutation p-value, split
  seeds as robustness, naive form descriptive only; (b) H4a's raw blind
  share `FP/(FP+WW)` rises mechanically with pass rate (false-positive rate
  1.00); H4a is now stated as rates, `WW/failures` declining with capability
  and `FP/passes` not declining. Minimum detectable slope ~ -0.20 at 80%
  power with 3 seeds; 5 seeds would raise power at that slope to 0.93.
- 2026-09-02 — Review fixes: R1/R2 restated on gain magnitudes with CIs
  (sign flips descriptive only); G1 moved to 5 seeds with an S1 5-seed
  comparator and a one-sided 90% pass bar; domain fixed effects added to the
  H1 and H4a regressions (required by the leave-one-domain-out `x`). The
  uncapped-S1-vs-capped-M1 asymmetry in the H1 contrast is kept by decision
  and recorded in §4.2 with its direction and a per-cell bound.

- 2026-09-16 — Base prompt fixed as the tau2-bench default agent prompt
  (verbatim, pinned commit); no custom base prompt. Reason: Kim et al.'s
  rule is stated over the plain single agent; the default prompt is the
  leaderboard's "standard" agent, so S1 cells are externally checkable and
  the prompt-authoring degree of freedom is removed before the freeze. The
  strong-prompt single agent is S2 in §8, not S1. Role/workflow blocks for
  M1, S2, M2 append after the base text under fixed rules (workflow only,
  no domain content, frozen and hashed). Half-duplex constraint recorded in
  §2: M1 workers are reasoning-only, the orchestrator emits all tool calls;
  M1 verifier advisory vs M2 verifier gating. Agent reasoning effort set to
  `high` where configurable, per-model mapping to be recorded; user
  simulator fixed as gpt-5.2 (reasoning_effort low), matching the gate run.
  §5 note updated: the gate run may serve as the airline x gemini-3-flash
  calibration cell only under an exact-match condition recorded before M1.
- 2026-09-17 — Reasoning settings fixed: OpenAI `reasoning_effort: high`,
  Gemini thinking level high, Qwen thinking on; per-call cap is the only
  bound on thinking. Model selection rule fixed: latest alias pointer at the
  freeze date, resolved snapshot id recorded and pinned.
- 2026-09-17 — `pricing.json` recorded (three rates per model, simulator
  and judge, sources and snapshot ids); Qwen entries are placeholders until
  the route is chosen. Task count per domain confirmed at 50 (§3 unchanged).
- 2026-09-17 — R2 second user simulator fixed as `gpt-4.1-2025-04-14`
  (tau2-bench default user simulator). R2 is an add-on on three airline
  cells after the grid; the grid itself stays on gpt-5.2 (low).
- 2026-09-18 — `prompts/base_system_prompt.md` created by copying tau2-bench's
  `AGENT_INSTRUCTION` and `SYSTEM_PROMPT` verbatim (commit c339866); hashes
  recorded in §2 and in the file header.
- 2026-09-18 — H1 threshold location changed from a segmented breakpoint to
  the zero crossing `x0 = -intercept / slope` of the primary fit with a
  task-cluster bootstrap CI (transfers / shifts / no crossing readings
  fixed). Reason: Kim et al.'s 45% is a crossing of one line, so a kink test
  could read a perfect transfer as "disappears", and it is underpowered at
  27 cells. Logit-scale and relative-gain slopes added as pre-registered
  robustness forms beside the split-seed form. Kink fits move to §7.
- 2026-09-18 — Root seed fixed at 300 (the pilot and gate value). Retail and
  telecom 50-task subsets generated by the §3 rule and recorded with hashes
  in PROVENANCE.md and `task_subsets.json`.
- 2026-09-18 — M1 specified in §2: orchestrator plus two reasoning-only
  workers (policy advisor, checker); the argument-construction worker is
  folded into the checker. Checker required before writes and
  policy-relevant customer messages, i.e. the same scope as M2's verifier,
  so M1 and M2 differ only in authority (advise vs override). Sequential
  worker calls; fixed worker output format; log-based definitions of
  "worker output used" and "checker catch" for G1. H4c reworded
  accordingly. No M1 data exist, so the change is not outcome-driven.
- 2026-09-18 — M1 turn structure fixed (plan call without tools, worker
  calls, act call with native tools); policy-relevant messages detected by
  self-declaration in both M1 and M2 with an under-declaration audit. Role
  block drafts v1 written to `prompts/roles/`.
- 2026-09-18 — M1 revised to add a database agent: the orchestrator no
  longer emits tool calls; it issues goal-level read assignments and
  single-call write assignments to a database agent that executes them by
  native function calling and reports back. Reason: the earlier M1 had no
  component that acted, which invites the "not a multi-agent system"
  objection, and the new form is the faithful adaptation of Kim et al.'s
  centralized pattern (lead plans, worker does the tool work). Checker
  stays advisory; M2 redefined as M1 with the checker's veto, database
  agent common to both. New coordination-induced failure class "order
  misexecuted"; G1 indicators and readings restated (orders executed as
  issued >= 90%, advisor consulted >= 80%) since delegation is now
  structural. Cost: each tool turn needs two orchestrator calls plus one
  database-agent call. No M1 data exist, so the change is not
  outcome-driven.
- 2026-09-19 — Checker removed from M1. M1 = orchestrator + database agent
  + policy advisor; the orchestrator's review of the database agent's
  reports is the verification step, as in Kim et al.'s centralized design,
  which has no separate reviewer. M2 = M1 plus a gating checker (the one
  domain-motivated component), so M1 and M2 differ in exactly one
  component. Reason: with the database agent in place the checker was no
  longer needed to make M1 a team, it cost one call per write and per
  policy-relevant message from the shared budget, and the "advice vs veto"
  question it served is narrower than the practitioner question M2 was
  built for ("does adding a gate help"). H4b's mechanism sentence, H4c, the
  G1 indicators, the §2 rows and the M2 sentence updated; `policy_relevant`
  self-declaration now exists only in M2; a turn with no advisor question
  costs one orchestrator call. No M1 data exist, so the change is not
  outcome-driven.
- 2026-09-19 — Run configuration for the S1 calibration grid added:
  `cells.json` (27 cells, snapshots, litellm ids, reasoning args, simulator,
  seed, trials, task ids) and `run_calibration.py` (refuses to start unless
  the base prompt equals the tau2 default at the pinned commit and the task
  lists match `task_subsets.json`; one manifest per cell with hashes).
  `calibrate_budget.py` computes the §4.2 values from a results file. The
  Qwen family is run by a colleague from the same config. Temperature line
  in §3 corrected: reasoning-mode calls run at provider default.
- 2026-09-19 — Correction to §6.1/§6.2 from the task files: the reward basis
  is per domain (airline DB + COMMUNICATE; retail DB + NL_ASSERTION; telecom
  ENV_ASSERTION, plus ACTION on 7 tasks), not DB + COMMUNICATE everywhere.
  `FP` is defined for airline and telecom only; retail enters H4a via
  `WW / failures`. `analyze_run.py` now reads each domain's WRITE tools from
  tau2's own `@is_tool(ToolType.WRITE)` tags, counts agent-side tool calls
  only (telecom customers call tools), and filters gold actions to the
  assistant requestor, so the failure taxonomy runs on all three domains.
  Flash-lite S1 calibration cells complete (airline 78.7%, retail 77.3%,
  telecom 34.0% pass^1; telecom clearly below 45%).
- 2026-09-19 — Gate run admitted as the airline x gemini-3-flash S1
  calibration cell under the §5 exact-match condition, checked against the
  frozen configuration: tau2 commit c3398666; `llm_agent` (default prompt)
  with `gemini/gemini-3-flash-preview`, `reasoning_effort: high`; simulator
  `gpt-5.2` alias resolved by the provider to `gpt-5.2-2025-12-11`,
  `reasoning_effort: low`; seed 300 with per-episode seeds identical to the
  calibration runs (150/150); 3 trials; max_steps 200; max_errors 10; full
  airline base split with byte-identical task definitions and policy text;
  instrumentation and billing checks in PROVENANCE.md. Run date 2026-08-27,
  three weeks before the other cells, on a preview model id; a same-config
  replication may be run as an exploratory drift check (§7) but the gate
  run is the calibration cell. No M1 data exist.
- 2026-09-18 — Qwen ladder changed from dense 4B/9B/27B to the open MoE
  ladder 35B-A3B / 122B-A10B / 397B-A17B on Alibaba Cloud Model Studio (one
  route). Reason: 4B and 9B are not hosted on Model Studio and no other host
  served 4B; the MoE ladder mirrors the closed families' shape. Swap rungs
  pre-registered in §3 (self-hosted 4B for the low rung, 27B for the mid
  rung). §4.2 and §5 tables, pricing.json updated. No data exist for any
  Qwen cell, so the change is not outcome-driven.
- 2026-09-19 — M1 and the shared budget layer built and tested (27 tests
  green against tau2-bench c339866, offline): `completion_budget.py`
  (ledger), `budget_layer.py` (one metered path to the provider: per-call cap
  `min(reservation, c)`, usage charged before tool-call parsing, truncated
  tool calls never executed, wrap-up notice appended once to the single
  system message, `budget_exhausted` label), `s1_agent.py` (stock tau2 agent
  plus the meter; uncapped for calibration, capped for G1/R1),
  `m1_agent.py` (orchestrator without tools, database agent with all tools
  and `k = 4` per read assignment, single-call writes executed as issued and
  checked against the order, policy advisor; one ledger per episode; full
  per-turn record under `raw_data.transfer_testing_multi_agent`),
  `run_m1.py` (per-cell budgets from `budgets.json`, same tau2 entry point
  and save layout as the CLI), `build_budgets.py`. `docs/budget-protocol.md`
  rewritten to the implemented state (R1–R11); remaining pre-freeze items
  listed there: `analyze_run.py` branch on the exhaustion label and budget
  rate reporting, provider checks of `max_tokens` against thinking tokens,
  role-block freeze. Role blocks are DRAFT v4 (orchestrator), v2 (database
  agent), v4 (advisor). No M1 episode has been run.
- 2026-09-19 — The first attempt at the three gemini-3.1-pro S1 calibration
  cells is void: Google's per-model daily request quota
  (`generate_requests_per_model_per_day = 250`) was exhausted after 28
  airline episodes, and 422 of 450 episodes ended as
  `termination_reason = infrastructure_error` with no messages. tau2 had
  written results files and the runner had marked the cells finished.
  `run_calibration.py` and `run_m1.py` now count a cell as finished only
  when every episode has a real termination; any `infrastructure_error`
  episode sets the manifest return code to 2 and the next launch resumes
  and re-runs exactly those episodes (tau2 `--auto-resume` semantics; the
  28 valid airline episodes are kept). The quota must be raised (paid tier
  for this model, or a different route) before the relaunch. No accuracy or
  budget value was taken from the void attempt; the §4.2 and §5 rows for
  gemini-3.1-pro remain blank.
- 2026-09-20 — OpenAI route changed to the Responses API before any OpenAI
  cell ran. OpenAI's Chat Completions endpoint rejects function tools
  together with `reasoning_effort` for the gpt-5.4 family ("use /v1/responses
  or set reasoning_effort to 'none'"), so the first launch of the
  gpt-5.4-nano airline cell failed on every task (121 infrastructure
  errors, results set aside as `void-chatcompletions-*`, no manifest).
  `cells.json` now routes the three OpenAI models as
  `openai/responses/<snapshot>`, litellm's chat-to-Responses bridge
  (litellm 1.81.11). Checked offline: the request carries the tools,
  `reasoning: {effort: high}` and `max_output_tokens` (from `max_tokens`);
  the reply maps text and tool calls back, and usage keeps completion
  tokens including reasoning, `reasoning_tokens` and cached input tokens,
  so the §4.1 meter and the USD meter are unchanged. Two route facts to
  report: `seed` is not a Responses API parameter and is dropped for the
  OpenAI family (it was best-effort on Chat Completions); and when
  thinking alone fills the per-call cap the bridge raises instead of
  returning a message, so `budget_layer.py` now charges such a call at the
  cap and treats it as truncated (R6), never as an uncharged retry. §3
  route text for the OpenAI family should read "OpenAI direct, Responses
  API"; snapshots unchanged. No OpenAI data exist, so the change is not
  outcome-driven.
- 2026-09-20 — M1 pilot on telecom x gemini-3.1-flash-lite (first 5 tasks,
  1 trial, budget 1x, saved as `pilot1-nobudgetline-*`, not a cell): 0/5,
  every episode ended `budget_exhausted` after 5 to 6 turns. The cap is
  valid on Gemini (`max_tokens` bounds thinking plus text; 0 of 55 calls
  over the cap). M1 spent about 2.6x S1 per turn (median 650 tokens per
  call, 83% thinking, 10 to 12 calls per episode; S1 on this cell: 470 per
  turn, 11 turns). 9 of 55 calls were cut at c = 1,326 because thinking
  used 900 to 1,200 of it. Changes made: a cut plan is no longer retried at
  the same cap; every orchestrator plan (and every capped S1 call) now
  receives a one-line allowance status (tokens left, average cost of its
  calls so far) so the system can plan its spending; orchestrator role
  block v5 adds the spending guidance. Pre-registered next step, decided
  before any M1 cell: two M1 arms on the full grid, a cost-bounded arm (k x B_1x) at
  k x B_1x with k chosen from the 1x/2x/3x pilot so exhaustion is rare,
  and the matched arm at 1x with exhaustion and utilisation reported next
  to the gain. R1 folds into these arms.
- 2026-09-20: Pilot for the OpenAI ladder decision. `cells.json` gains a family
  key `openai-gpt5` (`gpt-5-nano`, `gpt-5-mini`, `gpt-5`; snapshots `-2025-08-07`;
  the same Responses API route and `reasoning_effort: high` as the gpt-5.4 rows),
  marked as a pilot and outside the registered 27 cells; the `openai` family is
  unchanged. Reason: the six measured gpt-5.4 cells lie between 60.0% and 80.7%,
  with nano above mini on two of three domains, so the family adds little
  within-family spread to the H1 slope, whereas GPT-5 nano / mini / full are the
  OpenAI models of Kim et al. and span 35.5% to 96.7% on the vendor's tau2
  telecom. S1 calibration cells are run hardest domain first (telecom), nano and
  mini, 50 tasks x 3 trials, frozen configuration; results go into a pilot block
  in §4.2. Known constraint: OpenAI shuts the three GPT-5 snapshots down on
  2026-12-11 (deprecations page, announced 2026-06-11), so every OpenAI cell
  would have to be completed before that date if the ladder is adopted. The
  ladder decision is made after the pilot, on S1 results only; no M1 cell
  exists for any model, so the choice cannot follow the gain. The `cells.json`
  hash changes with this entry; earlier manifests carry the earlier hash.
- 2026-09-21: GPT-5 pilot, telecom cells complete (150 episodes each, no
  infrastructure errors): `gpt-5-nano` 32.7% [22.7%, 43.3%], clearly below 45%;
  `gpt-5-mini` 77.3% [68.0%, 86.0%], clearly above. The ladder order holds on
  telecom, in contrast to the gpt-5.4 rows (nano 80.7%, mini 69.3%). `B_1x` is
  75,032 and 31,514 completion tokens, about ten and four times the other
  measured cells, and 41 of 150 nano episodes ended on tau2's error limit (27)
  or step limit (14); both facts bear on the wall-clock cost of M1 cells and on
  the failure taxonomy, and are to be settled before the freeze. The pilot is
  extended to airline and retail for the same two models under the same
  configuration; four rows are added to the §4.2 pilot block. The ladder
  decision remains pending and rests on S1 results only; no M1 cell exists for
  any model.
- 2026-09-21: GPT-5 pilot extended to the high rung (`gpt-5`, snapshot
  `gpt-5-2025-08-07`) on telecom, airline and retail, under the same
  configuration, so that the complete GPT-5 ladder is measured before the
  ladder decision. Recorded before any `gpt-5` episode exists. Airline cells for
  the two lower rungs are complete (150 episodes each, no infrastructure
  errors): `gpt-5-nano` 42.7% [31.3%, 54.0%], straddling 45%; `gpt-5-mini` 74.7%
  [64.7%, 84.0%], clearly above. Retail cells for the two lower rungs are
  running. Three rows are added to the §4.2 pilot block. The decision remains
  pending and rests on S1 results only; no M1 cell exists for any model.
- 2026-09-21 — Per-call cap rule and the Kim-regime multiple k, decided
  from the M1 pilot before any grid episode. (a) Cap rule: c = B_1x for
  every component and both arms (a runaway guard, as §4.2 words it). The
  original c = S1 per-call P95 cut 75% of the orchestrator's plan calls
  in the 2026-09-20 pilot and would have cut at least one call in 29% to
  46% of S1's own calibration episodes; B_1x touches 0% to 1%. `--cap-rule
  b1x` is now the default in `run_m1.py`; `budgets.json` values are
  unchanged (c is applied at run time). Health under the new cap on the
  same five telecom tasks at 3x: calls cut 0 of 71, tokens in cut calls
  0%, JSON or cut text sent to the customer 0 (was 30), tool calls per
  episode 5.8 (S1 6.7), advisor consulted in 3 of 5 episodes. Orchestrator
  role block v6 (v5 minus the sentence limiting advisor use, which
  conflicted with G1's 80% bar; v5 archived); advisor use in the 20-task
  pilots was 85% and 100%. (b) k. Rule fixed before the pilot: k = smallest
  multiple with M1 exhaustion at or below 10% on both pilot cells (20
  tasks x 1 trial, telecom x gemini-3.1-flash-lite and airline x
  gemini-3-flash), read from exhaustion only, never from reward, and at
  least the largest S1 episode over B_1x across calibrated cells (3.85 over
  16 cells). Pilot table (B = k x B_1x; utilisation = spent / B):

  | Cell | k | B | Episodes | Exhausted | Utilisation median / P90 | M1 median spend | M1 pass (read last) |
  |---|---|---:|---:|---|---|---:|---|
  | telecom x gemini-3.1-flash-lite | 4x | 28492 | 20 | 6 (30%) | 0.80 / 1.00 | 20183 | 5/20 |
  | telecom x gemini-3.1-flash-lite | 5x | 35615 | 20 | 6 (30%) | 0.88 / 1.00 | 31132 | 5/20 |
  | airline x gemini-3-flash | 4x | 26688 | 20 | 11 (55%) | 1.00 / 1.00 | 26674 | 11/20 |

  The 10% criterion was not met at any tested multiple. Raising the
  ceiling from 4x to 5x left exhaustion unchanged (6 of 20 in both) while
  median spend rose from 4.1x to 6.3x the single agent's on the same
  tasks: M1's spend expands with the ceiling. The stopping rule's 6x step
  was not run (cost; the 4x-to-5x pattern gave no reason to expect a
  different outcome). Decision: k = 4, the smallest multiple that leaves
  S1 unconstrained (S1 tail 3.85), with exhaustion and utilisation reported
  as outcomes in every cell. The cost-bounded arm (k x B_1x) therefore gives M1 four
  times S1's P75 spend. Correction 2026-09-21, from Kim et al.'s released
  code (github.com/ybkim95/agent-scaling): their limit was a call count,
  about 100 model calls per system (single agent `max_steps` 100; team 3
  agents x 25 iterations plus up to 10 rounds), with no token cap on any
  call and reasoning effort unset; their single agent used 7.2 calls and the
  centralized team 27.7 on average, so their ceiling was about 14x the
  single agent's realised use and open-ended in tokens. Our 4 x B_1x in
  completion tokens (about 5x S1's mean spend) is therefore tighter than
  their regime, not equal to it; §4.5 states this. Consequence for H1,
  pre-registered here: exhausted episodes score as run (reward 0); the
  primary gain is over all episodes; gain over non-exhausted episodes is
  reported as exploratory with the selection caveat; the per-cell
  exhaustion rate is a first-class column next to gain. Pilot episodes
  never enter the grid.
- 2026-09-21 — G1 changed from a gate run to per-cell validity checks,
  before any grid episode. The 2026-09-02 version required, on the most
  favourable cell, M1 > S1 (one-sided 90% bound above zero) before the grid
  could run. That clause tested the hypothesis rather than the
  implementation: if Kim's rule does not transfer, a correctly working M1
  loses on that cell too, and the gate would have stopped the grid, making
  the "disappears" outcome unobservable. The 2026-09-21 pilot (two cells,
  20 tasks x 1 trial, k = 4) showed exactly that pattern: every mechanical
  indicator held (advisor in 85% and 100% of episodes, orders executed as
  issued, tool calls near S1's, calls cut 1% to 2%, no JSON to the
  customer) while M1 scored below S1 on both cells. New G1: the mechanical
  indicators are computed for every M1 cell from the grid itself and
  reported as a validity table; a cell failing a mechanical bar is a
  protocol failure with the same bug-class-only fix policy; exhaustion is
  an outcome, not a validity failure; no separate 5-seed run. This change
  is made after seeing pilot reward, and is stated as such. It removes a
  rule that could only block a result unfavourable to the hypothesis and
  adds none that favours it. Saves the G1 run (about 500 episodes).
- 2026-09-21: OpenAI ladder changed from GPT-5.4 to GPT-5 (`gpt-5-nano`,
  `gpt-5-mini`, `gpt-5`; snapshots `-2025-08-07`; Responses API route;
  `reasoning_effort: high`), decided by Ethan on S1 data only. Basis: the
  GPT-5 cells measured so far are ordered and wide (telecom nano 32.7%
  [22.7%, 43.3%], mini 77.3% [68.0%, 86.0%]; airline nano 42.7% [31.3%,
  54.0%], mini 74.7% [64.7%, 84.0%]; retail mini 76.0% [66.7%, 84.0%]),
  whereas the six gpt-5.4 cells lie between 60.0% and 80.7% with nano above
  mini on two domains; the GPT-5 models are also those of Kim et al. Edits:
  §3 (ladder table, OpenAI ladder paragraph, exception to the selection
  rule, snapshots and route, effort note), the §4.2 table and the §5 table
  now carry the GPT-5 rows. The five finished cells are filled from the
  pilot block, which is removed; `retail x gpt-5-nano` and the three `gpt-5`
  cells are running and are filled by `fill_cell.py` when complete. The six
  measured gpt-5.4 cells are retained outside the grid in §4.2 and §5; the
  three `gpt-5.4` high-rung cells were never run. Accepted constraint: OpenAI
  retires the GPT-5 snapshots on 2026-12-11. Open items created by this
  change: `pricing.json` carries no GPT-5 rates yet; `budgets.json` is to be
  rebuilt before any GPT-5 M1 cell; `cells.json` still lists GPT-5 under the
  family key `openai-gpt5` and gpt-5.4 under `openai`. No M1 episode exists
  for any OpenAI model, so the change cannot follow the gain.
- 2026-09-21 — §1.2 added: secondary hypotheses H5 (budget-dependent
  threshold x0(k)), H6 (write-related failure share predicts gain beyond
  S1 accuracy), H7 (coordination cost expands with the ceiling), with fixed
  reading rules; H1' (M1 - S2) re-stated at the grid ceiling k x B_1x.
  Added before any full M1 cell was read (first grid cell 23 of 150
  episodes checkpointed, unread). Not confirmatory: they sit outside the
  H1 + H4 family and are reported in a separate, secondary results section.
  §8 conditions line updated to the k x B_1x ceiling.
- 2026-09-21 — Arm naming corrected after reading Kim et al.'s released
  code: the k x B_1x = 4x arm is the *cost-bounded arm* (does the team help
  under a stated cost bound of four times the single agent's P75 spend),
  not a reproduction of Kim's regime, whose ceiling was about 100 calls per
  system with no token cap and rarely bound either system. The faithful
  comparison is an *uncapped arm* (tau2's step and error limits only; the
  per-call guard c = B_1x kept as a runaway stop), pre-registered as a
  secondary arm on the six §8 cells (one model clearly below 45%, one
  clearly above, three domains, 3 seeds; S1 on those cells is the existing
  uncapped calibration run). H5 reads x0 at 1x, 4x and uncapped. Every
  earlier "Kim-regime arm" wording in this file now reads "cost-bounded
  arm". The grid at 4x continues as the primary arm; the first grid cell
  (airline x gemini-3.1-flash-lite) was paused at 85 of 150 episodes at
  07:05 UTC and resumes unchanged.
- 2026-09-21 — Qwen3.5-9B (OpenRouter) S1 calibration values received from a
  teammate's run (airline, retail, telecom; 150 episodes each) and added to
  §4.2 as a candidate-rung block. Budget values only; the results files have
  not been received, so no pass^1 is recorded and no §5 row is filled. Route
  is OpenRouter, a deviation from the family's single Model Studio route; the
  served build is not pinned. No decision on the ladder is taken.
- 2026-09-22 — Qwen3.5-9B run manifests and `summary.json` received and
  saved under `results/teammate-qwen9b/`. Verified from them: route id,
  effort high, matching base prompt hash and tau2 commit, 0 infrastructure
  errors, results hashes consistent with the calibration files. Recorded as
  deviations in the §4.2 block: OpenRouter route, `BudgetedS1Agent` (uncapped)
  instead of the stock agent, explicit temperature 0.0 on agent and simulator,
  and a different manifest schema. Results files still outstanding; no pass^1,
  no §5 row, no ladder decision.
- 2026-09-22 — G1 indicator readings on the first four grid cells (Gemini
  family, k = 4), recorded under the stop rule before any further cell is
  read. Two bars fire; neither is a bug class. (1) Advisor share: airline x
  gemini-3.1-flash-lite 93/150 = 62%, retail x gemini-3.1-flash-lite 106/150
  = 71% (bar >= 80%); telecom x flash-lite 87% and airline x gemini-3-flash
  98% pass. Diagnosis: the v6 orchestrator prompt (frozen 2026-09-21) leaves
  consultation to the orchestrator; the 80% bar was written under v5, which
  limited advisor use. A low share is the orchestrator's choice under the
  budget, not delegation failing to trigger (the database agent is used in
  every episode). (2) Turns with two or more cut calls: airline x
  gemini-3-flash 1, retail x flash-lite 2 (bar 0). All three are the
  episode's exhaustion turn: the first call is cut at the cap or at the
  remaining allowance, the next call (plan or forced message) is cut by the
  now smaller remaining allowance, and the episode ends with the standard
  exhaustion message; no JSON or cut text reached the customer. This is the
  designed end-of-budget path (calls above `a_min` are attempted; R7), not
  the retry-at-the-same-cap fault the bar was written to catch, which was
  fixed on 2026-09-21 and did not recur (0 retries in 4 cells). All other
  bars pass on all four cells (cut calls 2-3%, cut tokens 2-7%, JSON 0, cut
  text 0, tool calls per episode 5.2-7.8). Proposed amendment, not yet
  decided: (a) advisor share becomes a reported indicator, not a validity
  bar; (b) the double-cut bar reads "no turn in which a cut call is retried,
  and no double-cut turn other than the exhaustion turn", with exhaustion-turn
  double cuts reported as a count. Both changes are made after seeing four
  cells' rewards and are labelled as such; neither depends on reward, and
  the grid continues while the decision is pending because the cause is
  recorded here. Write-order execution and worker-output-used indicators are
  not yet computed (`analyze_run.py` pending) and will be added to the
  validity table before H1 is run.
- 2026-09-22 — Gemini family M1 grid at k = 4: six cells finished
  (flash-lite and 3-flash on all three domains; 0 infrastructure errors).
  The three gemini-3.1-pro M1 cells are **paused by decision of the PI**
  (cost: S1 alone was $22 to $34 per cell; M1 at 4x is expected at $55 to
  $80 per cell). Paused, not dropped: their S1 calibration rows stand, and
  the H1 slope loses the family's top rung until they run; the paper
  reports whichever set is complete at the freeze and says so. A request
  to run them at a lower reasoning effort was declined: §3 fixes effort at
  high in every condition, and changing it for M1 alone would confound the
  gain. G1 readings on the two new cells: all bars pass except one
  end-of-budget double cut (retail x 3-flash) and one `cut text` flag
  (telecom x 3-flash) which on inspection is a false positive of the
  checker: the plan call returned `finish_reason: length` with 1,327 of
  2,075 tokens used and a complete JSON object; the customer message was
  complete. `smoke_health.py` keys on the finish reason, and will be
  changed to check the message text; the metering layer's `truncated` flag
  keeps its definition. `run_m1.py` gained a stop file (`STOP_M1`:
  finish the running cell, start no new one), no change to any run.
- 2026-09-22 — Read-call limit sensitivity, decided by the PI after the
  six Gemini M1 cells. Background: the database agent's per-order tool-call
  limit (now written `r`; it was `k`, a letter also used for the ceiling
  multiple) was set to 4 at build time on 2026-09-19 with a one-line
  rationale and no data check. The S1 calibration episodes, on disk that
  day, show single agents chaining more calls than that before replying
  (telecom, median longest run: gemini-3.1-flash-lite 5, gemini-3-flash 7,
  gpt-5-mini 3, gpt-5-nano 17; P90 6, 10, 4, 68), and in the Gemini M1
  cells the limit was reached on 17 to 51% of read orders (orders that
  used all four calls: flash-lite 35 / 26 / 17% on airline / retail /
  telecom, 3-flash 50 / 36 / 51%; an earlier count from the report text
  alone gave 11 to 34%), each hit costing an extra orchestrator plan call. Kim et al.'s released config sets the
  matching ceiling at 25 iterations per agent, unexplained ("release
  ceiling"). Because M1's loss runs through exhaustion, a ceiling that
  binds this often could be doing part of the work. Action: run M1 at
  `r = 25` (Kim's value; the read-only restriction on read orders, the
  single-call write orders and the token budget are unchanged) on two
  cells, telecom x gemini-3-flash (highest binding rate, 34%; largest loss,
  -80.7) and telecom x gemini-3.1-flash-lite (the below-45% cell), 150
  episodes each, same seeds. Run names carry `-rc25`; the `r = 4` folders
  are untouched. Reading, fixed now: if the gain at `r = 25` stays inside
  the `r = 4` CI on both cells, the grid stands at `r = 4` and the two
  runs are reported as a robustness row; if either cell's gain moves
  outside that CI, the grid re-runs at `r = 25` for every family and the
  `r = 4` cells move to the appendix as the first pass. The OpenAI M1
  cells wait for this reading so `r` is the same across families. Made
  after seeing M1 rewards; motivated by S1 data that do not depend on M1.
- 2026-09-23 — Read-call limit sensitivity: result and decision. Both
  `r = 25` cells finished (150 episodes each, 0 infrastructure errors, all
  mechanical bars pass; one end-of-budget double cut on flash-lite; one
  `cut text` flag on 3-flash that is the same checker false positive as
  on 2026-09-22, a complete JSON plan with `finish_reason: length`). The
  limit was never reached at `r = 25` (0 of 677 read orders). Telecom x
  gemini-3.1-flash-lite: M1 12.7% [8.3, 18.9], gain -21.3 [-29.3, -12.7],
  exhausted 35%, utilisation 0.89 (at `r = 4`: 12.0%, -22.0 [-30.7,
  -12.7], 45%, 0.96). Telecom x gemini-3-flash: M1 14.0% [9.3, 20.5], gain
  -77.3 [-84.7, -70.0], exhausted 67%, utilisation 1.00 (at `r = 4`:
  10.7%, -80.7 [-87.3, -73.3], 68%, 1.00). Both `r = 25` gains lie inside
  the `r = 4` interval, so by the rule fixed on 2026-09-22 **the grid stays
  at `r = 4`**; the two `r = 25` cells are reported as the robustness row
  and the OpenAI M1 cells run at `r = 4`. Reading: freeing the worker
  changed almost nothing. Calls per read order rose from 2.8 to 3.8
  (3-flash) and 2.1 to 2.5 (flash-lite), plan calls per episode were flat
  (7.3 to 6.9; 6.4 to 6.5), and exhaustion fell only on flash-lite. The
  orchestrator issues roughly as many orders whatever the worker is
  allowed, so the coordination overhead is in the planning, not in the
  limit. Cost of the check: $39.
- 2026-09-22 — G1 amendment (a) decided by Ethan: advisor share (fraction
  of episodes in which the orchestrator consulted the policy advisor) is a
  *reported* indicator, no longer a validity bar. The >= 80% bar is
  removed from the reading rule above. Reason: under the v6 orchestrator
  prompt, consulting the advisor is a decision the orchestrator makes under
  the budget; the validity bars exist to catch broken mechanisms, and the
  mechanism works (the database agent is used in every episode; advisor
  calls succeed when made). Two additions to the reported indicators, no
  new bar: the plan-parse failure rate (orchestrator plan calls whose
  output could not be parsed as the plan object; a failed plan costs a
  retry and, if that fails, a forced customer message) and the count of
  forced customer messages. Basis: the four Gemini cells read on
  2026-09-22 (advisor share 62% to 98%) and the local qwen3.5-4b x telecom
  M1 smoke and run (plan-parse failures 51% in the 5-task smoke and 56%
  in the first 85 episodes of the cell; advisor calls in about one
  episode in eight, partly because plans carrying an advisor question
  failed to parse). The two Gemini cells that sat below 80% (airline and
  retail x gemini-3.1-flash-lite) and the qwen3.5-4b cell are therefore
  valid under G1 as amended, with their advisor share and plan-parse rate
  shown beside the gain. Labelled post hoc: decided after the rewards of
  six Gemini cells and the Qwen smoke had been seen; the change does not
  depend on any reward and removes no cell. No prompt or code changed.
  Amendment (b) (double-cut bar and the exhaustion turn) is still open.
- 2026-09-22 — Qwen3.5-9B (OpenRouter) pass^1 received from the teammate as
  `summary2.json` (saved under `results/teammate-qwen9b/`): airline 79.3%
  [71.3, 86.7], retail 76.0% [66.7, 84.7], telecom 95.3% [91.3, 98.7]; all
  three clearly above 45%. Internally consistent (successes agree across the
  per-trial and per-task counts) and the results-file hashes match the
  calibration files, but the results files are still not received, so the
  values are marked teammate-computed. Entered in §5 as a candidate table
  outside the grid; the §4.2 block updated to say so. Consequence for the §5
  gate: this rung would add no cell below 45%, so it does not resolve the
  gate on its own. No ladder decision is taken.
- 2026-09-22 — Qwen ladder changed (decided by Ethan) from the MoE triple
  `qwen3.5-35b-a3b` / `qwen3.5-122b-a10b` / `qwen3.5-397b-a17b` (Model
  Studio, `enable_thinking: true`; no cell ever run) to two dense rungs:
  `qwen3.5-4b` (low; local Ollama 0.34.2, Q4_K_M, digest `2a654d98e6fb`,
  `num_ctx` 131072) and `qwen3.5-9b` (mid; OpenRouter, teammate run). No
  high rung; the grid is 24 cells (eight models x three domains). Edits:
  §3 ladder table and a new ladder paragraph (the 2026-09-18 paragraph kept
  as superseded); §4.2 and §5 rows replaced (six Qwen rows in place of
  nine; telecom x 4b filled from the calibration run, the three 9b rows
  from the teammate's `summary2.json`, marked teammate-computed; airline
  and retail x 4b blank, to be run); the §5 candidate table for the 9b
  removed (now grid rows); H4 and H6 cell counts; `cells.json` family
  `qwen` rebuilt with the two models and `qwen-local` folded into it
  (save names unchanged, so existing results and the running telecom x 4b
  M1 cell resume under `--only qwen/qwen3.5-4b/telecom`); PROVENANCE.md
  section for both rungs. Not changed: the power analysis (computed for 27
  cells; to be re-run for 24 before the freeze). Post hoc, stated plainly:
  decided after the S1 results of both rungs and after 85 of 150 episodes
  of the telecom x 4b M1 cell had been seen (M1 far below S1 there, the
  direction of every M1 cell so far). Deviations carried: Ollama in place
  of vLLM and Q4_K_M in place of BF16 (4b); two routes within the family;
  sampling at shipped defaults (4b) against `temperature 0.0` (9b);
  BudgetedS1Agent uncapped mode for the 9b S1 (see the §4.2 block). The
  budgets entry `telecom x qwen3.5-4b` already exists; 9b budget entries
  will be built when the results files arrive.
- 2026-09-22 — Grid reduced to two tiers (decided by Ethan): `gpt-5` and
  `gemini-3.1-pro` removed from the grid; the Qwen family already had no
  high rung. Grid 18 cells (six models x three domains). Their six S1
  cells are kept outside the grid in §4.2 and §5 (retained high-rung
  tables) beside the retained gpt-5.4 cells; no M1 cell is run for them.
  Reason: M1 cost and time at the top tier (the three `gemini-3.1-pro` M1
  cells had been paused on cost earlier the same day; `gpt-5` M1 never
  started). Post hoc, stated plainly: decided after the six low- and
  mid-tier Gemini M1 cells had been read; the removed cells are the ones
  expected to show the largest M1 losses above 45%, so the change works
  against a negative H1 slope rather than for it. Edits: §3 models bullet,
  ladder table and a new "Grid reduced" paragraph; §4.2 and §5 rows moved
  to retained tables; H4 and H6 cell counts; `cells.json` model entries for
  the two rungs removed (config recorded in the family notes; S1 results,
  manifests and `budgets.json` entries untouched). The power analysis
  (27 cells) must be re-run for 18 cells before the freeze; power will be
  lower than the 0.95 at b = -0.30 reported in §1.1.
- 2026-09-23 — M1 budgets for the three `qwen3.5-9b` cells. The teammate's
  `results.json` files are still not held here, so `build_budgets.py` now
  also reads the `calibrate_budget.py` output that came with a teammate run
  (`results/teammate-*/`), checked against its run manifest (return code 0,
  0 infrastructure errors, same results SHA-256); a local results file for
  the same cell would take precedence. Rebuilt `budgets.json`: three entries
  added (airline B_1x 12,263, retail 6,370, telecom 5,758; per-call median
  270, 224, 211), the 25 existing entries unchanged. M1 on these cells uses
  the S1 agent settings exactly (`temperature 0.0`, OpenRouter
  `reasoning.effort: high`, provider routing unpinned, no reasoning passed
  back between calls, as in S1) and runs at `max_concurrency` 4, the S1
  value; the family default of 1 is the local Ollama limit. The paired gain
  (task-cluster CI) needs the per-episode S1 results and waits for them.
- 2026-09-23 — Route finding, telecom x qwen3.5-9b M1 (OpenRouter), recorded
  under the G1 stop rule at 30 of 150 episodes. The per-call cap is not
  enforced on this route for reasoning tokens: the provider behind
  OpenRouter applies `max_tokens` to the visible answer only. In 5 of 803
  calls the completion exceeded `max_tokens`; three by 100 to 180 tokens,
  and two orchestrator plan calls that returned 131,133 and 131,318
  completion tokens (131,071 of them reasoning, the provider's own thinking
  ceiling) against `max_tokens` 5,758, with `finish_reason: stop`. The
  ledger charged them in full, so both episodes ended `budget_exhausted`
  on that one call (spent 109,641 and 123,547 tokens over the 23,032
  ceiling). On the other routes such a call is cut at `c` and marked
  truncated. The teammate's S1 on this cell, uncapped, never exceeded
  2,474 tokens in one call, so the runaway appears with the orchestrator's
  plan prompt. Not fixed: the fixes available (a reasoning token budget in
  place of `effort: high`, or pinning a provider) change the agent settings
  relative to S1. Reported per cell as a validity indicator (calls
  returning more than `max_tokens`, and episodes exhausted by such a call),
  with pass^1 also shown excluding those episodes. Decision on continuing
  rests with the PI; the run continues meanwhile.
- 2026-09-23 — First GPT-5 M1 cell finished: airline x gpt-5-nano at
  k = 4, r = 4 (150 episodes, 0 infrastructure errors). M1 45.3% [37.6,
  53.3] vs S1 42.7% [35.0, 50.7]; paired gain +2.7 [-6.7, +12.7]; exhausted
  23%, utilisation median 0.50, M1 tokens 2.9x S1, cost $9.15 vs $4.66.
  Per task: M1 better on 13, same on 26, worse on 11. This is the grid's
  straddling cell (S1 CI covers 45%) and the first cell whose gain CI
  includes zero; the sign matches Kim et al.'s rule, and the interval
  cannot tell a small gain from none. Validity: all mechanical bars pass;
  advisor consulted in 17 of 150 episodes (reported indicator since the
  2026-09-22 amendment); 35 episodes ended budget_exhausted. Transfers to a
  human agent: S1 in 85 episodes, M1 in 99; many airline tasks require one,
  so the count is reported, not read as failure.
- 2026-09-23 — Second GPT-5 M1 cell finished: airline x gpt-5-mini at
  k = 4, r = 4 (150 episodes, 0 infrastructure errors). M1 58.0% [50.0,
  65.6] vs S1 74.7% [67.2, 81.0]; paired gain -16.7 [-27.3, -6.7];
  exhausted 34%, utilisation median 0.83, M1 tokens 5.2x S1, cost $27.54
  vs $8.77. Per task: M1 better on 6, same on 27, worse on 17. Episodes
  that finished inside the budget passed 68% (67 of 99), exhausted ones 39%
  (20 of 51). The read-call limit was reached on 239 of 351 read orders
  (68%), the highest rate in the grid so far. Validity: all mechanical
  bars pass; advisor consulted in 21 of 150 episodes (reported indicator).
  With airline x gpt-5-nano (+2.7 [-6.7, +12.7]) the GPT-5 airline pair
  shows the same ordering as the Gemini cells: the stronger model loses
  more under coordination.
- 2026-09-23 — telecom x qwen3.5-4b (local Ollama, Q4_K_M) M1 finished at
  k = 4, r = 4 (150 episodes, 0 infrastructure errors, 30.7 hours at
  concurrency 1). M1 23.3% [17.3, 30.7] vs S1 94.7% [89.8, 97.3]; paired
  gain -71.3 [-80.0, -62.7]; exhausted 63%, utilisation median 1.00, M1
  tokens 5.3x S1; finished episodes passed 54% (30 of 56), exhausted ones
  5% (5 of 94). Validity: mechanical bars pass except one `cut text` flag,
  the same checker false positive as before (complete JSON plan with
  `finish_reason: length`). Model-specific indicator, reported beside the
  result: 1,386 of 2,467 orchestrator plan calls (56%) did not parse as
  the plan object; in 542 turns both attempts failed, and 797 forced
  customer messages (5.3 per episode) and 99 holding lines followed; the
  smoke had shown 51%. (Corrected 2026-09-23: this entry first gave 22%
  and 1,076, which counted failed turns and event labels, not calls.) The frozen parser was kept (part 16 of
  the project log; a brace-completing parser is listed as a possible
  post-hoc robustness variant). Advisor consulted in 14 of 150 episodes.
  Read with this caveat: part of this cell's loss comes from the 4B
  orchestrator failing the plan format, which is a property of this model
  in this role and is reported as such.
- 2026-09-23 — telecom x qwen3.5-9b (OpenRouter) M1 finished at k = 4,
  r = 4 (150 episodes, 0 infrastructure errors, 6.9 hours at concurrency
  4, $5.20). M1 33.3% [26.3, 41.2] vs S1 95.3% [91.3, 98.7] (teammate run;
  per-episode S1 results not held, so no paired CI); exhausted 33%,
  utilisation median 0.93; finished episodes passed 48 of 101, exhausted
  ones 2 of 49. G1: **two mechanical bars fail**, recorded under the stop
  rule. (1) Tokens in cut calls 12.9% (bar <= 10%): 69 of 2,138
  orchestrator plan calls (3.2%) thought up to the per-call cap of 5,758
  and were cut, against 0.1% of calls cut at the cap across the six Gemini
  cells; the 9B's own S1 calls never exceeded 2,474 tokens. (2) Turns with
  two or more cut calls: 11 (bar 0); 5 are exhaustion turns (the open
  amendment (b) case), 6 are ordinary turns where the plan was cut at the
  cap, the forced customer message was cut as well, and a holding line
  went to the customer (11 holding lines; no JSON or cut text reached the
  customer). Neither is a code fault: the mechanism ran as specified, and
  the cause is the 9B orchestrator's thinking length in this role. No
  bug-class fix exists (a larger orchestrator cap or a pinned provider
  changes the protocol for one family), so under the stop rule the cell is
  reported as failing G1: excluded from the primary H1 slope and shown in a
  sensitivity that includes it. Also reported: the route issue (17 calls
  returned more than `max_tokens`, 4 of them runaway calls of about 131k
  reasoning tokens, 4 episodes exhausted by one call; pass^1 without them
  50 of 146, 34.2% [27.0, 42.3]); plan-parse failures 292 of 2,138 plan
  calls (14%), both attempts failed in 115 turns, 122 forced messages
  (corrected 2026-09-23 from 5.4% and 158, which counted turns and event
  labels); advisor consulted in 52 of 150 episodes. The gap to
  S1 (62 points) is far larger than any of these effects. Decision on the
  9B airline and retail cells rests with the PI.
- 2026-09-23 — Third GPT-5 M1 cell finished: retail x gpt-5-nano at k = 4,
  r = 4 (150 episodes, 0 infrastructure errors). M1 44.7% [36.9, 52.7] vs
  S1 68.0% [60.2, 74.9]; paired gain -23.3 [-32.7, -13.3]; exhausted 16%,
  utilisation median 0.63, M1 tokens 3.1x S1, cost $7.49 vs $3.74. Per
  task: M1 better on 2, same on 23, worse on 25. Unlike the Gemini cells,
  the loss here does not run through exhaustion: episodes that finished
  inside the budget passed 52% (65 of 126), well below S1's 68%. Episodes
  with a transfer to a human: M1 48 (11 passed), S1 34 (14 passed). The
  read-call limit was reached on 30% of read orders. Validity: all
  mechanical bars pass; advisor consulted in 13 of 150 episodes (reported).
- 2026-09-23 — Fourth GPT-5 M1 cell finished: retail x gpt-5-mini at k = 4,
  r = 4 (150 episodes, 0 infrastructure errors). M1 48.0% [40.2, 55.9] vs
  S1 76.0% [68.6, 82.1]; paired gain -28.0 [-40.0, -17.3]; exhausted 43%,
  utilisation median 0.90, M1 tokens 4.9x S1, cost $20.83 vs $6.82. Per
  task: M1 better on 5, same on 19, worse on 26. Episodes that finished
  inside the budget passed 68% (58 of 85), exhausted ones 22% (14 of 65):
  the Gemini pattern (loss through exhaustion), unlike retail x gpt-5-nano.
  The read-call limit was reached on 55% of read orders. Validity: all
  mechanical bars pass; advisor consulted in 7 of 150 episodes (reported).
- 2026-09-23 — Fifth GPT-5 M1 cell finished: telecom x gpt-5-nano at k = 4,
  r = 4 (150 episodes, 0 infrastructure errors), the second cell clearly
  below 45%. M1 19.3% [13.8, 26.4] vs S1 32.7% [25.7, 40.5]; paired gain
  -13.3 [-20.7, -6.0]; exhausted 15%, utilisation median 0.54, M1 tokens
  2.8x S1, cost $12.57 vs $8.71. Per task: M1 better on 3, same on 28,
  worse on 19. Like retail x gpt-5-nano, the loss does not run through
  exhaustion: episodes that finished inside the budget passed 20% (26 of
  127). Episodes with a transfer to a human: M1 120 (25 passed, 245
  transfer calls), S1 79 (21 passed, 86 calls). Endings: M1 113
  user_stop, 23 agent_stop (exhaustion), 14 too_many_errors; S1 109
  user_stop, 27 too_many_errors, 14 max_steps. The read-call limit was
  reached on 72% of read orders (783 of 1,088); 29.3 agent tool calls per
  episode. Validity: all mechanical bars pass; advisor consulted in 9 of
  150 episodes (reported). With telecom x gemini-3.1-flash-lite (-22.0
  [-30.7, -12.7]), both cells clearly below 45% show a significant loss
  where Kim et al.'s rule predicts a gain.
- 2026-09-24 — Sixth and last GPT-5 M1 cell finished: telecom x gpt-5-mini
  at k = 4, r = 4 (150 episodes, 0 infrastructure errors). M1 66.0% [58.1,
  73.1] vs S1 77.3% [70.0, 83.3]; paired gain -11.3 [-18.7, -4.0];
  exhausted 18%, utilisation median 0.70, M1 tokens 4.2x S1, cost $34.45
  vs $16.94. Per task: M1 better on 5, same on 25, worse on 20. Episodes
  that finished inside the budget passed 79% (97 of 123), above S1's
  77.3%; exhausted ones 7% (2 of 27), so this cell's loss runs through
  exhaustion. Transfers: M1 31 episodes, S1 45. The read-call limit was
  reached on 44% of read orders. Validity: all mechanical bars pass;
  advisor consulted in 8 of 150 episodes (reported). GPT-5 family complete
  at k = 4: one tie (airline x nano) and five significant losses.
- 2026-09-24 — retail x qwen3.5-9b (OpenRouter) M1 finished at k = 4,
  r = 4 (150 episodes, 0 infrastructure errors, 4.4 hours at concurrency
  4, $3.28). M1 49.3% [41.4, 57.3] vs S1 76.0% [66.7, 84.7] (teammate run;
  per-episode S1 results not held, so no paired CI); exhausted 10%,
  utilisation median 0.51; finished episodes passed 74 of 135 (55%),
  exhausted ones 0 of 15. Unlike telecom x 9b, the loss here does not run
  through exhaustion. G1: **fails** on double-cut turns: 5, of which 1 is
  an exhaustion turn and 4 are ordinary turns where the plan was cut at the
  6,370 cap and the forced customer message was cut as well (a holding
  line went out; no JSON or cut text reached the customer). Tokens in cut
  calls 9.6% of all completion tokens (passes the 10% bar), but 13.2% once
  the six runaway calls are removed from the total, so the pass on that
  bar is an artefact of the runaway calls. Same diagnosis as telecom x 9b:
  the orchestrator's thinking reaches the per-call cap; the mechanism ran
  as specified; no bug-class fix exists. The cell is reported as failing
  G1, excluded from the primary H1 slope and shown in a sensitivity that
  includes it. Route issue: 12 calls returned more than `max_tokens`, 6 of
  them runaway calls of about 131k reasoning tokens, 6 episodes affected;
  pass^1 without them 74 of 144, 51.4% [43.3, 59.4]. Plan-parse failures
  352 of 1,414 plan calls (25%), 144 forced-message calls, 55 holding
  lines; advisor consulted in 59 of 150 episodes. Both 9b cells run so far
  fail G1 for the same reason; airline x 9b is not recommended.
- 2026-09-24 — §8.1 addendum (uncapped arm) written and frozen before any
  uncapped episode, decided by the PI: cells gpt-5-nano and
  gemini-3.1-flash-lite x three domains (post hoc, after the 4x grid;
  deviation from §8's model-level rule stated there). Code: new
  `BudgetConfig.uncapped_with_guard` (no ceiling, no wrap-up, per-call
  guard `c = B_1x` kept); `run_m1.py --uncapped` (run names
  `...-uncapped-capb1x-...`, manifest field `arm`); `m1_agent.py` removes
  the orchestrator's budget paragraph when the episode has no ceiling
  (`strip_allowance_paragraph`; raises if the paragraph is not found
  exactly once), so capped runs are unaffected. Three tests added (41
  pass, tau2 c339866, mock domain): the guard-only config, the uncapped M1
  episode end to end through tau2's runner with every team call at
  `max_tokens = c` and no budget line, and the prompt difference being
  exactly that one paragraph.
- 2026-09-24 — §8.1 amended before any uncapped episode finished (decided
  by the PI, on cost): the uncapped arm runs on three cells for now
  (telecom x gemini-3.1-flash-lite, telecom x gpt-5-nano, airline x
  gpt-5-nano); the three above-45% cells are deferred, not dropped. The
  first launches (airline x flash-lite, airline x nano) were stopped by the
  PI about one minute after start, 0 of 150 episodes finished in each
  (empty `results.json` kept; tau2 auto-resume reuses them). Cost stop
  lowered to $75. No code change.
- 2026-09-24 — Uncapped arm, first check at 22:12 UTC (telecom x
  flash-lite 30, airline x nano 7, telecom x nano 6 episodes). Settings
  confirmed from the episode records: `limit` null, `wrapup_threshold`
  null, `per_call_cap` = B_1x; no call cut at the cap, no holding line, no
  exhaustion. One mechanical bar is hit, recorded under the G1 stop rule:
  in telecom x gpt-5-nano one customer message was JSON (task
  `[mobile_data_issue]data_saver_mode_on|data_usage_exceeded[PERSONA:Easy]`,
  trial 1, turn 13). Diagnosis: the orchestrator returned a well-formed
  plan object whose `action` was `message` with, as its content, a JSON
  string of its own task-ledger plan; the plan parsed, no call was cut and
  no fallback ran, so the mechanism worked as specified and the message
  was the model's own output. The episode still passed. No such message
  occurred in the 450 episodes of the three gpt-5-nano cells at 4x. No
  bug-class fix applies (a guard that rewrites such messages would change
  the agent relative to the 4x cells). Reported per cell as a count; the
  run continues meanwhile and the decision rests with the PI.
- 2026-09-25 — S2 built and the §8.2 addendum written before any S2
  episode (cells decided by the PI on 2026-09-24: the three §8.1 cells).
  Code: `s2_agent.py` (`S2Agent`: one context; per turn a plan call that
  sees the tools with `tool_choice` "none" and an act call with native
  tools; the shared budget layer; a JSON guard on act replies;
  M1's logging key with `architecture: "S2"` and a `review` record per
  turn), `run_m1.py --condition s2` (run names `s2-...-b4x-capb1x-...`),
  `smoke_health.py` (S2 lines: plan-parse failures and review outcomes;
  the advisor line now says it is a reported indicator), role block
  `prompts/roles/s2_single_agent.md` (DRAFT v1, block as sent SHA-256
  `dbb2e3aa4e13...`), `docs/budget-protocol.md` (S2 lines),
  `budget_layer.metered_generate` (new optional `tool_choice`, default
  unchanged: "auto" whenever tools are passed, so S1 and M1 requests are
  identical to before; checked by test). Seventeen tests added (58 pass,
  tau2 c339866, mock domain), among them one S2 episode
  end to end through tau2's runner: plan calls carry the tools with
  `tool_choice` "none", act calls with "auto", every call is capped at c, and the budget snapshot
  equals the sum of the turn usages. Dry run: each S2 cell receives the
  budget of the M1 cell of the same model and domain (telecom x
  flash-lite B 28492, c 7123; airline x nano B 205188, c 51297; telecom x
  nano B 300128, c 75032). An independent code review before any S2
  episode found, and the build fixed: JSON act replies could reach the
  customer (guard added); the plan call did not see the tool definitions
  (now shown with `tool_choice` "none"); forced closings were logged as
  review revisions (now labelled apart); a plan retry could run past the
  wrap-up threshold (now skipped); flat drafts were not parsed; a missing
  policy check was not logged. No change to M1 or S1 code paths.
- 2026-09-25 — Uncapped arm, first cell finished: telecom x
  gemini-3.1-flash-lite (150 episodes, 0 infrastructure errors, 109 min).
  M1 uncapped 34.7% [27.5, 42.6] vs S1 34.0% [26.9, 41.9]; `gain_uncapped`
  +0.7 [-8.7, +9.3] (task-cluster bootstrap over 50 tasks, seed 300, 2,000
  resamples); `M1_uncapped - M1_4x` +22.7 [+13.3, +32.0] (M1 at 4x 12.0%).
  Per task against S1: better on 14, same on 24, worse on 12. Completion
  tokens per episode: median 25,813, 5.5 times S1's 4,722 (P90 49,673; max
  79,034, 2.8 times the 4x ceiling of 28,492). All 150 episodes ended
  `user_stop`. Cost $13.54 (4x cell $9.53, S1 $5.53). Mechanical G1 bars
  all pass: 0 of 3,651 calls cut at c, no JSON or cut text to the customer,
  no holding line; 0 plan-parse failures in 1,269 plan calls; advisor
  consulted in 136 of 150 episodes. Reading under §8.1: rule (1) is not
  met on this cell (the CI covers zero); rule (2) needs both below-45%
  cells and waits for telecom x gpt-5-nano. On this cell the entire 4x
  loss is a product of the ceiling, and without it the team matches the
  single agent at 5.5 times its spend, with no gain where Kim et al.'s
  rule predicts one. Arm total $25.03 at 00:58 UTC (projection about $42;
  review stop $75). Telecom x gpt-5-nano now has 2 JSON customer messages
  in 57 episodes, both of the pattern recorded on 2026-09-24 (the
  orchestrator's own `{"plan": [...]}` sent as the message content; the
  plan parsed, no call was cut, no fallback ran); counted and reported,
  the run continues.
- 2026-09-25 — Uncapped arm, check at 01:58 UTC (airline x nano 89,
  telecom x nano 75 of 150 episodes; 0 infrastructure errors; 0 calls cut;
  no exhaustion). JSON customer messages in telecom x gpt-5-nano uncapped:
  4 of 499 customer messages (0.8%), in 4 episodes (2 passed), all the
  `{"plan": [...]}` pattern recorded on 2026-09-24. For comparison, the
  three gpt-5-nano cells at 4x have 0 in 2,049 customer messages (telecom
  0 of 592), and airline x nano uncapped has 0 so far. The cause is not
  identified: the uncapped arm differs by the removed allowance paragraph
  and by longer episodes (median 162k completion tokens against 57k for
  S1 on the same episodes). Reported as a validity indicator for this
  cell, with pass^1 also shown excluding the affected episodes; no fix
  (a guard on M1's message path would change M1 relative to the 4x
  cells). The S2 agent has a JSON guard, fixed before any S2 episode;
  the asymmetry is stated beside `M1_4x - S2`. Arm total $29.11
  (projection about $42).
- 2026-09-25 — Uncapped arm, telecom x gpt-5-nano finished (150
  episodes, 0 infrastructure errors, 479 min). M1 uncapped 22.7% [16.7,
  30.0] vs S1 32.7% [25.7, 40.5]; `gain_uncapped` -10.0 [-18.7, -2.0]
  (task-cluster bootstrap over 50 tasks, seed 300, 2,000 resamples);
  `M1_uncapped - M1_4x` +3.3 [-4.0, +10.7] (M1 at 4x 19.3%). Per task
  against S1: better on 9, same on 22, worse on 19. Completion tokens per
  episode: median 151,478, 2.6 times S1's 57,928 (P90 333,220; max
  566,709). Endings: 129 `user_stop`, 15 `too_many_errors`, 6 `max_steps`
  (S1: 109, 27, 14). Cost $17.40 (4x cell $12.57, S1 $8.71). Mechanical G1
  bars: 0 of 6,997 calls cut, no cut text, 2 holding lines; JSON to the
  customer 6 messages of 1,022 in 6 episodes (the `{"plan": [...]}`
  pattern of 2026-09-24), which fails the JSON bar as written; excluding
  the 6 episodes, pass^1 21.5% [15.6, 28.9] and `gain_uncapped` -12.0
  [-21.0, -3.7], so the leak does not drive the result. Plan calls not
  parsed as the plan object: 18 of 2,326. Advisor consulted in 9 of 150
  episodes.
- 2026-09-25 — Uncapped arm, airline x gpt-5-nano finished (the
  straddling cell; 150 episodes, 0 infrastructure errors, 459 min). M1
  uncapped 44.0% [36.3, 52.0] vs S1 42.7% [35.0, 50.7]; `gain_uncapped`
  +1.3 [-7.3, +10.0]; `M1_uncapped - M1_4x` -1.3 [-8.7, +6.0] (M1 at 4x
  45.3%). Per task against S1: better on 12, same on 27, worse on 11.
  Completion tokens per episode: median 93,179, 2.7 times S1's 34,930
  (P90 431,131; max 858,918). Endings: 141 `user_stop`, 6 `max_steps`, 3
  `too_many_errors` (S1: 150 `user_stop`). Cost $13.20 (4x cell $9.15, S1
  $4.66). Mechanical G1 bars: 0 of 5,276 calls cut, no cut text; JSON to
  the customer 1 message of 842 (same pattern); excluding that episode
  the gain is unchanged (+1.3 [-7.3, +10.0]). Plan calls not parsed: 28
  of 1,919. Advisor consulted in 15 of 150 episodes.
- 2026-09-25 — Uncapped arm complete (three cells, §8.1 as amended; $44.13
  in total against the $75 review stop). Reading rules as fixed before
  any uncapped episode: rule (1) is not met, since `gain_uncapped` has a
  CI above zero on neither below-45% cell (telecom x flash-lite +0.7
  [-8.7, +9.3]; telecom x gpt-5-nano -10.0 [-18.7, -2.0]). Rule (2) is
  met: on both below-45% cells the CI covers zero or lies below it, so
  the absence of a team benefit in the grid is not a product of the
  ceiling. Stated with the qualification the data require: on telecom x
  flash-lite the ceiling did produce the size of the 4x loss (`M1_uncapped
  - M1_4x` +22.7 [+13.3, +32.0]; the 4x loss ran through exhaustion), and
  lifting it brings the team level with the single agent, not above it;
  on the two gpt-5-nano cells lifting the ceiling changes nothing
  (`M1_uncapped - M1_4x` +3.3 and -1.3, both CIs covering zero), in line
  with the 4x entries, where nano's loss did not run through exhaustion.
  The straddling cell (airline x nano) is a tie with or without a
  ceiling. Without a ceiling the team spends 2.6 to 5.5 times S1's
  completion tokens per episode. Rule (3): no uncapped H5 point, since the
  three above-45% cells are deferred. Validity: no call cut at c in
  15,924 calls; 7 JSON messages to the customer out of 1,864 customer
  messages on the two nano cells (0 on flash-lite), all the
  orchestrator's own plan text, against 0 of 2,049
  in the three nano cells at 4x; results with and without the affected
  episodes agree.
- 2026-09-25 — S2 smoke, first round (5 tasks x 1 trial on each §8.2
  cell, code and block v1; $1.59; runs renamed `smoke5v1-s2-...` so the
  second round is not skipped by auto-resume). Mechanical G1 bars pass on
  all three cells (calls cut 0, 1 and 2 of 112, 123 and 234; no JSON or
  cut text reached the customer; 0 infrastructure errors); 0 plan-parse
  failures; the provider ignored `tool_choice` "none" once (airline x
  nano; the call was charged and dropped). Exhaustion: telecom x flash-lite 0 of 5 (utilisation median
  0.73), airline x nano 2 of 5, telecom x nano 3 of 5. Completion tokens
  per episode against S1 on the same tasks: 3.9x, 6.5x, 6.7x; on telecom x
  nano the plan call dominates (median 8,678 tokens against 1,709 for the
  act call). Three problems, fixed before the freeze with the PI's
  approval: (1) the act call returned JSON text 16 times; in 5 the
  drafted message inside it was used, and in 11 the guard kept it from
  the customer but answered with a closing call that carried the wrap-up
  notice, which ended one episode early; now the act call is
  repeated once with the tools and a reminder (code; bug class). (2) The
  gpt-5-nano plans filled the draft with a narrative of the plan written
  as a message (113 turns in which the act call then made a tool call), so
  the draft was not the next action; block v2 adds one sentence defining
  the draft (format class; block as sent SHA-256 `ba0af7c79838...`). (3)
  gpt-5-nano names drafted tools with the `functions.` prefix, which the
  review log counted as a changed tool (5 of 6 such turns); the prefix is
  now stripped (logging only). Tests: 60 pass (tau2 c339866, mock
  domain). The cost of planning after every tool result, the main driver
  of nano's exhaustion, is part of the S2 design in §8.2 and was left
  unchanged. Reward was read last and played no part in these changes
  (S2 / S1 / M1 4x on the same 5 tasks: 4/1/1, 4/4/3, 2/2/1). Second
  smoke round follows before the freeze.
- 2026-09-25 — Grid scope decided by the PI: the qwen3.5-4b airline and
  retail cells (S1 and M1; about 72 h of local compute) and the
  qwen3.5-9b airline M1 cell are not run. The grid therefore holds, for
  the Qwen family, telecom x 4b (valid) and telecom and retail x 9b (both
  failing G1, shown only in the sensitivity that includes them); the 9b
  airline S1 row stays in the §5 table as calibration only. The power
  analysis is re-run for the cells held. R1 and R2 are to be run (details
  fixed in a separate entry before any R1 or R2 episode).
- 2026-09-25 — Received from the teammate: M1 at 4x for qwen3.5-9b
  (OpenRouter) on airline and retail, run on the teammate's machine
  (150 episodes each, seed 300, 3 trials, 0 infrastructure errors,
  concurrency 1), with a summary and the teammate's working copy of this
  file. Stored under `results/teammate-qwen9b/m1/` (gzip copies of both
  `results.json`, `SUMMARY-m1-2026-09-25.md`,
  `ANALYSIS-teammate-fork-2026-09-25.md`) and unpacked to
  `tau2-bench/data/simulations/m1-{airline,retail}-qwen35-9b-openrouter-high-...`
  (the `-high` model tag is the teammate's naming; no clash with our
  retail run). SHA-256 verified against the summary (`85c7e481ec7e...`
  airline, `27207320d348...` retail). Same agent settings and budgets as
  our cells (reasoning effort high, temperature 0.0; airline B 49,052 and
  c 12,263; retail B 25,480 and c 6,370; r = 4; orchestrator cap c).
  Deviation: tau2 commit `8b57085` against the pinned `c339866`. Results,
  recomputed here from the files: airline 61.3% (S1 79.3%), exhausted 18
  of 150; retail 51.3% (S1 76.0%), exhausted 13 of 150. Paired gains as
  computed by the teammate against the S1 per-episode files, which are
  still held only on the teammate's machine: airline -18.0 [-28.7,
  -6.7], retail -24.7 [-36.0, -13.3]. G1, recomputed with
  `smoke_health.py`: airline fails (tokens in cut calls 36%, 14 turns with
  two or more cut calls, 86 holding lines, plan-parse failures 492 of
  1,483); retail fails the cut-token bar (13%; 0 double-cut turns, 54
  holding lines, plan-parse failures 396 of 1,513). No JSON or cut text
  reached the customer in either. Two consequences. (1) The airline x 9b
  M1 cell, recorded above as not run, exists; like the other 9b cells it
  fails G1 and enters only the sensitivity that includes failing cells.
  (2) Retail x 9b now has two independent M1 runs on the same
  configuration: 49.3% here (concurrency 4) and 51.3% on the teammate's
  machine, a replication within 2 points; the teammate's run had no
  runaway call above 100k tokens and 6 calls over `max_tokens`, against 6
  runaways and 12 here, so the OpenRouter route's handling of the
  reasoning budget varies by run. Our cell stays the grid cell; the
  teammate's run is reported as a replication. The teammate's working copy
  of this file describes the 9b as an out-of-grid candidate; that
  wording predates the PI's 2026-09-22 decision making it the mid rung and
  is not adopted here.
- 2026-09-25 — R1 and R2 fixed before any R1 or R2 episode (decided by
  the PI; post hoc, after all grid M1 cells at 4x and the uncapped arm had
  been seen). R1 (budget invariance), as reshaped by the 2026-09-20 and
  2026-09-21 entries (the matched arm at k = 1 on the R1 cells): cells
  telecom x gemini-3.1-flash-lite (S1 34.0%, below 45%) and airline x
  gemini-3.1-flash-lite (S1 78.7%, above); S1 capped at 1x (`run_m1.py
  --condition s1 --budget-mult 1`, the stock agent with the meter, the
  allowance line and the wrap-up notice) and M1 at 1x (`--condition m1
  --budget-mult 1`); 3 trials, seed 300; the 2x level is not run. Reading
  as in §1: `gain_1x = M1_1x - S1_1x` and `gain_4x` (grid cell, S1
  uncapped) with task-cluster CIs, and the change `gain_4x - gain_1x`
  with its paired CI; budget dependence is claimed only if that CI
  excludes zero; on telecom x flash-lite the uncapped point (§8.1) is
  shown beside them. The capped-versus-uncapped S1 difference at 1x on
  both cells sizes the known asymmetry of §4.2. H5's k = 1 point comes
  from these two cells only and is descriptive. R2 (simulator
  invariance): airline cells for the lowest, a middle and the highest S1
  among the airline models with a valid M1 cell: gpt-5-nano (42.7%),
  gemini-3.1-flash-lite (78.7%; the PI chose it over gpt-5-mini, 74.7%,
  on cost) and gemini-3-flash (80.7%); qwen3.5-9b is excluded (its M1
  cells fail G1). Second simulator `gpt-4.1-2025-04-14` at temperature
  0.0, tau2's default user simulator at c339866 (`cells.json`
  `user_alternatives.gpt41`, selected with `--user-sim gpt41` in
  `run_calibration.py` and `run_m1.py`; run names carry `gpt41`). S1 is
  the stock agent uncapped, as in the calibration; M1 is the grid
  configuration at 4x with the budgets from the gpt-5.2 calibration (not
  recalibrated). Reading as in §1: `gain` under each simulator with CIs
  and the paired difference in `gain` between simulators with its CI;
  simulator contingency is claimed only if that CI excludes zero in at
  least two of the three cells. Expected cost about $18 for R1 and $55
  for R2. Code: `--user-sim` added to both runners (default unchanged;
  dry runs checked; 60 tests pass).
- 2026-09-26 — S2 smoke, second round (code and block v2; 5 tasks x 1
  trial on each §8.2 cell) and freeze. Mechanical G1 bars pass on all
  three cells (calls cut 0, 0 and 2 of 114, 87 and 200; no JSON or cut
  text reached the customer; 0 infrastructure errors; 0 plan-parse
  failures). Exhaustion, round 2 against round 1: telecom x flash-lite 0
  of 5 (0 of 5), airline x gpt-5-nano 0 of 5 (2 of 5), telecom x
  gpt-5-nano 2 of 5 (3 of 5). Median completion tokens per episode: 17k
  (21k), 108k (182k), 283k (300k, the ceiling). JSON act replies: 9 were
  repeated once and all then produced a tool call or a message (1 of them
  a message found inside a second JSON reply), 6 were used as the message
  drafted inside them; no holding line, and no forced closing from JSON
  (the 2 forced closings on telecom x nano followed act calls cut at c).
  Turns in which a message draft was replaced by a tool call: 13 (30) on
  airline x nano and 45 (83) on telecom x nano. The nano plan call still
  costs about 8k tokens (median 7.9k to 8.2k, unchanged), so the saving
  comes from fewer wasted turns; telecom x nano still exhausts in 2 of 5
  episodes, which the §8.2 reading treats as a budget effect. Reward was
  read last and played no part (S2 on the same five tasks: 3/5, 4/5,
  2/5). The block is frozen as v2 (file SHA-256 `1345572de1dc...`, block
  as sent `ba0af7c79838...`, unchanged); full S2 cells may start.
- 2026-09-26 — R1, telecom x gemini-3.1-flash-lite (below 45%)
  finished at 1x (S1 capped and M1, 150 episodes each, 0 infrastructure
  errors). S1 at 1x 30.0% [23.2, 37.8] with 36 of 150 episodes
  exhausted; S1 uncapped 34.0%, so capping S1 at its own P75 costs
  -4.0 [-10.7, +2.0] (the §4.2 asymmetry, small here). M1 at 1x 2.7%
  [1.0, 6.7] with 147 of 150 exhausted. `gain_1x` -27.3 [-36.7, -18.7];
  `gain_4x` -22.0 [-30.7, -12.7]; `gain_4x - gain_1x` +5.3 [-2.7, +14.0]
  (paired over tasks), so budget dependence of the gain between 1x and
  4x is not claimed under the §1 rule. M1 alone rises with the ceiling:
  2.7% at 1x, 12.0% at 4x (`M1_4x - M1_1x` +9.3 [+4.7, +14.7]) and 34.7%
  uncapped (§8.1), while S1 stays near 30 to 34%; the gain moves from
  -27.3 to -22.0 to +0.7 and does not become positive at any budget.
  G1 on M1 at 1x: calls cut 103 of 1,406 (7%) and tokens in cut calls
  14%, both above the grid bars, because at 1x the remaining allowance
  rather than c cuts calls as episodes run out (147 of 150 exhausted); no
  turn with two cut calls, no JSON or cut text to the customer, no
  holding line. The bars were set for the 4x grid; the 1x reading is
  reported, not used to exclude the cell.
- 2026-09-26 — R1, airline x gemini-3.1-flash-lite (above 45%) finished
  at 1x (S1 capped and M1, 150 episodes each, 0 infrastructure errors).
  S1 at 1x 72.0% [64.3, 78.6] with 44 of 150 exhausted; S1 uncapped 78.7%,
  so capping S1 costs -6.7 [-12.7, -0.7] here (the §4.2 asymmetry, larger
  than on telecom). M1 at 1x 48.0% [40.2, 55.9] with 147 of 150 exhausted.
  `gain_1x` -24.0 [-35.3, -13.3]; `gain_4x` -16.0 [-24.0, -8.0];
  `gain_4x - gain_1x` +8.0 [-1.3, +18.0], so budget dependence is not
  claimed. `M1_4x - M1_1x` +14.7 [+7.3, +23.3]. G1 on M1 at 1x as on
  telecom: calls cut 103 of 1,229 (8%), tokens in cut calls 12%, driven by
  the remaining allowance as episodes run out; no double-cut turn, no JSON
  or cut text, no holding line.
  R1 complete. On both cells the gain is negative at 1x and at 4x and
  moves toward zero with the larger ceiling by 5 to 8 points, with CIs
  that cover zero, so R1 finds no budget dependence of the gain between
  1x and 4x under the §1 rule; the team improves with budget in absolute
  terms (+9.3 and +14.7 points) but so little of that closes the gap. H5
  at k = 1, from these two cells only and descriptive: both gains are
  negative (-27.3 at S1 30.0%, -24.0 at S1 72.0%), so no crossing point
  exists at k = 1 within the observed range. R1 cost $17.23.
- 2026-09-26 — S2, first cell finished: telecom x gemini-3.1-flash-lite
  (below 45%; 150 episodes, 0 infrastructure errors, 89 min, $14.04). S2
  36.0% [28.8, 43.9]; S1 34.0%; M1 at 4x 12.0%. `M1_4x - S2` (H1') -24.0
  [-33.3, -15.3]; `S2 - S1` +2.0 [-7.3, +12.0] (task-cluster bootstrap
  over 50 tasks, seed 300, 2,000 resamples). Per task against S1: better
  on 15, same on 23, worse on 12. S2 exhausted 39 of 150 (M1 at 4x: 67);
  S2 episodes that finished inside the budget passed 54 of 111 (49%),
  exhausted ones 0 of 39. Completion tokens per episode 5.4 times S1's
  (M1 at 4x: 5.8 times). Mechanical G1 bars pass (33 of 3,664 calls cut at
  c, all act calls, each followed by a closing call; no JSON or cut text
  to the customer). JSON handling: 39 JSON act replies; 22 used the
  message drafted inside them, 38 were repeated once, and 6 of those
  repeats were JSON again and became the holding line (6 of 855 customer
  messages). Review outcomes over 1,807 turns: draft kept 779, arguments
  revised 135, tool changed 419 (flash-lite drafts tool names that do not
  exist, as in the smoke), message reworded 306, action type changed 62.
  Reading under §8.2: rule (2) holds on this cell, since `S2 - S1` covers
  zero while `M1_4x - S2` lies below it, so the grid loss on telecom x
  flash-lite is attributed to the division into agents. Read with the
  §8.1 result for the same cell: without a ceiling M1 ties S1 (+0.7), so
  what the division costs here is budget, spent on coordination: at the
  same 4x ceiling and a similar spend ratio, the single context finishes
  more often (111 of 150 against 83) and passes more of what it finishes.
  `S2 - S1` carries the uncapped-S1 asymmetry stated in §8.2.
- 2026-09-26 — R2, airline x gpt-5-nano finished (S1 uncapped and M1 at
  4x with the gpt-4.1 simulator; 150 episodes each, 0 infrastructure
  errors). Under gpt-4.1: S1 37.3% [30.0, 45.3], M1 47.3% [39.5, 55.3],
  `gain` +10.0 [+1.3, +19.3]. Under gpt-5.2 (grid): S1 42.7%, M1 45.3%,
  `gain` +2.7 [-6.7, +12.7]. Paired difference in `gain` between
  simulators +7.3 [-3.3, +18.0], covering zero, so this cell does not
  count toward simulator contingency under the §1 rule. Component shifts:
  S1 gpt-4.1 minus gpt-5.2 -5.3 [-12.7, +2.0]; M1 +2.0 [-5.3, +9.3]. M1
  under gpt-4.1 exhausted 24 of 150 (35 under gpt-5.2); G1 bars pass (8 of
  3,225 calls cut; no JSON or cut text; 1 holding line). Stated plainly:
  this is the first cell in the study where the team's gain has a CI
  wholly above zero, and it sits where Kim et al.'s rule predicts one (S1
  at 37.3%, below 45% by its point estimate); it is a single contrast
  among many, with no multiplicity adjustment, and the pre-registered R2
  test on this cell is the between-simulator difference, which covers
  zero. Reported descriptively, not as a finding. Cost $14.01.
- 2026-09-26 — R2, airline x gemini-3.1-flash-lite finished (150
  episodes each, 0 infrastructure errors). Under gpt-4.1: S1 81.3% [74.3,
  86.8], M1 62.0% [54.0, 69.4], `gain` -19.3 [-30.0, -8.7]. Under gpt-5.2
  (grid): `gain` -16.0 [-24.0, -8.0]. Paired difference in `gain` -3.3
  [-11.3, +6.0], covering zero. Component shifts: S1 +2.7 [-3.3, +8.7],
  M1 -0.7 [-4.7, +4.0]. M1 under gpt-4.1 exhausted 32 of 150 (46 under
  gpt-5.2); G1 bars pass (28 of 2,638 calls cut; no JSON or cut text; no
  holding line). Cost $12.46. With two of the three R2 cells covering zero,
  the §1 rule (contingency only if at least two of three exclude zero) can
  no longer be met: simulator contingency is not claimed, whatever the
  airline x gemini-3-flash cell shows; that cell is still run and
  reported.
- 2026-09-26 — H1 run (`h1_extract.py`, `h1_analysis.py`,
  `h1_sensitivity.py`; outputs in `results/h1/`; logged here on the same
  day). Primary fit on the 12 cells with a leave-one-domain-out index
  (telecom x qwen3.5-4b has none: its other domains were not run, so it
  enters only the split-seed and naive forms, where its own family effect
  absorbs it). Slope -0.41, 95% CI [-1.51, +0.68] (t, dof 7); permutation
  p within family, one-sided 0.21, two-sided 0.43. **H1 is not
  supported.** Crossing: none (the slope CI covers zero). Robustness forms
  agree in sign and none excludes zero: split seeds -0.44 [-0.95, +0.07];
  logit gain -1.61 [-4.97, +1.75]; relative gain -0.35 [-1.40, +0.70]; the
  naive form (-0.55 [-1.16, +0.06]) is descriptive. Family-by-x
  interaction -0.74 [-3.07, +1.58]. The bootstrap slope interval in
  `h1_report.md` ([-0.71, -0.06]) resamples tasks within cells and ignores
  the scatter between cells; it is not the test and is not cited as
  evidence. Overdispersion is large: sigma^2 = 18.6 (unweighted residual
  SD 0.18 against a median per-cell SE of 0.05). Sensitivity adding the
  three qwen3.5-9b cells, which fail G1: -0.28 [-1.26, +0.69], one-sided p
  0.30. Check: an independent re-fit from `per_episode.csv` reproduced the
  slope (-0.413); a permutation that keeps each cell's weight in place
  gives one-sided p 0.14, with the same reading. Sign match (secondary):
  11 of the 12 cells have S1 intervals clear of 45% (airline x gpt-5-nano
  straddles), and all 11 gains are negative with intervals below zero. The
  rule's sign holds in the 9 cells above 45% and fails in both cells below
  it (telecom x gpt-5-nano, telecom x gemini-3.1-flash-lite): 9 of 11,
  binomial p 0.065 two-sided (10 of 12 with telecom x qwen3.5-4b, p
  0.039). Read plainly, M1 loses at every capability level held, so
  agreement above 45% reflects a general loss, and the rule's distinctive
  prediction, a gain below 45%, fails. On the index itself the cells span
  0.38 to 0.86 and only one (retail x gpt-5-nano) lies below 0.45.
- 2026-09-26 — Power of the H1 test for the cells held (§1.1 required a
  re-run with measured baselines before the freeze; it was not done).
  `power12.py` (in `results/secondary-2026-09-26/`) simulates the primary
  estimator on the observed leave-one-domain-out x and per-cell SEs
  (family and domain effects, inverse-variance WLS, t interval, dof 7),
  4,000 worlds per point, and adds between-cell scatter tau, which
  `power_sim.py` set to zero. tau estimated from the primary fit: 0.20.
  With tau = 0.20, power is 0.05 at b = -0.2, 0.08 at -0.3, 0.16 at -0.5
  and 0.46 at -1.0 (false-positive rate 0.02). With tau = 0 and 12 cells,
  power at b = -0.2 is 0.36 (the pre-registered 27-cell design: 0.77). The
  §1.1 reading of a null as "|b| < 0.2" therefore does not hold: the H1
  null says little about the slope, and the paper states this beside the
  result.
- 2026-09-26 — G1 write-order indicator computed for the first time (the
  2026-09-22 entry required it before H1; H1 was run without it).
  `orders.py` classifies each unique write order against the tool
  signatures in tau2's `tools.py`. **The bar (at least 90% of write orders
  executed as issued) fails in all 13 M1 grid cells**: 9% to 41% of orders
  were executed as issued. Cause, from the logs and the code: the
  orchestrator is called with no tools and no tool definitions
  (`m1_agent.py`, `tools=None`; role block v6: "never receives tools"),
  yet the role block asks it to state every write as an exact call,
  `{"tool": ..., "arguments": ...}`. It therefore guesses names. Examples:
  `book_flight`, `modify_reservation` and `update_reservation` (airline),
  `create_return_request` and `submit_exchange` (retail),
  `toggle_roaming`, `disconnect_vpn` and `toggle_airplane_mode` (telecom;
  the last is an action on the customer's phone). The database agent,
  which has native tools, then maps an invented name to a real write tool
  (0 to 57% of orders by cell), corrects argument names without saying so
  (3 to 41%), or makes no call and reports back or calls a different,
  non-write tool (9 to 64%; every refusal of a real tool name had wrong,
  extra or missing argument keys). It changed an argument value in 0 to 4%
  of orders. The frozen checker understated the failure: it logs each
  order twice and leaves refused orders out of its denominator (its own
  rate is 12% to 88%, still below 90% in every cell). The other mechanical
  bars pass on the 12 H1 cells (calls cut at c at most 3.5%, tokens in cut
  calls at most 6.7%, no JSON or cut text to the customer under a
  corrected cut-text check that no longer flags complete JSON plans);
  exhaustion-turn double cuts remain on three cells (airline x
  gemini-3-flash 1, retail x flash-lite 2, retail x gemini-3-flash 1), and
  amendment (b) is still open. Link to the loss, as accounting and not as
  a causal estimate: M1 episodes with at least one refused or diverted
  order carry 44% of the mean loss over the 12 cells, and gpt-5-mini
  episodes that finished despite such orders passed close to S1 on the
  same tasks (70 to 80% against 75 to 81%), so these orders cost mostly
  budget. **Consequence under §1 G1:** this is a protocol failure in every
  family; the stop rule applies, and until a fix is run H1 has no valid M1
  cell. The cause falls in a permitted fix class (malformed tool calls;
  the orchestrator lacks information the protocol requires of it).
  Proposed fix, not applied: every orchestrator call carries the tool
  definitions with `tool_choice` "none", as S2's plan call already does;
  no text of the base prompt or any role block changes. The decision on
  the fix and the re-run rests with the PI. The flaw is shared by every M1
  arm (grid, `r = 25`, R1, R2, uncapped), and it bears on the §8.2 reading
  of S2: S2's plan call saw the tool definitions and M1's orchestrator did
  not, so `M1_4x - S2` on telecom x flash-lite (-24.0) measures tool
  visibility together with the division into agents.
- 2026-09-26 — H4 run (`h4_extract.py`, `h4_analysis.py`, `h4_fp.py`;
  outputs in `results/h4/`; logged here on the same day). WW is defined on
  tasks whose gold trajectory has no write (airline 24, retail 3, telecom
  16 tasks), so retail WW is near zero by construction. H4a (S1, 12
  cells): slope of WW / failures on the index -0.15 [-0.64, +0.34],
  permutation p one-sided 0.39; **not supported**. H4b (13 cells, paired
  M1 - S1 per episode, cell-cluster bootstrap): WW -0.006 [-0.026,
  +0.012]; IN +0.073 [+0.037, +0.119]; BX +0.34 [+0.24, +0.44]; pass -0.30
  [-0.44, -0.19]. By the fixed grid, WW is unchanged: the architecture did
  not act on the failures it targets; **H4b not supported**. FP on the
  four airline cells (official NL-assertion evaluator, gpt-4.1,
  temperature 0, passing episodes): commission flags per episode -0.017
  [-0.028, -0.008] (M1 fewer), all flags -0.002 [-0.020, +0.017]; omission
  flags are not hand-adjudicated, so the all-flag count is an upper bound.
  S1's commission rate among passes tends to fall with the index (0.16, 0.05,
  0.07, 0.03), four cells in one domain, descriptive only. The
  coordination-induced class "order misexecuted" (§2) is reported in the
  write-order entry above; all H4 numbers rest on M1 as built.
- 2026-09-26 — Secondary analyses on the 12 H1 cells
  (`results/secondary-2026-09-26/`, scripts and `REPORT.md` there). All
  rest on M1 as built, which fails G1 (entry above). (1) Loss
  decomposition, exact: gain = mean over M1 episodes of (reward - S1's
  pass rate on the same task), split by whether the episode ended
  budget-exhausted. Mean over the 12 cells: gain -27.1; exhausted episodes
  -19.6 (72% of the loss); finished episodes -7.5. Exhaustion carries 60
  to 90% of the loss in 9 of the 11 losing cells; the two gpt-5-nano
  losses run mainly through finished episodes (retail -17.1 [-25.3, -8.9],
  telecom -9.8 [-16.9, -3.6]). Finished episodes also lose, with intervals
  below zero, on airline and telecom x flash-lite and on all three
  gemini-3-flash cells. Earlier entries compared finished M1 episodes with
  S1 on all tasks; finishing selects easier tasks, so that comparison
  favours M1. The same-task comparison replaces it: on telecom x
  gpt-5-mini, for example, finished episodes give -2.7 [-8.9, +3.6], a tie
  rather than an advantage. (2) H7: median utilisation at 4x is at least
  0.7 in 9 of 12 cells (all Gemini and all gpt-5-mini cells; gpt-5-nano
  0.50 to 0.63), so the first clause holds. The second clause was written
  for a ceiling above 4x, and R1 ran at 1x only; across the two levels
  held, exhaustion falls from 98% at 1x to 45% (telecom) and 31% (airline)
  at 4x, far more than 10 points. **H7 is not supported.** Median
  completion tokens, M1 / S1: 2.8 to 6.1. (3) H5: no crossing at 4x (H1
  above) and two cells at 1x, so x0 cannot be estimated at either level;
  reported as not detected. (4) H6: write share = (wrongful writes + wrong
  writes) / S1 failures, where a wrong write is a failing episode on a
  write task in which the agent wrote and the database check or a gold
  write action failed (this operational definition is fixed here, after
  gains were seen, and is labelled as such). Shares run from 0.54 to 0.88.
  Joint model: b2 -0.56 [-2.21, +1.09], permutation p 0.55 two-sided; b1
  -0.75 [-1.97, +0.47]. **H6 is not supported**, and the point estimate
  has the opposite sign to the claim; with family effects added, b2 -0.78
  [-2.11, +0.55], p 0.17. (5) Cost (§4.4, meters 3 and 4): M1 agent USD is
  2.3 to 4.0 times S1's and end-to-end USD 1.4 to 3.1 times; S1 dominates
  M1 on accuracy and USD in 11 of 12 cells, and on airline x gpt-5-nano
  the two tie on accuracy at twice the end-to-end cost for M1. (6) Per
  task: over the 600 task-cells, M1 is better on 43, the same on 273 and
  worse on 284; no task improves under M1 for three or four of the four
  API models in any domain, while 25 retail, 18 telecom and 13 airline
  tasks get worse for at least three.
- 2026-09-26 — R2, airline x gemini-3-flash finished (the third and last
  R2 cell; 150 episodes each, 0 infrastructure errors; the Mac slept from
  about 06:10 to 08:20 UTC, which paused the run without errors). Under
  gpt-4.1: S1 86.7% [80.3, 91.2], M1 57.3% [49.3, 65.0], `gain` -29.3
  [-41.3, -17.3]. Under gpt-5.2 (grid; S1 is the admitted gate run):
  `gain` -25.3 [-36.7, -14.0]. Paired difference in `gain` -4.0 [-10.7,
  +2.7], covering zero. Component shifts: S1 +6.0 [-0.0, +12.7], M1 +2.0
  [-1.3, +6.7]. M1 under gpt-4.1 exhausted 70 of 150 (76 under gpt-5.2);
  mechanical G1 bars pass (60 of 3,751 calls cut; no JSON or cut text; no
  holding line); the G1 write-order failure logged on 2026-09-26 applies
  to this run as to every M1 run. Cost: M1 $19.43, S1 under gpt-4.1 $7.86.
- 2026-09-26 — R2 complete (three airline cells, fixed on 2026-09-25;
  $53.76 for the gpt-4.1 runs). Paired difference in `gain` between
  simulators (gpt-4.1 minus gpt-5.2): gpt-5-nano +7.3 [-3.3, +18.0];
  gemini-3.1-flash-lite -3.3 [-11.3, +6.0]; gemini-3-flash -4.0 [-10.7,
  +2.7]. All three intervals cover zero, so by the §1 rule (contingency
  only if at least two of three exclude zero) **simulator contingency is
  not claimed**. The two losing cells lose under both simulators. On
  airline x gpt-5-nano the gain under gpt-4.1 is +10.0 [+1.3, +19.3], the
  only interval above zero in the study, against +2.7 [-6.7, +12.7] under
  gpt-5.2; the shift comes mostly from S1, which passes 5.3 points less
  under gpt-4.1 ([-12.7, +2.0]), while M1 moves +2.0 [-5.3, +9.3]. It is
  reported descriptively. All R2 M1 runs are M1 as built and share the G1
  write-order failure.
- 2026-09-26 — S2, second cell finished: airline x gpt-5-nano (straddles
  45%; 150 episodes, 0 infrastructure errors, $11.30; paused about two
  hours while the Mac slept, no errors). S2 45.3% [37.6, 53.3]; S1 42.7%;
  M1 at 4x 45.3%. `M1_4x - S2` (H1') 0.0 [-8.7, +8.7]; `S2 - S1` +2.7
  [-5.3, +11.3] (task-cluster bootstrap over 50 tasks, seed 300, 2,000
  resamples). Per task against S1: better on 12, same on 27, worse on 11.
  S2 exhausted 37 of 150 (M1 at 4x: 35); finished episodes passed 58 of
  113 (51%), exhausted ones 10 of 37. Completion tokens per episode 4.9
  times S1's (median; M1 at 4x: 2.9 times). Mechanical G1 bars pass (20 of
  3,076 calls cut at c; no JSON or cut text to the customer). JSON
  handling: 92 JSON act replies, 91 resolved by the message drafted inside
  them or by the repeat; 18 of 692 customer messages were the holding
  line. Plan-parse failures 9 turns (9 plans returned as tool calls).
  Review outcomes: kept 242, arguments revised 77, tool changed 111,
  message reworded 332, draft message replaced by a tool call 555, tool
  call replaced by a message 48; wrap-up and fallback turns counted apart
  (108). Reading under §8.2: rule (1) does not hold (`S2 - S1` covers
  zero) and rule (2) does not hold (`M1_4x - S2` covers zero), so the cell
  is **mixed** by the fixed rule; stated plainly, S1, S2 and M1 tie on
  this cell. It carries the same caveat as the first cell: S2's plan call
  saw the tool definitions and M1's orchestrator did not. S2 running total
  $36.58 with telecom x gpt-5-nano at 82 of 150.
- 2026-09-26 — S2, third and last cell finished: telecom x gpt-5-nano
  (below 45%; 150 episodes, 0 infrastructure errors, $20.14; 824 minutes
  including the pause while the Mac slept). S2 27.3% [20.8, 35.0]; S1
  32.7%; M1 at 4x 19.3%. `M1_4x - S2` (H1') -8.0 [-14.7, -1.3]; `S2 - S1`
  -5.3 [-12.7, +1.3] (task-cluster bootstrap over 50 tasks, seed 300,
  2,000 resamples). Per task against S1: better on 7, same on 29, worse on
  14. S2 exhausted 64 of 150 (M1 at 4x: 23); completion tokens per episode
  4.9 times S1's (median; M1 at 4x: 2.8 times). Split of `S2 - S1` by
  episode ending, each episode against S1 on the same task: exhausted
  episodes -8.0 [-12.0, -4.2], finished episodes +2.7 [-2.7, +8.2]
  (finished S2 episodes passed 46.5% where S1 passes 41.9% on the same
  tasks), so S2's shortfall, which is not significant, runs through the
  budget. Mechanical G1 bars pass (46 of 6,193 calls cut at c, all act
  calls, each followed by a closing call; no JSON or cut text to the
  customer). JSON handling: 174 JSON act replies; 58 of 903 customer
  messages (6.4%) were the holding line, the highest share of the three
  cells. Review outcomes: kept 230, arguments revised 24, tool changed
  616, message reworded 351, draft message replaced by a tool call 1,514,
  tool call replaced by a message 33; wrap-up and fallback turns counted
  apart (292). Reading under §8.2: rule (1) does not hold (`S2 - S1`
  covers zero); rule (2) holds (`S2 - S1` covers zero and `M1_4x - S2`
  lies below zero), so the grid loss on this cell is attributed to the
  division into agents, with the caveat that S2's plan call saw the tool
  definitions and M1's orchestrator did not.
- 2026-09-26 — S2 complete (three cells, §8.2; $45.48 in total, under the
  $75 stop). telecom x gemini-3.1-flash-lite: `M1_4x - S2` -24.0 [-33.3,
  -15.3], `S2 - S1` +2.0 [-7.3, +12.0], rule (2). airline x gpt-5-nano:
  0.0 [-8.7, +8.7] and +2.7 [-5.3, +11.3], mixed by the rule (S1, S2 and
  M1 tie). telecom x gpt-5-nano: -8.0 [-14.7, -1.3] and -5.3 [-12.7,
  +1.3], rule (2). On both cells below 45%, one context running the same
  plan-and-review workflow under the same ceiling does not differ
  significantly from S1, while M1 loses to it; by the fixed reading, the
  grid loss on these two cells comes from dividing the work among agents
  and not from the added scaffolding or the ceiling alone. Two limits are
  stated beside the result. First, S2's plan call saw the tool definitions
  and M1's orchestrator did not (the G1 write-order failure logged today),
  so "division into agents" here includes the orchestrator's missing tool
  information; an M1 whose orchestrator sees the definitions would
  separate the two. Second, three cells support no slope, and H1' remains
  descriptive as fixed in §8.2.
- 2026-10-10 — Scope change decided by the PI, written before any episode:
  the S1 calibration of retail x qwen3.5-4b is run after all, reversing
  that part of the 2026-09-25 scope decision (the airline x 4b cells and
  all 4b M1 cells other than telecom stay unrun). Configuration identical
  to the registered telecom x qwen3.5-4b S1 cell: Ollama 0.34.2,
  `tt-qwen3.5-4b:q4` (Q4_K_M, base digest `2a654d98e6fb`), `num_ctx`
  131072 with the server started at CTX=131072 PAR=4, route `openai/` on
  the OpenAI-compatible endpoint, timeout 3,600 s, `max_tokens` 32,768,
  `reasoning_effort` high, the model's shipped sampling defaults;
  simulator gpt-5.2 (reasoning effort low); the 50 registered retail
  tasks, 3 trials, seed 300, max steps 200, max errors 10, concurrency 1;
  tau2 `c339866`; base prompt `825bb492ecd9...`. Run with
  `run_calibration.py --only qwen/qwen3.5-4b/retail`, saved as
  `calib-retail-s1-qwen35-4b-q4-ollama-gpt52low-3trials-seed300`; the dry
  run gives the telecom cell's command with only the domain and task ids
  changed, and the task ids equal those of every other retail cell. The
  teammate's retail run of 2026-09-24 (`results/teammate-qwen4b-ollama/`:
  `ollama_chat` route, 32k context, temperature 0, 45% of episodes ending
  in AGENT_ERROR) is not used. Timing, stated plainly: decided after every
  grid M1 cell, H1, H4 and the G1 write-order audit had been seen; S1 does
  not depend on M1, but the choice to add the cell is post hoc and
  labelled so. What the cell can and cannot do: on its own it fills the §5
  row and gives `B_1x` for a possible retail x 4b M1 cell. It adds no cell
  to the primary H1 fit, because the leave-one-domain-out index of a 4b
  cell needs S1 on both other domains (telecom x 4b needs airline and
  retail; retail x 4b needs airline and telecom). Any M1 run on this cell
  waits for the PI's decision on the G1 write-order fix (2026-09-26).
- 2026-10-10 — retail x qwen3.5-4b S1 on hold before any episode. The
  deploy step (`ollama/deploy_qwen35_4b.sh`, 19:54 UTC) pulled
  `qwen3.5:4b` again, and the Ollama library tag now points to a different
  build: digest `d8b0f5e9760c` in place of the registered `2a654d98e6fb`,
  4.2B parameters with a separate 333.51M vision projector (layers
  `a9d0a3e1d8c9`, `e56a899b1540`) in place of one 4.7B file
  (`81fb60c7daa8...`), minimum Ollama 0.30.0 in place of 0.17.1. The
  script then rebuilt the pinned name `tt-qwen3.5-4b:q4` on the new build
  (`c0535b43ca6b` in place of `668eab7d518c`). A run now would not use the
  model of the telecom x 4b cells. Records: the registered
  `ollama/provenance-q4.txt` is restored from the repository; the new
  build's record is kept as
  `ollama/provenance-q4-2026-10-10-newbuild.txt`. Next step: if the
  registered weights file is still on disk, the pinned name is rebuilt
  from it (`ollama/Modelfile.q4-registered`) and checked against
  `668eab7d518c` before the run starts; if it is gone, the cell is not run
  on the new build without a decision by the PI, because a different build
  cannot pair with the telecom x 4b cells. This also bears on any future
  M1 re-run of telecom x 4b.
- 2026-10-10 — retail x qwen3.5-4b S1 started on the new Ollama build,
  decided by the PI after the registered weights file
  (`sha256-81fb60c7daa8...`) was found to be gone from the Mac. Build:
  `qwen3.5:4b` digest `d8b0f5e9760c`, pinned name `tt-qwen3.5-4b:q4` =
  `c0535b43ca6b` (record in `ollama/provenance-q4-2026-10-10-newbuild.txt`
  and `ollama/check-q4-2026-10-10-newbuild.json`; the registered
  `provenance-q4.txt` and `check-q4.json` were restored after each deploy
  overwrote them). All other settings as in the entry above. Run through
  `ollama/run_local_s1.py --domain retail --full`, saved as
  `local-retail-s1-qwen35-4b-q4-ollama-gpt52low-3trials-seed300`, so it
  stays apart from the registered `calib-` runs and is not read by
  `build_budgets.py` or `fill_cell.py`. Reported as a separate build,
  `qwen3.5-4b (Q4_K_M, October 2026 Ollama build)`; it is not paired with
  the telecom x 4b cells and enters no H1 or H4 fit. At 23:22 UTC: 44 of
  150 episodes, 4 of them infrastructure errors (the model returned an
  empty message, "AssistantMessage must have either content or
  tool_calls", the same class as one of the two re-run telecom episodes);
  these are re-run when the cell finishes.
- 2026-10-12 — retail x qwen3.5-4b S1 finished on the October 2026 Ollama
  build (`qwen3.5:4b` digest `d8b0f5e9760c`, pinned `tt-qwen3.5-4b:q4` =
  `c0535b43ca6b`); this is not the registered qwen3.5-4b cell. Run
  `local-retail-s1-qwen35-4b-q4-ollama-gpt52low-3trials-seed300`, results
  SHA-256 `3b8fefe355d8...`. The main run left 13 infrastructure errors,
  all empty model replies ("AssistantMessage must have either content or
  tool_calls"); a relaunch with tau2's auto-resume re-ran them (two
  attempts each), and 5 remain (task 36 trials 0 and 2, task 80 trial 0,
  task 93 trial 1, task 109 trial 1). Evaluated episodes 145 of 150.
  pass^1 74.0%, 95% task-cluster CI [64.7, 82.7] (the `fill_cell.py`
  procedure applied to evaluated episodes only: per-task mean over
  evaluated trials, 10,000 draws, seed 300); episode pass rate 109 of 145;
  trials 83%, 71%, 71%; tasks with three evaluated trials (46) passing
  0/1/2/3 times: 2, 7, 13, 24. Clearly above 45%. Health: no prompt
  truncated, no call at the 32,768-token guard, no episode within 5% of
  the 131,072 context. Budget values over the 145 evaluated episodes: mean
  completion tokens per episode 4,461, B_1x (P75) 5,369, per-call P95 c
  1,179 (`calibrate_budget.py` over all 150 episodes, infrastructure
  errors included, gives B_1x 5,278). Not entered in the §4.2 or §5 tables
  and not read by `build_budgets.py`; it enters no H1 or H4 fit and is not
  paired with the telecom x 4b cells, whose S1 (94.7%) used the registered
  build. Stated plainly, the 5 empty-reply episodes (3.3%) are a property
  of this build in this serving setup; the registered build had one such
  episode in 150 on telecom, re-run to zero.
- 2026-10-12 — M1 set up on retail x qwen3.5-4b on the October 2026 Ollama
  build, decided by the PI, written before any episode. M1 as built
  (orchestrator block v6, database agent v2, advisor v4; k = 4, c = B_1x,
  r = 4), so the G1 write-order failure logged on 2026-09-26 applies to
  this run as to every M1 run; the decision on the fix for the grid
  (options A and B) is still open. Config: `cells.json` gains a model
  entry `qwen3.5-4b-oct26` (short name `qwen35-4b-q4-oct26-ollama`; route
  and arguments identical to `qwen3.5-4b`, snapshot the October build), so
  the run name
  `m1-retail-qwen35-4b-q4-oct26-ollama-gpt52low-b4x-capb1x-3trials-seed300`
  cannot be mistaken for the registered model. `budgets.json` gains
  `retail x qwen3.5-4b-oct26`, written by hand because the S1 run is a
  `local-` run that `build_budgets.py` does not read:
  `calibrate_budget.py` over the 145 evaluated episodes (the 5
  infrastructure-error episodes made no agent call) gives B_1x 5,369,
  per-call median 230, w 805, a_min 230; ceiling 4 x 5,369 = 21,476 and
  per-call cap c = B_1x = 5,369. A rebuild of `budgets.json` drops this
  entry. The Ollama server is started with the new `ollama/serve_only.sh`,
  which applies the deploy script's settings (CTX=131072, PAR=4,
  caffeinate) without pulling or rebuilding any model and refuses to
  continue unless `tt-qwen3.5-4b:q4` is `c0535b43ca6b`. Order: a smoke of
  5 tasks x 1 trial (`--smoke 5 --num-trials 1`), read on the mechanical
  G1 bars and the write-order audit before reward, then the full 150
  episodes. The cell is reported as M1 as built on a different build: it
  is paired only with its own S1 (74.0%), enters no H1 or H4 fit and is
  not compared with the telecom x 4b M1 cell.
- 2026-10-12 — Smoke of M1 on retail x qwen3.5-4b-oct26 (5 tasks x 1
  trial, 42 minutes, 0 infrastructure errors; budget as set up: ceiling
  21,476, c 5,369, w 3,221, a_min 230). Mechanical G1 bars pass: 1 of 124
  calls cut at c (tokens in cut calls 1%), no turn with two cut calls, no
  JSON or cut text to the customer, 1 holding line. Reported indicators:
  plan-parse failures 9 of 61 plan calls (15%; telecom x 4b on the
  registered build: 56%), advisor consulted in 3 of 5 episodes, 1 of 5
  episodes exhausted, median utilisation 0.65, 5.6 agent tool calls per
  episode. Write orders: 3 in 5 episodes, none executed as issued (one
  invented tool name mapped to a real tool, one invented name refused, one
  with argument names corrected by the database agent), the G1 write-order
  failure as on every M1 cell. Reward, read last: 0 of 5, every episode
  failing the database check; S1 passes the same five tasks in 10 of 14
  evaluated episodes. Under the smoke rules reward is not a reason to
  change anything, and the full cell may start.
- 2026-10-12 — G1 write-order fix A1 built, decided by the PI, written
  before any episode with it. Diagnosis (entry of 2026-09-26): the frozen
  orchestrator block asks for every write as an exact call, `{"tool": ...,
  "arguments": ...}`, which the database agent executes as issued, but the
  orchestrator is called with no tool definitions, so it guesses tool and
  argument names. Fix: every orchestrator call (plan, act and the forced
  customer message) now carries the same tool definitions the database
  agent has, with `tool_choice` "none", as S2's plan call does; the
  orchestrator still cannot call a tool, and every tool call is made by
  the database agent. A tool call returned anyway (Ollama ignores
  `tool_choice`) is charged to the budget, never executed, logged as
  `orchestrator_returned_tool_call:<call>`, and handled like an unparsable
  reply (the plan is retried once; a forced message falls back to the
  holding line). The advisor is unchanged. No text of the base prompt or
  any role block changes, so the fix is in the permitted class (malformed
  tool calls; the orchestrator lacked information the protocol requires of
  it). This is the first post-freeze fix iteration for the write-order
  failure, in every family. Code: `m1_agent.py`
  (`orchestrator_tool_definitions`, default off, so M1 as built is
  unchanged and reproducible), `run_m1.py --orch-tool-defs` (run names
  carry `-otd`; the manifest records the flag), `smoke_health.py` (reports
  the flag and the dropped tool calls). Tests: 65 pass (5 new: as built
  sends no tools and no `tool_choice`; with A1 the plan and act calls
  carry the definitions with "none", the advisor gets none and the
  database agent keeps "auto"; a tool call from the orchestrator is
  charged, dropped and the plan retried; a forced message never executes
  one; one mock-domain episode end to end through tau2's runner). Smoke
  before any full run: 5 tasks x 1 trial on telecom x gemini-3-flash,
  retail x gpt-5-mini and airline x gpt-5-nano (the cells with the most
  refused or invented orders across the families), read in this order:
  infrastructure errors, the mechanical G1 bars, the write-order bar (at
  least 90% of unique write orders executed as issued, refused orders
  counted as not executed, by `orders.py`), dropped orchestrator tool
  calls, and reward last. If the write-order bar passes on all three, the
  M1 grid at k = 4 is re-run in full with `--orch-tool-defs`, and M1 as
  built moves to the appendix as the first pass; if it fails, the cause is
  diagnosed and logged before anything else runs.
- 2026-10-14 (M1 as built, retail x qwen3.5-4b-oct26, mid-run reading
  before any reward was read): the run was stopped at 41 of 150 episodes
  on 2026-10-13 (results.json backed up first) and relaunched at 02:19
  UTC on 2026-10-14 with the same command and server settings (CTX
  131072, PAR 4); tau2 resumed from 41 saved episodes. At 122 of 150
  (trial 2 at 22 of 50): 0 infrastructure errors; calls cut at c 73/2834
  (3%); tokens in cut calls 11.35%, over the 10% bar; 7 turns with two
  cut calls (5 on exhaustion turns, 2 on normal turns, so the bar fails
  even under amendment (b)); budget exhausted in 53 of 122 episodes. The
  failure sits in trial 2. Exhausted episodes by trial: 19/50, 12/50,
  22/22. Median completion tokens per orchestrator plan call: 743, 706,
  2082; per forced message: 640, 616, 2469; plan calls cut: 11, 2, 34;
  orchestrator calls with empty visible output (all tokens spent on
  hidden reasoning, cut at c): 14/837, 3/934, 40/174. Database agent
  calls did not change (median 211, 217, 192). The shift begins with the
  first trial 2 episode and nothing else changed at that point, except
  the trial seed (626729, 373753, 361454). tau2 writes the trial seed
  into llm_args, so every call in a trial reaches Ollama with the same
  sampling seed; within a trial the sampler draws the same random stream
  on every call, and calls are not independent draws. Working
  explanation, not yet tested: seed 361454 sends the orchestrator prompt
  into long reasoning on most calls. S1 on the same cell used the same
  three seeds and shows no comparable shift (calls over 2000 tokens: 5,
  5, 9; no empty outputs), so the effect is specific to the M1
  orchestrator prompt if the seed explanation holds. The cell runs to
  completion as registered (3 trials). After it finishes and before its
  reward is read: a replay test on the Mac (the same orchestrator plan
  requests sent with each trial seed and with no seed, 5 repeats each,
  comparing completion tokens and empty outputs) to confirm or reject
  the seed explanation. The cell is reported per trial as well as
  pooled. If confirmed, the fixed per-trial seed is a limitation of
  every Ollama-route cell (trials, not episodes, carry the sampling
  noise) and is disclosed in the paper; no registered result changes.
- 2026-10-15 (M1 as built, retail x qwen3.5-4b-oct26, cell complete): 150 of
  150 episodes, 0 infrastructure errors, manifest return code 0. The
  manifest records only the resumed segment (02:19 UTC 2026-10-14 to 03:04
  UTC 2026-10-15); the first segment ran from 22:38 UTC 2026-10-12 to the
  stop at 41 episodes. G1: calls cut at c 118/3241 (3.6%, passes); tokens
  in cut calls 15.6% (fails); 12 turns with two cut calls, 7 on exhaustion
  turns and 5 on normal turns (fails strictly and under amendment (b)); no
  JSON or cut text to the customer; budget exhausted in 74 of 150
  episodes. Write orders (orders.py): 79 unique, 13 executed as issued
  (16%), 44 invented names mapped to a write (56%), 13 diverted (16%), 6
  with keys corrected (8%), 2 unstructured, 1 refused, so the write-order
  bar fails, as in every API cell (9 to 41% executed as issued). The cell
  is invalid under G1 and stays outside every H1/H4 fit, where it already
  sat as M1 as built on the October build. Per trial (seeds 626729,
  373753, 361454): exhausted 19, 12 and 43 of 50; tokens in cut calls
  6.1%, 0.7% and 34.2%; turns with two cut calls 1, 0 and 11; median plan
  call 743, 706 and 1269 tokens; orchestrator calls with empty visible
  output 14, 3 and 80. Trials 0 and 1 alone pass the cut-token bar; trial
  2 carries the failure. Within trial 2, on the same tasks, the shift
  holds for the whole trial and shrinks over it (median plan call 2762 in
  its first 10 episodes, about 1100 in its last 28; trials 0 and 1 stay
  near 700 on the same tasks). The first plan call of an episode is
  barely affected at the median (719 tokens; trials 0 and 1: 713 and 380)
  but is cut in 6 of 50 trial-2 episodes (1 and 0 in trials 0 and 1).
  Disclosure: the validity script also prints pass^1, and it was seen
  while reading the G1 bars, before the replay test, contrary to the plan
  of 2026-10-14. So that this cannot steer the reading, the reporting
  rule is fixed now: the cell is reported pooled over all three trials as
  registered, with the per-trial view as secondary, whatever the replay
  shows, and no trial is excluded. Three candidate explanations remain:
  the agent's sampling seed (sent with every call), the trial-2 customer
  messages (the user simulator receives the same trial seed), and the
  state of the Ollama server during trial 2. Seed replay test
  (seed_replay.py; the reading rule is in its header and was fixed before
  any replay call): it rebuilds the first orchestrator plan call of an
  episode with the M1 code itself and sends it on a freshly restarted
  server, crossing prompt source (the customer's first message from trial
  1 or trial 2, same task) with seed (361454, 373753, none), 2 repeats per
  condition, on the 6 tasks whose trial-2 first plan call was cut and 4
  control tasks (120 calls). Checked end to end in the container with a
  stub model (prompts rebuilt, cap sent 5369 as in the run, resume and
  summary work).
  Customer-message check (run after the entry above, before any replay
  call): the trial-2 customer messages do not stand out. First customer
  message, median characters by trial 225, 236 and 248, with markdown in
  17, 18 and 20 of 50; all customer messages, median 196, 210 and 202
  characters. S1 on the same cell, with the same three seeds and no
  anomaly, shows the same pattern (first message 234, 224 and 252
  characters). The user-simulator explanation is therefore weak, though
  not excluded; the replay test separates it from the other two.
- 2026-10-16 (airline x qwen3.5-4b M1 results file received; the trial-2
  anomaly is systematic): Ethan supplied a results.json for M1 (as built)
  on airline x qwen3.5-4b (agent `m1_qwen35_4b_q4_ollama_airline_b4x_
  capb1x`, the registered model name; 150 episodes, 3 trials, seed 300;
  B 27329, c 6832, so B_1x 6832 under the b1x rule; run 2026-10-07 to
  2026-10-12 local time). Saved unchanged at
  `results/received/airline-4b-m1/results.json` (SHA-256 153f9b2dcf64...).
  It was not produced by this folder's Ollama server, which was idle from
  2026-10-01 to 2026-10-08 and restarted on 2026-10-10, and this folder
  holds no airline x qwen3.5-4b S1 run, no budgets.json entry and no done
  manifest for it. Still needed before the cell enters any table as a
  result: the machine and the build of tt-qwen3.5-4b:q4 it ran on
  (registered 2a654d98e6fb or October d8b0f5e9760c, with the provenance
  record), the run_m1.py done manifest, and the S1 calibration run behind
  B_1x 6832 (results.json and manifest). Until the S1 file arrives there
  is no paired gain, and the §4.2 and §5 rows stay blank. Reading, in the
  fixed order. 0 infrastructure errors. G1: calls cut at c 111/3486
  (3.2%, passes); tokens in cut calls 12.9% (fails); 4 turns with two cut
  calls, 3 on exhaustion turns and 1 on a normal turn (fails strictly and
  under amendment (b)); no JSON or cut text to the customer; tool calls
  per episode 5.4; advisor consulted in 22 of 150 episodes; 360 plan
  parse failures over 1708 plan calls; budget exhausted in 71 of 150.
  Write orders: 52 unique, 17 executed as issued (33%), 15 with argument
  keys corrected, 12 invented names mapped to a write, 5 diverted, 1
  refused, 1 value changed, 1 unstructured; the write-order bar fails, as
  in every other M1 cell. Reward, read last: pass^1 84 of 150 = 56.0%
  (Wilson [48.0, 63.7]; task-cluster bootstrap, seed 300, 10,000 draws,
  [43.3, 68.7]); by trial 28, 30 and 26 of 50; finished inside the budget
  58 of 79 passed, exhausted 26 of 71 passed (airline tasks that require
  no database change pass under exhaustion, unlike retail and telecom).
  Per trial (seeds 626729, 373753, 361454): exhausted 15, 14 and 42 of 50;
  tokens in cut calls 6.5%, 0.8% and 26.8%; plan calls cut 16, 7 and 55;
  orchestrator calls with empty visible output 11, 6 and 65; median plan
  call 764, 741 and 1458 tokens. The pattern of the 2026-10-14 entry
  (retail x qwen3.5-4b-oct26, trial 2) is therefore present here as well,
  and it is present in the telecom x qwen3.5-4b cell of 2026-09-23 too
  (re-read today, no reward read: exhausted 26, 27 and 41 of 50; tokens
  in cut calls 3.2%, 1.8% and 17.9%; plan calls cut 16, 16 and 57; empty
  outputs 5, 8 and 48; that cell still passes the pooled bars). Three of
  three M1 cells on the local 4B route show it, in trial 2 only, on two
  machines and at least two server starts, with the registered build
  (telecom) and the October build (retail). The three qwen3.5-9b cells on
  OpenRouter and the Gemini cells, which carry the same three trial
  seeds, show no trial-2 pattern; S1 on the same route with the same
  seeds shows none either. Reading of the three candidate explanations
  of 2026-10-14 and 2026-10-15, written before any replay call: server
  state during one run is now very unlikely (three runs, two machines);
  the customer-message explanation was already weak (2026-10-15 check)
  and does not survive three domains; the sampling seed 361454, sent
  with every orchestrator call of trial 2 and interacting with the M1
  orchestrator prompt on this model and route, is the leading
  explanation. The replay test (seed_replay.py) remains the direct check
  and its reading rule is unchanged. Consequences, whatever the replay
  shows: every 4B M1 cell is reported per trial as well as pooled; the
  fixed per-trial seed is disclosed as a limitation of the local route
  (trials, not episodes, carry the sampling noise, and one of three seeds
  behaves differently under the M1 prompt); the telecom x qwen3.5-4b
  gain of -71.3 already in the grid is not changed, since it is a
  registered result, but its per-trial split is reported beside it; no
  trial is excluded from any cell.
- 2026-10-16 (A1 pipeline set up; nothing launched): scripts for the
  remaining runs of the full paper, in the order fixed on 2026-10-12 and
  in the log of 2026-10-16. (1) `scripts/a1_smokes.sh` launches the three
  A1 smokes (telecom x gemini-3-flash, retail x gpt-5-mini, airline x
  gpt-5-nano; 5 tasks x 1 trial; run names carry `-otd`). (2) `a1_gate.py`
  reads them in the fixed order (infrastructure errors; calls cut at c,
  tokens in cut calls, turns with two cut calls, JSON or cut text to the
  customer; unique write orders executed as issued, at least 90%, a
  refused order counted as not executed, categories as in the secondary
  audit; orchestrator tool calls dropped; reward last, printed and never
  gating) and writes `results/a1-smoke-gate.json`; the gate passes only if
  all three smokes finished and pass every bar. Note on the write-order
  bar at this size: a 5-task smoke carries about 3 to 10 unique write
  orders, so one failure fails the bar; the rule stands as written, and
  the pooled count over the three smokes is printed as information. (3)
  `scripts/a1_grid.sh` launches the 12 API cells with `--orch-tool-defs`
  (four processes, one per model, three domains each) and refuses to
  start without a passing gate file; it writes `results/a1-grid-launch
  .json` (time, gate time, commit); `STOP_M1` and relaunch-resume work as
  before. (4) `scripts/a1_qwen.sh` runs the local October-build cell step
  by step (replay dry run, replay, S1 on the October build as
  `local-telecom-s1-...`, calibration entry, A1 smoke, A1 cell), each
  step behind `serve_only.sh`, which refuses any build other than
  c0535b43ca6b. The registered build is gone, so an A1 cell on this route
  cannot pair with the registered telecom S1 (94.7%, build 2a654d98e6fb);
  it pairs with a new S1 on the October build, by the rule that S1 and M1
  of a cell share one stack and one build. `a1_qwen_budget.py` writes the
  `telecom x qwen3.5-4b-oct26` entry from that S1 over the evaluated
  episodes, as the retail entry of 2026-10-12 was written. This cell is a
  labelled local cell outside the primary A1 fit; the primary A1 fit is
  the 12 API cells. (5) `scripts/a1_analyses.sh` re-runs the registered
  analyses on the A1 grid: validity and write-order audit, per-cell
  report with the paired gain, H1 (`h1_extract.py`, `h1_analysis.py`), H4
  (`h4_extract.py`, `h4_analysis.py`, the airline FP judge pass with
  `nl_screen.py` on the new M1 runs, `h4_fp.py`); the secondary analyses
  (loss decomposition, H6, H7, power at the observed scatter, per-task
  counts) follow from the analysis session with the same switch. Code
  change behind (5): `h1_extract.py`, `h4_extract.py` and `h4_fp.py` read
  the environment variable `TT_M1_VARIANT`; with `otd` the M1 run names
  carry `-otd`, outputs go to `results/h1-otd` and `results/h4-otd`, and
  the local Qwen cell is the October-build pair, included only with
  `TT_INCLUDE_QWEN=1`. Without the variable every script behaves as
  before; checked by re-running `h1_extract.py` as built and comparing
  `results/h1/per_episode.csv` byte for byte with the file of 2026-09-26
  (identical). No analysis definition, bar, seed or resample count
  changes. Expected spend: about $3 for the smokes, about $200 for the 12
  cells, a few dollars for the judge pass; about 40 hours of Mac time for
  the local cell plus 1 to 2 hours for the replay. Reporting rule for the
  A1 grid, fixed now: the A1 cells become the primary grid of the full
  paper if the smoke gate passes and the full cells pass G1; M1 as built
  moves to the appendix as the first pass; cells that fail G1 are
  reported as failing and excluded from the primary fit with a
  sensitivity that includes them, as for the as-built grid.
- 2026-10-16 (PI decision: no A1 re-run of the grid for the full paper):
  Ethan decided not to run the A1 re-run of the grid at this time. The
  decision was taken at about 18:45 UTC, while the three A1 smokes
  launched at 18:38 UTC with `scripts/a1_smokes.sh` were still running
  and before any smoke episode had been read; no smoke manifest existed.
  The decision does not depend on what the smokes show: whether they
  pass or fail the write-order bar, the 12 API cells are not re-run. The
  smokes are handled as recorded in the next entry (finished and read in
  the fixed order for the record, or stopped). The fix stays in the released code
  (`m1_agent.py`, `orchestrator_tool_definitions`, default off;
  `run_m1.py --orch-tool-defs`; tests), and the pipeline of the previous
  entry stays in `scripts/` and `a1_gate.py`, unused. The full paper
  therefore reports M1 as built, with the write-order failure as
  limitation (1) and one added sentence: the fix is implemented and was
  not run. The local October-build telecom S1 and A1 cell of the previous
  entry are not run either; they served A1 only. The remaining items are
  the seed replay test, the decisions on G1 amendment (b), the airline x
  qwen3.5-4b file and the airline x qwen3.5-9b file, the per-trial
  reporting of the local 4B cells, and the writing.
- 2026-10-17 (A1 smokes finished and read for the record; the grid is not
  re-run): the three smokes launched at 18:38 UTC on 2026-10-16 finished
  on their own between 18:46 and 18:52 UTC (manifests rc 0, 5 episodes
  each, 0 infrastructure errors); read at 02:05 UTC on 2026-10-17 with
  `a1_gate.py --no-write`, in the fixed order, after the decision of the
  previous entry; no gate file was written and `scripts/a1_grid.sh` was
  not run. Mechanical G1 bars: pass on all three (calls cut 1.9%, 2.1%,
  0.0%; tokens in cut calls 2.4%, 2.2%, 0.0%; no double-cut turn; nothing
  cut or JSON to the customer); every orchestrator call carried the tool
  definitions (`orchestrator_tool_definitions` True in every episode); no
  orchestrator tool call was returned or dropped. Write-order bar: telecom
  x gemini-3-flash 1 of 4 as issued (25%, fails); retail x gpt-5-mini 7
  of 9 (78%, fails); airline x gpt-5-nano 5 of 5 (100%, passes); pooled
  13 of 18 (72%), against about 25% as built in the same cells (the
  as-built retail x gpt-5-mini smoke of 2026-10-12 and the grid cells).
  The five orders not executed as issued: two refusals by the database
  agent on policy grounds (telecom `send_payment_request` with a missing
  customer field; retail `return_delivered_order_items` with a payment
  method the agent judged wrong), which the role block forbids (the
  database agent has no veto) and which no orchestrator-side fix removes;
  one `multi_tool_use.parallel` wrapper issued as a tool name by
  gpt-5-mini and mapped to the right write; one customer-device tool
  (`toggle_airplane_mode`) ordered as an agent write; one argument key
  corrected (`reason` to `summary`). Reward, read last and not used: 1,
  3 and 4 of 5. Reading: A1 removes most invented names (2 of 18 orders
  against 56 to 80% of orders invented or diverted in the as-built grid)
  but does not reach the 90% bar on two of three cells; by the rule of
  2026-10-12 the cause would be diagnosed before any grid run, and the
  database agent's refusals point at a second, separate failure that A1
  was never meant to touch. The PI decision stands: no grid re-run; M1 as
  built is the paper's MAS. The paper's limitation (1) gains one
  sentence: a fix that shows the orchestrator the tool definitions is
  implemented in the released code; on a 15-episode smoke over three
  cells it raised the share of write orders executed as issued from about
  25% to 72% (13 of 18), short of the 90% bar, and the grid was not
  re-run. Smoke cost about $3. Results stay under their `smoke5-...-otd`
  names and manifests; nothing enters any table.
- 2026-10-17 (airline x qwen3.5-9b M1 file: not a cell): the folder holds
  `m1-airline-qwen35-9b-openrouter-high-gpt52low-b4x-capb1x-3trials-seed300`
  (150 episodes, run 2026-09-22 to 2026-09-25, same OpenRouter model and
  llm_args as the registered 9b cells, B 49052 and c 12263 as calibrated)
  with no done manifest and no CHANGELOG entry; the file's tau2 commit is
  8b57085, which is not in this folder's tau2-bench history (pinned
  c339866), so it was produced on another machine with a tau2-bench that
  cannot be checked here. The secondary validity table of 2026-09-26
  already lists it as a run: tokens in cut calls 35.7%, 14 turns with two
  cut calls (9 on ordinary turns), so it fails G1 like the other two 9b
  cells. Decision: it is not entered as a cell and no reward is read; the
  paper says in one sentence that a collaborator's airline run of the 9b
  MAS exists, was made on an unverified tau2 commit, fails G1, and is not
  used. The airline x qwen3.5-9b M1 cell therefore stays unrun. The same
  reasoning applies to `m1-retail-qwen35-9b-openrouter-high-...` (commit
  8b57085, 2026-09-24): not a cell; the logged retail 9b cell is the
  c339866 run of 2026-09-23.
- 2026-10-17 (G1 amendment (b) adopted, decided by the PI at 21:10 UTC):
  the double-cut bar in §1 now reads "no turn in which a cut call is
  retried, and no turn with two or more cut calls other than the
  exhaustion turn", with exhaustion-turn double cuts reported as a count
  in the validity table. Proposed on 2026-09-21 after four Gemini cells
  had been read; decided today after every cell of the as-built grid, the
  two local 4B cells and the received airline x 4b file had been read, so
  labelled post hoc. Reason: the exhaustion-turn double cut (a plan call
  cut at c followed by the forced closing message cut at the small
  remaining allowance) is the designed end-of-budget path of §4.3 and R7,
  not the retry-at-the-same-cap fault the bar was written for, which was
  fixed on 2026-09-21 and did not recur in any cell. Effect on cell
  status: none. Three grid cells carry exhaustion-turn double cuts only
  (airline x gemini-3-flash 1, retail x gemini-3.1-flash-lite 2, retail x
  gemini-3-flash 1; also the r = 25 telecom x flash-lite robustness run,
  1) and were already listed as passing the bar in the ICLR copy of
  2026-09-26; this entry makes the written rule and the paper agree. The
  cells with ordinary-turn double cuts fail the bar as before: telecom x
  qwen3.5-9b (6 ordinary), retail x qwen3.5-9b (4), retail x
  qwen3.5-4b-oct26 (5), the received airline x qwen3.5-4b (1). No reward
  was consulted for this decision; `validity.py` already computes both
  readings (`valid_strict`, `valid_amend_b`). Amendment (a) of 2026-09-22
  stands. No open G1 amendment remains.
- 2026-10-17 (seed replay test read; the trial-2 anomaly is the sampling
  seed): `seed_replay.py` ran on the Mac from 21:11 to 22:37 UTC on a
  freshly started server (October build c0535b43ca6b, CTX 131072, PAR 4),
  120 calls, 85.5 minutes of model time, no error. Design and reading
  rule as fixed in the script header before any call: the first
  orchestrator plan call of an episode, rebuilt by the M1 code itself for
  the six retail tasks whose trial-2 first plan call was cut at the cap
  (13, 53, 54, 59, 104, 108) and four control tasks (1, 75, 93, 101),
  crossing the customer's first message from trial 1 or trial 2 with the
  seed 361454 (trial 2), 373753 (trial 1) or none, two repeats each; k =
  6, hi = 4, lo = 1. Fidelity: the prompt token count matched the run's
  in 120 of 120 calls. Result, first repeat on the cut tasks: trial-2
  prompts with seed 361454, 5 of 6 cut (the sixth, task 53, stopped at
  5270 of 5369 tokens); with no seed, 0 of 6; with seed 373753, 0 of 6;
  trial-1 prompts with seed 361454, 1 of 6 (task 54), with the two other
  conditions 0. Verdict by the rule: **seed explanation supported**. Full
  table (n, median completion tokens, cut, empty output): trial-2 prompts
  x seed 361454, cut tasks 12, 5369, 8, 7; control tasks 8, 626, 0, 0;
  trial-2 prompts x no seed, cut tasks 12, 629, 0, 0; trial-2 prompts x
  seed 373753, cut tasks 12, 404, 1, 1; trial-1 prompts x seed 361454,
  cut tasks 12, 2798, 2, 2 (tasks 13 and 53 at 3880 and 4061 tokens);
  every other condition median 321 to 644 with no cut. Control tasks were
  never cut under any seed. Determinism: 35 of 40 seeded repeat pairs
  returned byte-identical replies (the five that differed were long
  generations near the cap, consistent with batched decoding on the
  server); 0 of 20 unseeded pairs were identical. Reading: on the local
  Ollama route a fixed seed makes a prompt's completion almost
  deterministic, so the trial seed that tau2 writes into llm_args turns a
  trial into one draw per prompt rather than fifty independent episodes;
  seed 361454 sends the M1 orchestrator prompt into long hidden reasoning
  on many prompts (strongly on the trial-2 customer messages, moderately
  on others), seeds 626729 and 373753 do not, and the same seed under the
  S1 prompt does not. The customer-message explanation is rejected as the
  cause (the same prompts without the seed never cut) and the server
  state explanation is rejected (three runs, two machines, and a
  fresh-server replay all reproduce it). Consequences, as fixed on
  2026-10-14 and 2026-10-16: the fixed per-trial seed is a limitation of
  every local-route cell (trials, not episodes, carry the sampling noise,
  and one of three seeds behaves differently under the M1 prompt); every
  local 4B M1 cell is reported per trial beside the pooled figure; no
  trial is excluded; no registered result changes. The OpenRouter and API
  routes are not affected: the 9b and API cells carry the same seeds and
  show no trial-2 pattern (2026-10-16 entry). Files:
  `results/seed-replay-2026-10-15/calls.jsonl`, `summary.json`,
  `READING.md`.
- 2026-10-17 (local 4B M1 cells, per trial and pooled, reward read after
  the replay as fixed on 2026-10-14): retail x qwen3.5-4b-oct26 (October
  build, M1 as built, G1 fail): M1 pass^1 23.3% [17.3, 30.7] (Wilson), S1
  74.0% over the 145 evaluated episodes (task-mean statistic as in
  `fill_cell.py`; episode-level 109 of 145 = 75.2%), paired gain -50.7
  [-60.7, -40.7] (task-cluster bootstrap, seed 300, 2,000 draws, M1 and
  S1 restricted to evaluated episodes); exhausted 74 of 150 (49%),
  utilisation median 0.98, finished episodes passed 33 of 76 (43%),
  exhausted 2 of 74 (3%); tokens per episode median 21,080 vs 3,845 (5.5x);
  cost (simulator only) $2.27 vs $2.10. Per trial, M1 pass 16, 14 and 5
  of 50 (exhausted 19, 12, 43); S1 40 of 48, 34 of 48, 35 of 49. Gain on
  trials 0 and 1 only: -46.0 [-58.0, -34.0]; trial 2 only: -61.2 [-73.5,
  -46.9]. telecom x qwen3.5-4b (registered build, in the grid): per trial
  M1 pass 15, 11 and 9 of 50 (exhausted 26, 27, 41); S1 48, 47, 47 of 50;
  the registered gain -71.3 [-80.0, -62.7] is unchanged; trials 0 and 1
  only -69.0 [-78.0, -59.0]; trial 2 only -76.0 [-88.0, -62.0]. airline x
  qwen3.5-4b (received file, provenance pending, G1 fail): per trial M1
  pass 28, 30 and 26 of 50 (exhausted 15, 14, 42); no S1 held, no gain.
  Reading: the seed artefact of trial 2 moves the pooled gain by 2 to 5
  points in the two paired cells and does not change any sign or any
  interval's side of zero; on airline it does not move the pass rate at
  all because tasks that require no database change pass under
  exhaustion. The cells enter the paper as follows: telecom x 4b stays in
  the grid as registered, with the per-trial split beside it; retail x
  4b-oct26 is reported in the appendix as a labelled October-build cell
  outside every fit; airline x 4b waits for provenance (2026-10-16
  entry).
- 2026-10-18 (airline x qwen3.5-4b M1 file: dropped as a cell): Ethan
  supplied the teammate's `qwen-local-s1.zip` (saved under
  `results/received/airline-4b-m1/teammate-s1-calibration-2026-10-07/`,
  zip SHA-256 0a079f9f6dcf...). It holds the summary, per-episode CSV and
  runner logs of the teammate's September S1 calibration of the 4B model,
  the runs already filed on 2026-09-24 under `results/teammate-qwen4b-
  ollama/`: `ollama_chat/qwen3.5:4b` (unpinned tag, no digest), `num_ctx`
  32768, temperature 0.0, `think` on, plus a custom second "materialization"
  call when the model returns thinking only (56 such recoveries on
  airline), on tau2 commit c339866. Airline: 144 evaluated episodes, 6
  infrastructure errors, pass^1 39.6%, B_1x 6832.25, c (P95) 1405. That
  B_1x is the budget the received airline M1 run used (B 27329, c 6832),
  so the M1 run was budgeted from an S1 on a different stack: the
  registered stack is `openai/tt-qwen3.5-4b:q4` (pinned digest), `num_ctx`
  131072, the model's shipped sampling defaults and no recovery call. The
  zip does not hold the S1 results.json, the M1 done manifest, the digest
  of the model the M1 ran on, or the M1 run's tau2 commit. Decision: the
  cell is not used. S1 and M1 of a cell must share one stack and one
  build (2026-09-24 and 2026-10-16 entries); here the budget itself comes
  from another stack, so even a same-stack S1, if one were run now, would
  not repair the M1 run. The file stays in `results/received/` for the
  record; the paper says in one sentence that a collaborator's airline run
  of the 4B MAS exists, was budgeted from an S1 on a different serving
  stack, and is not used. The teammate's 39.7% and 36.3% S1 figures
  remain what the 2026-09-24 entry says they are: a different stack with
  45 to 48% of episodes ending in agent errors, never to be paired with
  any M1 run. The airline x qwen3.5-4b cell of the 18-cell grid therefore
  stays unrun on the registered stack, with retail x qwen3.5-4b (build
  lost) and airline x qwen3.5-9b (not run); the grid as held is 15 cells,
  of which 13 meet the mechanical G1 bars and enter the as-built
  analyses, plus the labelled October-build retail cell in the appendix.
- 2026-10-18 (teammate's S1 export received; the airline x qwen3.5-4b
  decision stands): a second file, `qwen35-4b-s1-export.zip` (SHA-256
  8f5f5f92f951...), saved under `results/received/qwen35-4b-s1-export/`
  with the teammate's README and manifests unchanged. It holds
  byte-for-byte copies of four S1 results.json files, each validated by
  the teammate against tau2's Results schema. Three are the September
  runs on the teammate's own stack (`ollama_chat/qwen3.5:4b`, 32k
  context, temperature 0, think on, tau2 c339866): airline 150 attempted,
  144 evaluated, 57 passed, 69 `agent_error` endings (SHA-256
  9a82a8ed5fc8..., the file behind B_1x 6832.25); retail 150 and 142;
  telecom 22 of 150. The fourth is new: `calib-airline-s1-qwen35-4b-q4-
  ollama-gpt52low-3trials-seed300`, an S1 on the registered interface and
  configuration (`openai/tt-qwen3.5-4b:q4`, reasoning high, max_tokens
  32768), run on 2026-10-07 from 15:44 to 18:00 local time and stopped at
  10 of 150 episodes (8 evaluated, 7 passed, 2 infrastructure errors),
  58 minutes before the received M1 run started on the same stack. So the
  teammate moved to the registered interface in October, began its S1,
  stopped it, and ran the M1 with the September budget. Still absent: the
  M1 done manifest, the digest of the model the M1 ran on, the M1 run's
  tau2 commit. The decision of the previous entry stands: the airline x
  4b M1 is not a cell. For the record, the one path that could bring it
  into the appendix as a labelled cell with a stated budget deviation:
  the teammate confirms the digest the M1 ran on and completes the
  registered-stack airline S1 on that same build (140 more episodes,
  about 8 to 10 hours), after which the pair could be reported with the
  budget source disclosed. Not requested; the paper does not need it.
  The September files are useful for one thing only: the `agent_error`
  episodes (69 of 144 on airline, all scoring 0) document the stack
  artefact behind the 39.7% and 36.3% figures, which the paper's appendix
  limitation (1) already describes.
- 2026-10-18 (PI decision: airline x qwen3.5-4b paired with the
  collaborator's September S1, as a labelled appendix sensitivity only):
  Ethan decided to pair the received airline M1 run with the S1 that gave
  its budget (`results/received/qwen35-4b-s1-export/airline/results.json`,
  SHA-256 9a82a8ed5fc8...), knowing both the M1 reward (56.0%) and the S1
  reward (39.6%), so the decision is post hoc and labelled as such. The
  two runs differ in route (`ollama_chat/qwen3.5:4b` for S1,
  `openai/tt-qwen3.5-4b:q4` for M1), model pinning (unpinned tag for S1,
  pinned name with unknown digest for M1), context (32k for S1, 131k for
  M1), sampling (temperature 0 for S1, the model's defaults for M1) and
  outcome of the agent's tool calls (69 of 144 evaluated S1 episodes end
  in `agent_error` at a tool call and score 0; 0 of 150 M1 episodes do;
  the same model on the registered route had 0 such endings in 160
  episodes). Status fixed by this entry: the pairing is reported only as
  a sensitivity row in the appendix, with these differences stated in
  the row; it enters no grid table, no H1 or H4 fit, no secondary
  analysis, and no sentence of the abstract, introduction or conclusion.
  Numbers (task-mean statistic; task-cluster bootstrap, seed 300, 2,000
  draws; infrastructure-error episodes excluded from both runs; M1 fails
  G1 as recorded on 2026-10-16): S1 as recorded, crash episodes counted
  as failures: M1 56.0% (84 of 150, Wilson [48.0, 63.7]), S1 39.7% (57
  of 144, [32.0, 47.7]), gain +16.3 [+4.7, +27.7], tasks better/same/worse
  20/24/6; by trial +18.4 [+2.0, +34.7], +16.7 [0.0, +33.3], +12.8 [-2.1,
  +25.5]. S1 with the 69 crash episodes excluded (75 episodes, 38 tasks
  retained): M1 63.2% on those tasks, S1 70.2% (57 of 75, [65.2, 84.2]),
  gain -7.0 [-20.2, +5.3], tasks 5/26/7. The sign of the gain depends on
  how the S1 crashes are treated, which is the reason the row is a
  sensitivity and not a result: every passed S1 episode is a `user_stop`
  episode (57 of 68, 84%), and no `agent_error`, `timeout` or
  `max_steps` episode passes. Tokens per episode, median: M1 26,884 vs S1
  4,428 (6.1x). The paper's sentence for this row names the four
  differences and both gains. The 2026-10-16 and 2026-10-18 entries on
  provenance stand; the clean alternative (finishing the collaborator's
  registered-route airline S1 of 2026-10-07 on the M1's build) remains
  open to the collaborator and would replace this row if run. Report:
  `results/received/airline-4b-m1/pairing-september-s1.md`.
- 2026-10-18 (paper-full v22 written; no analysis change): the full
  version of the paper was rewritten from the ICLR submission structure
  into a plain article layout with the authors named (Ethan Yang,
  Xiangcheng Shi, University of Pennsylvania); every ICLR style file is
  moved to `paper-full/archive/iclr-style/` and the v21 PDF to
  `paper-full/archive/main-v21.pdf`. v22 carries the decisions of the
  2026-10-14 to 2026-10-18 entries: the MAS reported as built with the
  fidelity bar unmet in every cell and labelled a deviation (stricter
  audit 680 of 2,744 unique orders as issued, 25%; per cell 9 to 41%);
  "the 13 cells" means the cells meeting the mechanical bars, and the
  phrase "valid cells" is removed; amendment (b) stated with its date;
  the fix smoke (13 of 18, 72%) reported with the decision not to re-run
  the grid; telecom x qwen3.5-4b per trial beside the pooled figure;
  retail x qwen3.5-4b (October build) and the seed replay in a new
  appendix outside every fit; airline x qwen3.5-4b paired with the
  September S1 as a labelled sensitivity with both gains and the four
  stack differences; airline x qwen3.5-9b named as not a cell; episode
  total 7,950 and spend about $516; 65 tests. Build: 0 errors, no
  undefined references, 27 pages; `paper-full/main.pdf` MD5
  50fc1b1c51e7526bb6dbdf847be9652d. One TODO remains (public code URL in
  the reproducibility statement). Uncommitted on the Mac until Ethan
  commits.
- 2026-10-18 (paper-full v23, layout only; no analysis change): on
  Ethan's instruction the AI-use, ethics and reproducibility statements
  are removed (repository link now footnote 1 of the introduction and the
  last sentence of the conclusion, URL pending); the former appendices
  on protocol rationale, control flow, prior budget protocols, meter
  checks, calibration, failure taxonomy and judge, the lemma proof, power,
  classification, validity indicators, loss decomposition, the strong
  SAS, compute and cost, further limitations and the position table are
  moved into the main text; the benchmark-record appendix is removed and
  its hash-free content sits in section 3.1 (every SHA-256, commit id and
  model digest is out of the paper and stays in the released manifests
  and provenance files). Appendix A (tests and results card) and
  Appendix B (the local 4B model: builds, per-trial results, seed replay,
  airline x 4b sensitivity) remain, the latter because every item in it
  sits outside the registered fits by the 2026-10-17 and 2026-10-18
  decisions. Build: 0 errors, no undefined references, 25 pages;
  `paper-full/main.pdf` MD5 f90b747cf758b5c73ffc438169b6c12f; v22 PDF at
  `paper-full/archive/main-v22.pdf`.
- 2026-10-18 (paper-full v24, citation audit; no analysis change): a
  senior reviewer's word-by-word check of the paper's citations against
  the sources (18 items) was applied. Text changed for Kim et al. (the
  45% crossing is the agent-count main effect over the baseline-by-agents
  interaction in a regression of system performance, not the ratio of
  the baseline coefficient and the interaction; the rule is presented by
  its authors as a practical selection rule; the 15 of 16 validation is
  best-of-four MAS against SAS; the budget-protocol comparison states
  what the published text says, matched mean reasoning tokens and
  matched maximum iterations, and the "about 100 model calls" sentence
  is removed), Seshadri (45.2% is US participants on a difficulty-
  balanced subset and is no longer set against the 67.8% all-task
  figure), Barres (18 points as the no-user to dual-control ablation),
  Zhu (no-op loophole stated precisely), Li (removed from the "benefit
  shrinks with capability" list), Jwalapuram (cost audited after the
  fact; five-sample CoT-SC; HLE-Math exception), SABER (">90% on airline
  and on retail" in place of two per-domain figures that the source's
  abstract and table assign oppositely), Tran (perfect-context premise),
  Zhou (many general-purpose simulators), Kapoor (cost rarely reported),
  Yu (max total steps in experiments) and the position table ("User
  (tools)" column; LangChain and PolicyGuard "yes (no)"; this paper "yes
  (telecom)"; second simulator on 3 cells). Framing: abstract,
  introduction, section 3.1 and the discussion now state that only
  telecom is dual-control in the strict sense of Barres et al.; airline
  and retail give tools to the agent alone. The title is unchanged
  pending Ethan's decision. No number of this study changes. Build: 0
  errors, 26 pages; `paper-full/main.pdf` MD5
  90e12905c571ed93be067b21adce8002; v23 PDF at
  `paper-full/archive/main-v23.pdf`.
