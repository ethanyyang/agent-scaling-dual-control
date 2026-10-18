#!/usr/bin/env bash
# A1 re-run of the 12 API grid cells (ANALYSIS.md CHANGELOG 2026-10-12): M1 with the orchestrator seeing the
# tool definitions (tool_choice none), k = 4, c = B_1x, r = 4, 3 trials, seed 300. Run names carry -otd.
# Refuses to launch unless results/a1-smoke-gate.json says pass (written by a1_gate.py).
#   bash scripts/a1_grid.sh            # launch four processes, one per model (three domains each, in sequence)
#   bash scripts/a1_grid.sh --dry-run  # print the 12 run names only
#   touch STOP_M1                      # finish the running cell, start no new one; rm STOP_M1 to continue
# Relaunching is safe: finished cells are skipped, cells with infrastructure errors are resumed.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
GATE="$ROOT/results/a1-smoke-gate.json"
LOGS="$ROOT/results/calibration-manifests"
if [ "${1:-}" != "--dry-run" ]; then
  [ -f "$GATE" ] || { echo "no gate file: run the smokes (scripts/a1_smokes.sh) and read them (python3 a1_gate.py) first"; exit 3; }
  python3 -c "import json,sys; g=json.load(open('$GATE')); sys.exit(0 if g.get('pass') else 1)" \
    || { echo "gate file says FAIL (read at $(python3 -c "import json;print(json.load(open('$GATE'))['read_at_utc'])")): diagnose before anything else runs"; exit 3; }
  [ -f STOP_M1 ] && { echo "STOP_M1 is present; remove it to launch"; exit 4; }
  [ -f tau2-bench/.env ] || { echo "tau2-bench/.env with the API keys is missing"; exit 2; }
fi
MODELS=("google/gemini-3.1-flash-lite" "google/gemini-3-flash" "openai-gpt5/gpt-5-nano" "openai-gpt5/gpt-5-mini")
TAGS=("gemini31flashlite" "gemini3flash" "gpt5nano" "gpt5mini")
cd tau2-bench
if [ "${1:-}" = "--dry-run" ]; then
  for m in "${MODELS[@]}"; do uv run python ../run_m1.py --condition m1 --orch-tool-defs --only "$m" --dry-run 2>/dev/null | grep "dry-run" || true; done
  exit 0
fi
python3 - <<PY
import json, subprocess, datetime as dt
rec = dict(launched_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), gate_read_at=json.load(open("$GATE"))["read_at_utc"],
           commit=subprocess.check_output(["git", "-C", "$ROOT", "rev-parse", "--short", "HEAD"]).decode().strip(), models=${MODELS[@]+'"${MODELS[*]}"'}.split())
json.dump(rec, open("$ROOT/results/a1-grid-launch.json", "w"), indent=1); print("launch record -> results/a1-grid-launch.json")
PY
for i in 0 1 2 3; do
  nohup uv run python ../run_m1.py --condition m1 --orch-tool-defs --only "${MODELS[$i]}" > "$LOGS/launch-a1-${TAGS[$i]}.log" 2>&1 &
  echo "launched ${MODELS[$i]} (pid $!) -> results/calibration-manifests/launch-a1-${TAGS[$i]}.log"
done
echo "progress: grep -h 'Status:' results/calibration-manifests/launch-a1-*.log | tail -4"
