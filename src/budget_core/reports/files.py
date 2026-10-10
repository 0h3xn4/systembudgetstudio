"""Writing output files safely.

File names are often built from project text (mission phases, thermal case names, link ids), so
every name is reduced to a plain file name before it is joined to the output folder. A file is
written to a temporary name in the same folder and moved into place, so a failure never leaves a
half-written file, and a symlink at the target is replaced rather than followed.
"""

from __future__ import annotations

import contextlib
import os
import re
from pathlib import Path

MAX_NAME = 120
_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}
_BAD = re.compile(r"[^\w.\-]+", re.UNICODE)


class OutputError(Exception):
    """The outputs cannot be written; the message is plain language without project content."""


def safe_name(name: str) -> str:
    """A plain file name: letters, digits, '.', '-' and '_' only, no leading dot, never a Windows
    device name, at most MAX_NAME characters (the extension is kept)."""
    base = _BAD.sub("_", name).lstrip(".") or "_"  # separators become '_': never a folder
    stem, dot, ext = base.rpartition(".")
    stem, ext = (stem, dot + ext) if dot and stem else (base, "")
    if stem.lower() in _RESERVED:
        stem = "_" + stem
    if len(stem) + len(ext) > MAX_NAME:
        stem = stem[: max(MAX_NAME - len(ext), 1)]
    return stem + ext


def _discard(path: Path) -> None:
    with contextlib.suppress(OSError):
        path.unlink(missing_ok=True)


def write_file(folder: Path, name: str, data: bytes | str) -> Path:
    """Write `data` as `folder/<safe name>` atomically and return the path."""
    folder = Path(folder)
    if not isinstance(data, bytes | str):
        raise TypeError("data must be text or bytes")
    payload = data if isinstance(data, bytes) else data.encode("utf-8")
    target = folder / safe_name(name)
    temporary = folder / f".{target.name}.{os.getpid()}.tmp"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        temporary.write_bytes(payload)
        os.replace(temporary, target)
    except OSError as exc:
        _discard(temporary)
        raise OutputError(
            "A file could not be written. Check that the output folder exists, is a folder "
            "and that you may write to it."
        ) from exc
    except BaseException:
        _discard(temporary)
        raise
    return target
