# airline x qwen3.5-4b: M1 (received) paired with the collaborator's September S1, as a sensitivity

Decision: Ethan, 2026-10-18, after both rewards were known (post hoc). Appendix sensitivity row only; not in any
grid table, fit, secondary analysis, abstract, introduction or conclusion (ANALYSIS.md CHANGELOG 2026-10-18).

Files: M1 `results/received/airline-4b-m1/results.json` (SHA-256 153f9b2dcf64...; G1 fail: cut tokens 12.9%, 4 double-cut
turns, write orders 33% as issued); S1 `results/received/qwen35-4b-s1-export/airline/results.json` (SHA-256 9a82a8ed5fc8...).

| | S1 (collaborator, Sep 20-23) | M1 (collaborator, Oct 7-12) |
|---|---|---|
| route | `ollama_chat/qwen3.5:4b` | `openai/tt-qwen3.5-4b:q4` |
| model pinning | unpinned tag, no digest | pinned name, digest unknown |
| context | 32,768 | 131,072 |
| sampling | temperature 0 | model defaults |
| episodes ending in `agent_error` (score 0) | 69 of 144 evaluated | 0 of 150 |

Statistic: task-mean pass^1; paired gain per task; task-cluster bootstrap, seed 300, 2,000 draws; infrastructure-error
episodes excluded from both runs (S1 6, M1 0).

| pairing | tasks | M1 | S1 | gain [95% CI] | tasks better / same / worse |
|---|---:|---:|---:|---:|---|
| S1 as recorded (crashes count as failures) | 50 | 56.0% (84/150) | 39.7% (57/144) | +16.3 [+4.7, +27.7] | 20 / 24 / 6 |
| S1 crash episodes excluded (75 episodes) | 38 | 63.2% (on those tasks) | 70.2% (57/75) | -7.0 [-20.2, +5.3] | 5 / 26 / 7 |
| by trial, S1 as recorded: trial 0 | 49 | 57.1% | 38.8% | +18.4 [+2.0, +34.7] | 13 / 32 / 4 |
| trial 1 | 48 | 58.3% | 41.7% | +16.7 [0.0, +33.3] | 12 / 32 / 4 |
| trial 2 | 47 | 51.1% | 38.3% | +12.8 [-2.1, +25.5] | 9 / 35 / 3 |

S1 pass by ending: `user_stop` 57 of 68; `agent_error` 0 of 69; `timeout` 0 of 5; `max_steps` 0 of 2.
Tokens per episode, median: M1 26,884 vs S1 4,428 (6.1x). Simulator cost: M1 $2.77, S1 $1.21.

Reading: the sign of the gain depends on how the S1 crash episodes are treated, so this row is a sensitivity, not a
result. The clean version is the collaborator's registered-route airline S1 of 2026-10-07 completed to 150 episodes on
the M1's build; it would replace this row.
