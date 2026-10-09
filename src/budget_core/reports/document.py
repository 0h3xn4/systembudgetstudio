"""Neutral report model: every renderer (XLSX, PDF, later DOCX) draws the same document."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from budget_core.provenance import Provenance

Cell = str | float | None  # None renders as "n/a"
ColumnKind = Literal["text", "number", "percent"]
NA = "n/a"


@dataclass(frozen=True)
class Column:
    header: str
    kind: ColumnKind = "text"
    decimals: int = 3
    unit: str = ""


@dataclass(frozen=True)
class Table:
    title: str
    columns: tuple[Column, ...]
    rows: tuple[tuple[Cell, ...], ...]
    note: str = ""
    emphasise_last_row: bool = False


@dataclass(frozen=True)
class Figure:
    """A picture (PNG bytes) with a title; `alt` describes it for readers who cannot see it."""

    title: str
    png: bytes
    alt: str = ""


@dataclass(frozen=True)
class Section:
    title: str
    sheet_name: str  # short unique name for spreadsheet tabs (max 31 characters)
    paragraphs: tuple[str, ...] = ()
    tables: tuple[Table, ...] = ()
    figures: tuple[Figure, ...] = ()


@dataclass(frozen=True)
class ReportDocument:
    title: str
    provenance: Provenance
    sections: tuple[Section, ...] = field(default_factory=tuple)
    banner: str = ""  # shown first when results are incomplete


def format_cell(value: Cell, column: Column) -> str:
    if value is None:
        return NA
    if isinstance(value, str):
        return value
    if column.kind == "percent":
        return f"{value * 100:.{max(column.decimals - 2, 0)}f} %"
    return f"{value:.{column.decimals}f}"
