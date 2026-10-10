"""Help > User guide: the offline guide inside the window."""

from __future__ import annotations

from pathlib import Path

import pytest

from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def window(qtbot) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    return w


def test_guide_opens_without_a_project(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = window.open_guide()
    qtbot.addWidget(dialog)
    text = dialog.browser.toPlainText()
    assert "Quick start" in text and "Equations and sources" in text
    assert "Numbers in the configuration of" not in text


def test_guide_lists_the_open_projects_numbers(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    window.open_project(EXAMPLES / "cubesat_3u")
    dialog = window.open_guide()
    qtbot.addWidget(dialog)
    assert "Numbers in the configuration of" in dialog.browser.toPlainText()


def test_guide_can_be_saved(window: MainWindow, tmp_path: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
    dialog = window.open_guide()
    qtbot.addWidget(dialog)
    paths = dialog.save_to(tmp_path)
    assert sorted(p.name for p in paths) == [
        "system-budget-studio-guide.html",
        "system-budget-studio-guide.pdf",
    ]
    assert all(p.stat().st_size > 10000 for p in paths)
