#!/usr/bin/env bash
# A1 smokes (ANALYSIS.md CHANGELOG 2026-10-12): three cells, 5 tasks x 1 trial, orchestrator with tool
# definitions (tool_choice none). Run from the transfer-testing folder on the Mac:
#   bash scripts/a1_smokes.sh            # launch the three smokes in the background
#   bash scripts/a1_smokes.sh --dry-run  # print the run names only
# Then read them in the fixed order and write the gate file:
#   python3 a1_gate.py
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
LOGS="$ROOT/results/calibration-manifests"
mkdir -p "$LOGS"
[ -f tau2-bench/.env ] || { echo "tau2-bench/.env with the API keys is missing"; exit 2; }
CELLS=("google/gemini-3-flash/telecom" "openai-gpt5/gpt-5-mini/retail" "openai-gpt5/gpt-5-nano/airline")
TAGS=("telecom-3flash" "retail-mini" "airline-nano")
cd tau2-bench
for i in 0 1 2; do
  if [ "${1:-}" = "--dry-run" ]; then
    uv run python ../run_m1.py --condition m1 --orch-tool-defs --only "${CELLS[$i]}" --smoke 5 --num-trials 1 --dry-run 2>/dev/null | grep "dry-run" || true
  else
    nohup uv run python ../run_m1.py --condition m1 --orch-tool-defs --only "${CELLS[$i]}" --smoke 5 --num-trials 1 \
      > "$LOGS/smoke5-a1-${TAGS[$i]}.log" 2>&1 &
    echo "launched ${CELLS[$i]} (pid $!) -> results/calibration-manifests/smoke5-a1-${TAGS[$i]}.log"
  fi
done
[ "${1:-}" = "--dry-run" ] || echo "When all three logs end with 'done': python3 a1_gate.py"
