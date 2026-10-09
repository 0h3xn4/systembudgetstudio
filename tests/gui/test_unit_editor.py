"""Unit-aware table editor for a unit's power modes."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from budget_core.io.project_loader import load_project
from budget_gui.main_window import MainWindow
from budget_gui.unit_editor import COLUMNS, UnitEditor

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
AVG, PEAK, DUTY = (COLUMNS.index(c) for c in ("avg_power_w", "peak_power_w", "duty_cycle_ratio"))


@pytest.fixture
def project(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "cubesat_3u", tmp_path / "p")
    return tmp_path / "p"


@pytest.fixture
def window(qtbot, project: Path):  # type: ignore[no-untyped-def]
    w = MainWindow()
    # pytest-qt closes the window before fixtures finish: drop unsaved edits first, else it asks
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(project)
    return w


def editor_for(window: MainWindow, unit_id: str = "camera") -> UnitEditor:
    editor = window.open_unit_editor(unit_id)
    assert editor is not None
    return editor


def set_cell(editor: UnitEditor, row: int, column: int, text: str) -> None:
    item = editor.table.item(row, column)
    assert item is not None
    item.setText(text)


def test_editor_shows_the_unit(window: MainWindow) -> None:
    editor = editor_for(window)
    assert editor.table.rowCount() == 2  # off, imaging
    assert editor.table.item(1, 0).text() == "imaging"
    assert editor.table.item(1, AVG).text() == "2.4"
    assert editor.fields["name"].text() == "Camera payload"
    assert window.editors.currentWidget() is editor
    assert not editor.is_modified() and editor.error_label.text() == ""


def test_units_can_be_typed_in_cells_and_are_saved_canonically(
    window: MainWindow, project: Path
) -> None:
    editor = editor_for(window)
    set_cell(editor, 1, AVG, "2500 mW")
    set_cell(editor, 1, PEAK, "4 W")
    assert editor.is_modified() and editor.error_label.text() == ""
    assert editor.save() is True
    reloaded = load_project(project).project
    assert reloaded is not None
    mode = reloaded.units["camera"].modes[1]
    assert mode.avg_power_w == pytest.approx(2.5) and mode.peak_power_w == pytest.approx(4.0)
    assert not editor.is_modified()
    assert b"\r" not in (project / "units" / "camera.yaml").read_bytes()


def test_plain_numbers_mean_the_canonical_unit(window: MainWindow) -> None:
    editor = editor_for(window)
    set_cell(editor, 1, AVG, "3")
    assert editor.error_label.text() == ""
    assert editor.current_unit().modes[1].avg_power_w == 3.0


def test_wrong_unit_kind_is_explained_and_nothing_is_written(
    window: MainWindow, project: Path
) -> None:
    before = (project / "units" / "camera.yaml").read_bytes()
    editor = editor_for(window)
    set_cell(editor, 1, AVG, "3 dBW")
    text = editor.error_label.text()
    assert "avg_power_w" in text and "logarithmic" in text
    assert editor.save() is False
    assert (project / "units" / "camera.yaml").read_bytes() == before


def test_cross_field_rule_is_reported(window: MainWindow) -> None:
    editor = editor_for(window)
    set_cell(editor, 1, PEAK, "1 W")  # below the 2.4 W average
    assert "peak" in editor.error_label.text().lower()
    assert editor.save() is False


def test_out_of_range_duty(window: MainWindow) -> None:
    editor = editor_for(window)
    set_cell(editor, 1, DUTY, "1.5")
    assert "duty_cycle_ratio" in editor.error_label.text() and editor.save() is False


def test_add_and_remove_modes(window: MainWindow, project: Path) -> None:
    editor = editor_for(window)
    editor.add_mode()
    assert editor.table.rowCount() == 3
    set_cell(editor, 2, 0, "standby")
    set_cell(editor, 2, AVG, "0.1")
    set_cell(editor, 2, PEAK, "0.2")
    assert editor.save() is True
    reloaded = load_project(project)
    assert reloaded.project is not None
    assert [m.name for m in reloaded.project.units["camera"].modes] == ["off", "imaging", "standby"]
    # the spacecraft modes do not list 'standby', but they still refer to valid modes
    editor.remove_mode(2)
    assert editor.table.rowCount() == 2 and editor.save() is True


def test_removing_a_mode_in_use_is_reported_by_the_problems_panel(window: MainWindow) -> None:
    editor = editor_for(window)
    editor.remove_mode(1)  # 'imaging' is used by the imaging spacecraft mode
    assert editor.save() is True
    assert "1 error" in window.problems_panel.summary.text()
    codes = {
        window.problems_panel.table.item(r, 1).text()
        for r in range(window.problems_panel.table.rowCount())
    }
    assert "REF_UNKNOWN_UNIT_MODE" in codes


def test_save_updates_budget_and_problems(window: MainWindow) -> None:
    editor = editor_for(window)
    model = window.power_view.table_model("Summary", 0)
    row = next(r for r in range(model.rowCount()) if model.data(model.index(r, 0)) == "Imaging")
    before = model.data(model.index(row, 1))
    set_cell(editor, 1, AVG, "5")
    assert editor.save() is False  # 5 W average is above the 3.2 W peak: not written
    set_cell(editor, 1, PEAK, "6")
    assert editor.save() is True
    after_model = window.power_view.table_model("Summary", 0)
    after = after_model.data(after_model.index(row, 1))
    assert float(after) > float(before)


def test_unsaved_unit_edits_prompt_on_close(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtWidgets import QMessageBox

    editor = editor_for(window)
    set_cell(editor, 1, AVG, "3")
    assert window.editors.has_unsaved_changes()
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Cancel)
    assert window.close() is False
    editor.discard_changes()
    assert not window.editors.has_unsaved_changes()


def test_duplicate_open_reuses_the_tab(window: MainWindow) -> None:
    first = editor_for(window)
    assert editor_for(window) is first
    assert first.table.item(0, 0).flags() & Qt.ItemFlag.ItemIsEditable
