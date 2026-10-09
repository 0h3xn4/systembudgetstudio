"""Main window: project tree, budget view and file editors, Problems panel, export."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QStatusBar,
)

from budget_core import APP_NAME, __version__
from budget_core.problems import sort_problems
from budget_core.reports.run import REPORT_KINDS
from budget_gui.editor import EditorTabs
from budget_gui.scenario_view import ScenarioView
from budget_gui.session import ProjectSession
from budget_gui.timeline_view import PowerTimelineView
from budget_gui.unit_editor import UnitEditor
from budget_gui.widgets import PowerView, ProblemsPanel, ProjectTree
from budget_gui.worker import ExportWorker


class MainWindow(QMainWindow):
    export_finished = Signal(list)
    export_failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1400, 860)
        self.session = ProjectSession()
        self.tree = ProjectTree()
        self.problems_panel = ProblemsPanel()
        self.power_view = PowerView()
        self.mass_view = PowerView()
        self.editors = EditorTabs()
        self.editors.add_fixed(self.power_view, "Power budget")
        self.editors.add_fixed(self.mass_view, "Mass budget")
        self.scenario_view = ScenarioView()
        self.editors.add_fixed(self.scenario_view, "Scenario")
        self.editors.register_modifiable(self.scenario_view.editor)
        self.timeline_view = PowerTimelineView()
        self.timeline_view.run_provider = self.scenario_view.reusable_run
        self.editors.add_fixed(self.timeline_view, "Power timeline")
        self.setCentralWidget(self.editors)
        self._worker: ExportWorker | None = None

        left = QDockWidget("Project", self)
        left.setWidget(self.tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, left)
        bottom = QDockWidget("Problems", self)
        bottom.setWidget(self.problems_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, bottom)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(f"Version {__version__} — offline")

        self._build_menu()
        self.session.changed.connect(self._refresh)
        self.scenario_view.editor.saved.connect(self.session.reload)
        self.tree.file_requested.connect(lambda rel: self.open_file(rel))
        self.tree.unit_requested.connect(lambda unit_id: self.open_unit_editor(unit_id))
        self.problems_panel.jump_requested.connect(lambda rel, line: self.open_file(rel, line))
        self.timeline_view.computed.connect(lambda _result: self._update_problems())
        self.timeline_view.jump_requested.connect(self.jump_to_input)

    # ---- actions -----------------------------------------------------------------------------
    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        def add(text: str, shortcut: QKeySequence | QKeySequence.StandardKey, slot: object) -> None:
            action = QAction(text, self)
            action.setShortcut(shortcut)
            action.triggered.connect(slot)
            file_menu.addAction(action)

        add("&Open project…", QKeySequence.StandardKey.Open, self._choose_project)
        add("&Save file", QKeySequence.StandardKey.Save, self.save_current)
        add("&Reload project", QKeySequence(Qt.Key.Key_F5), self.session.reload)
        file_menu.addSeparator()
        add("Edit unit &power modes\u2026", QKeySequence("Ctrl+M"), self._edit_selected_unit)
        add("&Export reports…", QKeySequence("Ctrl+E"), self._choose_export)
        add("Export power &timeline…", QKeySequence("Ctrl+Shift+E"), self._choose_timeline_export)
        file_menu.addSeparator()
        add("&Quit", QKeySequence.StandardKey.Quit, self.close)

    def _choose_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open project folder")
        if folder:
            self.open_project(Path(folder))

    def _choose_scenario_export(self) -> None:
        if self.scenario_view.last_run is None:
            QMessageBox.information(self, APP_NAME, "Compute a scenario first (Ctrl+R).")
            return
        folder = QFileDialog.getExistingDirectory(self, "Export scenario results to folder")
        if folder:
            self.scenario_view.export_to(Path(folder))

    def _choose_timeline_export(self) -> None:
        if self.timeline_view.result is None:
            QMessageBox.information(
                self, APP_NAME, "Compute the power timeline first (Power timeline tab)."
            )
            return
        folder = QFileDialog.getExistingDirectory(self, "Export power timeline to folder")
        if folder:
            self.timeline_view.export_to(Path(folder), set(REPORT_KINDS))

    def _edit_selected_unit(self) -> None:
        unit_id = self.tree.current_unit_id()
        if unit_id:
            self.open_unit_editor(unit_id)

    def _choose_export(self) -> None:
        if not self.session.outputs:
            QMessageBox.information(
                self,
                APP_NAME,
                "There is no budget to export yet. Fix the errors in the Problems panel first.",
            )
            return
        folder = QFileDialog.getExistingDirectory(self, "Export reports to folder")
        if folder:
            self.export_to(Path(folder), set(REPORT_KINDS))

    # ---- project -----------------------------------------------------------------------------
    def open_project(self, path: Path) -> None:
        self.editors.close_all_files()
        self.session.open(Path(path))

    def open_file(self, rel: str, line: int | None = None) -> None:
        if self.session.path is None or not (self.session.path / rel).is_file():
            return
        self.editors.open_file(self.session.path, rel, line)

    def _line_of(self, rel: str, path: str) -> int | None:
        lines = self.session.load_result.lines.get(rel) if self.session.load_result else None
        if lines is None:
            return None
        return lines.lookup(tuple(p for p in path.split(".") if p))

    def jump_to_input(self, rel: str, path: str) -> None:
        """Open the file that governs a finding at the line of the named field."""
        self.open_file(rel, self._line_of(rel, path))

    def open_unit_editor(self, unit_id: str) -> UnitEditor | None:
        """Open (or focus) the power-mode table editor of a unit of the loaded project."""
        project = self.session.project
        if project is None or self.session.path is None or unit_id not in project.units:
            QMessageBox.information(
                self,
                APP_NAME,
                "Fix the errors in the Problems panel first; "
                "the table editor needs a project that loads.",
            )
            return None
        existing = self.editors.unit_editor(unit_id)
        if existing is not None:
            self.editors.setCurrentWidget(existing)
            return existing
        editor = UnitEditor(self.session.path, unit_id, project.units[unit_id])
        editor.saved.connect(self.session.reload)
        self.editors.add_unit_editor(unit_id, editor)
        return editor

    def save_current(self) -> bool:
        unit_editor = self.editors.current_unit_editor()
        if unit_editor is not None:
            return unit_editor.save()
        editor = self.editors.current_editor()
        if editor is None:
            return False
        try:
            editor.save()
        except OSError:
            QMessageBox.warning(
                self,
                APP_NAME,
                "The file could not be saved. Check that you may write to the project folder.",
            )
            return False
        self.session.reload()
        return True

    def _refresh(self) -> None:
        session = self.session
        project = session.project
        self.tree.set_project(session.path, project)
        self.power_view.set_document(session.document)
        self.mass_view.set_document(session.mass_document)
        self.scenario_view.set_project(project)
        load_problems = session.load_result.problems if session.load_result else []
        self.timeline_view.set_project(project, load_problems)
        self._update_problems()
        self.editors.reload_clean_files()
        name = project.meta.name if project else (session.path.name if session.path else "")
        self.setWindowTitle(f"{name} — {APP_NAME}" if name else APP_NAME)
        self.statusBar().showMessage(f"{name}: {self.problems_panel.summary.text()}")

    def _update_problems(self) -> None:
        """Project problems plus the findings of the last power timeline (violations, gaps), each
        with the line of its input so the panel can jump to it."""
        known = {(p.code, p.file, p.path, p.message) for p in self.session.problems}
        extra = [
            p
            for p in self.timeline_view.problems()
            if (p.code, p.file, p.path, p.message) not in known
        ]
        located = [
            replace(p, line=self._line_of(p.file, p.path))
            if p.line is None and p.file and p.path
            else p
            for p in [*self.session.problems, *extra]
        ]
        self.problems_panel.set_problems(sort_problems(located))
        if self.session.project is not None:
            name = self.session.project.meta.name
            self.statusBar().showMessage(f"{name}: {self.problems_panel.summary.text()}")

    # ---- export ------------------------------------------------------------------------------
    def export_to(self, folder: Path, kinds: Collection[str]) -> None:
        session = self.session
        if not session.outputs:
            self.export_failed.emit("There is no budget to export; fix the errors first.")
            return
        worker = ExportWorker(session.outputs, folder, kinds)
        worker.finished_ok.connect(self._export_done)
        worker.failed.connect(self._export_failed)
        self._worker = worker
        self.statusBar().showMessage("Exporting…")
        worker.start()

    def _export_done(self, paths: list[str]) -> None:
        self.statusBar().showMessage(f"Exported {len(paths)} file(s).")
        self.export_finished.emit(paths)

    def _export_failed(self, message: str) -> None:
        self.statusBar().showMessage(message)
        self.export_failed.emit(message)

    # ---- closing -----------------------------------------------------------------------------
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt naming)
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(10000)
        self.scenario_view.wait_for_worker()
        self.timeline_view.wait_for_worker()
        if self.editors.has_unsaved_changes():
            answer = QMessageBox.question(
                self,
                APP_NAME,
                "Some files have unsaved changes. Close without saving?",
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Discard:
                event.ignore()
                return
        event.accept()
