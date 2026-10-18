# A1 pipeline scripts (set up 2026-10-16; ANALYSIS.md CHANGELOG 2026-10-12 and 2026-10-16)

Run everything from the transfer-testing folder on the Mac. Nothing here changes agent code or prompts;
the A1 fix itself is `m1_agent.py` (`orchestrator_tool_definitions`) and `run_m1.py --orch-tool-defs`.

| Step | Command | What it does |
|---|---|---|
| 1 | `bash scripts/a1_qwen.sh replay`, then `replay-go` | Seed replay test on the Mac (seed_replay.py). Dry run first. |
| 2 | `bash scripts/a1_smokes.sh`, then `python3 a1_gate.py` | Three A1 smokes (5 tasks x 1 trial), read in the fixed order; writes `results/a1-smoke-gate.json`. |
| 3 | `bash scripts/a1_grid.sh` | The 12 API cells with `--orch-tool-defs`, four processes. Refuses without a passing gate file. |
| 4 | `bash scripts/a1_qwen.sh s1`, `budget`, `smoke`, `full` | The local October-build cell: S1 on the same build, its calibration entry, the A1 smoke, the A1 cell. One step at a time. |
| 5 | `bash scripts/a1_analyses.sh check`, then `run` | Validity, per-cell report, H1, H2 (H4) on the A1 grid; outputs in `results/h1-otd`, `results/h4-otd`, `results/a1-cells`. |

Steps 1 and 4 share the Mac's Ollama server and must not overlap; steps 2, 3 and 5 use the API and can
run alongside them. `touch STOP_M1` stops the grid after the running cell. Relaunching `a1_grid.sh` resumes.
Progress: `grep -h 'Status:' results/calibration-manifests/launch-a1-*.log | tail -4`.
