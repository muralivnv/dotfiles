# shell parsing stuff
_bash_completion_awk="$( builtin command -v gawk &>/dev/null && echo gawk || echo awk )"
_bash_completion_sed="$( builtin command -v gsed &>/dev/null && echo gsed || echo sed )"
_bash_completion_grep="$( builtin command -v ggrep &>/dev/null && echo ggrep || echo builtin command grep )"

# Cursor control, resolved once when this file is sourced. Asking tput on every key was
# three execs at ~0.8 ms each for three sequences that are identical on any terminal
# worth completing in -- and the literals below were already the fallback.
_bash_completion_save_cursor="$( command tput sc 2>/dev/null || printf '\0337' )"
_bash_completion_restore_cursor="$( command tput rc 2>/dev/null || printf '\0338' )"
_bash_completion_clear_eol="$( command tput el 2>/dev/null || printf '\033[K' )"

# Scratch space for the match list, one directory per shell. mktemp -d and rm -rf on
# every key were two more forks for two files whose names never mattered; the files are
# truncated by each write instead. XDG_RUNTIME_DIR is already private to this user, so
# a name derived from the PID is safe there; without it, one mktemp per shell is.
_bash_completion_tmpdir() {
    [ -d "${_bash_completion_tmp:-}" ] && return 0
    if [ -n "${XDG_RUNTIME_DIR:-}" ]; then
        # Sweep the dirs of shells that have exited. Runs on the first completion of
        # this shell and never again, which is what the old per-key rm -rf was paying
        # for. Every PID here is ours: XDG_RUNTIME_DIR is per-user.
        local stale
        for stale in "$XDG_RUNTIME_DIR"/bash-completion-*; do
            [ -d "$stale" ] && ! kill -0 "${stale##*-}" 2>/dev/null && rm -rf "$stale"
        done
        _bash_completion_tmp="$XDG_RUNTIME_DIR/bash-completion-$$"
        mkdir -p -m 700 "$_bash_completion_tmp" 2>/dev/null && return 0
    fi
    _bash_completion_tmp="$(mktemp -d "${TMPDIR:-/tmp}/bash-completion.XXXXXX")" || return 1
}

_bash_completion_awk_escape() {
    "$_bash_completion_sed" 's/\\/\\\\\\\\/g; s/[[*^$.]/\\\\&/g' <<<"$1"
}

_bash_completion_shell_split() {
    $_bash_completion_grep -E -o \
        -e '\|+|&+|<+|>+' \
        -e '[;(){}&\|]' \
        -e '(\\.|\$[-[:alnum:]_*@#?$!]|(\$\{[^}]*(\}|$))|[^$\|"[:space:];(){}&<>'"'${wordbreaks}])+" \
        -e "\\\$'(\\\\.|[^'])*('|$)" \
        -e "'[^']*('|$)" \
        -e '"(\\.|\$($|[^(])|[^"$])*("|$)' \
        -e '".*' \
        -e '[[:space:]]+' \
        -e .
}

_bash_completion_unbuffered_awk() {
    # need to get awk to be unbuffered either by using -W interactive or system("")
    "$_bash_completion_awk" -W interactive "${@:3}" "$1 { $2; print \$0; system(\"\") }" 2>/dev/null
}

_bash_completion_flatten_subshells() {
    (
        local count=0 buffer=
        while IFS= read -r line; do
            case "$line" in
                \(|\{) (( count -- )) ;;
                \)|\}) (( count ++ )) ;;
            esac

            if (( count < 0 )); then
                return
            elif (( count > 0 )); then
                buffer="$line$buffer"
            else
                printf '%s\n' "$line$buffer"
                buffer=
            fi
        done < <(tac)
        printf '%s\n' "$buffer"
    ) | tac
}

_bash_completion_find_matching_bracket() {
    local count=0
    while IFS=: read -r num bracket; do
        if [ "$bracket" = "$1" ]; then
            (( count++ ))
            if (( count > 0 )); then
                printf '%s\n' "$num"
                return 0
            fi
        else
            (( count -- ))
        fi
    done < <($_bash_completion_grep -F -e '(' -e ')' -n)
    return 1
}

_bash_completion_parse_dq() {
    local words="$(cat)"
    local last="$(<<<"$words" tail -n1)"

    if [[ "$last" == \"* ]]; then
        local line="${last:1}" shell_start string_end joined num
        local word=
        while true; do
            # we are in a double quoted string

            shell_start="$(<<<"$line" $_bash_completion_grep -E -o '^(\\.|\$[^(]|[^$])*\$\(')"
            string_end="$(<<<"$line" $_bash_completion_grep -E -o '^(\\.|[^"])*"')"

            if (( ${#string_end} && ( ! ${#shell_start} || ${#string_end} < ${#shell_start} )  )); then
                # found end of string
                line="${line:${#string_end}}"
                if (( ${#line} )); then
                    printf '%s\n' "${words:0:-${#line}}"
                    _bash_completion_parse_line <<<"$line"
                else
                    printf '%s\n' "$words"
                fi
                return

            elif (( ${#shell_start} && ( ! ${#string_end} || ${#shell_start} < ${#string_end} )  )); then
                # found a subshell

                word+="${shell_start:0:-2}"
                line="${line:${#shell_start}}"

                split="$(<<<"$line" _bash_completion_shell_split)"
                if ! split="$(_bash_completion_parse_dq <<<"$split")"; then
                    # bubble up
                    printf '%s\n' "$split"
                    return 1
                fi
                if ! num="$(_bash_completion_find_matching_bracket ')' <<<"$split")"; then
                    # subshell not closed, this is it
                    printf '%s\n' "$split"
                    return 1
                fi
                # subshell closed
                joined="$(<<<"$split" head -n "$num" | tr -d \\n)"
                word+=$'\n$('"$joined"$'\n'
                line="${line:${#joined}}"

            else
                # the whole line is an incomplete string
                break
            fi
        done
    fi
    printf '%s\n' "$words"
}

_bash_completion_unquote_strings() {
    local line
    while IFS= read -r line; do
        if [[ "$line" =~ ^\'[^\']*\'?$ ]]; then
            # single quoted with no single quotes inside
            line="${line%%"'"}"
            printf '%s\n' "${line:1}"
        elif [[ "$line" =~ ^\"(\\.|[^\"$])*\"?$ ]]; then
            # double quoted with all special characters quoted
            "$_bash_completion_sed" -r 's/\\(.)/\1/g' <<<"${line:1-1}"
        elif [[ "$line" == *\\* && "$line" =~ ^(\\.|[a-zA-Z0-9_])*$ ]]; then
            # all special characters are quoted
            "$_bash_completion_sed" -r 's/\\(.)/\1/g' <<<"$line"
        else
            # this string is either boring or too complicated to parse
            # print as is
            printf '%s\n' "$line"
        fi
    done
}

# Built once when this file is sourced: as a $(cat <<EOF) inside parse_line it was a
# subshell and a cat exec per completion, to produce a string that never changes.
_bash_completion_parse_sed="$(cat <<'EOF'
# collapse newlines
s/\x00\x00/\x00/g;
# leave trailing space
s/\x00(\s*)$/\n\1/;
# A & B -> (A, &, B)
s/([^&\n\x00])&([^&\n\x00])/\1\n\&\n\2/g;
# > B -> (>, B)
s/([\n\x00\z])([<>]+)([^\n\x00])/\1\2\n\3/g;
s/([<>][\n\x00])$/\1\n/;
# clear up until the a keyword starting a new command
# except the last line isn't a keyword, it may be the start of a command
s/^(.*[\x00\n])?(\[\[|case|do|done|elif|else|esac|fi|for|function|if|in|select|then|time|until|while|&|;|&&|\|[|&]?)\x00//;
# remove ENVVAR=VALUE
s/^(\s*[\n\x00]|\w+=[^\n\x00]*[\n\x00])*//
EOF
)"

_bash_completion_parse_line() {
    _bash_completion_shell_split \
        | _bash_completion_parse_dq \
        | _bash_completion_flatten_subshells \
        | tr \\n \\0 \
        | "$_bash_completion_sed" -r "$_bash_completion_parse_sed" \
        | tr \\0 \\n
}

# Characters a shell would have to think about. A line free of them -- and free of every
# COMP_WORDBREAKS character, since the parser makes those words of their own -- splits
# on whitespace and nothing else, which bash can do in-process. That is the difference
# between six execs and none, so the common line takes this door.
_bash_completion_is_simple() {
    [[ -n "$1" && "$1" != *[^A-Za-z0-9_./+,%^~*?!\ -]* ]]
}

# Fills the named array the way parse_line would for a simple line: words with the
# whitespace runs between them kept as their own elements, leading blanks dropped and a
# trailing run kept. Verified against parse_line over a corpus, because downstream code
# reads those separators.
_bash_completion_split_simple() {
    local -n _words="$2"
    local rest="$1" word ws
    _words=()
    rest="${rest#"${rest%%[^ ]*}"}"
    while [ -n "$rest" ]; do
        word="${rest%% *}"
        rest="${rest#"$word"}"
        _words+=( "$word" )
        [ -n "$rest" ] || break
        ws="${rest%%[^ ]*}"
        rest="${rest#"$ws"}"
        _words+=( "$ws" )
    done
}

_bash_completion_compspec() {
    if [[ "$2" =~ .*\$(\{?)([A-Za-z0-9_]*)$ ]]; then
        printf '%s\n' 'complete -F _bash_completion_complete_variables'
    elif [[ "$COMP_CWORD" == 0 && -z "$2" ]]; then
        # If the command word is the empty string (completion attempted at the beginning of an empty line), any compspec defined with the -E option to complete is used.
        complete -p -E || { ! shopt -q no_empty_cmd_completion && printf '%s\n' 'complete -F _bash_completion_complete_commands -E'; }
    elif [[ "$COMP_CWORD" == 0 ]]; then
        complete -p -I || printf '%s\n' 'complete -F _bash_completion_complete_commands -I'
    else
       # If the command word is a full pathname, a compspec for the full pathname is searched for first.  If no compspec is found for the full pathname, an attempt is made to find a compspec for the portion following the final slash.  If those searches do not result in a compspec, any compspec defined with the -D option to complete is used as the default
        complete -p -- "$1" || complete -p -- "${1##*/}" || complete -p -D || printf '%s\n' 'complete -o filenames -F _bash_completion_fallback_completer'
    fi
}

_bash_completion_fallback_completer() {
    # fallback completion in case no compspecs loaded. $2 is the word being completed;
    # $1 is the command, and completing against that returned matches for the wrong
    # string -- usually none at all.
    if [[ "$2" == \~* && "$2" != */* ]]; then
        # complete ~user directories
        readarray -t COMPREPLY < <(compgen -P '~' -u -- "${2#\~}")
    else
        # complete files
        readarray -t COMPREPLY < <(compgen -f -- "$2")
    fi
}

_bash_completion_complete_commands() {
    # commands
    compopt -o filenames
    readarray -t COMPREPLY < <(compgen -abc -- "$2")
}

_bash_completion_complete_variables() {
    if [[ "$2" =~ .*\$(\{?)([A-Za-z0-9_]*)$ ]]; then
        # environment variables
        local brace="${BASH_REMATCH[1]}"
        local filter="${BASH_REMATCH[2]}"
        if [ -n "$filter" ]; then
            local prefix="${2:: -${#filter}}"
        else
            local prefix="$2"
        fi
        readarray -t COMPREPLY < <(compgen -v -P "$prefix" -S "${brace:+\}}" -- "$filter")
    fi
}

# Written straight to the terminal rather than through a $(...), which was a subshell per
# key. An override should print without a trailing newline for the same reason.
_bash_completion_loading_msg() {
    printf '%s' 'Loading matches ...'
}

bash_completion() {
    # bail early if no_empty_cmd_completion
    if ! [[ "$READLINE_LINE" =~ [^[:space:]] ]] && shopt -q no_empty_cmd_completion; then
        return 1
    fi

    printf '\r%s' "$_bash_completion_save_cursor"
    _bash_completion_loading_msg
    printf '%s' "$_bash_completion_restore_cursor"

    local raw_comp_words=()
    local COMP_WORDS=() COMP_CWORD COMP_POINT COMP_LINE
    local COMP_TYPE=37 # % == indicates menu completion
    local line="${READLINE_LINE:0:READLINE_POINT}"
    local wordbreaks="$COMP_WORDBREAKS"
    wordbreaks="${wordbreaks//[]^]/\\&}"
    wordbreaks="${wordbreaks//[[:space:]]/}"

    local fast=0
    if _bash_completion_is_simple "$line"; then
        fast=1
        _bash_completion_split_simple "$line" raw_comp_words
    elif [[ "$line" =~ [^[:space:]] ]]; then
        readarray -t raw_comp_words < <(_bash_completion_parse_line <<<"$line")
    fi

    if [[ ${#raw_comp_words[@]} -gt 1 ]]; then
        _bash_completion_expand_alias "${raw_comp_words[@]}"
        # An alias expands to arbitrary text, so the fast lane's premise has to hold
        # again afterwards before the unquote pass can be skipped.
        (( fast )) && ! _bash_completion_is_simple "${raw_comp_words[*]}" && fast=0
    fi

    if (( fast )); then
        # Nothing to unquote: these words came out of a line with no quoting in it.
        COMP_WORDS=( "${raw_comp_words[@]}" )
    else
        readarray -t COMP_WORDS < <(printf '%s\n' "${raw_comp_words[@]}" | _bash_completion_unquote_strings)
    fi

    printf -v COMP_LINE '%s' "${COMP_WORDS[@]}"
    COMP_POINT="${#COMP_LINE}"
    # remove the ones that just spaces
    local i
    # iterate in reverse
    for (( i = ${#COMP_WORDS[@]}-2; i >= 0; i --)); do
        if ! [[ "${COMP_WORDS[i]}" =~ [^[:space:]] ]]; then
            COMP_WORDS=( "${COMP_WORDS[@]:0:i}" "${COMP_WORDS[@]:i+1}" )
        fi
    done
    # add an extra blank word if last word is just space
    if [[ "${#COMP_WORDS[@]}" = 0 ]]; then
        COMP_WORDS+=( '' )
    elif ! [[ "${COMP_WORDS[${#COMP_WORDS[@]}-1]}" =~ [^[:space:]] ]]; then
        COMP_WORDS[${#COMP_WORDS[@]}-1]=''
    fi
    COMP_CWORD="${#COMP_WORDS[@]}"
    (( COMP_CWORD-- ))

    local cmd="${COMP_WORDS[0]}"
    local prev
    if [ "$COMP_CWORD" = 0 ]; then
        prev=
    else
        prev="${COMP_WORDS[COMP_CWORD-1]}"
    fi
    local cur="${COMP_WORDS[COMP_CWORD]}"
    if [[ "$cur" =~ ^[$wordbreaks]$ ]]; then
        cur=
    fi
    local raw_cur="${cur:+${raw_comp_words[-1]}}"

    local COMPREPLY=
    _bash_completion_run "$cmd" "$cur" "$prev"
    if [ -n "$COMPREPLY" ]; then
        if [ -n "$raw_cur" ]; then
            line="${line::-${#raw_cur}}"
        fi
        READLINE_LINE="${line}${COMPREPLY}${READLINE_LINE:$READLINE_POINT}"
        (( READLINE_POINT+=${#COMPREPLY} - ${#raw_cur} ))
    fi

    printf '\r%s' "$_bash_completion_clear_eol"
}

# Pick one of the collected matches, leaving it in _bash_completion_choice. Nothing to
# pick and exactly one match are both settled here without spawning anything, which is
# the common case; only an ambiguous completion is worth a picker -- and only that case
# pays for a subshell, since a command substitution around the whole function would have
# charged one for the settled cases too. The old -1/-0 flags existed because matches
# arrived as a stream it could not count.
_bash_completion_select() {
    _bash_completion_choice=
    (( ${#matches[@]} )) || return 1
    if (( ${#matches[@]} == 1 )); then
        _bash_completion_choice="${matches[0]}"
        return 0
    fi
    _bash_completion_choice="$(printf '%s\n' "${matches[@]}" |
        tooey --height 50 --prompt "> $1" --query-process-command 'gai --no-color -f {{@QUERY@}}')"
}

_bash_completion_expand_alias() {
    if alias "$1" &>/dev/null; then
        value=( ${BASH_ALIASES[$1]} )
        if [ -n "${value[*]}" -a "${value[0]}" != "$1" ]; then
            raw_comp_words=( "${value[@]}" "${raw_comp_words[@]:1}" )
        fi
    fi
}

_bash_completion_run() {
    local value code
    local compl_bashdefault compl_default compl_dirnames compl_filenames compl_noquote compl_nosort compl_nospace compl_plusdirs

    # preload completions in top shell
    { complete -p -- "$1" || __load_completion "$1"; } &>/dev/null
    local compspec
    if ! compspec="$(_bash_completion_compspec "$@" 2>/dev/null)"; then
        return
    fi

    # Matches are generated in this shell, which is where bash runs a compspec anyway.
    # Feeding a picker while still generating is what forced the old coproc, the
    # sentinel-delimited eval and the recursive ps -ef kill of leftover generators; two
    # files replace all three. The compl_* flags still need a channel of their own
    # because the generator's last stage is a pipeline, so those assignments happen in a
    # subshell -- $__evaled is that channel, now just an fd on a file.
    local matches=()
    _bash_completion_tmpdir || return
    local out="$_bash_completion_tmp/matches" flags="$_bash_completion_tmp/flags" __evaled
    exec {__evaled}>"$flags"

    compopt() { _bash_completion_compopt "$@"; }
    # The compspec is already in hand, so the first attempt reuses it. A retry must not:
    # 124 means the completion function loaded a new one, and looking it up again is the
    # whole point of trying twice.
    local compspec_first="$compspec" count=0 code
    _bash_completion_complete "$@" >"$out"
    code=$?
    compspec_first=
    while (( code == 124 )); do
        if (( ++count > 32 )); then
            printf '%s: possible retry loop\n' "$1" >/dev/tty
            break
        fi
        _bash_completion_complete "$@" >>"$out"
        code=$?
    done
    unset -f compopt

    exec {__evaled}>&-
    source "$flags"
    # awk rather than a bash loop on purpose: measured, bash wins below ~1000 matches
    # and loses badly above it, and `compgen -abc` alone is several thousand.
    readarray -t matches < <("$_bash_completion_awk" '$0 != "" && !seen[$0]++' "$out")

    # Compspec functions fill COMPREPLY, and they now run in this shell rather than a
    # subshell, so it has to be cleared: the caller treats a non-empty COMPREPLY as the
    # text to splice, and would otherwise insert a leftover match after a cancelled pick.
    COMPREPLY=
    _bash_completion_select "$line"
    code="$?"

    if [ "$code" = 0 ] && [ -n "$_bash_completion_choice" ]; then
        COMPREPLY="$_bash_completion_choice"
        [ "$compl_nospace" != 1 ] && COMPREPLY="$COMPREPLY "
        [[ "$compl_filenames" == *1* ]] && COMPREPLY="${COMPREPLY/%\/ //}"
    fi
}

_bash_completion_complete() {
    local compgen_actions=() compspec="${compspec_first:-}"
    if [ -z "$compspec" ] && ! compspec="$(_bash_completion_compspec "$@" 2>/dev/null)"; then
        return
    fi

    local args=( "$@" )
    eval "compspec=( $compspec )"
    set -- "${compspec[@]}"
    shift # remove the complete command
    while (( $# > 1 )); do
        case "$1" in
        -F)
            local compl_function="$2"
            shift ;;
        -C)
            local compl_command="$2"
            shift ;;
        -G)
            local compl_globpat="$2"
            shift ;;
        -W)
            local compl_wordlist="$2"
            shift ;;
        -X)
            local compl_xfilter="$2"
            shift ;;
        -o)
            _bash_completion_compopt -o "$2"
            shift ;;
        -A)
            local compgen_opts+=( "$1" "$2" )
            shift ;;
        -P)
            local compl_prefix="$(_bash_completion_awk_escape "$2")"
            shift ;;
        -S)
            local compl_suffix="$(_bash_completion_awk_escape "$2")"
            shift ;;
        -[a-z])
            compgen_actions+=( "$1" )
            ;;
        esac
        shift
    done
    set -- "${args[@]}"

    COMPREPLY=()
    if [ -n "$compl_function" ]; then
        "$compl_function" "$@" >/dev/null
        if [ "$?" = 124 ]; then
            local newcompspec
            if ! newcompspec="$(_bash_completion_compspec "$@" 2>/dev/null)"; then
                return
            elif [ "$newcompspec" != "$compspec" ]; then
                return 124
            fi
            "$compl_function" "$@" >/dev/null
        fi
    fi

    if [[ "$compl_filenames" == 1 ]]; then
        local dir_marker=_bash_completion_dir_marker
    else
        local dir_marker=cat
    fi

    printf 'compl_filenames=%q\n' "$compl_filenames" >&"${__evaled}"
    printf 'compl_noquote=%q\n' "$compl_noquote" >&"${__evaled}"
    printf 'compl_nospace=%q\n' "$compl_nospace" >&"${__evaled}"

    # Most compspecs carry neither -P nor -S, and escaping two empty strings still cost
    # two subshells and two seds on every key. '&' alone is awk's identity substitution.
    local replace='&'
    if [ -n "$compl_prefix$compl_suffix" ]; then
        replace="$(printf %s "$compl_prefix" | "$_bash_completion_sed" 's/[&\]/\\&/g')&$(printf %s "$compl_suffix" | "$_bash_completion_sed" 's/[&\]/\\&/g')"
    fi

    # A compspec with no generator of its own -- no -W, -G, -C, -X, no compgen actions,
    # no plusdirs, no affixes -- has already produced everything it is going to, in
    # COMPREPLY. The pipeline below would be eight processes spent copying an array, so
    # print it and run only the filters that would have applied. Which is most
    # completions: every -F function compspec lands here, and so does file fallback.
    if [ -z "$compl_globpat$compl_wordlist$compl_command$compl_xfilter$compl_prefix$compl_suffix" ] \
       && [ -z "${compgen_actions[*]}" ] && [ "$compl_plusdirs" != 1 ] && (( ${#COMPREPLY[@]} )); then
        if [ "$compl_filenames" = 1 ]; then
            printf '%s\n' "${COMPREPLY[@]}" \
                | _bash_completion_quote_filenames "$@" \
                | _bash_completion_dir_marker
        else
            printf '%s\n' "${COMPREPLY[@]}"
        fi
        return
    fi

    (
        (
            if [ -n "${compgen_actions[*]}" ]; then
                compgen "${compgen_actions[@]}" -- "$2"
            fi

            if [ -n "$compl_globpat" ]; then
                printf %s\\n "$compl_globpat"
            fi

            if [ -n "$compl_wordlist" ]; then
                eval "printf '%s\\n' $compl_wordlist"
            fi

            if [ -n "${COMPREPLY[*]}" ]; then
                printf %s\\n "${COMPREPLY[@]}"
            fi

            if [ -n "$compl_command" ]; then
                (
                    unset COMP_WORDS COMP_CWORD
                    export COMP_LINE="$COMP_LINE" COMP_POINT="$COMP_POINT" COMP_KEY="$COMP_KEY" COMP_TYPE="$COMP_TYPE"
                    eval "$compl_command"
                )
            fi

            printf '\n'
        ) | _bash_completion_apply_xfilter "$compl_xfilter" \
          | _bash_completion_unbuffered_awk '$0!=""' 'sub(find, replace)' -vfind='.*' -vreplace="$replace" \
          | if IFS= read -r line || (( ${#COMPREPLY[@]} )); then
              ([[ -z "$line" ]] || printf '%s\n' "$line"; cat) | _bash_completion_quote_filenames "$@"
            else
                # got no results
                local compgen_opts=()
                [ "$compl_bashdefault" = 1 ] && compgen_opts+=( -o bashdefault )
                [ "$compl_default" = 1 ] && compgen_opts+=( -o default )
                [ "$compl_dirnames" = 1 ] && compgen_opts+=( -o dirnames )
                # don't open a second picker
                if [ -n "${compgen_opts[*]}" ]; then
                    # these are all filenames
                    printf 'compl_filenames=1\n'>&"${__evaled}"
                    compgen "${compgen_opts[@]}" -- "$2" \
                    | compl_filenames=1 _bash_completion_quote_filenames "$@" \
                    | _bash_completion_dir_marker
                fi
            fi

        if [ "$compl_plusdirs" = 1 ]; then
            compgen -o dirnames -- "$2" \
            | compl_filenames=1 _bash_completion_quote_filenames "$@" \
            | _bash_completion_dir_marker
        fi
    ) \
    | "$dir_marker"
}

_bash_completion_apply_xfilter() {
    if [ -z "$1" ]; then
        cat
        return
    fi

    local pattern line word="$cur"
    word="${word//\//\\/}"
    word="${word//&/\\&}"
    # replace any unescaped & with the word being completed
    pattern="$("$_bash_completion_sed" 's/\(\(^\|[^\]\)\(\\\\\)*\)&/\1'"$word"'/g' <<<"${1:1}")"

    if [ "${1::1}" = ! ]; then
        while IFS= read -r line; do [[ "$line" == $pattern ]] && printf '%s\n' "$line"; done
    elif [ -n "$1" ]; then
        while IFS= read -r line; do [[ "$line" != $pattern ]] && printf '%s\n' "$line"; done
    fi
}

_bash_completion_dir_marker() {
    local line expanded
    while IFS= read -r line; do
        expanded="$line"

        # adapted from __expand_tilde_by_ref
        if [[ "$expanded" == \~* ]]; then
            eval "$(printf expanded=~%q "${expanded:1}")"
        fi

        if [[ "$compl_noquote" != 1 && "$expanded" == *\\* ]]; then
            expanded="$("$_bash_completion_sed" -r 's/\\(.)/\1/g' <<<"$expanded")"
        fi

        [ -d "$expanded" ] && line="${line%/}/"
        printf '%s\n' "$line"
    done
}

_bash_completion_quote_filenames() {
    if [ "$compl_noquote" != 1 -a "$compl_filenames" = 1 ]; then
        local IFS line
        while IFS= read -r line; do
            if [ "${line::1}" = '~' ]; then
                printf '~%q\n' "${line:1}"
            else
                printf '%q\n' "$line"
            fi
        done
    else
        cat
    fi
}

_bash_completion_compopt() {
    while [ "$#" -gt 0 ]; do
        local val
        if [ "$1" = -o ]; then
            val=1
        elif [ "$1" = +o ]; then
            val=0
        else
            break
        fi

        if [[ "$2" =~ bashdefault|default|dirnames|filenames|noquote|nosort|nospace|plusdirs ]]; then
            eval "compl_$2=$val"
        fi
        shift 2
    done
}
