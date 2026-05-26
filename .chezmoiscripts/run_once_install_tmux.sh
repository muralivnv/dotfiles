#!/usr/bin/env bash
set -euo pipefail

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
cd "$TMP_DIR"
mkdir -p "$TMP_DIR/libs"

sudo apt update
sudo apt install -y automake autoconf libtool bison byacc libssl-dev pkg-config curl git wget

############
# LIBEVENT #
############
wget -O libevent.tar.gz https://github.com/libevent/libevent/archive/refs/tags/release-2.1.12-stable.tar.gz
tar xvzf libevent.tar.gz
cd $(find . -maxdepth 1 -type d -name "libevent-*" -printf '%P\n')

echo "Building libevent ..."
./autogen.sh
./configure --prefix="$TMP_DIR/libs" --disable-shared
make -j$(nproc)
make install
cd ..

###########
# NCURSES #
###########
wget -O ncurses.tar.gz http://ftp.gnu.org/gnu/ncurses/ncurses-6.5.tar.gz
tar xvzf ncurses.tar.gz
cd $(find . -maxdepth 1 -type d -name "ncurses-*" -printf '%P\n')

echo "Building ncurses ..."
./configure --prefix="$TMP_DIR/libs" \
    --with-default-terminfo-dir=/usr/share/terminfo \
    --with-terminfo-dirs="/usr/share/terminfo" \
    --enable-widec \
    --enable-pc-files \
    --with-pkg-config-libdir="$TMP_DIR/libs/lib/pkgconfig"

make libs -j$(nproc)
make install.libs
make install.includes
cd ..

########
# TMUX #
########
wget -O tmux.tar.gz https://github.com/tmux/tmux/archive/449f255f3ef0167c6d226148cdaabac70686dde9.tar.gz
tar xvzf tmux.tar.gz
cd $(find . -maxdepth 1 -type d -name "tmux-*" -printf '%P\n')

# patch for non-blocking popup
curl -L https://patch-diff.githubusercontent.com/raw/tmux/tmux/pull/4379.diff -o 4379.diff
git apply 4379.diff

echo "Building tmux ..."
./autogen.sh

# Export local pkgconfig so tmux can easily discover ncursesw and libevent
export PKG_CONFIG_PATH="$TMP_DIR/libs/lib/pkgconfig:${PKG_CONFIG_PATH:-}"

./configure --prefix="$HOME/.local" \
    --enable-static \
    CPPFLAGS="-I$TMP_DIR/libs/include -I$TMP_DIR/libs/include/ncursesw" \
    LDFLAGS="-L$TMP_DIR/libs/lib" \
    LIBEVENT_CFLAGS="-I$TMP_DIR/libs/include" \
    LIBEVENT_LIBS="-L$TMP_DIR/libs/lib -levent"

make -j$(nproc)
make install
echo "Tmux installation complete."
