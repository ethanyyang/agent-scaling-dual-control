# Derived results

Small files that the paper's tables and figures are read from. Every one of them is reproducible from the trajectories (`data/`) with the scripts at the repository root and in `analysis/`; the top-level README maps each table and figure to its command.

- `calibration-manifests/`: one JSON per run we launched (cell, budget values, snapshot, seed, task-id hash, prompt hashes, benchmark commit, episodes, infrastructure errors, SHA-256 of the results file).
- `h1/`: per-episode rewards, per-cell table, the H1 fit, sensitivities and bootstrap draws (`h1_extract.py`, `h1_analysis.py`, `h1_sensitivity.py`).
- `h4/`: the failure taxonomy per episode, the H2 fits, the assertion-judge outputs for the airline cells and the FP counts (`h4_extract.py`, `h4_analysis.py`, `nl_screen.py`, `h4_fp.py`).
- `secondary-2026-09-26/`: validity indicators, the stricter write-order audit, the loss decomposition, H6 and the 12-cell power re-run; scripts and outputs together.
- `m1-retail-4b-oct26/`: validity, write-order counts, per-trial script and the evaluated-episode list of the October-build retail qwen3.5-4b pair.
- `seed-replay-2026-10-15/`: the design, calls and reading of the local-route seed replay (`seed_replay.py`).
- `canonical-refit/`: the refit of Kim et al.'s 260-configuration regression from their released data (`canonical_refit.py`).
- `judge-read-packet/`: episode excerpts prepared for hand adjudication (flagged passes, random unflagged passes, failures, revert candidates).
- `gate-airline-sas-gemini3flash-high-gpt52low-3trials-seed300/`, `exploratory-airline-sas-gpt41mini-full-3trials-seed300/`: per-episode tables, the assertion screens and notes of the reproduction gate and the pilot (`power_sim.py` reads both).
- `teammate-qwen9b/`, `teammate-qwen4b-ollama/`, `received/`: files produced by a collaborator (see `COLLABORATOR-RUNS.md`).
