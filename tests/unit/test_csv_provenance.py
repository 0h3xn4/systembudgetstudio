"""Every set of CSV files carries a provenance file (spec constraint 19)."""

from __future__ import annotations

import csv
from pathlib import Path

from budget_core.provenance import Provenance
from budget_core.reports.csvutil import provenance_csv
from budget_core.reports.document import Column, ReportDocument, Section, Table
from budget_core.reports.run import BudgetOutput, write_outputs

PROV = Provenance(
    tool="System Budget Studio",
    tool_version="0.1.0",
    python_version="3.13",
    libraries=(("pint", "0.26"),),
    project_name="Demo",
    project_revision="r1",
    scenario="static (no scenario)",
    generated="2026-01-02T03:04:05Z",
    user="Test User",
)


def output() -> BudgetOutput:
    table = Table("T", (Column("Item"),), (("a",),))
    document = ReportDocument("R", PROV, (Section("S", "S", tables=(table,)),))
    return BudgetOutput(
        "demo", document, None, PROV, (("demo_table.csv", "Item\na\n"),), json_text="{}\n"
    )


def test_provenance_csv_lists_every_item_once() -> None:
    rows = list(csv.reader(provenance_csv(PROV).splitlines()))
    assert rows[0] == ["item", "value"]
    assert ["Project revision", "r1"] in rows and [
        "Generated (UTC)",
        "2026-01-02T03:04:05Z",
    ] in rows
    assert len(rows) == 1 + len(PROV.rows())


def test_provenance_csv_is_deterministic() -> None:
    assert provenance_csv(PROV) == provenance_csv(PROV)


def test_csv_outputs_come_with_their_provenance_file(tmp_path: Path) -> None:
    written = write_outputs([output()], tmp_path, {"csv"})
    assert sorted(p.name for p in written) == ["demo_provenance.csv", "demo_table.csv"]
    assert (tmp_path / "demo_provenance.csv").read_text(encoding="utf-8") == provenance_csv(PROV)


def test_no_provenance_file_without_csv_output(tmp_path: Path) -> None:
    written = write_outputs([output()], tmp_path, {"json"})
    assert [p.name for p in written] == ["demo.json"]


def test_scenario_files_come_with_provenance(tmp_path: Path) -> None:
    from budget_core.scenario.export import write_scenario_outputs
    from tests.power_helpers import synthetic_env, synthetic_run

    run = synthetic_run(synthetic_env(600.0, 60.0, [(100.0, 200.0)]))
    names = {p.name for p in write_scenario_outputs(run, PROV, tmp_path)}
    assert f"{run.scenario_id}_provenance.csv" in names
