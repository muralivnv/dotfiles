extract_commit_hash() {
  echo "$1" | purl -extract '#\*\s+([a-z0-9]{4,})#$1#'
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

checkout_commit() {
  local commit
  commit=$(extract_commit_hash "$1")
  run_editable_command "git checkout \"$commit\" "
}

soft_reset_to_commit() {
  local commit
  commit=$(extract_commit_hash "$1")
  run_editable_command "git reset --soft \"$commit\" "
}

hard_reset_to_commit() {
  local commit
  commit=$(extract_commit_hash "$1")
  run_editable_command "git reset --hard \"$commit\" "
}

cherry_pick() {
  local commit
  commit=$(extract_commit_hash "$1")
  run_editable_command "git cherry-pick \"$commit\" "
}

cherry_pick_no_commit() {
  local commit
  commit=$(extract_commit_hash "$1")
  run_editable_command "git cherry-pick --no-commit \"$commit\" "
}

commit_changes() {
  local tmpfile msgfile
  tmpfile=$(mktemp --suffix=.diff)
  msgfile="$tmpfile.msg"
  trap 'rm -f "$tmpfile" "$msgfile"' RETURN

  cat >"$tmpfile" <<-EOF
		>>> COMMIT_MESSAGE

		<<< COMMIT_MESSAGE
		<<<DIFF>>>
	EOF
  git diff --staged >> "$tmpfile"

  "$EDITOR" "$tmpfile"
  local msgfile="$tmpfile.msg"

  sed '/<<<DIFF>>>/,$d' "$tmpfile" | purl -exclude '^[<>]{3}\sCOMMIT_MESSAGE' > "$msgfile"

  if purl -exclude '^\n$' "$msgfile" | purl -fail -filter '[a-zA-Z0-9]{1}' > /dev/null; then
    git commit -F "$msgfile"
    rm "$tmpfile" "$msgfile"
  else
    echo "Empty commit message -- aborting"
  fi
}

push_changes() {
  run_editable_command "git push "
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
