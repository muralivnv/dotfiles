source ~/.config/bash_custom_functions.sh
source ~/.config/fzf_tab/fzf-bash-completion.sh
source ~/.config/bash_aliases.sh

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
