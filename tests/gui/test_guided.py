"""Guided mode: wizard from orbit to the first budget, with a timed end-to-end check."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from PySide6.QtWidgets import QWizard

from budget_core.wizard import SAMPLES
from budget_gui.guided import GuidedWizard
from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui

TEN_MINUTES_S = 600.0


@pytest.fixture
def window(qtbot) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    return w


def test_pages_in_order_and_defaults_allow_finishing(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    wizard = GuidedWizard(tmp_path)
    qtbot.addWidget(wizard)
    assert [wizard.page(i).title() for i in wizard.pageIds()] == [
        "Project",
        "Spacecraft",
        "Orbit",
        "Scenario",
        "Review",
    ]
    assert wizard.currentPage().isComplete()
    for _ in range(4):
        wizard.next()
    assert wizard.currentId() == wizard.pageIds()[-1]
    assert wizard.button(QWizard.WizardButton.FinishButton).isEnabled()


def test_invalid_answer_blocks_next_and_explains(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    wizard = GuidedWizard(tmp_path)
    qtbot.addWidget(wizard)
    wizard.next()
    wizard.next()  # orbit page
    wizard.altitude.setValue(100.0)  # the spin box allows it; the shared check blocks it
    assert not wizard.currentPage().isComplete()
    assert "altitude" in wizard.error_label.text().lower()
    wizard.altitude.setValue(600.0)
    assert wizard.currentPage().isComplete()
    assert wizard.error_label.text() == ""


def test_name_page_rejects_an_existing_folder(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "my-first-satellite").mkdir()
    wizard = GuidedWizard(tmp_path)
    qtbot.addWidget(wizard)
    assert not wizard.currentPage().isComplete()
    assert "already exists" in wizard.error_label.text()


def test_every_sample_is_offered(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    wizard = GuidedWizard(tmp_path)
    qtbot.addWidget(wizard)
    assert [wizard.sample_combo.itemData(i) for i in range(wizard.sample_combo.count())] == list(
        SAMPLES
    )


def test_orbit_to_first_budget_is_far_inside_ten_minutes(
    window: MainWindow,
    tmp_path: Path,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    started = time.perf_counter()
    wizard = window.open_guided_wizard(tmp_path)
    qtbot.addWidget(wizard)
    wizard.name_edit.setText("Timed satellite")
    wizard.altitude.setValue(600.0)
    wizard.inclination.setValue(97.8)
    for _ in range(4):
        wizard.next()
    with qtbot.waitSignal(window.timeline_view.computed, timeout=TEN_MINUTES_S * 1000):
        wizard.accept()
    elapsed = time.perf_counter() - started
    assert elapsed < TEN_MINUTES_S  # the spec's limit; the automated walk takes seconds
    assert elapsed < 120.0, "the first budget should appear within two minutes on any CI runner"
    assert window.session.project is not None
    assert window.session.project.meta.name == "Timed satellite"
    assert window.timeline_view.result is not None
    assert window.editors.currentWidget() is window.timeline_view
    assert (tmp_path / "timed-satellite" / "project.yaml").is_file()


def test_cancel_creates_nothing(window: MainWindow, tmp_path: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
    wizard = window.open_guided_wizard(tmp_path)
    qtbot.addWidget(wizard)
    wizard.reject()
    assert list(tmp_path.iterdir()) == []
    assert window.session.project is None
