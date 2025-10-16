#!/usr/bin/env bash

# Popup terminal around active window in various modes.
# Usage examples:
#   ./popup-terminal --bottom 0.5 -- -e htop
#   ./popup-terminal --center 0.6 0.6 -- -e bash
#   ./popup-terminal --right 0.4 -- -e vim
#   ./popup-terminal -e fzf  # defaults to --bottom 0.5

set -euo pipefail

# dependencies
for cmd in xprop xwininfo wmctrl awk; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "Missing required tool: $cmd" >&2
    exit 1
  }
done

# pick terminal command
if command -v x-terminal-emulator >/dev/null 2>&1; then
  TERM_CMD=(x-terminal-emulator)
else
  echo "x-terminal-emulator not found" >&2
  exit 1
fi

# --- argument parsing ---
mode="bottom"
frac1=0.5
frac2=0.5
block=false
term_args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --block)
      block=true
      shift
      ;;
    --bottom|--top|--left|--right)
      mode="${1#--}"
      frac1="${2:-0.5}"
      shift 2
      ;;
    --center)
      mode="center"
      frac1="${2:-0.6}"
      frac2="${3:-0.6}"
      shift 3
      ;;
    --)
      shift
      term_args=("$@")
      break
      ;;
    -*)
      term_args=("$@")
      break
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

# get active window geometry
read X Y W H < <(xwininfo -id "$(xprop -root _NET_ACTIVE_WINDOW | awk '{print $5}')" |
  awk '/Absolute upper-left X:/ {x=$4}
       /Absolute upper-left Y:/ {y=$4}
       /Width:/ {w=$2}
       /Height:/ {h=$2}
       END {print x, y, w, h}')

[[ -z "$X" || -z "$Y" ]] && { echo "Failed to get geometry."; exit 1; }

# compute new geometry
case "$mode" in
  bottom)
    newH=$(awk -v H="$H" -v f="$frac1" 'BEGIN{h=int(H*f); if(h<1) h=1; print h}')
    newY=$(( Y + H - newH ))
    newX=$X
    newW=$W
    ;;
  top)
    newH=$(awk -v H="$H" -v f="$frac1" 'BEGIN{h=int(H*f); if(h<1) h=1; print h}')
    newY=$Y
    newX=$X
    newW=$W
    ;;
  left)
    newW=$(awk -v W="$W" -v f="$frac1" 'BEGIN{w=int(W*f); if(w<1) w=1; print w}')
    newX=$X
    newY=$Y
    newH=$H
    ;;
  right)
    newW=$(awk -v W="$W" -v f="$frac1" 'BEGIN{w=int(W*f); if(w<1) w=1; print w}')
    newX=$(( X + W - newW ))
    newY=$Y
    newH=$H
    ;;
  center)
    newW=$(awk -v W="$W" -v f="$frac1" 'BEGIN{w=int(W*f); if(w<1) w=1; print w}')
    newH=$(awk -v H="$H" -v f="$frac2" 'BEGIN{h=int(H*f); if(h<1) h=1; print h}')
    newX=$(( X + (W - newW) / 2 ))
    newY=$(( Y + (H - newH) / 2 ))
    ;;
  *)
    echo "Invalid mode: $mode" >&2
    exit 1
    ;;
esac

# record window list before launch
before=$(mktemp)
wmctrl -lp > "$before"

# launch terminal
"${TERM_CMD[@]}" "${term_args[@]}" >/dev/null 2>&1 &

# find new window
popup_id=""
for i in {1..50}; do
  after=$(mktemp)
  wmctrl -lp > "$after"
  popup_id=$(comm -13 <(sort "$before") <(sort "$after") | awk '{print $1; exit}')
  rm -f "$after"
  [[ -n "$popup_id" ]] && break
  # sleep 0.025
done
rm -f "$before"

if [[ -z "$popup_id" ]]; then
  echo "Could not find popup window (WM delay or Wayland?)."
  exit 1
fi

# move + resize + borderless
wmctrl -i -r "$popup_id" -e "0,$newX,$newY,$newW,$newH" 2>/dev/null || true
xprop -id "$popup_id" -f _MOTIF_WM_HINTS 32c \
  -set _MOTIF_WM_HINTS "2, 0, 0, 0, 0" 2>/dev/null || true

# raise + focus
wmctrl -i -r "$popup_id" -b add,above
wmctrl -i -a "$popup_id"

# make opaque
xprop -id "$popup_id" -f _NET_WM_WINDOW_OPACITY 32c \
  -set _NET_WM_WINDOW_OPACITY 0xffffffff 2>/dev/null || true

# wait until the popup window is closed
if $block; then
  while xprop -id "$popup_id" >/dev/null 2>&1; do
      sleep 0.1
  done
fi
