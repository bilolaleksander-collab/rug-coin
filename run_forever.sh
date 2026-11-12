#!/bin/bash
# Keeps the bot alive 24/7 — restarts 3s after any crash
cd "$(dirname "$0")"
while true; do
  echo "$(date -u) | starting bot..."
  python3 get_rugged_bot.py >> bot.log 2>&1
  echo "$(date -u) | bot exited — restart in 3s"
  sleep 3
done
