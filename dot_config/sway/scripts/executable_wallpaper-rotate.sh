#!/bin/bash

WALLPAPER_DIR="$HOME/Pictures/wallpapers"
MODE="fill"   # available options: fit, center, tile, fill

# select random image
FILE=$(find "$WALLPAPER_DIR" -type f \( -iname "*.jpg" -o -iname "*.png" \) | shuf -n 1)

swaymsg "output * bg \"$FILE\" $MODE"
