# Judge-validity reading packet (§6.6) + revert candidates (§6.8)

Generated 2026-08-29. Random draws: `random.Random(20260829).sample(...)`, pools sorted for display.

Verdict per episode: **confirmed / not confirmed / ambiguous-omission (hand-adjudicate)** — record in each file, then tally below.


## Pool 1 — all 12 judge-flagged passes (gate run)

*Question answered: judge precision — is each flagged violation real?*

- [ ] [task 8, trial 0](pool1-flagged-task8-trial0.md)
- [ ] [task 2, trial 0](pool1-flagged-task2-trial0.md)
- [ ] [task 38, trial 0](pool1-flagged-task38-trial0.md)
- [ ] [task 2, trial 1](pool1-flagged-task2-trial1.md)
- [ ] [task 27, trial 1](pool1-flagged-task27-trial1.md)
- [ ] [task 38, trial 1](pool1-flagged-task38-trial1.md)
- [ ] [task 2, trial 2](pool1-flagged-task2-trial2.md)
- [ ] [task 3, trial 2](pool1-flagged-task3-trial2.md)
- [ ] [task 9, trial 2](pool1-flagged-task9-trial2.md)
- [ ] [task 4, trial 2](pool1-flagged-task4-trial2.md)
- [ ] [task 27, trial 2](pool1-flagged-task27-trial2.md)
- [ ] [task 38, trial 2](pool1-flagged-task38-trial2.md)

## Pool 2 — 5 random unflagged passes (gate run, seed 20260829)

*Question answered: false negatives — did the judge miss violations?*

- [ ] [task 12, trial 1](pool2-random-unflagged-task12-trial1.md)
- [ ] [task 13, trial 2](pool2-random-unflagged-task13-trial2.md)
- [ ] [task 18, trial 2](pool2-random-unflagged-task18-trial2.md)
- [ ] [task 20, trial 2](pool2-random-unflagged-task20-trial2.md)
- [ ] [task 26, trial 1](pool2-random-unflagged-task26-trial1.md)

## Pool 3 — 5 random failures (gate run, seed 20260829)

*Question answered: sanity — does the judge behave sensibly on known-bad episodes?*

- [ ] [task 14, trial 0](pool3-failures-task14-trial0.md)
- [ ] [task 14, trial 2](pool3-failures-task14-trial2.md)
- [ ] [task 20, trial 0](pool3-failures-task20-trial0.md)
- [ ] [task 29, trial 0](pool3-failures-task29-trial0.md)
- [ ] [task 32, trial 2](pool3-failures-task32-trial2.md)

## Revert candidates — pilot run (§6.8)

*Question answered: write-then-revert invisible to the DB hash?*

- [ ] [task 34, trial 0](revert-candidates-task34-trial0.md)
- [ ] [task 0, trial 2](revert-candidates-task0-trial2.md)
- [ ] [task 45, trial 2](revert-candidates-task45-trial2.md)

## Tally (fill after reading)

| Pool | Read | Confirmed | Not confirmed | Ambiguous |
|---|---|---|---|---|
| 1 (flagged) | /12 | | | |
| 2 (random unflagged) | /5 | | | |
| 3 (failures) | /5 | | | |
| Revert candidates | /3 | | | |


Record the sampling frames + tally into ANALYSIS.md §6.6 (and §6.8 for the revert candidates) before the freeze.
