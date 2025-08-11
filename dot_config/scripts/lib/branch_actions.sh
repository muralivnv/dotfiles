extract_branch() {
  echo "$1" | purl -extract '#^\d+@([A-Za-z0-9._\/-]+)#$1#' | sed 's#^origin/##'
}

checkout_branch() {
  local branch
  branch=$(extract_branch "$1")
  local target=$(gum input --header.foreground="#00ff00" --header="Checkout branch" --no-show-help --value="$branch")
  test $target && (git switch "$branch" 1> /tmp/tmp.txt 2>&1 || less /tmp/tmp.txt)
}

reset_branch() {
  local branch
  branch=$(extract_branch "$1")
  local target=$(gum input --header.foreground="#00ff00" --header="Reset branch to " --no-show-help --value="$branch")
  test $target && (git reset --hard "$branch" 1> /tmp/tmp.txt 2>&1 || less /tmp/tmp.txt)
}

delete_branch() {
  local branch
  branch=$(extract_branch "$1")
  gum confirm "Delete branch >>>> $branch? <<<< " --no-show-help && \
    (git branch -d "$branch" 1> /tmp/tmp.txt 2>&1 || less /tmp/tmp.txt)
}

force_delete_branch() {
  local branch
  branch=$(extract_branch "$1")
  gum confirm "Force delete branch >>>> $branch? <<<< " --no-show-help && \
    (git branch -D "$branch" 1> /tmp/tmp.txt 2>&1 || less /tmp/tmp.txt)
}

create_branch() {
  local branch parent child
  branch=$(extract_branch "$1")
  parent=$(gum input --header.foreground="#00ff00" --header="Create branch from" --no-show-help --value="$branch")
  child=$(gum input --header.foreground="#00ff00" --header="Branch name" --no-show-help)
  test $parent && test $child && (git branch "$child" "$parent" 1> /tmp/tmp.txt 2>&1 || less /tmp/tmp.txt)
}

pull_rebase() {
  git pull --rebase 1> /tmp/tmp.txt 2>&1 || less /tmp/tmp.txt
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
