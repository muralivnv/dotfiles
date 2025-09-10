source ~/.config/bash_custom_functions.sh
source ~/.config/fzf_tab/fzf-bash-completion.sh

# set PATH so it includes user's private ~/.local/bin if it exists
if [ -d "$HOME/.local/bin" ] ; then
    PATH="$HOME/.local/bin:$PATH"
fi

# setup zoxide
eval "$(zoxide init bash)"

# setup starship prompt
eval "$(starship init bash)"

# other
set +H

bind -x '"\C-h": __fzf_history__'
bind -x '"\C-o": __fzf_cd__'
bind -x '"\C-p": fzf_file_widget'
bind -x '"\t" : fzf_bash_completion'

alias '..'='cd ..'
alias gr="python3 $HOME/.config/scripts/git_repo_list.py"
alias gl="python3 $HOME/.config/scripts/git_log.py"
alias gc="python3 $HOME/.config/scripts/git_commit.py"
alias gf="git fetch --all"
alias gp="git pull --rebase"
alias gP="git push"
alias gPf="git push --force-with-lease"

function jack {
    python3 "$HOME/.config/scripts/jack.py" "$@"
}
export -f jack
export EDITOR=hx
export GIT_EDITOR=hx
