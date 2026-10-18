#!/usr/bin/env bash
# Re-run the registered analyses on the A1 grid (M1 runs with -otd), no new agent runs except the small
# airline FP judge pass (gpt-4.1, passing episodes only). Outputs go to results/h1-otd, results/h4-otd and
# results/a1-cells/; the as-built results in results/h1 and results/h4 are not touched.
#   bash scripts/a1_analyses.sh check   # which of the 12 A1 cells are finished (manifest rc 0, 0 infrastructure errors)
#   bash scripts/a1_analyses.sh run     # everything below, in order; stops at the first missing cell
#   bash scripts/a1_analyses.sh fp      # only the airline judge pass + h4_fp (needs the API key; about 600 episodes)
# Order: validity bars and write-order audit (a1_gate.py --runs, reward printed last) -> per-cell report
# (cell_report.py, paired gain) -> H1 (h1_extract, h1_analysis) -> H2/H4 (h4_extract, h4_analysis, judge pass,
# h4_fp). The secondary scripts (loss decomposition, H6, H7, power, per-task counts; results/secondary-2026-09-26)
# are run afterwards from the analysis session with TT_M1_VARIANT=otd.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
export TT_M1_VARIANT=otd
STEP="${1:-check}"
RUNS=$(python3 - <<'PY'
from h1_extract import cells
for *_, m1 in cells(): print(m1.parent.name)
PY
)
check() {
  local ok=0 n=0
  for r in $RUNS; do
    n=$((n+1)); m="results/calibration-manifests/$r.json"
    if [ -f "$m" ] && python3 -c "import json,sys;d=json.load(open('$m'));sys.exit(0 if d.get('return_code')==0 and d.get('infrastructure_errors')==0 else 1)"; then
      ok=$((ok+1)); echo "done     $r"
    else
      ep=$(python3 -c "import json;print(len(json.load(open('tau2-bench/data/simulations/$r/results.json'))['simulations']))" 2>/dev/null || echo 0)
      echo "pending  $r ($ep/150 episodes)"
    fi
  done
  echo "$ok of $n A1 cells finished"
  [ "$ok" = "$n" ]
}
case "$STEP" in
  check) check ;;
  run)
    check || { echo "not all 12 cells are finished; stopping"; exit 3; }
    mkdir -p results/a1-cells
    echo "== 1. validity bars and write-order audit (reward printed last)"
    python3 a1_gate.py --runs $RUNS | tee results/a1-cells/validity.txt
    echo "== 2. per-cell report (M1 vs S1, paired gain)"
    python3 - <<'PY' | tee results/a1-cells/cell_report.txt
import subprocess
from h1_extract import cells
for *_, s1, m1 in cells():
    subprocess.run(["python3", "cell_report.py", m1.parent.name, str(s1)], check=True)
PY
    echo "== 3. H1"
    python3 h1_extract.py && python3 h1_analysis.py results/h1-otd/per_episode.csv
    echo "== 4. H2 (H4 in the plan): taxonomy"
    python3 h4_extract.py && python3 h4_analysis.py results/h4-otd/taxonomy_per_episode.csv
    echo "== 5. H2: airline FP judge pass and h4_fp"
    bash "$0" fp
    echo "done. Reports: results/h1-otd/h1_report.md, results/h4-otd/h4_report.md, results/h4-otd/h4_fp.md, results/a1-cells/" ;;
  fp)
    mkdir -p results/h4-otd/nl_screen
    for s in results/h4/nl_screen/calib-airline-s1-*.json; do cp -n "$s" results/h4-otd/nl_screen/ 2>/dev/null || true; done
    for r in $RUNS; do
      case "$r" in m1-airline-*) ;; *) continue ;; esac
      out="results/h4-otd/nl_screen/$r.json"
      [ -f "$out" ] && { echo "screen exists: $out"; continue; }
      tau2-bench/.venv/bin/python nl_screen.py "tau2-bench/data/simulations/$r/results.json" --out "$out"
    done
    python3 h4_fp.py ;;
  *) echo "unknown step $STEP"; exit 2 ;;
esac
