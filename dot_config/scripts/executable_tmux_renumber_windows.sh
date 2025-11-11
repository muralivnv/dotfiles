#!/usr/bin/env bash

session="${1:-$(tmux display-message -p '#S')}"
windows=$(tmux list-windows -t "$session" -F '#{window_index}' | sort -n)
new=0
for old in $windows
do
  tmux move-window -s "${session}:$old" -t "${session}:$new"
  ((new++))
done
