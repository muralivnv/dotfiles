source ~/.config/bash_custom_functions.sh
source ~/.config/fzf_tab/fzf-bash-completion.sh

# set PATH so it includes user's private ~/.local/bin if it exists
if [ -d "$HOME/.local/bin" ] ; then
    PATH="$HOME/.local/bin:$PATH"
fi

bind -x '"\C-h": __fzf_history__'
bind -x '"\C-o": __fzf_cd__'
bind -x '"\C-p": fzf_file_widget'
bind -x '"\t": fzf_bash_completion'

alias '..'='cd ..'
alias gr="uv run $HOME/.config/scripts/git_repo_list.py"
alias gl="uv run $HOME/.config/scripts/git_log.py"
alias gc="uv run $HOME/.config/scripts/git_commit.py"
alias yy="yazi"
alias yy_scratch="swaymsg exec 'footclient --app-id=\"yazi_scratchpad\" -e $HOME/.local/bin/yazi'"
alias py_scratch="swaymsg exec 'footclient --app-id=\"python_scratchpad\" -e $HOME/.local/bin/uv run --python 3.14 --with numpy --with matplotlib python -i $HOME/.config/scripts/repl.py'"

export EDITOR=hx
export GIT_EDITOR=hx
export COLORTERM=truecolor

# jumping between prompts in foot terminal
# Reference: https://codeberg.org/dnkl/foot/wiki#jumping-between-prompts
prompt_marker() {
    printf '\e]133;A\e\\'
}
PROMPT_COMMAND=${PROMPT_COMMAND:+$PROMPT_COMMAND; }prompt_marker

# setup starship prompt
eval "$(starship init bash)"

# setup zoxide
eval "$(zoxide init bash)"
