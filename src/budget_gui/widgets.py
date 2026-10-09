"""Project tree, Problems panel and the power budget view."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QLabel,
    QMenu,
    QScrollArea,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from budget_core.model import Project
from budget_core.problems import Problem, Severity
from budget_core.reports.document import NA, ReportDocument, Table, format_cell

SEVERITY_COLOURS = {
    Severity.ERROR: "#da1e28",
    Severity.WARNING: "#b28600",
    Severity.INFO: "#0043ce",
}
Index = QModelIndex | QPersistentModelIndex
_NO_PARENT = QModelIndex()
UNIT_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class DocTableModel(QAbstractTableModel):
    """Read-only model over a report `Table`, so the screen shows exactly what reports contain."""

    def __init__(self, table: Table) -> None:
        super().__init__()
        self.table = table

    def rowCount(self, parent: Index = _NO_PARENT) -> int:
        return 0 if parent.isValid() else len(self.table.rows)

    def columnCount(self, parent: Index = _NO_PARENT) -> int:
        return 0 if parent.isValid() else len(self.table.columns)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.table.columns[section].header
        return None

    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        column = self.table.columns[index.column()]
        value = self.table.rows[index.row()][index.column()]
        text = format_cell(value, column)
        if role == Qt.ItemDataRole.DisplayRole:
            return text
        if role == Qt.ItemDataRole.TextAlignmentRole:
            numeric = column.kind != "text" or value is None
            horizontal = Qt.AlignmentFlag.AlignRight if numeric else Qt.AlignmentFlag.AlignLeft
            return int(horizontal | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ForegroundRole and text == NA:
            return QBrush(QColor("#8d8d8d"))
        return None


class ProblemsPanel(QWidget):
    """All problems of the open project; double-click or Enter jumps to the offending line."""

    jump_requested = Signal(str, int)

    def __init__(self) -> None:
        super().__init__()
        self.summary = QLabel("No project open")
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Severity", "Code", "Location", "Message"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemActivated.connect(lambda item: self.activate_row(item.row()))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.addWidget(self.summary)
        layout.addWidget(self.table)
        self._problems: list[Problem] = []

    def set_problems(self, problems: list[Problem]) -> None:
        self._problems = list(problems)
        errors = sum(p.severity is Severity.ERROR for p in problems)
        warnings = sum(p.severity is Severity.WARNING for p in problems)
        infos = len(problems) - errors - warnings
        self.summary.setText(
            f"{errors} error{'s' if errors != 1 else ''}, "
            f"{warnings} warning{'s' if warnings != 1 else ''}"
            + (f", {infos} info" if infos else "")
        )
        self.table.setRowCount(len(problems))
        for row, problem in enumerate(problems):
            where = problem.file or "<project>"
            if problem.line is not None:
                where += f":{problem.line}"
            message = problem.message + (f"  {problem.hint}" if problem.hint else "")
            cells = [problem.severity.value.capitalize(), problem.code, where, message]
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if column == 0:
                    item.setForeground(QBrush(QColor(SEVERITY_COLOURS[problem.severity])))
                item.setToolTip(problem.path)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

    def activate_row(self, row: int) -> None:
        if 0 <= row < len(self._problems):
            problem = self._problems[row]
            if problem.file:
                self.jump_requested.emit(problem.file, problem.line or 1)


class ProjectTree(QTreeWidget):
    """Files of the project folder, grouped like the project layout."""

    file_requested = Signal(str)
    unit_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setHeaderHidden(True)
        self.itemDoubleClicked.connect(self._activated)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)

    def _activated(self, item: QTreeWidgetItem, _column: int) -> None:
        rel = item.data(0, Qt.ItemDataRole.UserRole)
        if rel:
            self.file_requested.emit(str(rel))

    def current_unit_id(self) -> str | None:
        item = self.currentItem()
        unit = item.data(0, UNIT_ROLE) if item else None
        return str(unit) if unit else None

    def _context_menu(self, pos: Any) -> None:
        item = self.itemAt(pos)
        unit = item.data(0, UNIT_ROLE) if item else None
        if not unit:
            return
        menu = QMenu(self)
        action = menu.addAction("Edit power modes…")
        if menu.exec(self.viewport().mapToGlobal(pos)) is action:
            self.unit_requested.emit(str(unit))

    def request_file(self, rel: str) -> None:
        self.file_requested.emit(rel)

    def file_item_count(self) -> int:
        count = 0
        stack = [self.invisibleRootItem()]
        while stack:
            node = stack.pop()
            for i in range(node.childCount()):
                child = node.child(i)
                count += 1 if child.data(0, Qt.ItemDataRole.UserRole) else 0
                stack.append(child)
        return count

    def set_project(self, root: Path | None, project: Project | None) -> None:
        self.clear()
        if root is None:
            return
        top = QTreeWidgetItem([project.meta.name if project else root.name])
        self.addTopLevelItem(top)

        def add(parent: QTreeWidgetItem, label: str, rel: str, unit_id: str | None = None) -> None:
            item = QTreeWidgetItem([label])
            item.setData(0, Qt.ItemDataRole.UserRole, rel)
            if unit_id:
                item.setData(0, UNIT_ROLE, unit_id)
            parent.addChild(item)

        for name in ("project.yaml", "spacecraft.yaml"):
            if (root / name).is_file():
                add(top, name, name)
        for folder, title in (
            ("units", "Units"),
            ("expendables", "Expendables"),
            ("modes", "Spacecraft modes"),
            ("config", "Configuration"),
        ):
            files = sorted((root / folder).glob("*.yaml")) if (root / folder).is_dir() else []
            if not files:
                continue
            group = QTreeWidgetItem([f"{title} ({len(files)})"])
            top.addChild(group)
            for path in files:
                label = path.stem
                if project and folder == "units" and path.stem in project.units:
                    label = f"{path.stem}: {project.units[path.stem].name}"
                add(
                    group,
                    label,
                    f"{folder}/{path.name}",
                    path.stem
                    if folder == "units" and project and path.stem in project.units
                    else None,
                )
            group.setExpanded(folder != "config")
        top.setExpanded(True)


class PowerView(QWidget):
    """Tabs with the same tables the reports contain (Summary, one tab per mode, Assumptions)."""

    def __init__(self) -> None:
        super().__init__()
        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.setStyleSheet("color: #da1e28; font-weight: 600; padding: 4px;")
        self.empty_label = QLabel("No budget to show. Open a project without errors.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tabs = QTabWidget()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.banner)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.tabs)
        self._models: dict[str, list[DocTableModel]] = {}
        self.set_document(None)

    def count(self) -> int:
        return self.tabs.count()

    def tabText(self, index: int) -> str:  # noqa: N802 (Qt naming)
        return self.tabs.tabText(index)

    def table_model(self, tab: str, index: int) -> DocTableModel:
        return self._models[tab][index]

    def set_document(self, document: ReportDocument | None) -> None:
        self.tabs.clear()
        self._models = {}
        shown = document is not None
        self.empty_label.setVisible(not shown)
        self.tabs.setVisible(shown)
        self.banner.setVisible(bool(document and document.banner))
        self.banner.setText(document.banner if document else "")
        if document is None:
            return
        for section in document.sections:
            if section.sheet_name == "Problems":  # shown in the Problems panel instead
                continue
            page = QWidget()
            layout = QVBoxLayout(page)
            models: list[DocTableModel] = []
            for text in section.paragraphs:
                layout.addWidget(QLabel(text))
            for table in section.tables:
                title = QLabel(table.title)
                title.setStyleSheet("font-weight: 600; padding-top: 6px;")
                layout.addWidget(title)
                model = DocTableModel(table)
                models.append(model)
                view = QTableView()
                view.setModel(model)
                view.verticalHeader().setVisible(False)
                view.setAlternatingRowColors(True)
                view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
                view.resizeColumnsToContents()
                view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                height = view.horizontalHeader().height() + 2 * view.frameWidth() + 18
                height += sum(view.rowHeight(r) for r in range(len(table.rows)))
                view.setFixedHeight(max(height, 60))
                layout.addWidget(view)
                if table.note:
                    note = QLabel(table.note)
                    note.setWordWrap(True)
                    layout.addWidget(note)
            layout.addStretch(1)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(page)
            self.tabs.addTab(
                scroll, section.sheet_name if section.sheet_name != "Summary" else "Summary"
            )
            self._models[section.sheet_name] = models
