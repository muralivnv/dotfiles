extract_branch() {
  echo "$1" | purl -extract '#^\d+@([A-Za-z0-9._\/-]+)#$1#' | sed 's#^origin/##'
}

run_editable_command() {
  local initial_cmd="$1"
  local user_cmd
  if read -e -i "$initial_cmd" -p "" user_cmd; then
    if ! eval "$user_cmd"; then
      echo
      read -r || true
    fi
  else
    return 1
  fi
}

checkout_branch() {
  local branch
  branch=$(extract_branch "$1")
  run_editable_command "git switch \"$branch\" "
}

reset_branch() {
  local branch
  branch=$(extract_branch "$1")
  run_editable_command "git reset --hard \"$branch\" "
}

delete_branch() {
  local branch
  branch=$(extract_branch "$1")
  run_editable_command "git branch -d \"$branch\" "
}

force_delete_branch() {
  local branch
  branch=$(extract_branch "$1")
  run_editable_command "git branch -D \"$branch\" "
}

create_branch() {
  local branch parent child
  branch=$(extract_branch "$1")
  run_editable_command "git branch <NEW-BRANC> \"$branch\""
}

pull_rebase() {
  run_editable_command "git pull --rebase "
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  # Called directly, dispatch first argument as function
  cmd="$1"
  shift
  if declare -f "$cmd" > /dev/null; then
    "$cmd" "$@"
  else
    echo "Unknown command: $cmd" >&2
    exit 1
  fi
fi
