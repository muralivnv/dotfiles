if [ -d "$HOME/.local/bin" ] ; then
    PATH="$HOME/.local/bin:$PATH"
fi

if command -v zoxide &> /dev/null; then
    export _ZO_DOCTOR=0.
    eval "$(zoxide init bash)"
fi

if command -v starship &> /dev/null; then
    eval "$(starship init bash)"
fi

# other
set +H

bind -x '"\C-h": __fzf_history__'
bind -x '"\C-o": __fzf_cd__'
bind -x '"\C-p": fzf_file_widget'
bind -x '"\t": fzf_bash_completion'

alias '..'='cd ..'
alias gr="uv run $HOME/.config/scripts/git_repo_list.py"
alias gl="uv run $HOME/.config/scripts/git_log.py"
alias gc="uv run $HOME/.config/scripts/git_commit.py"
alias yy="yazi"
export EDITOR=hx
export GIT_EDITOR=hx
export COLORTERM=truecolor
