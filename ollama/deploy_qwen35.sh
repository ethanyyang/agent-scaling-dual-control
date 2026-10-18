#!/usr/bin/env bash
# Deploy a small dense Qwen3.5 model on this Mac with Ollama, for the threshold-transfer study.
#
#   bash ollama/deploy_qwen35.sh 2b            # qwen3.5:2b   (Q4_K_M)
#   bash ollama/deploy_qwen35.sh 0.8b          # qwen3.5:0.8b (Q4_K_M)
#   bash ollama/deploy_qwen35.sh 4b bf16       # qwen3.5:4b-bf16
#
# Same steps and same server settings as deploy_qwen35_4b.sh (which it generalises): fixed
# context length, pinned model name, provenance file, and the two checks. Safe to re-run.
# The server keeps one model loaded at a time, so run pilots one size after another.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"
OUT="$ROOT/ollama"
SIZE="${1:-}"
PREC="${2:-q4}"
case "$SIZE" in
  0.8b|2b|4b|9b) ;;
  *) echo "usage: $0 <0.8b|2b|4b|9b> [q4|bf16]"; exit 2 ;;
esac
case "$PREC" in
  q4)   BASE="qwen3.5:$SIZE" ;;
  bf16) BASE="qwen3.5:$SIZE-bf16" ;;
  *) echo "usage: $0 <0.8b|2b|4b|9b> [q4|bf16]"; exit 2 ;;
esac
NAME="tt-qwen3.5-$SIZE:$PREC"
VARIANT="$SIZE-$PREC"
CTX="${CTX:-131072}"
LOG="$OUT/deploy-$VARIANT.log"
exec > >(tee -a "$LOG") 2>&1

echo "=================================================================="
echo "deploy $NAME  (base $BASE)   $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "=================================================================="

# ---- 1. machine ----------------------------------------------------------
if [ "$(uname -s)" != "Darwin" ]; then
  echo "This script is written for macOS. Stop."; exit 2
fi
RAM_GB=$(( $(sysctl -n hw.memsize) / 1073741824 ))
CHIP="$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo unknown)"
FREE_GB="$(df -g "$HOME" | awk 'NR==2{print $4}')"
echo "chip: $CHIP | RAM: ${RAM_GB} GB | macOS $(sw_vers -productVersion) | free disk: ${FREE_GB} GB"

if [ -z "${PAR:-}" ]; then
  if [ "$PREC" = "bf16" ]; then
    if [ "$RAM_GB" -ge 64 ]; then PAR=4; elif [ "$RAM_GB" -ge 32 ]; then PAR=2; else PAR=1; fi
  else
    if [ "$RAM_GB" -ge 32 ]; then PAR=4; elif [ "$RAM_GB" -ge 16 ]; then PAR=2; else PAR=1; fi
  fi
fi
echo "context length: $CTX tokens per request | parallel requests: $PAR"
if [ "$PREC" = "bf16" ] && [ "$SIZE" != "0.8b" ] && [ "$RAM_GB" -lt 24 ]; then
  echo "WARNING: BF16 weights are large (9.3 GB for 4b). With ${RAM_GB} GB RAM the model may spill to CPU."
  echo "         Check 5 below tells you. If it fails, use the q4 variant."
fi
if [ "${FREE_GB:-0}" -lt 15 ]; then
  echo "WARNING: less than 15 GB free disk."
fi

# ---- 2. ollama binary ----------------------------------------------------
find_ollama() {
  if command -v ollama >/dev/null 2>&1; then command -v ollama; return 0; fi
  for p in /Applications/Ollama.app/Contents/Resources/ollama \
           "$HOME/Applications/Ollama.app/Contents/Resources/ollama" \
           /opt/homebrew/bin/ollama /usr/local/bin/ollama "$HOME/.homebrew/bin/ollama"; do
    if [ -x "$p" ]; then echo "$p"; return 0; fi
  done
  return 1
}
OLLAMA="$(find_ollama || true)"
if [ -z "$OLLAMA" ]; then
  if command -v brew >/dev/null 2>&1; then
    echo "Ollama not found. Installing with Homebrew: brew install ollama"
    brew install ollama || { echo "brew install failed. Stop."; exit 3; }
    OLLAMA="$(find_ollama || true)"
  fi
fi
if [ -z "$OLLAMA" ]; then
  echo "Ollama is not installed and Homebrew was not found."
  echo "Install it from https://ollama.com/download (macOS), then run this script again."
  exit 3
fi
echo "ollama binary: $OLLAMA"
"$OLLAMA" --version 2>&1 | tail -n 2

# ---- 3. server -----------------------------------------------------------
is_up()      { curl -sf --max-time 3 http://127.0.0.1:11434/api/version >/dev/null 2>&1; }
ours_alive() { [ -f "$OUT/serve.pid" ] && kill -0 "$(cat "$OUT/serve.pid")" 2>/dev/null; }
WANT_ENV="CTX=$CTX PAR=$PAR"

if is_up && ! ours_alive; then
  echo
  echo "An Ollama server is already running, and this script did not start it."
  echo "Its context length and parallel settings cannot be changed while it runs."
  echo "Quit it first (menu bar llama icon -> Quit Ollama, or: pkill -x ollama), then run this script again."
  exit 4
fi
if ours_alive && [ "$(cat "$OUT/serve.env" 2>/dev/null)" != "$WANT_ENV" ]; then
  echo "A server from an earlier run is up with other settings ($(cat "$OUT/serve.env" 2>/dev/null))."
  echo "Run: bash ollama/stop_ollama.sh   then run this script again."
  exit 4
fi
if ! ours_alive; then
  echo "starting: ollama serve  (log: ollama/serve.log)"
  OLLAMA_HOST=127.0.0.1:11434 \
  OLLAMA_CONTEXT_LENGTH="$CTX" \
  OLLAMA_NUM_PARALLEL="$PAR" \
  OLLAMA_MAX_LOADED_MODELS=1 \
  OLLAMA_KEEP_ALIVE=-1 \
  nohup "$OLLAMA" serve >> "$OUT/serve.log" 2>&1 &
  SERVE_PID=$!
  echo "$SERVE_PID" > "$OUT/serve.pid"
  echo "$WANT_ENV" > "$OUT/serve.env"
  # keep the Mac awake for as long as the server lives (a sleeping Mac froze the gpt-5 run)
  nohup caffeinate -i -w "$SERVE_PID" >/dev/null 2>&1 &
  for i in $(seq 1 30); do is_up && break; sleep 1; done
fi
if ! is_up; then
  echo "Server did not come up. Last lines of ollama/serve.log:"; tail -n 20 "$OUT/serve.log"; exit 5
fi
echo "server is up: $(curl -s http://127.0.0.1:11434/api/version)"

# ---- 4. model ------------------------------------------------------------
echo "pulling $BASE (this is the long step) ..."
"$OLLAMA" pull "$BASE" || { echo "pull failed. If the message asks for a newer Ollama, upgrade it and re-run."; exit 6; }

cat > "$OUT/Modelfile.$VARIANT" <<MODELFILE
# Pinned serving config for the threshold-transfer study. Sampling parameters are
# NOT set here: the model keeps the defaults shipped with $BASE.
FROM $BASE
PARAMETER num_ctx $CTX
MODELFILE
"$OLLAMA" create "$NAME" -f "$OUT/Modelfile.$VARIANT" || { echo "create failed"; exit 6; }

# ---- 5. provenance -------------------------------------------------------
PROV="$OUT/provenance-$VARIANT.txt"
{
  echo "recorded: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
  echo "machine: $CHIP | ${RAM_GB} GB | macOS $(sw_vers -productVersion)"
  echo "ollama: $("$OLLAMA" --version 2>&1 | tr '\n' ' ')"
  echo "server env: OLLAMA_CONTEXT_LENGTH=$CTX OLLAMA_NUM_PARALLEL=$PAR OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_KEEP_ALIVE=-1"
  echo; echo "--- ollama list ---";            "$OLLAMA" list
  echo; echo "--- ollama show $BASE ---";      "$OLLAMA" show "$BASE"
  echo; echo "--- ollama show $NAME --modelfile (head) ---"; "$OLLAMA" show "$NAME" --modelfile | grep -v '^LICENSE' | head -n 40
  echo; echo "--- ollama show $NAME --parameters ---"; "$OLLAMA" show "$NAME" --parameters
} > "$PROV" 2>&1
echo "provenance written: ollama/provenance-$VARIANT.txt"

# ---- 6. checks -----------------------------------------------------------
echo
echo "=== check A: server behaviour (thinking, tools, long context, speed) ==="
python3 "$OUT/check_ollama.py" --model "$NAME" --ctx "$CTX" --parallel "$PAR" --ollama-bin "$OLLAMA" --out "$OUT/check-$VARIANT.json"
A=$?
echo
echo "=== check B: the exact litellm route the tau2 runner will use ==="
if [ -x "$ROOT/tau2-bench/.venv/bin/python" ]; then
  "$ROOT/tau2-bench/.venv/bin/python" "$OUT/check_litellm_route.py" --model "$NAME"
  B=$?
else
  echo "tau2-bench/.venv not found; trying uv"
  ( cd "$ROOT/tau2-bench" && uv run python "$OUT/check_litellm_route.py" --model "$NAME" )
  B=$?
fi

echo
echo "=================================================================="
echo "check A exit code: $A   check B exit code: $B   (0 = all passed)"
echo "model name for the runner: openai/$NAME   api_base: http://127.0.0.1:11434/v1"
echo "logs: ollama/deploy-$VARIANT.log, ollama/check-$VARIANT.json, ollama/provenance-$VARIANT.txt, ollama/serve.log"
echo "The server keeps running and keeps the Mac awake. Stop it with: bash ollama/stop_ollama.sh"
echo "=================================================================="
