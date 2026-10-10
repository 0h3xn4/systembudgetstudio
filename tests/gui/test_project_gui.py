"""Main GUI flows for M2a: open, Problems, jump to the offending line, edit, save, export."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from budget_gui.main_window import MainWindow
from tests.helpers import edit, line_of, write_valid_project

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def window(qtbot):  # type: ignore[no-untyped-def]
    w = MainWindow()
    # pytest-qt closes the window before fixtures finish: drop unsaved edits first, else it asks
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    return w


def replace_text(editor, old: str, new: str) -> None:  # type: ignore[no-untyped-def]
    """Edit like a user would (a cursor edit), so the document is marked as modified."""
    from PySide6.QtGui import QTextCursor

    text = editor.toPlainText()
    assert old in text
    cursor = QTextCursor(editor.document())
    cursor.select(QTextCursor.SelectionType.Document)
    cursor.insertText(text.replace(old, new, 1))


@pytest.fixture
def broken(tmp_path: Path) -> Path:
    write_valid_project(tmp_path / "proj")
    edit(tmp_path / "proj", "units/obc.yaml", "bus: main", "bus: nope")
    return tmp_path / "proj"


def test_open_example_fills_tree_problems_and_power_view(window: MainWindow) -> None:
    window.open_project(EXAMPLES / "cubesat_3u")
    assert "Example 3U CubeSat" in window.windowTitle()
    top = window.tree.topLevelItem(0)
    assert top is not None and "Example 3U CubeSat" in top.text(0)
    assert window.tree.file_item_count() >= 6 + 5 + 2  # units, modes, project and spacecraft files
    assert window.problems_panel.table.rowCount() == len(window.session.problems) > 0
    assert "0 errors" in window.problems_panel.summary.text()
    titles = [window.power_view.tabText(i) for i in range(window.power_view.count())]
    assert titles[0] == "Summary" and "Assumptions" in titles and "Provenance" in titles
    assert len(titles) == 1 + 5 + 3 - 1  # the Problems section lives in the Problems panel


def test_placeholders_show_as_na_and_a_banner_is_visible(window: MainWindow) -> None:
    window.open_project(EXAMPLES / "cubesat_3u")
    assert (
        window.power_view.banner.isVisibleTo(window)
        and "INCOMPLETE" in window.power_view.banner.text()
    )
    model = window.power_view.table_model("Summary", 0)
    assert model.data(model.index(0, 2), Qt.ItemDataRole.DisplayRole) == "n/a"
    assert model.data(model.index(0, 1), Qt.ItemDataRole.DisplayRole) != "n/a"


def test_errors_block_the_budget_and_are_listed(window: MainWindow, broken: Path) -> None:
    window.open_project(broken)
    assert "1 error" in window.problems_panel.summary.text()
    assert window.power_view.count() == 0 and window.power_view.empty_label.isVisibleTo(window)
    codes = [
        window.problems_panel.table.item(r, 1).text()
        for r in range(window.problems_panel.table.rowCount())
    ]
    assert "REF_UNKNOWN_BUS" in codes


def test_double_click_jumps_to_the_offending_line(window: MainWindow, broken: Path) -> None:
    window.open_project(broken)
    window.problems_panel.activate_row(0)
    editor = window.editors.current_editor()
    assert editor is not None and editor.rel_path == "units/obc.yaml"
    assert editor.current_line() == line_of(broken, "units/obc.yaml", "bus: nope")


def test_fix_save_reloads_and_clears_the_error(window: MainWindow, broken: Path) -> None:
    window.open_project(broken)
    window.problems_panel.activate_row(0)
    editor = window.editors.current_editor()
    assert editor is not None
    replace_text(editor, "bus: nope", "bus: main")
    assert editor.document().isModified()
    assert window.save_current() is True
    assert "bus: main" in (broken / "units" / "obc.yaml").read_text(encoding="utf-8")
    assert "0 errors" in window.problems_panel.summary.text()
    assert window.power_view.count() > 0
    assert not editor.document().isModified()


def test_saved_files_use_lf_line_endings(window: MainWindow, broken: Path) -> None:
    window.open_project(broken)
    window.problems_panel.activate_row(0)
    editor = window.editors.current_editor()
    assert editor is not None
    replace_text(editor, "bus: nope", "bus: main")
    window.save_current()
    assert b"\r" not in (broken / "units" / "obc.yaml").read_bytes()


def test_export_runs_in_a_worker_and_writes_files(
    window: MainWindow, qtbot, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    window.open_project(EXAMPLES / "cubesat_3u")
    with qtbot.waitSignal(window.export_finished, timeout=60000) as blocker:
        window.export_to(tmp_path / "out", {"xlsx", "json"})
    names = sorted(Path(p).name for p in blocker.args[0])
    assert names == [
        "link_static.json",
        "link_static.xlsx",
        "mass_static.json",
        "mass_static.xlsx",
        "power_static.json",
        "power_static.xlsx",
        "thermal_static.json",
        "thermal_static.xlsx",
    ]
    assert (tmp_path / "out" / "power_static.xlsx").stat().st_size > 1000


def test_export_failure_is_a_plain_message_not_a_traceback(
    window: MainWindow, qtbot, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    window.open_project(EXAMPLES / "cubesat_3u")
    blocked = tmp_path / "file"
    blocked.write_text("x", encoding="utf-8")
    with qtbot.waitSignal(window.export_failed, timeout=60000) as blocker:
        window.export_to(blocked / "sub", {"json"})
    assert "Traceback" not in blocker.args[0] and "folder" in blocker.args[0].lower()


def test_open_missing_folder_is_reported_not_raised(window: MainWindow, tmp_path: Path) -> None:
    window.open_project(tmp_path / "nope")
    assert "FILE_NOT_FOUND" in window.problems_panel.table.item(0, 1).text()
    assert window.power_view.count() == 0


def test_tree_double_click_opens_the_file(window: MainWindow) -> None:
    window.open_project(EXAMPLES / "cubesat_3u")
    window.tree.request_file("units/obc.yaml")
    editor = window.editors.current_editor()
    assert editor is not None and editor.rel_path == "units/obc.yaml"
    assert "schema_version: 2" in editor.toPlainText()


def test_dirty_state_is_shown_in_the_tab_title(window: MainWindow) -> None:
    window.open_project(EXAMPLES / "cubesat_3u")
    window.tree.request_file("units/obc.yaml")
    editor = window.editors.current_editor()
    assert editor is not None
    replace_text(editor, "schema_version: 2", "schema_version: 2 ")
    assert window.editors.tabText(window.editors.currentIndex()).endswith("*")
    assert window.editors.has_unsaved_changes()
    editor.document().setModified(False)  # otherwise closing the window asks (tested below)
    assert not window.editors.tabText(window.editors.currentIndex()).endswith("*")


def test_closing_with_unsaved_changes_asks(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtWidgets import QMessageBox

    window.open_project(EXAMPLES / "cubesat_3u")
    window.tree.request_file("units/obc.yaml")
    editor = window.editors.current_editor()
    assert editor is not None
    replace_text(editor, "schema_version: 2", "schema_version: 2 ")
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Cancel)
    assert window.close() is False
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Discard)
    assert window.close() is True


def test_reload_keeps_unsaved_edits(window: MainWindow, broken: Path) -> None:
    window.open_project(broken)
    window.problems_panel.activate_row(0)
    editor = window.editors.current_editor()
    assert editor is not None
    replace_text(editor, "bus: nope", "bus: main")
    window.session.reload()  # e.g. F5: the file on disk still has the error
    assert "bus: main" in editor.toPlainText() and editor.document().isModified()
    assert "1 error" in window.problems_panel.summary.text()
    editor.document().setModified(False)


def test_mass_budget_tab_shows_phases_and_a_centre_of_gravity(window: MainWindow) -> None:
    window.open_project(EXAMPLES / "microsat_150kg")
    view = window.mass_view
    window.editors.setCurrentWidget(view)  # a hidden tab is not visible
    titles = [view.tabText(i) for i in range(view.count())]
    assert titles == [
        "Summary",
        "Phase launch",
        "Phase bol",
        "Phase eol",
        "Assumptions",
        "Provenance",
    ]
    assert view.banner.isVisibleTo(window) and "INCOMPLETE" in view.banner.text()
    model = view.table_model("Summary", 0)
    assert model.data(model.index(0, 0)) == "launch"
    assert model.data(model.index(0, 4)) != "n/a"  # CG x is computed from invented geometry
    assert model.data(model.index(0, 2)) == "n/a"  # margined totals need placeholders


def test_expendables_are_in_the_tree_and_can_be_opened(window: MainWindow) -> None:
    window.open_project(EXAMPLES / "microsat_150kg")
    window.tree.request_file("expendables/propellant.yaml")
    editor = window.editors.current_editor()
    assert editor is not None and "masses_kg" in editor.toPlainText()


def test_removing_a_position_in_the_editor_produces_a_mass_warning(
    window: MainWindow, tmp_path: Path
) -> None:
    import shutil

    shutil.copytree(EXAMPLES / "cubesat_3u", tmp_path / "p")
    window.open_project(tmp_path / "p")
    window.tree.request_file("units/gnss.yaml")
    editor = window.editors.current_editor()
    assert editor is not None
    text = editor.toPlainText()
    start = text.index("mass_properties:")
    replace_text(editor, text[start:], "")
    assert window.save_current() is True
    codes = {
        window.problems_panel.table.item(r, 1).text()
        for r in range(window.problems_panel.table.rowCount())
    }
    assert "MASS_PROPS_MISSING" in codes
    assert "1 error" not in window.problems_panel.summary.text()


def test_unit_editor_keeps_mass_properties(window: MainWindow, tmp_path: Path) -> None:
    import shutil

    from budget_core.io.project_loader import load_project

    shutil.copytree(EXAMPLES / "cubesat_3u", tmp_path / "p")
    window.open_project(tmp_path / "p")
    editor = window.open_unit_editor("camera")
    assert editor is not None
    editor.table.item(1, 1).setText("2.6")
    editor.table.item(1, 2).setText("3.5")
    assert editor.save() is True
    unit = load_project(tmp_path / "p").project.units["camera"]  # type: ignore[union-attr]
    assert unit.mass_properties is not None and unit.mass_properties.position_m[2] == 0.26
