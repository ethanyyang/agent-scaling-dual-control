#!/usr/bin/env bash
# The local October-build cell, telecom x qwen3.5-4b-oct26, step by step on the Mac. One step per call;
# read the result of each step before the next (ANALYSIS.md CHANGELOG 2026-10-16). Ollama serves one job
# at a time, so these steps and the seed replay share the Mac and must not overlap.
#   bash scripts/a1_qwen.sh replay     # seed replay test: dry run only (rebuilds the prompts, no model call)
#   bash scripts/a1_qwen.sh replay-go  # seed replay test, about 1 to 2 hours
#   bash scripts/a1_qwen.sh s1       # S1 on the October build, 150 episodes (about 8 hours alone)
#   bash scripts/a1_qwen.sh budget   # calibration entry from that S1 (a1_qwen_budget.py --write)
#   bash scripts/a1_qwen.sh smoke    # A1 M1 smoke, 5 tasks x 1 trial; read with: python3 a1_gate.py --runs <name>
#   bash scripts/a1_qwen.sh full     # A1 M1 cell, 150 episodes (about 30 hours)
#   bash scripts/a1_qwen.sh status   # what exists
# Every step starts the server with serve_only.sh, which exits 6 (WRONG BUILD) unless the pinned tag is
# the October build c0535b43ca6b; nothing runs in that case.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"; LOGS="$ROOT/results/calibration-manifests"; mkdir -p "$LOGS"
STEP="${1:-status}"
S1="local-telecom-s1-qwen35-4b-q4-ollama-gpt52low-3trials-seed300"
SMOKE="smoke5-m1-telecom-qwen35-4b-q4-oct26-ollama-gpt52low-b4x-capb1x-otd-1trials-seed300"
FULL="m1-telecom-qwen35-4b-q4-oct26-ollama-gpt52low-b4x-capb1x-otd-3trials-seed300"
have() { [ -f "tau2-bench/data/simulations/$1/results.json" ]; }
count() { python3 -c "import json,sys;print(len(json.load(open('tau2-bench/data/simulations/$1/results.json'))['simulations']))" 2>/dev/null || echo 0; }
server() { bash ollama/serve_only.sh || { echo "server check failed (exit $?); nothing launched"; exit 6; }; }
case "$STEP" in
  status)
    if [ -f results/seed-replay-2026-10-15/summary.json ]; then echo "replay: done (results/seed-replay-2026-10-15/summary.json)";
    elif [ -f results/seed-replay-2026-10-15/calls.jsonl ]; then echo "replay: in progress, $(wc -l < results/seed-replay-2026-10-15/calls.jsonl) calls";
    else echo "replay: not run"; fi
    echo "S1 oct26 telecom: $(have $S1 && echo "$(count $S1)/150 episodes" || echo "not run")"
    echo "budgets.json entry: $(python3 -c "import json;print('present' if 'telecom x qwen3.5-4b-oct26' in json.load(open('budgets.json'))['cells'] else 'missing')")"
    echo "A1 smoke: $(have $SMOKE && echo "$(count $SMOKE)/5 episodes" || echo "not run")"
    echo "A1 full: $(have $FULL && echo "$(count $FULL)/150 episodes" || echo "not run")"
    ps aux | grep -E "run_m1\.py|run_local_s1\.py|seed_replay\.py" | grep -v grep || echo "no run process alive" ;;
  replay)
    server; cd tau2-bench
    uv run python ../seed_replay.py --dry-run 2>&1 | grep -v "DEBUG\|INFO\|WARNING" | tail -16
    echo "dry run only. If the prompt sizes and caps match the run, launch with: bash scripts/a1_qwen.sh replay-go" ;;
  replay-go)
    server; cd tau2-bench
    nohup uv run python ../seed_replay.py > "$LOGS/seed-replay.log" 2>&1 &
    echo "launched seed_replay.py (pid $!) -> results/calibration-manifests/seed-replay.log; summary in results/seed-replay-2026-10-15/summary.json" ;;
  s1)
    server
    nohup python3 ollama/run_local_s1.py --domain telecom --full > "$LOGS/launch-s1-telecom-4b-oct26.log" 2>&1 &
    echo "launched S1 telecom on the October build (pid $!) -> results/calibration-manifests/launch-s1-telecom-4b-oct26.log" ;;
  budget)
    python3 a1_qwen_budget.py --write ;;
  smoke)
    server; cd tau2-bench
    nohup uv run python ../run_m1.py --condition m1 --orch-tool-defs --only qwen/qwen3.5-4b-oct26/telecom --smoke 5 --num-trials 1 \
      > "$LOGS/smoke5-a1-telecom-4b-oct26.log" 2>&1 &
    echo "launched (pid $!) -> results/calibration-manifests/smoke5-a1-telecom-4b-oct26.log; read with: python3 a1_gate.py --runs $SMOKE" ;;
  full)
    server; cd tau2-bench
    nohup uv run python ../run_m1.py --condition m1 --orch-tool-defs --only qwen/qwen3.5-4b-oct26/telecom \
      > "$LOGS/launch-a1-telecom-4b-oct26.log" 2>&1 &
    echo "launched (pid $!) -> results/calibration-manifests/launch-a1-telecom-4b-oct26.log" ;;
  *) echo "unknown step $STEP"; exit 2 ;;
esac
