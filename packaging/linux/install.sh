#!/bin/sh
# Usage: ./install.sh [--prefix DIR] [--no-links] [--no-desktop] [--force]
#
# Per-user install of System Budget Studio from the extracted bundle folder. No administrator
# rights, no network. Installs to $HOME/.local/opt/system-budget-studio by default, links
# `system-budget-studio` and `budget` into $HOME/.local/bin, and adds an application-menu entry.
# An existing command of yours with one of these names is not replaced unless you pass --force.
# Everything it creates is recorded in <prefix>/install-manifest.txt, which uninstall.sh uses.
set -eu

prefix="${HOME}/.local/opt/system-budget-studio"
links=1
desktop=1
force=0
while [ $# -gt 0 ]; do
    case "$1" in
        --prefix) [ $# -ge 2 ] || { echo "--prefix needs a folder" >&2; exit 2; }; prefix="$2"; shift 2 ;;
        --no-links) links=0; shift ;;
        --no-desktop) desktop=0; shift ;;
        --force) force=1; shift ;;
        -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done

# The folder this script lives in, also when it was started through a symlink.
self="$0"
if command -v readlink >/dev/null 2>&1 && resolved="$(readlink -f "$self" 2>/dev/null)"; then
    self="$resolved"
fi
src="$(cd "$(dirname "$self")" && pwd -P)"
if [ ! -x "$src/system-budget-studio" ] || [ ! -x "$src/budget" ]; then
    echo "Run this script from the extracted bundle folder (system-budget-studio and budget are missing)." >&2
    exit 1
fi

# One canonical absolute prefix, so links and the manifest never depend on how it was typed.
mkdir -p "$prefix"
prefix="$(cd "$prefix" && pwd -P)"
case "$prefix" in
    /|"$HOME"|"$(cd "$HOME" && pwd -P)") echo "Refusing to install into $prefix" >&2; exit 1 ;;
esac
if [ "$src" = "$prefix" ]; then
    echo "This is the installed copy. To reinstall or upgrade, run install.sh from the downloaded bundle folder." >&2
    exit 1
fi

bindir="${XDG_BIN_HOME:-$HOME/.local/bin}"
marker="$prefix/install-manifest.txt"
if [ ! -f "$marker" ] && [ -n "$(ls -A "$prefix" 2>/dev/null)" ]; then
    echo "$prefix exists and was not created by this installer; choose another --prefix." >&2
    exit 1
fi

if [ -f "$marker" ]; then
    # Upgrade: take the old installation away completely (nothing of the old version is mixed
    # in). This does not depend on the old uninstall.sh still being there.
    echo "Replacing the existing installation in $prefix"
    while IFS=' ' read -r kind path; do
        if [ "$kind" = "link" ]; then
            if [ -L "$path" ] && [ "$(readlink "$path")" = "$prefix/$(basename "$path")" ]; then
                rm -f "$path"
            fi
        elif [ "$kind" = "file" ]; then
            rm -f "$path"
        fi
    done < "$marker"
    find "$prefix" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
fi

cp -a "$src/." "$prefix/"
manifest="$prefix/install-manifest.txt"
: > "$manifest"

if [ "$links" = 1 ]; then
    mkdir -p "$bindir"
    for name in system-budget-studio budget; do
        link="$bindir/$name"
        if { [ -e "$link" ] || [ -L "$link" ]; } && [ "$force" = 0 ]; then
            echo "Not replacing the existing $link (use --force to replace it)." >&2
            continue
        fi
        ln -sf "$prefix/$name" "$link"
        echo "link $link" >> "$manifest"
    done
fi

if [ "$desktop" = 1 ]; then
    appdir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
    mkdir -p "$appdir"
    entry="$appdir/system-budget-studio.desktop"
    # Desktop Entry rules: a quoted Exec argument escapes " ` $ and \ with a backslash, the
    # string value then doubles every backslash, and a literal % is written %%.
    quoted="$(printf '%s' "$prefix/system-budget-studio" \
        | sed -e 's/\\/\\\\\\\\/g' -e 's/["`$]/\\\\&/g' -e 's/%/%%/g')"
    {
        echo "[Desktop Entry]"
        echo "Type=Application"
        echo "Name=System Budget Studio"
        echo "Comment=Satellite power, mass, thermal and link budgets (offline)"
        printf 'Exec="%s" %%f\n' "$quoted"  # printf: echo would interpret the backslashes
        echo "Terminal=false"
        echo "Categories=Science;Engineering;"
    } > "$entry"
    echo "file $entry" >> "$manifest"
fi

echo "Installed to $prefix"
if ! "$prefix/system-budget-studio" --self-test; then
    echo "The self-test failed. The installation is in place but may be incomplete." >&2
    exit 1
fi
[ "$links" = 1 ] && echo "Commands: $bindir/system-budget-studio and $bindir/budget (add $bindir to PATH if needed)."
exit 0
