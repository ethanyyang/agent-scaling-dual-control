#!/usr/bin/env bash
# ============================================================
# Setup for agent-scaling-dual-control (SAS vs centralized MAS on tau2-bench)
# Run from the repository root:   bash setup.sh
# Safe to re-run — every step is idempotent.
# ============================================================
set -euo pipefail

# Pin the exact tau2-bench commit this project's results are based on.
# (v1.0.1 — July 2026 grading update. Results across versions are NOT comparable.)
TAU2_COMMIT="c3398666e6559e3a063da3fc04b5acf7f941464e"

echo "==> [1/7] Checking Python >= 3.12"
if command -v python3 >/dev/null && python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)'; then
  echo "    OK: $(python3 --version)"
else
  echo "    ERROR: Python 3.12+ required. Install it first (e.g. from python.org or 'brew install python@3.12')."
  exit 1
fi

echo "==> [2/7] Installing uv (if missing)"
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
echo "    OK: $(uv --version)"

echo "==> [3/7] Cloning tau2-bench (pinned to ${TAU2_COMMIT:0:12})"
if [ ! -d tau2-bench ]; then
  git clone https://github.com/sierra-research/tau2-bench.git
fi
cd tau2-bench
git fetch --all --quiet
git checkout --quiet "$TAU2_COMMIT"
echo "    OK: pinned at $(git rev-parse --short HEAD)"

echo "==> [4/7] Installing dependencies (core only — no voice/knowledge extras)"
uv sync
echo "    OK"

echo "==> [5/7] Setting up .env"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "    Created .env — EDIT IT NOW and add your API key(s):"
  echo "      OPENAI_API_KEY, GEMINI_API_KEY and, for the 9b route, OPENROUTER_API_KEY (LiteLLM names)"
else
  echo "    .env already exists, leaving it alone"
fi
cd ..

echo "==> [6/7] Linking released trajectories into tau2-bench/data/simulations"
# data/download.sh unpacks the Zenodo archives into data/simulations/<run>/results.json.
# Every analysis script reads tau2-bench/data/simulations/<run>/results.json, so link them.
mkdir -p data/simulations tau2-bench/data/simulations
linked=0
for run in data/simulations/*/; do
  [ -d "$run" ] || continue
  name=$(basename "$run")
  if [ ! -e "tau2-bench/data/simulations/$name" ]; then
    ln -s "../../../data/simulations/$name" "tau2-bench/data/simulations/$name"
    linked=$((linked+1))
  fi
done
echo "    OK: $linked run folders linked (run data/download.sh first if this is 0)"

echo "==> [7/7] Recording provenance"
{
  echo "date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "tau2-bench commit: $TAU2_COMMIT (v1.0.1)"
  echo "python: $(python3 --version)"
  echo "uv: $(uv --version)"
} > PROVENANCE.txt
cat PROVENANCE.txt

echo ""
echo "============================================================"
echo "Setup complete. Next:"
echo "  1. Edit tau2-bench/.env with your API key"
echo "  2. Smoke test (5 tasks, ~\$0.50):"
echo "     cd tau2-bench && uv run tau2 run --domain retail \\"
echo "        --agent-llm gpt-4.1-mini --user-llm gpt-4.1-mini \\"
echo "        --num-trials 1 --num-tasks 5"
echo "  3. Offline tests (no API calls):  cd tau2-bench && uv run python -m pytest ../tests -q"
echo "  4. Trajectories: bash data/download.sh, then re-run this script to link them."
echo "  5. README.md lists the command behind every table and figure."
echo "============================================================"
