"""Comparison of two budgets (two project revisions, or two scenarios of one project).

The comparison works on the neutral report documents the budgets already produce, so one
implementation serves the power, mass, thermal and link budgets and every scenario result.
Tables are matched by section and table title, rows by their first column, values by column
header. Only values that differ *as displayed* are reported (a change below the displayed
precision is not a change a reader could see). Nothing is dropped silently: rows beyond the
display limit are counted and stated.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Literal

from budget_core.provenance import Provenance
from budget_core.reports.common import BANNER, sheet_name
from budget_core.reports.document import (
    Cell,
    Column,
    ReportDocument,
    Section,
    Table,
    format_cell,
)
from budget_core.reports.run import BudgetOutput

Status = Literal["changed", "added", "removed", "now computed", "now n/a"]

SKIP_SECTIONS = frozenset({"Problems", "Provenance"})
SKIP_TABLES = frozenset({"Equations"})
DEFAULT_MAX_ROWS = 200
WHOLE_ROW = "(whole row)"


@dataclass(frozen=True)
class Difference:
    section: str
    table: str
    row: str
    quantity: str
    value_a: str
    value_b: str
    change: str
    change_percent: str
    status: Status


@dataclass(frozen=True)
class Unmatched:
    """A section (`table` empty) or table that exists on one side only."""

    section: str
    table: str
    status: Literal["added", "removed"]


@dataclass(frozen=True)
class ComparisonResult:
    name: str
    label_a: str
    label_b: str
    differences: tuple[Difference, ...]
    compared: int  # value cells present on both sides
    unchanged: int
    truncated: int  # differences beyond the display limit
    unmatched: tuple[Unmatched, ...]
    incomplete_a: bool
    incomplete_b: bool
    provenance_a: Provenance
    provenance_b: Provenance


def _is_number(value: Cell) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _keys(table: Table) -> list[str]:
    """Row keys: the first cell as displayed; repeated keys get ' #2', ' #3', ... in order."""
    seen: dict[str, int] = {}
    keys: list[str] = []
    for row in table.rows:
        base = format_cell(row[0], table.columns[0]) if row else ""
        seen[base] = seen.get(base, 0) + 1
        keys.append(base if seen[base] == 1 else f"{base} #{seen[base]}")
    return keys


def _headers(table: Table) -> list[str]:
    seen: dict[str, int] = {}
    names: list[str] = []
    for column in table.columns:
        seen[column.header] = seen.get(column.header, 0) + 1
        names.append(
            column.header if seen[column.header] == 1 else f"{column.header} #{seen[column.header]}"
        )
    return names


def _rounded(value: float, column: Column) -> float:
    decimals = max(column.decimals - 2, 0) if column.kind == "percent" else column.decimals
    scale = 100.0 if column.kind == "percent" else 1.0
    return round(value * scale, decimals) / scale


def _change(a: float, b: float, column: Column) -> tuple[str, str]:
    ra, rb = _rounded(a, column), _rounded(b, column)
    if column.kind == "percent":
        decimals = max(column.decimals - 2, 0)
        change = f"{(rb - ra) * 100:+.{decimals}f} pp"
    else:
        change = f"{rb - ra:+.{column.decimals}f}" + (f" {column.unit}" if column.unit else "")
    percent = f"{(rb - ra) / abs(ra) * 100:+.1f} %" if ra != 0.0 else ""
    return change, percent


def _compare_cell(column: Column, a: Cell, b: Cell) -> tuple[str, str, str, str, Status] | None:
    """(value_a, value_b, change, change %, status), or None when the displays are equal."""
    shown_a, shown_b = format_cell(a, column), format_cell(b, column)
    if shown_a == shown_b:
        return None
    if a is None:
        return shown_a, shown_b, "", "", "now computed"
    if b is None:
        return shown_a, shown_b, "", "", "now n/a"
    if _is_number(a) and _is_number(b):
        change, percent = _change(float(a), float(b), column)
        return shown_a, shown_b, change, percent, "changed"
    return shown_a, shown_b, "", "", "changed"


def _tables(doc: ReportDocument) -> dict[tuple[str, str], Table]:
    found: dict[tuple[str, str], Table] = {}
    for section in doc.sections:
        if section.title in SKIP_SECTIONS:
            continue
        for table in section.tables:
            if table.title not in SKIP_TABLES:
                found.setdefault((section.title, table.title), table)
    return found


def _compare_tables(
    section: str, table: str, a: Table, b: Table
) -> tuple[list[Difference], int, int]:
    """Differences, number of compared cells, number of unchanged cells of one table pair."""
    keys_a, keys_b = _keys(a), _keys(b)
    index_b = {key: i for i, key in enumerate(keys_b)}
    names_a, names_b = _headers(a), _headers(b)
    shared = [(names_a.index(n), names_b.index(n)) for n in names_a[1:] if n in names_b]
    differences: list[Difference] = []
    compared = unchanged = 0
    for i, key in enumerate(keys_a):
        j = index_b.get(key)
        if j is None:
            differences.append(
                Difference(section, table, key, WHOLE_ROW, "present", "absent", "", "", "removed")
            )
            continue
        for ca, cb in shared:
            outcome = _compare_cell(a.columns[ca], a.rows[i][ca], b.rows[j][cb])
            compared += 1
            if outcome is None:
                unchanged += 1
                continue
            value_a, value_b, change, percent, status = outcome
            differences.append(
                Difference(
                    section, table, key, names_a[ca], value_a, value_b, change, percent, status
                )
            )
    index_a = set(keys_a)
    for key in keys_b:
        if key not in index_a:
            differences.append(
                Difference(section, table, key, WHOLE_ROW, "absent", "present", "", "", "added")
            )
    return differences, compared, unchanged


def compare_documents(
    name: str,
    a: ReportDocument,
    b: ReportDocument,
    label_a: str,
    label_b: str,
    *,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> ComparisonResult:
    tables_a, tables_b = _tables(a), _tables(b)
    differences: list[Difference] = []
    unmatched: list[Unmatched] = []
    compared = unchanged = 0
    sections_a = {s for s, _ in tables_a}
    sections_b = {s for s, _ in tables_b}
    for (section, table), table_a in tables_a.items():
        table_b = tables_b.get((section, table))
        if table_b is None:
            if section in sections_b:
                unmatched.append(Unmatched(section, table, "removed"))
            continue
        found, n, same = _compare_tables(section, table, table_a, table_b)
        differences += found
        compared += n
        unchanged += same
    for section in sorted(sections_a - sections_b, key=lambda s: _first_index(a, s)):
        unmatched.append(Unmatched(section, "", "removed"))
    for section, table in tables_b:
        if (section, table) in tables_a:
            continue
        if section in sections_a:
            unmatched.append(Unmatched(section, table, "added"))
    for section in sorted(sections_b - sections_a, key=lambda s: _first_index(b, s)):
        unmatched.append(Unmatched(section, "", "added"))
    truncated = max(len(differences) - max_rows, 0)
    return ComparisonResult(
        name,
        label_a,
        label_b,
        tuple(differences[:max_rows]),
        compared,
        unchanged,
        truncated,
        tuple(unmatched),
        bool(a.banner),
        bool(b.banner),
        a.provenance,
        b.provenance,
    )


def _first_index(doc: ReportDocument, section: str) -> int:
    for i, s in enumerate(doc.sections):
        if s.title == section:
            return i
    return len(doc.sections)


# ---- output ------------------------------------------------------------------------------------

CSV_HEADER = [
    "comparison",
    "section",
    "table",
    "row",
    "quantity",
    "value_a",
    "value_b",
    "change",
    "change_percent",
    "status",
]


def _csv(results: Sequence[ComparisonResult]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for r in results:
        for d in r.differences:
            writer.writerow(
                [
                    r.name,
                    d.section,
                    d.table,
                    d.row,
                    d.quantity,
                    d.value_a,
                    d.value_b,
                    d.change,
                    d.change_percent,
                    d.status,
                ]
            )
    return buffer.getvalue()


def _json(results: Sequence[ComparisonResult], label_a: str, label_b: str, prov: Provenance) -> str:
    payload = {
        "label_a": label_a,
        "label_b": label_b,
        "compared": sum(r.compared for r in results),
        "unchanged": sum(r.unchanged for r in results),
        "truncated": sum(r.truncated for r in results),
        "differences": [
            {"comparison": r.name, **asdict(d)} for r in results for d in r.differences
        ],
        "unmatched": [{"comparison": r.name, **asdict(u)} for r in results for u in r.unmatched],
        "provenance": asdict(prov),
    }
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def _table_sections(result: ComparisonResult, used: set[str]) -> Section:
    columns = (
        Column("Row"),
        Column("Quantity"),
        Column(result.label_a),
        Column(result.label_b),
        Column("Change"),
        Column("Change (%)"),
        Column("Status"),
    )
    grouped: dict[tuple[str, str], list[Difference]] = {}
    for d in result.differences:
        grouped.setdefault((d.section, d.table), []).append(d)
    tables = tuple(
        Table(
            f"{section} — {table}",
            columns,
            tuple(
                (d.row, d.quantity, d.value_a, d.value_b, d.change, d.change_percent, d.status)
                for d in rows
            ),
        )
        for (section, table), rows in grouped.items()
    )
    paragraphs: list[str] = []
    if not result.differences:
        paragraphs.append("No differences.")
    paragraphs += [
        f"Present only in {result.label_a if u.status == 'removed' else result.label_b}: "
        + (f"{u.section} — {u.table}" if u.table else f"section {u.section}")
        + "."
        for u in result.unmatched
    ]
    if result.truncated:
        paragraphs.append(
            f"{_plural(result.truncated, 'further difference')} not shown here; the CSV and JSON "
            "exports list the first "
            f"{len(result.differences)} only. Narrow the comparison to a single budget to see them."
        )
    return Section(
        f"Differences: {result.name}",
        sheet_name(f"Differences {result.name}", used),
        paragraphs=tuple(paragraphs),
        tables=tables,
    )


def comparison_output(
    results: Sequence[ComparisonResult],
    label_a: str,
    label_b: str,
    provenance: Provenance,
    title: str,
) -> BudgetOutput:
    """The report document, CSV and JSON of a set of comparisons (`BudgetOutput` prefix
    `compare`)."""
    used: set[str] = set()
    changed = sum(1 for r in results for d in r.differences if d.quantity != WHOLE_ROW)
    rows = sum(1 for r in results for d in r.differences if d.quantity == WHOLE_ROW)
    compared = sum(r.compared for r in results)
    truncated = sum(r.truncated for r in results)
    summary_lines = [
        f"{label_a} compared with {label_b}.",
        f"{_plural(changed + truncated, 'value')} differ out of {compared} compared"
        + (f", and {_plural(rows, 'row')} exist on one side only" if rows else "")
        + ".",
        "Values that look equal at the displayed precision are not reported as differences.",
    ]
    side_rows: list[tuple[Cell, ...]] = []
    if results:
        first = results[0]
        pa, pb = first.provenance_a, first.provenance_b
        side_rows = [
            ("Project", pa.project_name, pb.project_name),
            ("Project revision", pa.project_revision, pb.project_revision),
            ("Scenario", pa.scenario, pb.scenario),
        ]
    summary = Section(
        "Summary",
        sheet_name("Summary", used),
        paragraphs=tuple(summary_lines),
        tables=(
            (
                Table(
                    "Compared sides",
                    (Column("Item"), Column(label_a), Column(label_b)),
                    tuple(side_rows),
                ),
            )
            if side_rows
            else ()
        ),
    )
    sections = [summary, *(_table_sections(r, used) for r in results)]
    sections.append(
        Section(
            "Provenance",
            sheet_name("Provenance", used),
            tables=(
                Table("Provenance", (Column("Item"), Column("Value")), tuple(provenance.rows())),
            ),
        )
    )
    incomplete = any(r.incomplete_a or r.incomplete_b for r in results)
    document = ReportDocument(title, provenance, tuple(sections), BANNER if incomplete else "")
    return BudgetOutput(
        "compare",
        document,
        results,
        provenance,
        (("compare_differences.csv", _csv(results)),),
        _json(results, label_a, label_b, provenance),
    )
