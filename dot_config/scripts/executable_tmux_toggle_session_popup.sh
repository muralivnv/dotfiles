#!/usr/bin/env bash

SESSION="${1:-yazi_session}"
CWD="${2:-$PWD}"
CMD="${3:-yazi}"

POPUP_HEIGHT="80%"
POPUP_WIDTH="80%"

if [ -z "$TMUX" ]; then
  echo "Cannot open tmux popup outside tmux session." >&2
  exit 1
fi

CURRENT_SESSION="$(tmux display-message -p '#S')"

# if we are already attached to the yazi session, detach from session
if [ "$CURRENT_SESSION" = "$SESSION" ]; then
    tmux detach-client
    exit 0
fi

if ! tmux has-session -t "$SESSION" 2>/dev/null; then
    tmux new-session -ds "$SESSION" -c "$CWD"
    tmux set -t "$SESSION" status off
    tmux send-keys -t "$SESSION" "$CMD" C-m
fi

tmux display-popup -d "$CWD" -h "$POPUP_HEIGHT" -w "$POPUP_WIDTH" -E "tmux attach -t '$SESSION'"
