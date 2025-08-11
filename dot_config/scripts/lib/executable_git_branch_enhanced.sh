#!/bin/bash

C_CYAN="\033[36m"
C_ORANGE="\033[38;5;214m"
C_GREEN="\033[32m"
C_YELLOW="\033[33m"
C_BOLD_RED="\033[1;31m"
C_BOLD_PURPLE="\033[1;35m"
C_RESET="\033[0m"

current_branch=$(git symbolic-ref --quiet --short HEAD)
local_branches=$(git for-each-ref --count=50 --format='%(refname)|%(refname:short)|%(upstream:short)|%(committerdate:unix)|%(objectname:short)|%(authorname)|%(contents:subject)' refs/heads)
remote_branches=$(git for-each-ref --count=50 --format='%(refname) %(refname:short) %(committerdate:unix) %(authorname) %(contents:subject)' refs/remotes)

tmpfile=$(mktemp)

while IFS='|' read -r full_ref local_branch upstream unixdate commit_hash author subject; do
  if [ -z "$upstream" ]; then
    upstream=">>> NO-REMOTE <<<"
    ahead=0
    behind=0
  else
    counts=$(git rev-list --left-right --count "$local_branch...$upstream")
    ahead=$(echo "$counts" | cut -f1)
    behind=$(echo "$counts" | cut -f2)
  fi

  prefix=""
  if [[ "$local_branch" == "$current_branch" ]]; then
    prefix="${C_BOLD_RED}"
  fi

  echo -e "$unixdate\tlocal\t$prefix$local_branch\t$upstream\t$ahead\t$behind\t$author\t$subject" >> "$tmpfile"
done <<< "$local_branches"

while read -r full_ref remote_branch unixdate author subject; do
  tracked=$(git for-each-ref --format='%(upstream:short)' refs/heads | grep -Fx "$remote_branch" || true)
  if [ -z "$tracked" ]; then
    echo -e "$unixdate\tremote\t$remote_branch\t-\t-\t-\t$author\t$subject" >> "$tmpfile"
  fi
done <<< "$remote_branches"

sort -k1,1nr "$tmpfile" | while IFS=$'\t' read -r unixdate type branch upstream ahead behind author subject; do
  date_str=$(date -d "@$unixdate" '+%Y-%m-%d %H:%M')

  if [ "$type" = "local" ]; then
    echo -e "${C_CYAN}${branch}${C_RESET} (${C_ORANGE}${upstream}${C_RESET}) | ↑ ${C_GREEN}${ahead}${C_RESET} ↓ ${C_GREEN}${behind}${C_RESET} | ${C_GREEN}${author} ${date_str}${C_RESET} | ${C_BOLD_PURPLE}${subject}${C_RESET}"
  else
    echo -e "${C_ORANGE}${branch}${C_RESET} | | ${C_GREEN}${author} ${date_str}${C_RESET} | ${C_BOLD_PURPLE}${subject}${C_RESET}"
  fi
done | column -t -s'|'

rm "$tmpfile"
