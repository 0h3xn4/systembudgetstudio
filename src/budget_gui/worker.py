"""Background export so the window stays responsive (spec: GUI responsive during runs)."""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from budget_core.power.static_budget import StaticPowerResult
from budget_core.provenance import Provenance
from budget_core.reports.document import ReportDocument
from budget_core.reports.run import write_power_reports


class ExportWorker(QThread):
    finished_ok = Signal(list)
    failed = Signal(str)

    def __init__(
        self,
        document: ReportDocument,
        power: StaticPowerResult,
        provenance: Provenance,
        folder: Path,
        kinds: Collection[str],
    ) -> None:
        super().__init__()
        self._args = (document, power, provenance, folder, set(kinds))

    def run(self) -> None:
        document, power, provenance, folder, kinds = self._args
        try:
            written = write_power_reports(document, power, provenance, folder, kinds)
        except OSError:
            self.failed.emit(
                "The reports could not be written. Check that the folder exists, is a folder "
                "and that you may write to it."
            )
            return
        except Exception as exc:  # plain message only, no traceback or project content
            self.failed.emit(f"The export failed ({type(exc).__name__}).")
            return
        self.finished_ok.emit([str(p) for p in written])
