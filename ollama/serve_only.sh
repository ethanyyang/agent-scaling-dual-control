#!/usr/bin/env bash
# Start the Ollama server with the study's settings WITHOUT pulling or rebuilding any model
# (deploy_qwen35_4b.sh pulls the latest qwen3.5:4b tag, which changed the build on 2026-10-10).
# Same server settings as deploy_qwen35_4b.sh. Checks that the pinned name is the expected build.
#   bash ollama/serve_only.sh                      # expects tt-qwen3.5-4b:q4 = c0535b43ca6b (October 2026 build)
#   EXPECT=668eab7d518c bash ollama/serve_only.sh  # the registered build, if it is ever restored
set -u
cd "$(dirname "$0")" || exit 1
CTX="${CTX:-131072}"; PAR="${PAR:-4}"; EXPECT="${EXPECT:-c0535b43ca6b}"; NAME="tt-qwen3.5-4b:q4"
OLLAMA="$(command -v ollama || echo /opt/homebrew/bin/ollama)"
is_up()      { curl -sf --max-time 3 http://127.0.0.1:11434/api/version >/dev/null 2>&1; }
ours_alive() { [ -f serve.pid ] && kill -0 "$(cat serve.pid)" 2>/dev/null; }
WANT_ENV="CTX=$CTX PAR=$PAR"
if is_up && ! ours_alive; then echo "Another Ollama server is running (not started by these scripts). Quit it first: pkill -x ollama"; exit 4; fi
if ours_alive && [ "$(cat serve.env 2>/dev/null)" != "$WANT_ENV" ]; then echo "Server up with other settings ($(cat serve.env)). Run: bash ollama/stop_ollama.sh"; exit 4; fi
if ! ours_alive; then
  echo "starting: ollama serve (log: ollama/serve.log)"
  OLLAMA_HOST=127.0.0.1:11434 OLLAMA_CONTEXT_LENGTH="$CTX" OLLAMA_NUM_PARALLEL="$PAR" \
  OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_KEEP_ALIVE=-1 nohup "$OLLAMA" serve >> serve.log 2>&1 &
  SERVE_PID=$!; echo "$SERVE_PID" > serve.pid; echo "$WANT_ENV" > serve.env
  nohup caffeinate -i -w "$SERVE_PID" >/dev/null 2>&1 &
  for i in $(seq 1 30); do is_up && break; sleep 1; done
fi
is_up || { echo "Server did not come up. Last lines of ollama/serve.log:"; tail -n 20 serve.log; exit 5; }
ID="$("$OLLAMA" list | awk -v n="$NAME" '$1==n {print $2}')"
echo "server up | $WANT_ENV | $NAME = ${ID:-missing}"
if [ "$ID" != "$EXPECT" ]; then echo "WRONG BUILD: expected $EXPECT. Do not run anything; tell Claude."; exit 6; fi
echo "OK: expected build. Safe to run."
