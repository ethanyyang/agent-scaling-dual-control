# Seed replay test: reading (2026-10-17, 22:50 UTC)

Run: 2026-10-17 21:11 to 22:37 UTC, Mac, fresh Ollama server (October build c0535b43ca6b, CTX 131072, PAR 4), 120 calls, 85.5 min of model time, 0 errors. Prompt tokens matched the run in 120 of 120 calls.

Rule (fixed in `seed_replay.py` before any call): k = 6 cut tasks (13, 53, 54, 59, 104, 108), hi = 4, lo = 1; first-repeat cuts on the cut tasks.

| condition | cut tasks: cut on first repeat | all calls on cut tasks: n / median tokens / cut / empty |
|---|---:|---|
| trial-2 prompt, seed 361454 | 5 of 6 | 12 / 5369 / 8 / 7 |
| trial-2 prompt, seed 373753 | 0 of 6 | 12 / 404 / 1 / 1 |
| trial-2 prompt, no seed | 0 of 6 | 12 / 629 / 0 / 0 |
| trial-1 prompt, seed 361454 | 1 of 6 | 12 / 2798 / 2 / 2 |
| trial-1 prompt, seed 373753 | 0 of 6 | 12 / 371 / 0 / 0 |
| trial-1 prompt, no seed | 0 of 6 | 12 / 538 / 0 / 0 |

Control tasks (1, 75, 93, 101): never cut under any condition (medians 321 to 644).

Verdict: **seed explanation supported**. Determinism: 35 of 40 seeded repeat pairs byte-identical; 0 of 20 unseeded pairs identical.

Consequences (fixed in the ANALYSIS.md CHANGELOG, 2026-10-14, 2026-10-16, 2026-10-17): every local 4B M1 cell is reported per trial beside the pooled figure; no trial is excluded; the fixed per-trial seed is a limitation of the local route; no registered result changes.
