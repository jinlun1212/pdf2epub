#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <epub_path> <out_dir> <num_screens> [start_delay_sec] [step_delay_sec]"
  exit 1
fi

EPUB_PATH="$1"
OUT_DIR="$2"
NUM_SCREENS="$3"
START_DELAY="${4:-6}"
STEP_DELAY="${5:-0.8}"

mkdir -p "$OUT_DIR"

open -a Books "$EPUB_PATH"
sleep "$START_DELAY"

osascript <<'APPLESCRIPT'
tell application "Books" to activate
tell application "System Events"
  key code 115
end tell
APPLESCRIPT
sleep 0.8

for ((i=1; i<=NUM_SCREENS; i++)); do
  printf -v idx "%04d" "$i"
  outfile="$OUT_DIR/screen_${idx}.png"
  screencapture -x "$outfile"

  if [[ "$i" -lt "$NUM_SCREENS" ]]; then
    osascript <<'APPLESCRIPT'
tell application "System Events"
  key code 124
end tell
APPLESCRIPT
    sleep "$STEP_DELAY"
  fi
done

echo "Saved $NUM_SCREENS screenshots to $OUT_DIR"
