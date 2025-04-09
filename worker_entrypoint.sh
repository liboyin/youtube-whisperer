#!/bin/bash

set -euo pipefail
python -m youtube_whisperer.worker &
pid=$!
while true; do
  if ! nvidia-smi > /dev/null 2>&1; then
    echo "Health check failed. Stopping service..."
    kill -TERM "$pid"
    wait "$pid"
    exit 1
  fi
  sleep 60
done
