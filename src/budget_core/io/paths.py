"""Confine every path named inside a project file to the project folder.

A project file such as a link (`pattern_file`) or a scenario (`import_dir`) names other files. A
project can come from someone else, so those names must not make the tool read anything outside
the project folder: no absolute paths, no `..`, no symlink that leads out.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath


def resolve_inside(root: Path, rel: str) -> Path | None:
    """The path `rel` names below `root`, or None when it is empty, absolute, or leads outside
    `root` (through `..` or a symlink). The target does not need to exist."""
    if not rel or "\x00" in rel:
        return None
    windows = PureWindowsPath(rel)
    if PurePosixPath(rel).is_absolute() or windows.is_absolute() or windows.drive or windows.root:
        return None
    try:
        base = Path(root).resolve()
        target = (base / rel).resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    return target if target.is_relative_to(base) else None
