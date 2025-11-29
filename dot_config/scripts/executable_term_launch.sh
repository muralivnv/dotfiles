#!/usr/bin/env bash

get_focused_id() {
    swaymsg -t get_tree | jq -r '
        recurse(.nodes[], .floating_nodes[]) |
        select(.focused==true) |
        .id
    '
}

PARENT_WINDOW_ID=$(get_focused_id)

# Build the Command String
    # All arguments passed to this script are treated as the command to run (e.g., 'bash /path/to/script.sh').
    # We combine them back into a single quoted string, then append the parent ID.
CMD_TO_EXEC=""
for arg in "$@"; do
    CMD_TO_EXEC+="\"${arg}\" "
done

footclient -E --no-wait -D "$(pwd)" -e bash -ic "${CMD_TO_EXEC} --parent-id ${PARENT_WINDOW_ID} || { echo -e \"\nCommand failed (Exit code: \$?): Press ENTER to close...\"; read -r; }"
