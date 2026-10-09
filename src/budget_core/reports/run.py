"""Write the static power budget outputs; shared by the CLI and the GUI."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from pathlib import Path

from budget_core.model import Project
from budget_core.power.static_budget import StaticPowerResult
from budget_core.problems import Problem
from budget_core.provenance import Provenance
from budget_core.reports.document import ReportDocument
from budget_core.reports.export import result_csv, result_json
from budget_core.reports.power_report import build_power_report

REPORT_KINDS = ("xlsx", "pdf", "json", "csv")


def power_document(
    project: Project,
    power: StaticPowerResult,
    provenance: Provenance,
    load_problems: Sequence[Problem] = (),
) -> ReportDocument:
    return build_power_report(project, power, provenance, list(load_problems))


def write_power_reports(
    document: ReportDocument,
    power: StaticPowerResult,
    provenance: Provenance,
    out_dir: Path,
    kinds: Collection[str] = REPORT_KINDS,
) -> list[Path]:
    """Write the selected outputs into `out_dir` (created if needed); returns the paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def write(name: str, data: bytes | str) -> None:
        path = out_dir / name
        path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        written.append(path)

    # Renderers are imported only when needed: ReportLab pulls in networking modules (never used).
    if "xlsx" in kinds:
        from budget_core.reports.xlsx import render_xlsx

        write("power_static.xlsx", render_xlsx(document))
    if "pdf" in kinds:
        from budget_core.reports.pdf import render_pdf

        write("power_static.pdf", render_pdf(document))
    if "json" in kinds:
        write("power_static.json", result_json(power, provenance))
    if "csv" in kinds:
        for mode in power.modes:
            write(f"power_static_{mode.mode_id}.csv", result_csv(mode))
    return written
