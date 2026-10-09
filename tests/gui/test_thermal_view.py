"""Thermal budget tab: tables of the report, findings in the Problems panel with jump links."""

from __future__ import annotations

import shutil
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


def test_the_tab_shows_cases_modes_and_node_temperatures(window: MainWindow) -> None:
    window.open_project(EXAMPLES / "cubesat_3u_eps")
    view = window.thermal_view
    window.editors.setCurrentWidget(view)
    titles = [view.tabText(i) for i in range(view.count())]
    assert titles[0] == "Summary" and "Case cold" in titles and "Case hot" in titles
    assert "Mode charging" in titles and titles[-2:] == ["Assumptions", "Provenance"]
    nodes = view.table_model("Case hot", 0)
    assert nodes.data(nodes.index(0, 0)) == "ADCS"
    assert float(nodes.data(nodes.index(0, 1))) == pytest.approx(334.4, abs=0.5)  # about 61 C


def test_placeholder_examples_show_na_and_the_banner(window: MainWindow) -> None:
    window.open_project(EXAMPLES / "cubesat_3u")
    view = window.thermal_view
    window.editors.setCurrentWidget(view)
    assert view.banner.isVisibleTo(window) and "INCOMPLETE" in view.banner.text()
    model = view.table_model("Summary", 0)
    assert model.data(model.index(0, 1)) != ""
    cold = view.table_model("Case cold", 0)
    assert cold.data(cold.index(0, 0)).startswith("not computed")


def test_a_finding_reaches_the_problems_panel_and_jumps_to_the_unit(window: MainWindow) -> None:
    window.open_project(EXAMPLES / "cubesat_3u_eps")
    panel = window.problems_panel
    codes = [panel.table.item(r, 1).text() for r in range(panel.table.rowCount())]
    assert "THERMAL_MARGIN_INSUFFICIENT" in codes
    panel.activate_row(codes.index("THERMAL_MARGIN_INSUFFICIENT"))
    editor = window.editors.current_editor()
    assert editor is not None and editor.rel_path == "units/radio.yaml"


def test_editing_a_limit_updates_the_findings(window: MainWindow, tmp_path: Path) -> None:
    shutil.copytree(EXAMPLES / "cubesat_3u_eps", tmp_path / "p")
    path = tmp_path / "p" / "units" / "radio.yaml"
    path.write_text(path.read_text().replace("operating_max_k: 335.15", "operating_max_k: 340.0"))
    window.open_project(tmp_path / "p")
    panel = window.problems_panel
    codes = [panel.table.item(r, 1).text() for r in range(panel.table.rowCount())]
    assert "THERMAL_MARGIN_INSUFFICIENT" not in codes
