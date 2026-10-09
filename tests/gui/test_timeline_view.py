"""Power timeline tab: compute in a worker, plots, violations, jumps, stale state, export."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt, QTimer

from budget_core.power.time_domain import PEAK_POWER_EXCEEDED
from budget_gui.main_window import MainWindow
from tests.helpers import edit, line_of

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLES / "cubesat_3u_eps", tmp_path / "p")
    return tmp_path / "p"


@pytest.fixture
def window(qtbot, project: Path) -> MainWindow:  # type: ignore[no-untyped-def]
    w = MainWindow()
    qtbot.addWidget(w, before_close_func=lambda win: win.editors.discard_all_changes())
    w.open_project(project)
    return w


def compute(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    with qtbot.waitSignal(window.timeline_view.computed, timeout=120000):
        window.timeline_view.compute()


def test_the_tab_lists_the_scenario_and_waits_for_compute(window: MainWindow) -> None:
    view = window.timeline_view
    assert [view.scenario_combo.itemText(i) for i in range(view.scenario_combo.count())] == [
        "one_day"
    ]
    assert view.result is None and "Not computed" in view.status.text()
    assert not view.export_button.isEnabled()
    assert "Power timeline" in [window.editors.tabText(i) for i in range(window.editors.count())]


def test_compute_fills_plot_and_tables(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    compute(window, qtbot)
    view = window.timeline_view
    result = view.result
    assert result is not None and result.steps == 8640
    spec = view.plot.spec()
    assert spec is not None and [p.title for p in spec.panels] == ["Power", "Battery", "Margin"]
    assert [b.label for b in spec.bands][:1] == ["Eclipse"]
    assert view.summary_table.rowCount() == 2  # BOL and EOL
    assert view.violations_table.rowCount() == len(result.violations) > 0
    assert view.orbits_table.rowCount() == len(result.case("bol").balances) == 15
    assert view.modes_table.rowCount() == len(result.modes)
    assert view.export_button.isEnabled() and view.compute_button.isEnabled()
    assert "violation" in view.status.text()


def test_switching_the_case_changes_the_plot_without_recomputing(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    compute(window, qtbot)
    view = window.timeline_view
    bol = view.plot.spec()
    view.case_combo.setCurrentText("EOL")
    eol = view.plot.spec()
    assert bol is not None and eol is not None and bol.title.endswith("BOL")
    assert eol.title.endswith("EOL")


def test_violations_reach_the_problems_panel_with_a_line(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    before = window.problems_panel.table.rowCount()
    compute(window, qtbot)
    panel = window.problems_panel
    codes = [panel.table.item(r, 1).text() for r in range(panel.table.rowCount())]
    assert PEAK_POWER_EXCEEDED in codes and panel.table.rowCount() > before
    row = codes.index(PEAK_POWER_EXCEEDED)
    panel.activate_row(row)
    editor = window.editors.current_editor()
    assert editor is not None and editor.rel_path == "config/power_system.yaml"
    # the jump lands on the first line inside the field (its `value:` line)
    field = line_of(window.session.path, "config/power_system.yaml", "peak_power_w:")  # type: ignore[arg-type]
    assert editor.current_line() == field + 1


def test_selecting_a_violation_zooms_the_plot_and_double_click_opens_the_input(
    window: MainWindow,
    qtbot,  # type: ignore[no-untyped-def]
) -> None:
    compute(window, qtbot)
    view = window.timeline_view
    assert view.result is not None
    first = view.result.violations[0]
    view.select_violation(0)
    start, end = view.plot.view()
    assert start < first.start_s and end > first.end_s
    assert end - start < view.result.run.scenario.duration_s / 2
    assert view.plot.pinned_s() == pytest.approx(first.start_s)
    with qtbot.waitSignal(view.jump_requested) as signal:
        view.jump_to(0)
    assert signal.args == [first.file, first.path]
    window.jump_to_input(first.file, first.path)
    editor = window.editors.current_editor()
    assert editor is not None and editor.rel_path == "config/power_system.yaml"


def test_the_scenario_environment_is_reused_when_current(
    window: MainWindow,
    qtbot,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> None:
    with qtbot.waitSignal(window.scenario_view.computed, timeout=120000):
        window.scenario_view.compute()
    import budget_gui.timeline_view as tv

    def forbidden(*_a: object, **_k: object) -> None:
        raise AssertionError("the environment was computed again")

    monkeypatch.setattr(tv, "run_scenario", forbidden)
    compute(window, qtbot)
    assert window.timeline_view.result is not None


def test_computing_does_not_block_the_event_loop(
    window: MainWindow,
    qtbot,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> None:
    import budget_gui.timeline_view as tv

    original = tv.time_domain_budget

    def slow(*args, **kwargs):  # type: ignore[no-untyped-def]
        time.sleep(0.6)
        return original(*args, **kwargs)

    monkeypatch.setattr(tv, "time_domain_budget", slow)
    ticks: list[int] = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start(40)
    window.timeline_view.compute()
    assert not window.timeline_view.compute_button.isEnabled()
    with qtbot.waitSignal(window.timeline_view.computed, timeout=120000):
        pass
    timer.stop()
    assert len(ticks) >= 5  # the loop kept running during the 0.6 s the worker slept


def test_project_changes_mark_the_result_stale(window: MainWindow, project: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
    compute(window, qtbot)
    edit(
        project,
        "config/power_system.yaml",
        "peak_power_w:\n    value: 7.5",
        "peak_power_w:\n    value: 9.0",
    )
    window.session.reload()
    view = window.timeline_view
    assert view.is_stale and "Press Compute" in view.status.text()
    compute(window, qtbot)
    assert not view.is_stale
    assert not [v for v in view.result.violations if v.code == PEAK_POWER_EXCEEDED]  # type: ignore[union-attr]


def test_placeholders_show_na_and_a_hint(window: MainWindow, project: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
    edit(
        project,
        "config/power_config.yaml",
        "converter_efficiency_ratio:\n  main:\n    value: 0.9",
        "converter_efficiency_ratio:\n  main:\n    value: null",
    )
    window.session.reload()
    compute(window, qtbot)
    view = window.timeline_view
    assert "placeholder" in view.status.text()
    cells = [view.summary_table.item(0, c).text() for c in range(view.summary_table.columnCount())]
    assert "n/a" in cells


def test_a_failing_run_is_a_plain_message(window: MainWindow, project: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
    folder = project / "imports" / "run1"
    folder.mkdir(parents=True)
    (folder / "orbit.csv").write_text("time_utc,x_m\nSECRET,1\n", encoding="utf-8")
    edit(
        project,
        "scenarios/one_day.yaml",
        "environment_source: elements\norbit: leo",
        "environment_source: spacemissionstudio\nimport_dir: imports/run1",
    )
    window.session.reload()
    view = window.timeline_view
    with qtbot.waitSignal(view.compute_failed, timeout=60000):
        view.compute()
    assert "ENV_INPUT_INVALID" in view.status.text() and "SECRET" not in view.status.text()
    assert view.result is None and view.compute_button.isEnabled()


def test_export_writes_the_power_timeline_files(window: MainWindow, qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    compute(window, qtbot)
    with qtbot.waitSignal(window.timeline_view.export_finished, timeout=120000):
        window.timeline_view.export_to(tmp_path / "out", {"json", "csv", "docx"})
    names = sorted(p.name for p in (tmp_path / "out").iterdir())
    assert "power_time_one_day.docx" in names and "power_time_one_day_bol.csv" in names


def test_export_before_compute_is_refused(window: MainWindow, qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    with qtbot.waitSignal(window.timeline_view.export_failed):
        window.timeline_view.export_to(tmp_path / "out", {"json"})


# ---- plot widget ----------------------------------------------------------------------------


def test_plot_widget_view_zoom_pan_and_reset(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    compute(window, qtbot)
    plot = window.timeline_view.plot
    full = plot.view()
    assert full == (0.0, 86400.0)
    plot.zoom(4.0, 43200.0)
    start, end = plot.view()
    assert end - start == pytest.approx(21600.0) and (start + end) / 2 == pytest.approx(43200.0)
    plot.pan(1e9)  # clamped to the scenario
    assert plot.view()[1] == pytest.approx(86400.0)
    plot.reset_view()
    assert plot.view() == full


def test_plot_readout_gives_every_series_and_differences(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    compute(window, qtbot)
    plot = window.timeline_view.plot
    lines = plot.readout_lines(1000.0)
    text = "\n".join(lines)
    assert lines[0] == "t = 00:16:40"
    assert "Generation:" in text and "State of charge:" in text and "Mode:" in text
    plot.pin_cursor(500.0)
    assert "difference 00:08:20" in "\n".join(plot.readout_lines(1000.0))
    plot.pin_cursor(None)
    assert plot.pinned_s() is None


def test_plot_widget_cursor_pin_and_paint(window: MainWindow, qtbot) -> None:  # type: ignore[no-untyped-def]
    compute(window, qtbot)
    window.resize(1200, 800)
    window.editors.setCurrentWidget(window.timeline_view)
    window.show()
    plot = window.timeline_view.plot
    qtbot.waitExposed(window)
    x = int(plot.time_to_x(30000.0))
    qtbot.mouseMove(plot, QPoint(x, 100))
    qtbot.mouseClick(plot, Qt.MouseButton.LeftButton, pos=QPoint(x, 100))
    assert plot.pinned_s() == pytest.approx(30000.0, abs=200.0)
    qtbot.keyClick(plot, Qt.Key.Key_Escape)
    assert plot.pinned_s() is None
    image = plot.grab().toImage()
    colours = {
        image.pixelColor(px, py).name()
        for px in range(0, image.width(), 7)
        for py in range(0, image.height(), 7)
    }
    assert len(colours) > 6  # shading, lines and text were painted
