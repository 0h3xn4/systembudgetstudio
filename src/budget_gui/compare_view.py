"""Compare tab: the open project against another project folder (a revision), or two scenarios.

Differences are listed budget by budget with the status coloured (changed, added, removed,
now computed, now n/a). The comparison runs in a worker thread; the report files come from the
same code as `budget compare`.
"""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from budget_core.compare_run import Side, compare_sides, default_kinds
from budget_core.io.project_loader import load_project
from budget_core.model import Project
from budget_core.problems import Severity
from budget_core.reports.run import REPORT_KINDS, BudgetOutput
from budget_core.scenario.run import ScenarioRunError
from budget_gui.worker import ExportWorker

NO_SCENARIO = "(none)"
HEADERS = ["Budget", "Section", "Row", "Quantity", "A", "B", "Change", "Change (%)", "Status"]
TINTS = {  # Carbon support-colour backgrounds, dark text on all of them
    "changed": "#fcf4d6",
    "added": "#defbe6",
    "removed": "#fff1f1",
    "now computed": "#edf5ff",
    "now n/a": "#e8daff",
}


class CompareWorker(QThread):
    finished_ok = Signal(object, list)
    failed = Signal(str)

    def __init__(
        self, project: Project, scenario_a: str | None, other: Path | None, scenario_b: str | None
    ) -> None:
        super().__init__()
        self._args = (project, scenario_a, other, scenario_b)

    def run(self) -> None:
        project, scenario_a, other, scenario_b = self._args
        try:
            other_project = project
            if other is not None:
                loaded = load_project(other)
                errors = sum(1 for p in loaded.problems if p.severity is Severity.ERROR)
                if loaded.project is None or errors:
                    self.failed.emit(
                        "The other project cannot be compared: it has errors. "
                        "Open it and fix the problems listed there first."
                    )
                    return
                other_project = loaded.project
            a, b = Side(project, scenario_a), Side(other_project, scenario_b)
            kinds = default_kinds(a, b, same_project=other is None)
            if not kinds:
                self.failed.emit(
                    "Choose another project folder, or two different scenarios, to compare."
                )
                return
            output, notes = compare_sides(a, b, kinds)
        except ScenarioRunError as exc:
            self.failed.emit(exc.problem.format())
            return
        except Exception as exc:  # plain message only, never a traceback or project content
            self.failed.emit(f"The comparison failed ({type(exc).__name__}).")
            return
        self.finished_ok.emit(output, notes)


class CompareView(QWidget):
    computed = Signal(object)
    compute_failed = Signal(str)
    export_finished = Signal(list)
    export_failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.project: Project | None = None
        self.output: BudgetOutput | None = None
        self._worker: CompareWorker | None = None
        self._export_worker: ExportWorker | None = None

        self.scenario_a = QComboBox()
        self.other_edit = QLineEdit()
        self.other_edit.setPlaceholderText(
            "Other project folder (leave empty to compare scenarios)"
        )
        self.browse_button = QPushButton("Browse…")
        self.scenario_b = QComboBox()
        self.compare_button = QPushButton("Compare")
        self.export_button = QPushButton("Export…")
        self.export_button.setEnabled(False)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.table = QTableWidget(0, len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        row_a = QHBoxLayout()
        row_a.addWidget(QLabel("A: this project, scenario"))
        row_a.addWidget(self.scenario_a)
        row_a.addStretch(1)
        row_b = QHBoxLayout()
        row_b.addWidget(QLabel("B:"))
        row_b.addWidget(self.other_edit, 1)
        row_b.addWidget(self.browse_button)
        row_b.addWidget(QLabel("scenario"))
        row_b.addWidget(self.scenario_b)
        row_c = QHBoxLayout()
        row_c.addWidget(self.compare_button)
        row_c.addWidget(self.export_button)
        row_c.addWidget(self.status, 1)
        layout = QVBoxLayout(self)
        for row in (row_a, row_b, row_c):
            layout.addLayout(row)
        layout.addWidget(self.table, 1)

        self.browse_button.clicked.connect(lambda: self._browse())
        self.compare_button.clicked.connect(lambda: self.compare())
        self.export_button.clicked.connect(lambda: self._choose_export())
        self.set_project(None)

    # ---- project -----------------------------------------------------------------------------
    def set_project(self, project: Project | None) -> None:
        self.project = project
        ids = [NO_SCENARIO, *sorted(project.scenarios)] if project else [NO_SCENARIO]
        for combo in (self.scenario_a, self.scenario_b):
            previous = combo.currentText()
            combo.clear()
            combo.addItems(ids)
            if previous in ids:
                combo.setCurrentText(previous)
        self.compare_button.setEnabled(project is not None and self._worker is None)
        if project is None:
            self._show(None)
            self.status.setText("Open a project to compare it with another revision.")
        elif self.output is not None:
            self.status.setText("The project changed since the last comparison. Press Compare.")

    def set_other_folder(self, folder: Path) -> None:
        self.other_edit.setText(str(folder))

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose the project folder to compare")
        if folder:
            self.set_other_folder(Path(folder))

    @staticmethod
    def _scenario(combo: QComboBox) -> str | None:
        text = combo.currentText()
        return None if text in ("", NO_SCENARIO) else text

    # ---- compare -----------------------------------------------------------------------------
    def compare(self) -> None:
        if self.project is None or self._worker is not None:
            return
        text = self.other_edit.text().strip()
        self.compare_button.setEnabled(False)
        self.status.setText("Comparing…")
        worker = CompareWorker(
            self.project,
            self._scenario(self.scenario_a),
            Path(text) if text else None,
            self._scenario(self.scenario_b),
        )
        worker.finished_ok.connect(self._done)
        worker.failed.connect(self._failed)
        self._worker = worker
        worker.start()

    def _finish_worker(self) -> None:
        if self._worker is not None:
            self._worker.wait(30000)
            self._worker = None
        self.compare_button.setEnabled(self.project is not None)

    def _done(self, output: BudgetOutput, notes: list[str]) -> None:
        self._finish_worker()
        self.output = output
        self._show(output)
        results = output.result
        total = sum(len(r.differences) + r.truncated for r in results)
        text = (
            f"{total} value(s) differ across {len(results)} budget(s)."
            if total
            else "No differences."
        )
        if any(r.truncated for r in results):
            text += " Some differences are not listed; the export holds the first ones only."
        if notes:
            text += " " + " ".join(notes)
        self.status.setText(text)
        self.export_button.setEnabled(True)
        self.computed.emit(output)

    def _failed(self, message: str) -> None:
        self._finish_worker()
        self.output = None
        self._show(None)
        self.status.setText(message)
        self.compute_failed.emit(message)

    def wait_for_worker(self) -> None:
        for worker in (self._worker, self._export_worker):
            if worker is not None:
                worker.wait(30000)

    # ---- display -----------------------------------------------------------------------------
    def _show(self, output: BudgetOutput | None) -> None:
        rows = [(r.name, d) for r in (output.result if output else ()) for d in r.differences]
        self.table.setRowCount(len(rows))
        for i, (name, d) in enumerate(rows):
            texts = [
                name,
                d.section,
                d.row,
                d.quantity,
                d.value_a,
                d.value_b,
                d.change,
                d.change_percent,
                d.status,
            ]
            for column, text in enumerate(texts):
                item = QTableWidgetItem(text)
                item.setBackground(QBrush(QColor(TINTS[d.status])))
                item.setForeground(QBrush(QColor("#161616")))
                if column in (4, 5, 6, 7):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(i, column, item)
        self.table.resizeColumnsToContents()
        if output is None:
            self.export_button.setEnabled(False)

    # ---- export ------------------------------------------------------------------------------
    def _choose_export(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Export the comparison to folder")
        if folder:
            self.export_to(Path(folder), set(REPORT_KINDS))

    def export_to(self, folder: Path, kinds: Collection[str]) -> None:
        if self._export_worker is not None and self._export_worker.isRunning():
            self.export_failed.emit("An export is already running; wait for it to finish.")
            return
        if self.output is None:
            self.export_failed.emit("Run a comparison first.")
            return
        worker = ExportWorker([self.output], folder, kinds)
        worker.finished_ok.connect(self._export_done)
        worker.failed.connect(self._export_failed)
        self._export_worker = worker
        self.status.setText("Exporting…")
        worker.start()

    def _export_done(self, paths: list[str]) -> None:
        self.status.setText(f"Exported {len(paths)} file(s).")
        self.export_finished.emit(paths)

    def _export_failed(self, message: str) -> None:
        self.status.setText(message)
        self.export_failed.emit(message)
