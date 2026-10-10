"""Link passes tab: margin, selected data rate and data volume over every pass of a scenario.

The computation (environment and link budget) runs in a worker thread; the environment of the
Scenario tab is reused when it is current. The plot shows the selected link inside its passes;
selecting a pass row zooms to it.
"""

from __future__ import annotations

import bisect
from collections.abc import Callable, Collection
from datetime import timedelta
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
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

from budget_core.link.evaluate import (
    LinkSeries,
    LinkSeriesResult,
    link_pass_series,
    link_static_budget,
)
from budget_core.model import Project
from budget_core.plots.link import link_plot
from budget_core.power.time_domain import format_offset
from budget_core.problems import Problem
from budget_core.provenance import make_provenance
from budget_core.reports.run import BudgetOutput, link_output
from budget_core.scenario.run import ScenarioRun, ScenarioRunError, run_scenario
from budget_core.timeutil import format_utc
from budget_gui.plot_widget import PlotWidget
from budget_gui.scenario_view import fill_table
from budget_gui.worker import ExportWorker


class LinkWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, project: Project, scenario_id: str, run: ScenarioRun | None) -> None:
        super().__init__()
        self._args = (project, scenario_id, run)

    def run(self) -> None:
        project, scenario_id, scenario_run = self._args
        try:
            if scenario_run is None:
                scenario_run = run_scenario(project, scenario_id)
            result = link_pass_series(project, scenario_run)
        except ScenarioRunError as exc:
            self.failed.emit(exc.problem.format())
            return
        except Exception as exc:  # plain message only, never a traceback or project content
            self.failed.emit(f"The link budget could not be computed ({type(exc).__name__}).")
            return
        self.finished_ok.emit(result)


class LinkPassesView(QWidget):
    computed = Signal(object)
    compute_failed = Signal(str)
    export_finished = Signal(list)
    export_failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.project: Project | None = None
        self.load_problems: list[Problem] = []
        self.result: LinkSeriesResult | None = None
        self.is_stale = False
        self.run_provider: Callable[[str], ScenarioRun | None] | None = None
        self._worker: LinkWorker | None = None
        self._export_worker: ExportWorker | None = None
        self._computing_for: Project | None = None

        self.scenario_combo = QComboBox()
        self.link_combo = QComboBox()
        self.compute_button = QPushButton("Compute")
        self.export_button = QPushButton("Export…")
        self.export_button.setEnabled(False)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.empty_label = QLabel("No links to show. Add links/*.yaml and a scenario.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        top = QHBoxLayout()
        for text, widget in (("Scenario", self.scenario_combo), ("Link", self.link_combo)):
            top.addWidget(QLabel(text))
            top.addWidget(widget)
        top.addWidget(self.compute_button)
        top.addWidget(self.export_button)
        top.addWidget(self.status, 1)

        self.plot = PlotWidget()
        self.passes_table = QTableWidget()
        self.volume_table = QTableWidget()
        self.tabs = QTabWidget()
        self.tabs.addTab(self.passes_table, "Passes")
        self.tabs.addTab(self.volume_table, "Data volume")
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
        self.link_combo.currentTextChanged.connect(lambda _t: self._show())
        self.scenario_combo.currentTextChanged.connect(self._scenario_changed)
        self.passes_table.cellClicked.connect(lambda row, _c: self.select_pass(row))
        self.plot.set_info_provider(self._info_at)
        self.set_project(None, [])

    # ---- project -----------------------------------------------------------------------------
    def selected_id(self) -> str:
        return self.scenario_combo.currentText()

    def selected_link(self) -> LinkSeries | None:
        if self.result is None:
            return None
        name = self.link_combo.currentText()
        return next((s for s in self.result.series if s.link_id == name), None)

    def set_project(self, project: Project | None, load_problems: list[Problem]) -> None:
        previous = self.selected_id()
        self.project = project
        self.load_problems = list(load_problems)
        ids = sorted(project.scenarios) if project and project.links else []
        self.scenario_combo.blockSignals(True)
        self.scenario_combo.clear()
        self.scenario_combo.addItems(ids)
        if previous in ids:
            self.scenario_combo.setCurrentText(previous)
        self.scenario_combo.blockSignals(False)
        shown = bool(ids)
        self.empty_label.setVisible(not shown)
        self.body.setVisible(shown)
        for widget in (self.scenario_combo, self.link_combo):
            widget.setEnabled(shown)
        self.compute_button.setEnabled(shown and self._worker is None)
        if not shown:
            self.result = None
            self._show()
            self.status.setText("")
            return
        if self.result is not None:
            self.is_stale = True
            self.export_button.setEnabled(False)  # the result belongs to the old project
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
        self._computing_for = self.project
        worker = LinkWorker(self.project, self.selected_id(), reused)
        worker.finished_ok.connect(self._done)
        worker.failed.connect(self._failed)
        self._worker = worker
        worker.start()

    def _finish_worker(self) -> None:
        if self._worker is not None:
            self._worker.wait(30000)
            self._worker = None
        self.compute_button.setEnabled(self.project is not None and bool(self.selected_id()))

    def _done(self, result: LinkSeriesResult) -> None:
        self._finish_worker()
        self.result = result
        self.is_stale = self.project is not self._computing_for  # reloaded while it ran
        previous = self.link_combo.currentText()
        self.link_combo.blockSignals(True)
        self.link_combo.clear()
        self.link_combo.addItems([s.link_id for s in result.series])
        if previous in [s.link_id for s in result.series]:
            self.link_combo.setCurrentText(previous)
        self.link_combo.blockSignals(False)
        self._show()
        self.export_button.setEnabled(not self.is_stale)
        total = sum((s.volume_bits or 0.0) for s in result.series) / 8e6
        n = sum(len(s.passes) for s in result.series)
        text = f"{len(result.series)} link(s), {n} pass(es), {total:.1f} MByte in the scenario"
        if any(s.margin_db is None for s in result.series):
            text += "; some inputs are placeholders, results marked n/a are not computed"
        if self.is_stale:
            text = "The project changed while this ran. Press Compute again"
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
        return [] if self.result is None else list(self.result.problems)

    def _info_at(self, t: float) -> str:
        series, result = self.selected_link(), self.result
        if series is None or result is None:
            return ""
        timeline = result.run.timeline
        index = max(bisect.bisect_right([s.start_s for s in timeline], t) - 1, 0)
        mode = timeline[index].mode if timeline else ""
        utc = format_utc(result.run.env.grid.start + timedelta(seconds=round(t)))
        return f"{utc}\nMode: {mode}"

    def _show(self) -> None:
        series, result = self.selected_link(), self.result
        if result is None or series is None:
            self.plot.set_spec(None)
            for table in (self.passes_table, self.volume_table):
                table.setRowCount(0)
                table.setColumnCount(0)
            if result is None:
                self.export_button.setEnabled(False)
            return
        self.plot.set_spec(link_plot(series, result.run.env.grid.duration_s))

        def num(value: float | None, digits: int = 2) -> str:
            return "n/a" if value is None else f"{value:.{digits}f}"

        fill_table(
            self.passes_table,
            [
                "Pass",
                "AOS (T+)",
                "Duration (s)",
                "Max elevation (deg)",
                "Usable (s)",
                "Lowest margin (dB)",
                "Volume (Mbit)",
            ],
            [
                [
                    str(p.index),
                    format_offset(p.aos_s),
                    f"{p.los_s - p.aos_s:.0f}",
                    f"{p.max_elevation_deg:.1f}",
                    f"{p.usable_s:.0f}",
                    num(p.minimum_margin_db),
                    num(None if p.volume_bits is None else p.volume_bits / 1e6),
                ]
                for p in series.passes
            ],
        )
        fill_table(
            self.volume_table,
            ["Link", "Station", "Passes", "Scenario total (Mbit)", "Per day (MByte)"],
            [
                [
                    s.link_id,
                    s.site,
                    str(len(s.passes)),
                    num(None if s.volume_bits is None else s.volume_bits / 1e6),
                    num(None if s.volume_per_day_bits is None else s.volume_per_day_bits / 8e6),
                ]
                for s in result.series
            ],
        )

    def select_pass(self, row: int) -> None:
        series = self.selected_link()
        if series is None or not 0 <= row < len(series.passes):
            return
        p = series.passes[row]
        pad = max((p.los_s - p.aos_s) * 0.5, 120.0)
        self.plot.set_view(p.aos_s - pad, p.los_s + pad)
        self.plot.pin_cursor(p.aos_s)

    # ---- export ------------------------------------------------------------------------------
    def output(self) -> BudgetOutput | None:
        if self.result is None or self.project is None or self.is_stale:
            return None
        provenance = make_provenance(self.project, scenario=self.result.run.scenario_id)
        static = link_static_budget(self.project)
        return link_output(self.project, static, provenance, self.load_problems, self.result)

    def _choose_export(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Export link results to folder")
        if folder:
            from budget_core.reports.run import REPORT_KINDS

            self.export_to(Path(folder), set(REPORT_KINDS))

    def export_to(self, folder: Path, kinds: Collection[str]) -> None:
        if self._export_worker is not None and self._export_worker.isRunning():
            self.export_failed.emit("An export is already running; wait for it to finish.")
            return
        output = self.output()
        if output is None:
            self.export_failed.emit(
                "The project changed since this result was computed. Press Compute again."
                if self.is_stale
                else "Compute the link passes first."
            )
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
