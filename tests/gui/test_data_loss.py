"""GUI data-loss and stale-result fixes: a second export while one runs, unsaved edits, results of
an older project revision, and jump lines for list paths."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def window(qtbot) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    return w


@pytest.fixture
def eps(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "cubesat_3u_eps", tmp_path / "p")
    return tmp_path / "p"


def answer(monkeypatch: pytest.MonkeyPatch, button: QMessageBox.StandardButton) -> list[str]:
    asked: list[str] = []

    def fake(_parent, _title, text, *_args, **_kwargs):  # type: ignore[no-untyped-def]
        asked.append(text)
        return button

    monkeypatch.setattr(QMessageBox, "question", staticmethod(fake))
    return asked


# ---- a second export while one runs ----------------------------------------------------------
def test_a_second_export_is_refused_while_one_runs(
    window: MainWindow, eps: Path, tmp_path: Path, qtbot
) -> None:  # type: ignore[no-untyped-def]
    window.open_project(EXAMPLES / "stress_200_units")
    refused: list[str] = []
    window.export_failed.connect(refused.append)
    window.export_to(tmp_path / "a", {"pdf", "docx"})
    window.export_to(tmp_path / "b", {"pdf", "docx"})  # used to destroy the running thread
    assert refused and "already" in refused[0]
    with qtbot.waitSignal(window.export_finished, timeout=120000):
        pass
    assert not (tmp_path / "b").exists()


def test_compare_view_refuses_a_second_export(
    window: MainWindow, eps: Path, tmp_path: Path, qtbot
) -> None:  # type: ignore[no-untyped-def]
    window.open_project(eps)
    view = window.compare_view
    view.set_other_folder(eps)
    with qtbot.waitSignal(view.computed, timeout=120000):
        view.compare()
    refused: list[str] = []
    view.export_failed.connect(refused.append)
    view.export_to(tmp_path / "a", {"pdf", "docx"})
    view.export_to(tmp_path / "b", {"pdf", "docx"})
    assert refused and "already" in refused[0]
    with qtbot.waitSignal(view.export_finished, timeout=120000):
        pass


# ---- stale results ---------------------------------------------------------------------------
def test_a_reload_blocks_exporting_the_old_timeline(window: MainWindow, eps: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
    window.open_project(eps)
    view = window.timeline_view
    with qtbot.waitSignal(view.computed, timeout=120000):
        view.compute()
    assert view.export_button.isEnabled() and view.output() is not None
    window.session.reload()
    assert view.is_stale
    assert not view.export_button.isEnabled()
    assert view.output() is None
    failed: list[str] = []
    view.export_failed.connect(failed.append)
    view.export_to(eps / "out", {"csv"})
    assert failed and "changed" in failed[0]


def test_a_result_that_arrives_after_a_reload_is_marked_stale(
    window: MainWindow, eps: Path, qtbot
) -> None:  # type: ignore[no-untyped-def]
    window.open_project(eps)
    view = window.timeline_view
    view.compute()
    window.session.reload()  # the project changes while the worker runs
    with qtbot.waitSignal(view.computed, timeout=120000):
        pass
    assert view.is_stale and not view.export_button.isEnabled()


def test_link_view_blocks_a_stale_export(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    window.open_project(EXAMPLES / "microsat_150kg")
    view = window.link_passes_view
    with qtbot.waitSignal(view.computed, timeout=120000):
        view.compute()
    window.session.reload()
    assert view.is_stale and not view.export_button.isEnabled() and view.output() is None


# ---- unsaved edits ---------------------------------------------------------------------------
def modify(window: MainWindow, rel: str):  # type: ignore[no-untyped-def]
    window.open_file(rel)
    editor = window.editors.current_editor()
    assert editor is not None
    editor.textCursor().insertText("# edit\n")
    assert editor.document().isModified()
    return editor


def test_closing_a_modified_tab_asks_first(
    window: MainWindow, eps: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window.open_project(eps)
    editor = modify(window, "project.yaml")
    asked = answer(monkeypatch, QMessageBox.StandardButton.Cancel)
    window.editors._close_tab(window.editors.indexOf(editor))
    assert asked and window.editors.indexOf(editor) >= 0 and editor.document().isModified()
    answer(monkeypatch, QMessageBox.StandardButton.Discard)
    window.editors._close_tab(window.editors.indexOf(editor))
    assert window.editors.indexOf(editor) < 0


def test_opening_another_project_asks_when_edits_are_unsaved(
    window: MainWindow, eps: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window.open_project(eps)
    modify(window, "project.yaml")
    asked = answer(monkeypatch, QMessageBox.StandardButton.Cancel)
    window.open_project(EXAMPLES / "microsat_150kg")
    assert asked and window.session.path == eps  # still the first project
    answer(monkeypatch, QMessageBox.StandardButton.Discard)
    window.open_project(EXAMPLES / "microsat_150kg")
    assert window.session.path == EXAMPLES / "microsat_150kg"


def test_clean_tabs_close_without_asking(
    window: MainWindow, eps: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window.open_project(eps)
    window.open_file("project.yaml")
    editor = window.editors.current_editor()
    assert editor is not None
    asked = answer(monkeypatch, QMessageBox.StandardButton.Cancel)
    window.editors._close_tab(window.editors.indexOf(editor))
    assert not asked and window.editors.indexOf(editor) < 0


# ---- jump lines ------------------------------------------------------------------------------
def test_jump_line_for_a_list_path(window: MainWindow) -> None:
    window.open_project(EXAMPLES / "cubesat_3u")
    text = (EXAMPLES / "cubesat_3u" / "config" / "mass_limits.yaml").read_text(encoding="utf-8")
    expected = next(i for i, line in enumerate(text.splitlines(), 1) if "limit_kg" in line)
    # a mapping-valued key resolves to its first child line, so it is at or just after the key
    assert (
        expected <= window._line_of("config/mass_limits.yaml", "limits[0].limit_kg") <= expected + 1
    )
    assert window._line_of("config/mass_limits.yaml", "limits[0]") is not None


def test_an_unexpected_error_while_computing_becomes_a_plain_problem(
    window: MainWindow, eps: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import budget_gui.session as session_module

    def boom(*_: object) -> None:
        raise RuntimeError("SECRET project text")

    monkeypatch.setattr(session_module, "static_mass_budget", boom)
    window.open_project(eps)
    problems = window.session.problems
    assert [p.code for p in problems] == ["INTERNAL_ERROR"]
    assert "RuntimeError" in problems[0].message and "SECRET" not in problems[0].message
