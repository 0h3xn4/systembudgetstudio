#!/bin/sh
# Removes what install.sh created: the program folder, the command links and the menu entry.
# Your projects, reports and settings are not touched (the tool stores none outside them).
# Usage: uninstall.sh [--quiet]
set -eu

quiet=0
[ "${1:-}" = "--quiet" ] && quiet=1

prefix="$(cd "$(dirname "$0")" && pwd)"
manifest="$prefix/install-manifest.txt"
if [ ! -f "$manifest" ]; then
    echo "$prefix has no install-manifest.txt; it was not installed by install.sh." >&2
    exit 1
fi

while IFS=' ' read -r kind path; do
    if [ "$kind" = "link" ]; then
        # only remove a link that still points into this installation
        if [ -L "$path" ] && [ "$(readlink "$path")" = "$prefix/$(basename "$path")" ]; then
            rm -f "$path"
        fi
    elif [ "$kind" = "file" ]; then
        rm -f "$path"
    fi
done < "$manifest"

# The script is running from inside the folder it removes; that works because the shell has read it.
cd /
rm -rf "$prefix"
[ "$quiet" = 1 ] || echo "Removed $prefix"
exit 0
