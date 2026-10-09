"""YAML text editor with line numbers and jump-to-line (the target of Problems links)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QTextCharFormat,
    QTextFormat,
)
from PySide6.QtWidgets import QPlainTextEdit, QTabBar, QTabWidget, QTextEdit, QWidget

from budget_gui.unit_editor import UnitEditor


class _Gutter(QWidget):
    def __init__(self, editor: YamlEditor) -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return QSize(self._editor.gutter_width(), 0)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        self._editor.paint_gutter(event)


class YamlEditor(QPlainTextEdit):
    def __init__(self, path: Path, rel_path: str) -> None:
        super().__init__()
        self.path = path
        self.rel_path = rel_path
        self.setFont(QFont("IBM Plex Mono", 10))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._gutter = _Gutter(self)
        self.blockCountChanged.connect(self._update_margin)
        self.updateRequest.connect(self._scroll_gutter)
        self._update_margin()
        self.load()

    def load(self) -> None:
        text = self.path.read_bytes().decode("utf-8", errors="replace")
        self.setPlainText(text.replace("\r\n", "\n"))
        self.document().setModified(False)

    def save(self) -> None:
        self.path.write_bytes(self.toPlainText().encode("utf-8"))  # LF only (QPlainTextEdit)
        self.document().setModified(False)

    def current_line(self) -> int:
        return int(self.textCursor().blockNumber()) + 1

    def goto_line(self, line: int) -> None:
        block = self.document().findBlockByNumber(max(line - 1, 0))
        if not block.isValid():
            block = self.document().lastBlock()
        cursor = self.textCursor()
        cursor.setPosition(block.position())
        self.setTextCursor(cursor)
        self.centerCursor()
        selection = QTextEdit.ExtraSelection()
        highlight = QTextCharFormat()
        highlight.setBackground(QColor("#fcf4d6"))
        highlight.setProperty(QTextFormat.Property.FullWidthSelection, True)
        selection.format = highlight  # type: ignore[attr-defined]
        selection.cursor = cursor  # type: ignore[attr-defined]
        self.setExtraSelections([selection])
        self.setFocus()

    # ---- line number gutter ------------------------------------------------------------------
    def gutter_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_margin(self) -> None:
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _scroll_gutter(self, rect: QRect, dy: int) -> None:
        if dy:
            self._gutter.scroll(0, dy)
        else:
            self._gutter.update(0, rect.y(), self._gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_margin()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        area = self.contentsRect()
        self._gutter.setGeometry(QRect(area.left(), area.top(), self.gutter_width(), area.height()))

    def paint_gutter(self, event: QPaintEvent) -> None:
        painter = QPainter(self._gutter)
        painter.fillRect(event.rect(), QColor("#f4f4f4"))
        painter.setPen(QColor("#6f6f6f"))
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(
                    0,
                    top,
                    self._gutter.width() - 6,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    str(number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            number += 1


class EditorTabs(QTabWidget):
    """Workspace tabs: fixed tabs (the budget view) plus one closable tab per open file."""

    dirty_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self._close_tab)
        self._editors: dict[str, YamlEditor] = {}
        self._unit_editors: dict[str, UnitEditor] = {}
        self._modifiable: list[Any] = []  # fixed widgets with is_modified() and discard_changes()

    def add_fixed(self, widget: QWidget, title: str) -> None:
        index = self.addTab(widget, title)
        bar = self.tabBar()
        if bar is not None:  # the budget view cannot be closed: hide its close button
            button = bar.tabButton(index, QTabBar.ButtonPosition.RightSide)
            if button is not None:
                button.hide()

    def current_editor(self) -> YamlEditor | None:
        widget = self.currentWidget()
        return widget if isinstance(widget, YamlEditor) else None

    def open_file(self, root: Path, rel: str, line: int | None = None) -> YamlEditor:
        editor = self._editors.get(rel)
        if editor is None:
            editor = YamlEditor(root / rel, rel)
            editor.document().modificationChanged.connect(lambda _m, e=editor: self._retitle(e))
            self._editors[rel] = editor
            self.addTab(editor, Path(rel).name)
            self.setTabToolTip(self.indexOf(editor), rel)
        self.setCurrentWidget(editor)
        if line is not None:
            editor.goto_line(line)
        return editor

    def _retitle(self, editor: YamlEditor) -> None:
        index = self.indexOf(editor)
        if index >= 0:
            name = Path(editor.rel_path).name
            self.setTabText(index, name + ("*" if editor.document().isModified() else ""))
        self.dirty_changed.emit()

    def _close_tab(self, index: int) -> None:
        widget = self.widget(index)
        if isinstance(widget, YamlEditor):
            self._editors.pop(widget.rel_path, None)
        elif isinstance(widget, UnitEditor):
            self._unit_editors.pop(widget.unit_id, None)
        else:
            return
        self.removeTab(index)
        widget.deleteLater()

    def add_unit_editor(self, unit_id: str, editor: UnitEditor) -> None:
        self._unit_editors[unit_id] = editor
        index = self.addTab(editor, f"{unit_id} (modes)")
        editor.modified_changed.connect(lambda _m, e=editor: self._retitle_unit(e))
        self.setTabToolTip(index, editor.rel_path)
        self.setCurrentWidget(editor)

    def unit_editor(self, unit_id: str) -> UnitEditor | None:
        return self._unit_editors.get(unit_id)

    def current_unit_editor(self) -> UnitEditor | None:
        widget = self.currentWidget()
        return widget if isinstance(widget, UnitEditor) else None

    def _retitle_unit(self, editor: UnitEditor) -> None:
        index = self.indexOf(editor)
        if index >= 0:
            self.setTabText(
                index, f"{editor.unit_id} (modes)" + ("*" if editor.is_modified() else "")
            )
        self.dirty_changed.emit()

    def register_modifiable(self, widget: Any) -> None:
        self._modifiable.append(widget)

    def has_unsaved_changes(self) -> bool:
        return (
            any(e.document().isModified() for e in self._editors.values())
            or any(u.is_modified() for u in self._unit_editors.values())
            or any(w.is_modified() for w in self._modifiable)
        )

    def discard_all_changes(self) -> None:
        """Forget unsaved edits (after the user chose 'close without saving')."""
        for editor in self._editors.values():
            editor.document().setModified(False)
        for unit_editor in self._unit_editors.values():
            unit_editor.discard_changes()
        for widget in self._modifiable:
            widget.discard_changes()

    def close_all_files(self) -> None:
        for rel in list(self._editors):
            self._close_tab(self.indexOf(self._editors[rel]))
        for unit_id in list(self._unit_editors):
            self._close_tab(self.indexOf(self._unit_editors[unit_id]))

    def reload_clean_files(self) -> None:
        """After a project reload, refresh editors that have no unsaved edits."""
        for editor in self._editors.values():
            if not editor.document().isModified() and editor.path.is_file():
                line = editor.current_line()
                editor.load()
                if editor is self.currentWidget():
                    editor.goto_line(line)
