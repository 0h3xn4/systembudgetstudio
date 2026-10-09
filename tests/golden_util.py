"""Content dumps of report files for golden tests (compressed bytes differ between zlib builds)."""

from __future__ import annotations

import io
import os
from pathlib import Path

from openpyxl import load_workbook
from pypdf import PdfReader

GOLDEN_DIR = Path(__file__).parent / "golden"


def dump_xlsx(data: bytes, max_rows: int | None = None) -> str:
    wb = load_workbook(io.BytesIO(data))
    lines: list[str] = []
    for ws in wb:
        lines.append(f"## sheet {ws.title} rows={ws.max_row} cols={ws.max_column}")
        for i, row in enumerate(ws.iter_rows(values_only=True), 1):
            if max_rows is not None and i > max_rows:
                lines.append("...")
                break
            cells = ["" if v is None else repr(v) for v in row]
            if any(cells):
                lines.append(f"{i}: " + " | ".join(cells))
    return "\n".join(lines) + "\n"


def dump_pdf(data: bytes, max_pages: int | None = None) -> str:
    reader = PdfReader(io.BytesIO(data))
    lines = [f"pages={len(reader.pages)}"]
    for number, page in enumerate(reader.pages, 1):
        if max_pages is not None and number > max_pages:
            lines.append("...")
            break
        lines.append(f"## page {number}")
        lines.append((page.extract_text() or "").strip())
    return "\n".join(lines) + "\n"


def check_golden(name: str, actual: str) -> None:
    path = GOLDEN_DIR / name
    if os.environ.get("UPDATE_GOLDEN") == "1":
        path.write_text(actual, encoding="utf-8", newline="\n")
        return
    assert path.exists(), f"missing golden file {name}; run with UPDATE_GOLDEN=1"
    assert actual == path.read_text(encoding="utf-8"), (
        f"{name} differs; if intended, regenerate with UPDATE_GOLDEN=1 and review the diff"
    )
