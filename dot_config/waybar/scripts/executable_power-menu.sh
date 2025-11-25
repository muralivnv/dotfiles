#!/bin/bash

options=' Power Off\n Restart\n Lock\n󰒲 Suspend'

chosen=$(echo -e "$options" | fuzzel --dmenu --lines=4)

case "$chosen" in
    " Power Off")
        shutdown -h now
        ;;
    " Restart")
        reboot
        ;;
    " Lock")
        gtklock
        ;;
    "󰒲 Suspend")
        setsid gtklock &/dev/null 2>&1 & systemctl suspend
        ;;
esac


