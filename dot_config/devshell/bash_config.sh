if [ -d "$HOME/.local/bin" ] ; then
    PATH="$HOME/.local/bin:$PATH"
fi

if command -v zoxide &> /dev/null; then
    export _ZO_DOCTOR=0
    eval "$(zoxide init bash)"
fi

if command -v starship &> /dev/null; then
    eval "$(starship init bash)"
fi

# other
set +H

# check whether fzf is present and we are in interactive shell
if command -v fzf &> /dev/null && [[ $- =~ i ]]; then
    bind -x '"\C-h": __fzf_history__'
    bind -x '"\C-o": __fzf_cd__'
    bind -x '"\C-p": fzf_file_widget'
    bind -x '"\t": fzf_bash_completion'
fi

alias '..'='cd ..'


if command -v uv &> /dev/null; then
    alias gr="uv run $HOME/.config/scripts/git_repo_list.py"
    alias gl="uv run $HOME/.config/scripts/git_log.py"
    alias gc="uv run $HOME/.config/scripts/git_commit.py"
fi
if command -v yazi &> /dev/null; then
    alias yy="yazi"
fi

if command -v hx &> /dev/null; then
    export EDITOR=hx
    export GIT_EDITOR=hx
fi
export COLORTERM=truecolor
