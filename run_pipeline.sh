#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"
source .venv/bin/activate

LOG="pipeline.log"
echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >> "$LOG"

python fetch.py > new.json 2>> "$LOG"
echo "fetch done" >> "$LOG"

claude -p "$(cat nightly_prompt.md)" \
  --allowedTools "Read,Write" \
  --output-format text >> "$LOG" 2>&1
echo "score done" >> "$LOG"

python write.py scored.json >> "$LOG" 2>&1
echo "write done" >> "$LOG"
