"""Power timeline tab: time-domain power budget with plots, cursors, violations and export.

The computation (environment, array, battery) runs in a worker thread. The environment of the
Scenario tab is reused when it is current. Both cases (BOL and EOL) are solved together; the case
selector only changes what is shown. Violations zoom the plot to their interval, and a double
click opens the input that governs them.
"""

from __future__ import annotations

import bisect
from collections.abc import Callable, Collection
from datetime import timedelta
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from budget_core.model import Project
from budget_core.plots.power import power_plot
from budget_core.power.time_domain import (
    CODES_TEXT,
    TimeDomainResult,
    format_offset,
    time_domain_budget,
    violation_problems,
)
from budget_core.problems import Problem, sort_problems
from budget_core.provenance import make_provenance
from budget_core.reports.run import BudgetOutput, timeline_output
from budget_core.scenario.run import ScenarioRun, ScenarioRunError, run_scenario
from budget_core.timeutil import format_utc
from budget_gui.plot_widget import PlotWidget
from budget_gui.scenario_view import fill_table
from budget_gui.worker import ExportWorker

BASES = ("nominal", "margined")
CASE_NAMES = ("bol", "eol")


class TimelineWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(
        self, project: Project, scenario_id: str, basis: str, run: ScenarioRun | None
    ) -> None:
        super().__init__()
        self._args = (project, scenario_id, basis, run)

    def run(self) -> None:
        project, scenario_id, basis, scenario_run = self._args
        try:
            if scenario_run is None:
                scenario_run = run_scenario(project, scenario_id)
            result = time_domain_budget(
                project,
                scenario_run,
                load_basis="margined" if basis == "margined" else "nominal",
            )
        except ScenarioRunError as exc:
            self.failed.emit(exc.problem.format())
            return
        except Exception as exc:  # plain message only, never a traceback or project content
            self.failed.emit(f"The power budget could not be computed ({type(exc).__name__}).")
            return
        self.finished_ok.emit(result)


class PowerTimelineView(QWidget):
    computed = Signal(object)
    compute_failed = Signal(str)
    jump_requested = Signal(str, str)  # file, path in the file
    export_finished = Signal(list)
    export_failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.project: Project | None = None
        self.load_problems: list[Problem] = []
        self.result: TimeDomainResult | None = None
        self.is_stale = False
        self.run_provider: Callable[[str], ScenarioRun | None] | None = None
        self._worker: TimelineWorker | None = None
        self._export_worker: ExportWorker | None = None

        self.scenario_combo = QComboBox()
        self.basis_combo = QComboBox()
        self.basis_combo.addItems(BASES)
        self.basis_combo.setToolTip("Demand without margins, or with unit and system margins.")
        self.case_combo = QComboBox()
        self.case_combo.addItems(["BOL", "EOL"])
        self.shading = QCheckBox("Shade eclipses and passes")
        self.shading.setChecked(True)
        self.compute_button = QPushButton("Compute")
        self.export_button = QPushButton("Export…")
        self.export_button.setEnabled(False)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.empty_label = QLabel("No scenario to show. Open a project that has scenarios.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        top = QHBoxLayout()
        for text, widget in (
            ("Scenario", self.scenario_combo),
            ("Demand", self.basis_combo),
            ("Case", self.case_combo),
        ):
            top.addWidget(QLabel(text))
            top.addWidget(widget)
        top.addWidget(self.shading)
        top.addWidget(self.compute_button)
        top.addWidget(self.export_button)
        top.addWidget(self.status, 1)

        self.plot = PlotWidget()
        self.summary_table = QTableWidget()
        self.violations_table = QTableWidget()
        self.orbits_table = QTableWidget()
        self.modes_table = QTableWidget()
        self.tabs = QTabWidget()
        self.tabs.addTab(self.summary_table, "Summary")
        self.tabs.addTab(self.violations_table, "Violations")
        self.tabs.addTab(self.orbits_table, "Orbits")
        self.tabs.addTab(self.modes_table, "Modes")
        self.body = QSplitter(Qt.Orientation.Vertical)
        self.body.addWidget(self.plot)
        self.body.addWidget(self.tabs)
        self.body.setStretchFactor(0, 3)
        self.body.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.body)

        self.compute_button.clicked.connect(lambda: self.compute())
        self.export_button.clicked.connect(lambda: self._choose_export())
        self.case_combo.currentTextChanged.connect(lambda _t: self._show())
        self.shading.toggled.connect(self.plot.set_shading)
        self.scenario_combo.currentTextChanged.connect(self._scenario_changed)
        self.violations_table.cellClicked.connect(lambda row, _c: self.select_violation(row))
        self.violations_table.cellDoubleClicked.connect(lambda row, _c: self.jump_to(row))
        self.plot.set_info_provider(self._info_at)
        self.set_project(None, [])

    # ---- project -----------------------------------------------------------------------------
    def selected_id(self) -> str:
        return self.scenario_combo.currentText()

    def current_case(self) -> str:
        return self.case_combo.currentText().lower()

    def set_project(self, project: Project | None, load_problems: list[Problem]) -> None:
        previous = self.selected_id()
        self.project = project
        self.load_problems = list(load_problems)
        ids = sorted(project.scenarios) if project else []
        self.scenario_combo.blockSignals(True)
        self.scenario_combo.clear()
        self.scenario_combo.addItems(ids)
        if previous in ids:
            self.scenario_combo.setCurrentText(previous)
        self.scenario_combo.blockSignals(False)
        shown = bool(ids)
        self.empty_label.setVisible(not shown)
        self.body.setVisible(shown)
        for widget in (self.scenario_combo, self.basis_combo, self.case_combo, self.shading):
            widget.setEnabled(shown)
        self.compute_button.setEnabled(shown and self._worker is None)
        if not shown:
            self.result = None
            self._show()
            self.status.setText("")
            return
        if self.result is not None:
            self.is_stale = True
            self.status.setText("The project changed since the last computation. Press Compute.")
        else:
            self.status.setText("Not computed yet. Press Compute.")

    def _scenario_changed(self, _text: str) -> None:
        if self.result is not None and self.result.run.scenario_id != self.selected_id():
            self.result = None
            self._show()
            self.status.setText("Not computed yet. Press Compute.")

    # ---- compute -----------------------------------------------------------------------------
    def compute(self) -> None:
        if self.project is None or not self.selected_id() or self._worker is not None:
            return
        self.compute_button.setEnabled(False)
        self.status.setText("Computing…")
        reused = self.run_provider(self.selected_id()) if self.run_provider else None
        worker = TimelineWorker(
            self.project, self.selected_id(), self.basis_combo.currentText(), reused
        )
        worker.finished_ok.connect(self._done)
        worker.failed.connect(self._failed)
        self._worker = worker
        worker.start()

    def _finish_worker(self) -> None:
        if self._worker is not None:
            self._worker.wait(30000)
            self._worker = None
        self.compute_button.setEnabled(self.project is not None and bool(self.selected_id()))

    def _done(self, result: TimeDomainResult) -> None:
        self._finish_worker()
        self.result = result
        self.is_stale = False
        self._show()
        self.export_button.setEnabled(True)
        count = len(result.violations)
        incomplete = any(a.placeholder for a in result.assumptions)
        text = f"{result.steps} steps; {count} violation(s)"
        if incomplete:
            text += "; some inputs are placeholders, results marked n/a are not computed"
        self.status.setText(text + ".")
        self.computed.emit(result)

    def _failed(self, message: str) -> None:
        self._finish_worker()
        self.result = None
        self._show()
        self.status.setText(message)
        self.compute_failed.emit(message)

    def wait_for_worker(self) -> None:
        for worker in (self._worker, self._export_worker):
            if worker is not None:
                worker.wait(30000)

    # ---- display -----------------------------------------------------------------------------
    def problems(self) -> list[Problem]:
        """Findings and configuration gaps of the last result, for the Problems panel."""
        if self.result is None:
            return []
        return sort_problems([*self.result.problems, *violation_problems(self.result)])

    def _info_at(self, t: float) -> str:
        result = self.result
        if result is None:
            return ""
        timeline = result.run.timeline
        starts = [s.start_s for s in timeline]
        index = max(bisect.bisect_right(starts, t) - 1, 0)
        mode = timeline[index].mode if timeline else ""
        eclipse = any(e.start_s <= t <= e.end_s for e in result.run.env.eclipses)
        utc = format_utc(result.run.env.grid.start + timedelta(seconds=round(t)))
        return f"{utc}\nMode: {mode}\n{'Eclipse' if eclipse else 'Sunlit'}"

    def _show(self) -> None:
        result = self.result
        if result is None:
            self.plot.set_spec(None)
            for table in (
                self.summary_table,
                self.violations_table,
                self.orbits_table,
                self.modes_table,
            ):
                table.setRowCount(0)
                table.setColumnCount(0)
            self.export_button.setEnabled(False)
            return
        self.plot.set_spec(power_plot(result, self.current_case()))
        self.plot.set_shading(self.shading.isChecked())
        self._fill_tables(result)

    def _fill_tables(self, result: TimeDomainResult) -> None:
        def num(value: float | None, digits: int = 2) -> str:
            return "n/a" if value is None else f"{value:.{digits}f}"

        def pct(value: float | None) -> str:
            return "n/a" if value is None else f"{value * 100:.1f}"

        case = result.case(self.current_case())
        rows: list[list[str]] = []
        for c in result.cases:
            s = c.summary
            rows.append(
                [
                    c.case.upper(),
                    num(c.capacity_wh, 1),
                    num(s.average_generation_w),
                    num(s.average_demand_w),
                    num(s.generated_wh, 1),
                    num(s.demanded_wh, 1),
                    pct(s.minimum_soc_ratio),
                    pct(s.maximum_dod_ratio),
                    num(s.unmet_wh, 2),
                    str(len(c.violations)),
                ]
            )
        fill_table(
            self.summary_table,
            [
                "Case",
                "Capacity (Wh)",
                "Avg generation (W)",
                "Avg demand (W)",
                "Generated (Wh)",
                "Demanded (Wh)",
                "Lowest SoC (%)",
                "Deepest DoD (%)",
                "Not supplied (Wh)",
                "Violations",
            ],
            rows,
        )
        fill_table(
            self.violations_table,
            [
                "Case",
                "Finding",
                "From (T+)",
                "To (T+)",
                "Duration (s)",
                "Worst",
                "Limit",
                "Unit",
                "Input",
            ],
            [
                [
                    v.case.upper() if v.case else "both",
                    CODES_TEXT.get(v.code, v.code),
                    format_offset(v.start_s),
                    format_offset(v.end_s),
                    f"{v.end_s - v.start_s:.1f}",
                    num(v.extreme, 4),
                    num(v.limit, 4),
                    v.unit,
                    f"{v.file}: {v.path}" if v.path else v.file,
                ]
                for v in result.violations
            ],
        )
        fill_table(
            self.orbits_table,
            [
                "Orbit",
                "Start (T+)",
                "Eclipse (s)",
                "Generated (Wh)",
                "Demanded (Wh)",
                "Balance (Wh)",
                "Stored change (Wh)",
            ],
            [
                [
                    str(b.index),
                    format_offset(b.start_s),
                    f"{b.eclipse_s:.0f}",
                    num(b.generation_wh),
                    num(b.demand_wh),
                    num(b.balance_wh),
                    num(b.battery_change_wh),
                ]
                for b in case.balances
            ],
        )
        total = result.run.scenario.duration_s
        fill_table(
            self.modes_table,
            ["Mode", "Name", "Share (%)", "Load (W)", "Demand at source (W)", "Peak at source (W)"],
            [
                [
                    m.mode_id,
                    m.mode_name,
                    f"{m.duration_s / total * 100:.1f}",
                    num(m.load_w),
                    num(m.demand_w),
                    num(m.peak_demand_w),
                ]
                for m in result.modes
            ],
        )

    # ---- violations --------------------------------------------------------------------------
    def select_violation(self, row: int) -> None:
        if self.result is None or not 0 <= row < len(self.result.violations):
            return
        v = self.result.violations[row]
        pad = max((v.end_s - v.start_s) * 0.5, 300.0)
        self.plot.set_view(v.start_s - pad, v.end_s + pad)
        self.plot.pin_cursor(v.start_s)
        if v.case in CASE_NAMES:
            self.case_combo.setCurrentText(v.case.upper())

    def jump_to(self, row: int) -> None:
        if self.result is None or not 0 <= row < len(self.result.violations):
            return
        v = self.result.violations[row]
        self.jump_requested.emit(v.file, v.path)

    # ---- export ------------------------------------------------------------------------------
    def output(self, series_every: int = 1) -> BudgetOutput | None:
        if self.result is None or self.project is None:
            return None
        provenance = make_provenance(self.project, scenario=self.result.run.scenario_id)
        return timeline_output(
            self.project,
            self.result,
            provenance,
            self.load_problems,
            series_every=series_every,
        )

    def _choose_export(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Export power timeline to folder")
        if folder:
            from budget_core.reports.run import REPORT_KINDS

            self.export_to(Path(folder), set(REPORT_KINDS))

    def export_to(self, folder: Path, kinds: Collection[str]) -> None:
        output = self.output()
        if output is None:
            self.export_failed.emit("Compute the power timeline first.")
            return
        worker = ExportWorker([output], folder, kinds)
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
