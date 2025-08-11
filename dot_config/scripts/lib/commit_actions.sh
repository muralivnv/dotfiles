extract_commit_hash() {
  echo "$1" | purl -extract '#\*\s+([a-z0-9]{4,})#$1#'
}

checkout_commit() {
  local commit
  commit=$(extract_commit_hash "$1")
  gum confirm "Checkout >>>> $commit <<<< ?" --no-show-help && \
    (git checkout "$commit" 1> /tmp/tmp.txt 2>&1 || less /tmp/tmp.txt)
}

soft_reset_to_commit() {
  local commit
  commit=$(extract_commit_hash "$1")
  local branch=$(git branch --show-current)
  local target=$(gum input --header.foreground="#00ff00" --header="Soft reset $branch to" --no-show-help --value="$commit")
  test $target && (git reset --soft "$target" 1> /tmp/tmp.txt 2>&1 || less /tmp/tmp.txt)
}

hard_reset_to_commit() {
  local commit
  commit=$(extract_commit_hash "$1")
  local branch=$(git branch --show-current)
  local target=$(gum input --header.foreground="#00ff00" --header="Hard reset $branch to" --no-show-help --value="$commit")
  test $target && (git reset --hard "$target" 1> /tmp/tmp.txt 2>&1 || less /tmp/tmp.txt)
}

cherry_pick() {
  local commit
  commit=$(extract_commit_hash "$1")
  gum confirm "Cherry-pick >>>> $commit ? <<<< " --no-show-help && \
  (git cherry-pick "$commit" 1> /tmp/tmp.txt 2>&1 || less /tmp/tmp.txt)
}

cherry_pick_no_commit() {
  local commit
  commit=$(extract_commit_hash "$1")
  gum confirm "Apply changes from >>>> $commit ? <<<< " --no-show-help && \
  (git cherry-pick --no-commit "$commit" 1> /tmp/tmp.txt 2>&1 || less /tmp/tmp.txt)
}

commit_changes() {
  local subject=$(gum input --width=100 --char-limit=80 --header="Commit Subject" --header.foreground="#00ff00")
  if [[ -z "${subject//[[:space:]]/}" ]]; then
    return
  fi
  local description=$(gum write --width=100 --height=15 --show-cursor-line --show-line-numbers --char-limit=80 --header="Commit Message" --header.foreground="#00ff00")
  gum confirm "Commit changes?" --no-show-help && git commit -m "$subject" -m "$description"
}

push_changes() {
  git push 1> /tmp/tmp.txt 2>&1 || less /tmp/tmp.txt
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
