from __future__ import annotations

import json
from dataclasses import replace

import pytest

from budget_core.compare import (
    ComparisonResult,
    compare_documents,
    comparison_output,
)
from budget_core.provenance import Provenance
from budget_core.reports.document import Column, ReportDocument, Section, Table

PROV = Provenance(
    tool="System Budget Studio",
    tool_version="0",
    python_version="3",
    libraries=(),
    project_name="P",
    project_revision="1",
    scenario="static (no scenario)",
    generated="2026-01-02T03:04:05Z",
    user="Test User",
)

COLS = (Column("Mode"), Column("Load", "number", 3, "W"), Column("Share", "percent", 3))


def doc(
    rows: list[tuple[object, ...]], banner: str = "", prov: Provenance = PROV
) -> ReportDocument:
    table = Table("Power by mode", COLS, tuple(rows))  # type: ignore[arg-type]
    section = Section("Power budget", "Power", tables=(table,))
    return ReportDocument("Report", prov, (section,), banner)


def run(a: ReportDocument, b: ReportDocument, **kw: object) -> ComparisonResult:
    return compare_documents("Power", a, b, "rev 1", "rev 2", **kw)  # type: ignore[arg-type]


def test_identical_documents_have_no_differences() -> None:
    a = doc([("Nominal", 10.0, 0.5), ("Safe", 4.0, 0.25)])
    result = run(a, a)
    assert result.differences == ()
    assert result.compared == 4  # two rows x two value columns
    assert result.unchanged == 4


def test_changed_number_reports_change_and_percent() -> None:
    result = run(doc([("Nominal", 10.0, 0.5)]), doc([("Nominal", 12.5, 0.5)]))
    (d,) = result.differences
    assert (d.row, d.quantity, d.value_a, d.value_b) == ("Nominal", "Load", "10.000", "12.500")
    assert d.change == "+2.500 W"
    assert d.change_percent == "+25.0 %"
    assert d.status == "changed"


def test_difference_below_displayed_precision_is_not_reported() -> None:
    result = run(doc([("Nominal", 10.0, 0.5)]), doc([("Nominal", 10.0000004, 0.5)]))
    assert result.differences == ()


def test_percent_column_change_is_in_percentage_points() -> None:
    result = run(doc([("Nominal", 10.0, 0.5)]), doc([("Nominal", 10.0, 0.6)]))
    (d,) = result.differences
    assert d.quantity == "Share"
    assert d.change == "+10.0 pp"
    assert d.change_percent == "+20.0 %"


def test_zero_baseline_has_no_percent() -> None:
    result = run(doc([("Nominal", 0.0, 0.5)]), doc([("Nominal", 1.0, 0.5)]))
    assert result.differences[0].change_percent == ""


def test_added_and_removed_rows() -> None:
    result = run(doc([("Nominal", 10.0, 0.5), ("Safe", 4.0, 0.1)]), doc([("Nominal", 10.0, 0.5)]))
    (d,) = result.differences
    assert (d.row, d.status) == ("Safe", "removed")
    result = run(
        doc([("Nominal", 10.0, 0.5)]), doc([("Nominal", 10.0, 0.5), ("Eclipse", 3.0, 0.1)])
    )
    (d,) = result.differences
    assert (d.row, d.status) == ("Eclipse", "added")


def test_n_a_transitions_are_named() -> None:
    result = run(doc([("Nominal", None, 0.5)]), doc([("Nominal", 3.0, 0.5)]))
    assert result.differences[0].status == "now computed"
    assert result.differences[0].value_a == "n/a"
    result = run(doc([("Nominal", 3.0, 0.5)]), doc([("Nominal", None, 0.5)]))
    assert result.differences[0].status == "now n/a"
    assert result.differences[0].change == ""


def test_text_change_is_reported_without_arithmetic() -> None:
    cols = (Column("Id"), Column("Status"))
    a = ReportDocument("R", PROV, (Section("S", "S", tables=(Table("T", cols, (("u1", "ok"),)),)),))
    b = ReportDocument(
        "R", PROV, (Section("S", "S", tables=(Table("T", cols, (("u1", "exceeded"),)),)),)
    )
    (d,) = run(a, b).differences
    assert (d.value_a, d.value_b, d.change, d.status) == ("ok", "exceeded", "", "changed")


def test_duplicate_row_keys_are_matched_in_order() -> None:
    a = doc([("Nominal", 1.0, 0.1), ("Nominal", 2.0, 0.1)])
    b = doc([("Nominal", 1.0, 0.1), ("Nominal", 3.0, 0.1)])
    (d,) = run(a, b).differences
    assert d.row == "Nominal #2"
    assert d.value_b == "3.000"


def test_tables_only_on_one_side_are_listed() -> None:
    a = doc([("Nominal", 1.0, 0.1)])
    b = replace(
        a, sections=(*a.sections, Section("Extra", "Extra", tables=(a.sections[0].tables[0],)))
    )
    result = run(a, b)
    assert [(m.section, m.status) for m in result.unmatched] == [("Extra", "added")]


def test_skipped_tables_are_not_compared() -> None:
    cols = (Column("Item"), Column("Value"))
    noisy = Section(
        "Problems", "Problems", tables=(Table("Problems and open items", cols, (("a", "b"),)),)
    )
    a = ReportDocument("R", PROV, (noisy,))
    b = ReportDocument(
        "R", PROV, (replace(noisy, tables=(Table(noisy.tables[0].title, cols, (("a", "c"),)),)),)
    )
    assert run(a, b).differences == ()


def test_truncation_is_stated_never_silent() -> None:
    a = doc([(f"m{i}", float(i), 0.1) for i in range(30)])
    b = doc([(f"m{i}", float(i) + 1.0, 0.1) for i in range(30)])
    result = run(a, b, max_rows=10)
    assert len(result.differences) == 10
    assert result.truncated == 20


def test_output_document_structure_and_files() -> None:
    a = doc([("Nominal", 10.0, 0.5)], banner="INCOMPLETE x")
    b = doc([("Nominal", 12.0, 0.5)], prov=replace(PROV, project_revision="2"))
    out = comparison_output([run(a, b)], "rev 1", "rev 2", PROV, "Revision comparison")
    assert out.prefix == "compare"
    assert out.document.banner  # one side is incomplete
    titles = [s.title for s in out.document.sections]
    assert titles[0] == "Summary"
    assert "Differences: Power" in titles
    summary = out.document.sections[0]
    assert any("1 value" in p for p in summary.paragraphs)
    assert out.csv_files[0][0] == "compare_differences.csv"
    assert "Nominal" in out.csv_files[0][1]
    assert out.json_text is not None
    assert json.loads(out.json_text)["differences"][0]["status"] == "changed"


def test_output_is_deterministic() -> None:
    a, b = doc([("Nominal", 10.0, 0.5)]), doc([("Nominal", 12.0, 0.5)])
    one = comparison_output([run(a, b)], "a", "b", PROV, "T")
    two = comparison_output([run(a, b)], "a", "b", PROV, "T")
    assert one.document == two.document
    assert one.json_text == two.json_text


@pytest.mark.parametrize("kind", ["xlsx", "pdf", "docx"])
def test_comparison_renders(kind: str, tmp_path: object) -> None:
    from pathlib import Path

    from budget_core.reports.run import write_outputs

    a, b = doc([("Nominal", 10.0, 0.5)]), doc([("Nominal", 12.0, 0.5)])
    out = comparison_output([run(a, b)], "a", "b", PROV, "T")
    (path,) = write_outputs([out], Path(str(tmp_path)), {kind})
    assert path.stat().st_size > 1000
