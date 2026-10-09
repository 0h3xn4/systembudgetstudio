"""Build and write budget outputs; shared by the CLI and the GUI."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from budget_core.mass.static_mass import StaticMassResult
from budget_core.model import Project
from budget_core.power.static_budget import StaticPowerResult
from budget_core.problems import Problem
from budget_core.provenance import Provenance
from budget_core.reports.document import ReportDocument
from budget_core.reports.export import mass_csv, result_csv, result_json
from budget_core.reports.mass_report import build_mass_report
from budget_core.reports.power_report import build_power_report

REPORT_KINDS = ("xlsx", "pdf", "json", "csv")


@dataclass(frozen=True)
class BudgetOutput:
    """Everything needed to write one budget's files: `<prefix>.xlsx|pdf|json` and CSV parts."""

    prefix: str
    document: ReportDocument
    result: Any
    provenance: Provenance
    csv_files: tuple[tuple[str, str], ...]  # (file name, text)


def power_output(
    project: Project,
    power: StaticPowerResult,
    provenance: Provenance,
    load_problems: Sequence[Problem] = (),
) -> BudgetOutput:
    document = build_power_report(project, power, provenance, list(load_problems))
    csvs = tuple((f"power_static_{m.mode_id}.csv", result_csv(m)) for m in power.modes)
    return BudgetOutput("power_static", document, power, provenance, csvs)


def mass_output(
    project: Project,
    mass: StaticMassResult,
    provenance: Provenance,
    load_problems: Sequence[Problem] = (),
) -> BudgetOutput:
    document = build_mass_report(project, mass, provenance, list(load_problems))
    csvs = tuple((f"mass_static_{p.phase}.csv", mass_csv(p)) for p in mass.phases)
    return BudgetOutput("mass_static", document, mass, provenance, csvs)


def write_outputs(
    outputs: Sequence[BudgetOutput], out_dir: Path, kinds: Collection[str] = REPORT_KINDS
) -> list[Path]:
    """Write the selected kinds of every output into `out_dir` (created if needed)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def write(name: str, data: bytes | str) -> None:
        path = out_dir / name
        path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        written.append(path)

    for out in outputs:
        # Renderers are imported only when needed: ReportLab pulls in networking modules.
        if "xlsx" in kinds:
            from budget_core.reports.xlsx import render_xlsx

            write(f"{out.prefix}.xlsx", render_xlsx(out.document))
        if "pdf" in kinds:
            from budget_core.reports.pdf import render_pdf

            write(f"{out.prefix}.pdf", render_pdf(out.document))
        if "json" in kinds:
            write(f"{out.prefix}.json", result_json(out.result, out.provenance))
        if "csv" in kinds:
            for name, text in out.csv_files:
                write(name, text)
    return written
