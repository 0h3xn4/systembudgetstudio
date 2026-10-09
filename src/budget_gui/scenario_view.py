"""Scenario view: timeline, rule and segment editors, results tables, background computation.

The environment (orbit, eclipses, passes) is computed in a worker thread. Editing rules, segments
or the default mode only rebuilds the timeline from the existing environment (it is reused while
`environment_key` is unchanged); changing orbit, sites, times or step marks the results stale.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from budget_core.io.errors import explain
from budget_core.io.project_loader import dump_model, model_to_data
from budget_core.io.yamlio import LineMap
from budget_core.model import Project, Scenario
from budget_core.provenance import make_provenance
from budget_core.scenario.export import write_scenario_outputs
from budget_core.scenario.run import (
    ScenarioRun,
    ScenarioRunError,
    environment_key,
    rebuild_timeline,
    run_scenario,
)
from budget_core.timeutil import format_utc
from budget_gui.timeline import TimelineWidget

RULE_KINDS = ("during_pass", "in_eclipse", "in_sunlight")
SHADOW_MODELS = ("cylindrical", "conical")


def _number(text: str) -> Any:
    stripped = text.strip()
    try:
        return float(stripped)
    except ValueError:
        return stripped


class ScenarioWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, project: Project, scenario_id: str) -> None:
        super().__init__()
        self._project = project
        self._scenario_id = scenario_id

    def run(self) -> None:
        try:
            self.finished_ok.emit(run_scenario(self._project, self._scenario_id))
        except ScenarioRunError as exc:
            self.failed.emit(exc.problem.format())
        except Exception as exc:  # plain message only, never a traceback or project content
            self.failed.emit(f"The scenario could not be computed ({type(exc).__name__}).")


class ScenarioEditor(QWidget):
    """Edits the default mode, shadow model, sites, rules and manual segments of a scenario."""

    saved = Signal()
    modified_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._root: Path | None = None
        self._id = ""
        self._original: Scenario | None = None
        self._modes: list[str] = []
        self._sites: list[str] = []
        self._modified = False
        self._loading = False

        self.default_mode = QComboBox()
        self.shadow_model = QComboBox()
        self.shadow_model.addItems(SHADOW_MODELS)
        self.sites_list = QListWidget()
        self.sites_list.setMaximumHeight(90)
        form = QFormLayout()
        form.addRow("Default mode", self.default_mode)
        form.addRow("Shadow model", self.shadow_model)
        form.addRow("Sites", self.sites_list)

        self.rules_table = QTableWidget(0, 5)
        self.rules_table.setHorizontalHeaderLabels(["Rule", "Site", "Mode", "Lead (s)", "Lag (s)"])
        self.segments_table = QTableWidget(0, 3)
        self.segments_table.setHorizontalHeaderLabels(["Start (s)", "Duration (s)", "Mode"])
        for table in (self.rules_table, self.segments_table):
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.itemChanged.connect(lambda _item: self._edited())

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #da1e28;")

        def button(text: str, slot: Any) -> QPushButton:
            b = QPushButton(text)
            b.clicked.connect(slot)
            return b

        rule_buttons = [
            button("Add rule", lambda: self.add_rule()),
            button("Remove rule", lambda: self.remove_rule(self.rules_table.currentRow())),
        ]
        segment_buttons = [
            button("Add segment", lambda: self.add_segment()),
            button("Remove segment", lambda: self.remove_segment(self.segments_table.currentRow())),
        ]
        save_buttons = [
            button("Save scenario", lambda: self.save()),
            button("Discard changes", lambda: self.discard_changes()),
        ]

        for table in (self.rules_table, self.segments_table):
            table.setMinimumHeight(150)
            table.horizontalHeader().setStretchLastSection(True)

        def row_of(*buttons: QPushButton) -> QHBoxLayout:
            row = QHBoxLayout()
            for b in buttons:
                row.addWidget(b)
            row.addStretch(1)
            return row

        left = QVBoxLayout()
        left.addLayout(form)
        left.addWidget(QLabel("Rules (applied in order, later rules win)"))
        left.addWidget(self.rules_table, 1)
        left.addLayout(row_of(*rule_buttons))
        right = QVBoxLayout()
        right.addWidget(
            QLabel("Manual segments (applied last; Shift+drag on the timeline adds one)")
        )
        right.addWidget(self.segments_table, 1)
        right.addLayout(row_of(*segment_buttons))
        right.addWidget(self.error_label)
        right.addLayout(row_of(*save_buttons))
        right.addStretch(1)
        layout = QHBoxLayout(self)
        layout.addLayout(left, 3)
        layout.addLayout(right, 2)

        self.default_mode.currentTextChanged.connect(lambda _t: self._edited())
        self.shadow_model.currentTextChanged.connect(lambda _t: self._edited())
        self.sites_list.itemChanged.connect(lambda _i: self._edited())

    # ---- state -------------------------------------------------------------------------------
    def is_modified(self) -> bool:
        return self._modified

    def _set_modified(self, value: bool) -> None:
        if value != self._modified:
            self._modified = value
            self.modified_changed.emit(value)

    def clear(self) -> None:
        self._original = None
        self._loading = True
        self.rules_table.setRowCount(0)
        self.segments_table.setRowCount(0)
        self.sites_list.clear()
        self.default_mode.clear()
        self._loading = False
        self._set_modified(False)
        self.error_label.setText("")

    def load(
        self, root: Path, scenario_id: str, scenario: Scenario, modes: list[str], sites: list[str]
    ) -> None:
        self._root, self._id, self._original = root, scenario_id, scenario
        self._modes, self._sites = sorted(modes), sorted(sites)
        self._populate(scenario)

    def _populate(self, scenario: Scenario) -> None:
        self._loading = True
        self.default_mode.clear()
        self.default_mode.addItems(self._modes)
        self.default_mode.setCurrentText(scenario.default_mode)
        self.shadow_model.setCurrentText(scenario.shadow_model)
        self.sites_list.clear()
        for site in self._sites:
            item = QListWidgetItem(site)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if site in scenario.sites else Qt.CheckState.Unchecked
            )
            self.sites_list.addItem(item)
        self.rules_table.setRowCount(0)
        for rule in scenario.rules:
            self._append_rule(rule.kind, rule.site or "", rule.mode, rule.lead_s, rule.lag_s)
        self.segments_table.setRowCount(0)
        for seg in scenario.segments:
            self._append_segment(seg.start_s, seg.duration_s, seg.mode)
        self._loading = False
        self.error_label.setText("")

    def discard_changes(self) -> None:
        if self._original is not None:
            self._populate(self._original)
        self._set_modified(False)

    def reload_if_clean(self, scenario: Scenario, modes: list[str], sites: list[str]) -> None:
        """After the project reloaded: refresh the widgets unless the user has pending edits."""
        self._original = scenario
        self._modes, self._sites = sorted(modes), sorted(sites)
        if not self._modified:
            self._populate(scenario)

    # ---- rules -------------------------------------------------------------------------------
    def _combo(self, items: list[str], current: str) -> QComboBox:
        box = QComboBox()
        box.addItems(items)
        box.setCurrentText(current)
        box.currentTextChanged.connect(lambda _t: self._edited())
        return box

    def _append_rule(self, kind: str, site: str, mode: str, lead: float, lag: float) -> None:
        row = self.rules_table.rowCount()
        self._loading = True
        self.rules_table.insertRow(row)
        self.rules_table.setCellWidget(row, 0, self._combo(list(RULE_KINDS), kind))
        self.rules_table.setCellWidget(row, 1, self._combo(["", *self._sites], site))
        self.rules_table.setCellWidget(row, 2, self._combo(self._modes, mode))
        self.rules_table.setItem(row, 3, QTableWidgetItem(str(lead)))
        self.rules_table.setItem(row, 4, QTableWidgetItem(str(lag)))
        self._loading = False

    def add_rule(self) -> None:
        mode = self.default_mode.currentText() or (self._modes[0] if self._modes else "")
        self._append_rule("during_pass", self._sites[0] if self._sites else "", mode, 0.0, 0.0)
        self._edited()

    def remove_rule(self, row: int) -> None:
        if 0 <= row < self.rules_table.rowCount():
            self.rules_table.removeRow(row)
            self._edited()

    def set_rule(
        self,
        row: int,
        kind: str | None = None,
        site: str | None = None,
        mode: str | None = None,
        lead_s: float | None = None,
        lag_s: float | None = None,
    ) -> None:
        for column, value in ((0, kind), (1, site), (2, mode)):
            if value is not None:
                box = self.rules_table.cellWidget(row, column)
                assert isinstance(box, QComboBox)
                box.setCurrentText(value)
        for column, number in ((3, lead_s), (4, lag_s)):
            if number is not None:
                item = self.rules_table.item(row, column)
                assert item is not None
                item.setText(str(number))

    def _rule_data(self, row: int) -> dict[str, Any]:
        def combo(column: int) -> str:
            box = self.rules_table.cellWidget(row, column)
            assert isinstance(box, QComboBox)
            return box.currentText()

        rule: dict[str, Any] = {"kind": combo(0), "mode": combo(2)}
        if combo(1):
            rule["site"] = combo(1)
        for column, key in ((3, "lead_s"), (4, "lag_s")):
            item = self.rules_table.item(row, column)
            value = _number(item.text()) if item else 0.0
            if value != 0.0:
                rule[key] = value
        return rule

    # ---- segments ----------------------------------------------------------------------------
    def _append_segment(self, start: float, duration: float, mode: str) -> None:
        row = self.segments_table.rowCount()
        self._loading = True
        self.segments_table.insertRow(row)
        self.segments_table.setItem(row, 0, QTableWidgetItem(str(start)))
        self.segments_table.setItem(row, 1, QTableWidgetItem(str(duration)))
        self.segments_table.setCellWidget(row, 2, self._combo(self._modes, mode))
        self._loading = False

    def add_segment(self, start: float = 0.0, duration: float = 60.0) -> None:
        self._append_segment(start, duration, self.default_mode.currentText())
        self._edited()

    def remove_segment(self, row: int) -> None:
        if 0 <= row < self.segments_table.rowCount():
            self.segments_table.removeRow(row)
            self._edited()

    def set_segment(
        self,
        row: int,
        start: float | None = None,
        duration: float | None = None,
        mode: str | None = None,
    ) -> None:
        for column, number in ((0, start), (1, duration)):
            if number is not None:
                item = self.segments_table.item(row, column)
                assert item is not None
                item.setText(str(number))
        if mode is not None:
            box = self.segments_table.cellWidget(row, 2)
            assert isinstance(box, QComboBox)
            box.setCurrentText(mode)

    def segment(self, row: int) -> tuple[float, float, str]:
        start, duration = self.segments_table.item(row, 0), self.segments_table.item(row, 1)
        box = self.segments_table.cellWidget(row, 2)
        assert start and duration and isinstance(box, QComboBox)
        return float(start.text()), float(duration.text()), box.currentText()

    # ---- validation and saving ---------------------------------------------------------------
    def _edited(self) -> None:
        if self._loading:
            return
        self._set_modified(True)
        self._validate()

    def _data(self) -> dict[str, Any]:
        assert self._original is not None
        data = model_to_data(self._original)
        data["default_mode"] = self.default_mode.currentText()
        data["shadow_model"] = self.shadow_model.currentText()
        checked = [
            self.sites_list.item(i).text()
            for i in range(self.sites_list.count())
            if self.sites_list.item(i).checkState() == Qt.CheckState.Checked
        ]
        data["sites"] = [s for s in self._original.sites if s in checked] + [
            s for s in checked if s not in self._original.sites
        ]
        data["rules"] = [self._rule_data(r) for r in range(self.rules_table.rowCount())]
        data["segments"] = []
        for row in range(self.segments_table.rowCount()):
            start, duration = self.segments_table.item(row, 0), self.segments_table.item(row, 1)
            box = self.segments_table.cellWidget(row, 2)
            assert isinstance(box, QComboBox)
            data["segments"].append(
                {
                    "start_s": _number(start.text()) if start else 0.0,
                    "duration_s": _number(duration.text()) if duration else 0.0,
                    "mode": box.currentText(),
                }
            )
        return data

    def current_scenario(self) -> Scenario:
        return Scenario.model_validate(self._data())

    def _validate(self) -> Scenario | None:
        try:
            scenario = self.current_scenario()
        except ValidationError as exc:
            lines = [
                f"{p.path or 'scenario'}: {p.message}" + (f" {p.hint}" if p.hint else "")
                for p in explain(exc, Scenario, f"scenarios/{self._id}.yaml", LineMap())
            ]
            self.error_label.setText("\n".join(lines))
            return None
        problems = [
            f"rules[{i}].site: the site is not listed under Sites of this scenario."
            for i, rule in enumerate(scenario.rules)
            if rule.site is not None and rule.site not in scenario.sites
        ]
        if problems:
            self.error_label.setText("\n".join(problems))
            return None
        self.error_label.setText("")
        return scenario

    def save(self) -> bool:
        scenario = self._validate()
        if scenario is None or self._root is None:
            return False
        path = self._root / "scenarios" / f"{self._id}.yaml"
        try:
            path.write_bytes(dump_model(scenario).encode("utf-8"))
        except OSError:
            self.error_label.setText("The file could not be written. Check the folder permissions.")
            return False
        self._original = scenario
        self._set_modified(False)
        self.saved.emit()
        return True


def _fill(table: QTableWidget, headers: list[str], rows: list[list[str]]) -> None:
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(r, c, item)
    table.resizeColumnsToContents()


class ScenarioView(QWidget):
    computed = Signal(object)
    compute_failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.project: Project | None = None
        self.last_run: ScenarioRun | None = None
        self.is_stale = False
        self._key = ""
        self._worker: ScenarioWorker | None = None

        self.combo = QComboBox()
        self.compute_button = QPushButton("Compute")
        self.compute_button.clicked.connect(lambda: self.compute())
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.empty_label = QLabel("No scenario to show. Open a project that has scenarios.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        top = QHBoxLayout()
        top.addWidget(QLabel("Scenario"))
        top.addWidget(self.combo)
        top.addWidget(self.compute_button)
        top.addWidget(self.status, 1)

        self.timeline = TimelineWidget()
        self.editor = ScenarioEditor()
        self.eclipse_table = QTableWidget()
        self.passes_table = QTableWidget()
        self.timeline_table = QTableWidget()
        tabs = QTabWidget()
        tabs.addTab(self.editor, "Rules and segments")
        tabs.addTab(self.eclipse_table, "Eclipses")
        tabs.addTab(self.passes_table, "Passes")
        tabs.addTab(self.timeline_table, "Mode timeline")

        self.body = QSplitter(Qt.Orientation.Vertical)
        self.body.addWidget(self.timeline)
        self.body.addWidget(tabs)
        self.body.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.body)

        self.combo.currentTextChanged.connect(self._selected)
        self.timeline.range_selected.connect(self._range_selected)
        self.set_project(None)

    # ---- project -----------------------------------------------------------------------------
    def selected_id(self) -> str:
        return self.combo.currentText()

    def set_project(self, project: Project | None) -> None:
        previous = self.selected_id()
        self.project = project
        ids = sorted(project.scenarios) if project else []
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItems(ids)
        if previous in ids:
            self.combo.setCurrentText(previous)
        self.combo.blockSignals(False)

        shown = bool(ids)
        self.empty_label.setVisible(not shown)
        self.body.setVisible(shown)
        self.compute_button.setEnabled(shown and self._worker is None)
        self.combo.setEnabled(shown)
        if not shown or project is None:
            self.editor.clear()
            self._show_run(None)
            self.status.setText("")
            return

        scenario_id = self.selected_id()
        scenario = project.scenarios[scenario_id]
        modes, sites = (
            sorted(project.modes),
            sorted(set(project.ground_stations) | set(project.targets)),
        )
        if self.editor._id == scenario_id and self.editor._original is not None:
            self.editor.reload_if_clean(scenario, modes, sites)
        else:
            self.editor.load(project.root, scenario_id, scenario, modes, sites)

        run = self.last_run
        if run is None or run.scenario_id != scenario_id:
            self._show_run(None)
            self.is_stale = False
            self.status.setText("Not computed yet. Press Compute.")
        elif run.scenario != scenario:
            if environment_key(project, scenario) == self._key:
                self.last_run = rebuild_timeline(run, scenario)
                self._show_run(self.last_run)
                self.status.setText("Timeline updated from the unchanged environment.")
            else:
                self.is_stale = True
                self.status.setText(
                    "The scenario parameters changed since the last computation. Press Compute."
                )

    def _selected(self, _text: str) -> None:
        if self.project is not None:
            self.last_run = None
            self.set_project(self.project)

    # ---- compute -----------------------------------------------------------------------------
    def compute(self) -> None:
        if self.project is None or not self.selected_id() or self._worker is not None:
            return
        self.compute_button.setEnabled(False)
        self.status.setText("Computing…")
        worker = ScenarioWorker(self.project, self.selected_id())
        worker.finished_ok.connect(self._done)
        worker.failed.connect(self._failed)
        self._worker = worker
        worker.start()

    def _finish_worker(self) -> None:
        if self._worker is not None:
            self._worker.wait(10000)
            self._worker = None
        self.compute_button.setEnabled(self.project is not None and bool(self.selected_id()))

    def _done(self, run: ScenarioRun) -> None:
        self._finish_worker()
        assert self.project is not None
        self.last_run = run
        self.is_stale = False
        self._key = environment_key(self.project, run.scenario)
        self._show_run(run)
        env = run.env
        passes = ", ".join(f"{sid} {len(v.passes)}" for sid, v in sorted(env.sites.items()))
        text = f"{len(env.eclipses)} eclipse(s)" + (f"; passes: {passes}" if passes else "")
        if run.notes:
            text += " — " + "; ".join(run.notes)
        self.status.setText(text)
        self.computed.emit(run)

    def _failed(self, message: str) -> None:
        self._finish_worker()
        self.last_run = None
        self._show_run(None)
        self.status.setText(message)
        self.compute_failed.emit(message)

    def wait_for_worker(self) -> None:
        if self._worker is not None:
            self._worker.wait(30000)

    # ---- display -----------------------------------------------------------------------------
    def _show_run(self, run: ScenarioRun | None) -> None:
        modes = sorted(self.project.modes) if self.project else []
        self.timeline.set_run(run, modes)
        if run is None:
            for table in (self.eclipse_table, self.passes_table, self.timeline_table):
                table.setRowCount(0)
            return
        start = run.env.grid.start

        def utc(seconds: float) -> str:
            return format_utc(start + timedelta(seconds=seconds))

        _fill(
            self.eclipse_table,
            ["Start (s)", "End (s)", "Duration (s)", "Start (UTC)"],
            [
                [f"{e.start_s:.1f}", f"{e.end_s:.1f}", f"{e.duration_s:.1f}", utc(e.start_s)]
                for e in run.env.eclipses
            ],
        )
        _fill(
            self.passes_table,
            ["Site", "Kind", "AOS (s)", "LOS (s)", "Duration (s)", "Max elevation (deg)"],
            [
                [
                    sid,
                    vis.site.kind,
                    f"{p.aos_s:.1f}",
                    f"{p.los_s:.1f}",
                    f"{p.duration_s:.1f}",
                    f"{p.max_elevation_deg:.1f}",
                ]
                for sid, vis in sorted(run.env.sites.items())
                for p in vis.passes
            ],
        )
        _fill(
            self.timeline_table,
            ["Start (s)", "End (s)", "Duration (s)", "Mode"],
            [
                [f"{s.start_s:.1f}", f"{s.end_s:.1f}", f"{s.duration_s:.1f}", s.mode]
                for s in run.timeline
            ],
        )

    def _range_selected(self, start: float, end: float) -> None:
        if self.project is not None and self.selected_id():
            self.editor.add_segment(round(start, 1), round(end - start, 1))

    # ---- export ------------------------------------------------------------------------------
    def export_to(self, folder: Path) -> list[Path]:
        if self.last_run is None or self.project is None:
            return []
        provenance = make_provenance(self.project, scenario=self.last_run.scenario_id)
        return write_scenario_outputs(self.last_run, provenance, folder)

    def confirm_discard_pending_edit(self) -> bool:
        if not self.editor.is_modified():
            return True
        answer = QMessageBox.question(
            self,
            "Scenario",
            "The scenario has unsaved edits. Discard them?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Discard
