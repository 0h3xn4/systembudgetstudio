"""Link budget tabs: static tables of the report, and the pass series computed in a worker."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QTimer

from budget_gui.main_window import MainWindow

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def window(qtbot) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    return w


@pytest.fixture
def micro(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "microsat_150kg", tmp_path / "p")
    return tmp_path / "p"


def compute(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    with qtbot.waitSignal(window.link_passes_view.computed, timeout=120000):
        window.link_passes_view.compute()


def test_static_tab_shows_the_link_tables(window: MainWindow) -> None:
    window.open_project(EXAMPLES / "microsat_150kg")
    view = window.link_view
    window.editors.setCurrentWidget(view)
    titles = [view.tabText(i) for i in range(view.count())]
    assert titles[0] == "Summary" and titles[-2:] == ["Assumptions", "Provenance"]
    model = view.table_model("Summary", 0)
    assert model.data(model.index(0, 0)) == "sband_down"
    assert model.data(model.index(0, 10)) != "n/a"  # C/N0 is computed from invented values


def test_a_project_without_links_has_an_empty_tab_and_a_disabled_passes_view(
    window: MainWindow, micro: Path
) -> None:
    shutil.rmtree(micro / "links")
    window.open_project(micro)
    assert window.link_view.count() == 0
    assert not window.link_passes_view.compute_button.isEnabled()


def test_placeholder_links_show_na(window: MainWindow) -> None:
    window.open_project(EXAMPLES / "cubesat_3u")
    view = window.link_view
    window.editors.setCurrentWidget(view)
    assert view.banner.isVisibleTo(window)
    model = view.table_model("Summary", 0)
    assert model.data(model.index(0, 10)) == "n/a"


def test_compute_fills_plot_and_tables(window: MainWindow, micro: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
    window.open_project(micro)
    view = window.link_passes_view
    assert "Not computed" in view.status.text() and not view.export_button.isEnabled()
    compute(window, qtbot)
    result = view.result
    assert result is not None and [s.link_id for s in result.series] == ["sband_down", "xband_down"]
    spec = view.plot.spec()
    assert spec is not None and [p.title for p in spec.panels] == [
        "Link margin",
        "Selected rate",
        "Elevation",
    ]
    series = view.selected_link()
    assert series is not None and view.passes_table.rowCount() == len(series.passes) == 11
    assert view.volume_table.rowCount() == 2
    assert view.export_button.isEnabled() and "MByte" in view.status.text()


def test_switching_links_changes_the_plot_and_selecting_a_pass_zooms(
    window: MainWindow,
    micro: Path,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    window.open_project(micro)
    compute(window, qtbot)
    view = window.link_passes_view
    view.link_combo.setCurrentText("xband_down")
    assert view.plot.spec().title.startswith("Link X-band")  # type: ignore[union-attr]
    assert view.passes_table.rowCount() == 4
    series = view.selected_link()
    assert series is not None
    view.select_pass(1)
    start, end = view.plot.view()
    p = series.passes[1]
    assert start < p.aos_s and end > p.los_s and end - start < 4 * (p.los_s - p.aos_s) + 600


def test_the_scenario_environment_is_reused(
    window: MainWindow,
    micro: Path,
    qtbot,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> None:
    window.open_project(micro)
    with qtbot.waitSignal(window.scenario_view.computed, timeout=120000):
        window.scenario_view.compute()
    import budget_gui.link_view as lv

    def forbidden(*_a: object, **_k: object) -> None:
        raise AssertionError("the environment was computed again")

    monkeypatch.setattr(lv, "run_scenario", forbidden)
    compute(window, qtbot)
    assert window.link_passes_view.result is not None


def test_computing_does_not_block_the_event_loop(
    window: MainWindow,
    micro: Path,
    qtbot,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> None:
    window.open_project(micro)
    import budget_gui.link_view as lv

    original = lv.link_pass_series

    def slow(*args, **kwargs):  # type: ignore[no-untyped-def]
        time.sleep(0.6)
        return original(*args, **kwargs)

    monkeypatch.setattr(lv, "link_pass_series", slow)
    ticks: list[int] = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start(40)
    window.link_passes_view.compute()
    assert not window.link_passes_view.compute_button.isEnabled()
    with qtbot.waitSignal(window.link_passes_view.computed, timeout=120000):
        pass
    timer.stop()
    assert len(ticks) >= 5


def test_a_project_change_marks_the_result_stale(window: MainWindow, micro: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
    window.open_project(micro)
    compute(window, qtbot)
    window.session.reload()
    assert (
        window.link_passes_view.is_stale
        and "Press Compute" in window.link_passes_view.status.text()
    )


def test_placeholder_links_compute_to_na(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    window.open_project(EXAMPLES / "cubesat_3u")
    compute(window, qtbot)
    view = window.link_passes_view
    assert "placeholders" in view.status.text()
    series = view.selected_link()
    assert series is not None and series.margin_db is None
    assert view.passes_table.item(0, 6).text() == "n/a"


def test_export_writes_the_pass_files(
    window: MainWindow, micro: Path, qtbot, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    window.open_project(micro)
    compute(window, qtbot)
    with qtbot.waitSignal(window.link_passes_view.export_finished, timeout=120000):
        window.link_passes_view.export_to(tmp_path / "out", {"json", "csv"})
    names = {p.name for p in (tmp_path / "out").iterdir()}
    assert "link_passes_commissioning_day.json" in names
    assert "link_passes_commissioning_day_summary.csv" in names


def test_export_before_compute_is_refused(
    window: MainWindow, micro: Path, qtbot, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    window.open_project(micro)
    with qtbot.waitSignal(window.link_passes_view.export_failed):
        window.link_passes_view.export_to(tmp_path / "out", {"json"})
