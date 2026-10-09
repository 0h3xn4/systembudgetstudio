"""Project session: loads a project folder and computes the budgets. No widgets here."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from budget_core.io.project_loader import LoadResult, load_project
from budget_core.model import Project
from budget_core.power.static_budget import StaticPowerResult, static_power_budget
from budget_core.problems import Problem, Severity, sort_problems
from budget_core.provenance import Provenance, make_provenance
from budget_core.reports.document import ReportDocument
from budget_core.reports.run import power_document


class ProjectSession(QObject):
    """Holds the open project and its results; emits `changed` after every (re)load."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.path: Path | None = None
        self.load_result: LoadResult | None = None
        self.power: StaticPowerResult | None = None
        self.provenance: Provenance | None = None
        self.document: ReportDocument | None = None
        self.problems: list[Problem] = []

    @property
    def project(self) -> Project | None:
        return self.load_result.project if self.load_result else None

    def open(self, path: Path) -> None:
        self.path = Path(path)
        self.reload()

    def reload(self) -> None:
        if self.path is None:
            return
        self.power = self.provenance = self.document = None
        try:
            self.load_result = load_project(self.path)
            self.problems = list(self.load_result.problems)
            project = self.load_result.project
            if project is not None:
                self.power = static_power_budget(project)
                self.provenance = make_provenance(project)
                self.document = power_document(
                    project, self.power, self.provenance, self.load_result.problems
                )
                self.problems = sort_problems([*self.problems, *self.power.problems])
        except Exception as exc:  # never show a traceback; say what happened in plain words
            self.load_result = None
            self.power = self.provenance = self.document = None
            self.problems = [
                Problem(
                    Severity.ERROR,
                    "INTERNAL_ERROR",
                    f"The project could not be processed ({type(exc).__name__}).",
                    hint="Run 'budget validate' on the folder to see the details, then report it.",
                )
            ]
        self.changed.emit()
