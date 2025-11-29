#!/bin/sh

# The standard location for the Sway IPC socket uses the user ID and the Sway PID.
# We use 'pgrep -f ^/usr/bin/sway' to find the PID of the main Sway process.
export SWAYSOCK="/run/user/$(id -u)/sway-ipc.$(id -u).$(pgrep -f '^/usr/bin/sway').sock"

# Execute waybar
exec /usr/bin/waybar
