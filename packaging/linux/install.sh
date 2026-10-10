#!/bin/sh
# Per-user install of System Budget Studio from the extracted bundle folder. No administrator
# rights, no network. Usage: ./install.sh [--prefix DIR] [--no-links] [--no-desktop]
#
# Installs to $HOME/.local/opt/system-budget-studio by default, links `system-budget-studio` and
# `budget` into $HOME/.local/bin, and adds an application-menu entry. Everything it creates is
# recorded in <prefix>/install-manifest.txt, which uninstall.sh uses.
set -eu

prefix="${HOME}/.local/opt/system-budget-studio"
links=1
desktop=1
while [ $# -gt 0 ]; do
    case "$1" in
        --prefix) [ $# -ge 2 ] || { echo "--prefix needs a folder" >&2; exit 2; }; prefix="$2"; shift 2 ;;
        --no-links) links=0; shift ;;
        --no-desktop) desktop=0; shift ;;
        -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done

src="$(cd "$(dirname "$0")" && pwd)"
if [ ! -x "$src/system-budget-studio" ] || [ ! -x "$src/budget" ]; then
    echo "Run this script from the extracted bundle folder (system-budget-studio and budget are missing)." >&2
    exit 1
fi
case "$prefix" in
    /|"$HOME"|"$HOME"/) echo "Refusing to install into $prefix" >&2; exit 1 ;;
esac

marker="$prefix/install-manifest.txt"
if [ -e "$prefix" ] && [ ! -f "$marker" ]; then
    if [ -n "$(ls -A "$prefix" 2>/dev/null)" ]; then
        echo "$prefix exists and was not created by this installer; choose another --prefix." >&2
        exit 1
    fi
fi
if [ -f "$marker" ]; then  # upgrade: remove the old program files first, keep nothing else
    echo "Replacing the existing installation in $prefix"
    "$prefix/uninstall.sh" --quiet || true
fi

mkdir -p "$prefix"
cp -a "$src/." "$prefix/"
manifest="$prefix/install-manifest.txt"
: > "$manifest"

bindir="${XDG_BIN_HOME:-$HOME/.local/bin}"
if [ "$links" = 1 ]; then
    mkdir -p "$bindir"
    for name in system-budget-studio budget; do
        ln -sf "$prefix/$name" "$bindir/$name"
        echo "link $bindir/$name" >> "$manifest"
    done
fi
if [ "$desktop" = 1 ]; then
    appdir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
    mkdir -p "$appdir"
    entry="$appdir/system-budget-studio.desktop"
    cat > "$entry" <<DESKTOP
[Desktop Entry]
Type=Application
Name=System Budget Studio
Comment=Satellite power, mass, thermal and link budgets (offline)
Exec="$prefix/system-budget-studio" %f
Terminal=false
Categories=Science;Engineering;
DESKTOP
    echo "file $entry" >> "$manifest"
fi

echo "Installed to $prefix"
if ! "$prefix/system-budget-studio" --self-test; then
    echo "The self-test failed. The installation is in place but may be incomplete." >&2
    exit 1
fi
[ "$links" = 1 ] && echo "Commands: $bindir/system-budget-studio and $bindir/budget (add $bindir to PATH if needed)."
exit 0
