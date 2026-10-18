#!/usr/bin/env bash
# Stop the Ollama server that deploy_qwen35_4b.sh started. The Mac may sleep again afterwards.
cd "$(dirname "$0")" || exit 1
if [ -f serve.pid ] && kill -0 "$(cat serve.pid)" 2>/dev/null; then
  kill "$(cat serve.pid)" && echo "stopped ollama serve (pid $(cat serve.pid))"
else
  echo "no server started by the deploy script is running"
fi
rm -f serve.pid serve.env
