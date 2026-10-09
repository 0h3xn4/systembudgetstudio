"""Timeline widget: rows, zoom and pan, hover text, range selection and painting."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QColor

from budget_core.io.project_loader import load_project
from budget_core.scenario.run import ScenarioRun, run_scenario
from budget_gui.timeline import TimelineWidget, mode_colour, nice_tick_step

pytestmark = pytest.mark.gui

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture(scope="module")
def run() -> ScenarioRun:
    project = load_project(EXAMPLES / "cubesat_3u").project
    assert project is not None
    return run_scenario(project, "one_day")


@pytest.fixture
def widget(qtbot, run: ScenarioRun) -> TimelineWidget:  # type: ignore[no-untyped-def]
    w = TimelineWidget()
    qtbot.addWidget(w)
    w.resize(1100, 240)
    w.set_run(run)
    return w


def test_nice_tick_steps() -> None:
    assert nice_tick_step(86400.0, 1000) in (7200.0, 3600.0, 10800.0)
    assert nice_tick_step(600.0, 1000) in (60.0, 120.0)
    assert nice_tick_step(3.0, 1000) <= 1.0
    steps = {nice_tick_step(r, 900) for r in (10, 100, 1000, 10000, 100000, 1000000)}
    assert all(s > 0 for s in steps)


def test_mode_colours_are_stable_and_distinct() -> None:
    modes = ["charging", "downlink", "imaging", "nominal", "safe"]
    colours = [mode_colour(m, modes).name() for m in modes]
    assert len(set(colours)) == len(modes)
    assert mode_colour("downlink", modes) == mode_colour("downlink", list(reversed(modes)))
    assert mode_colour("downlink", modes).name() == colours[1]


def test_rows_and_full_range(widget: TimelineWidget) -> None:
    assert widget.rows() == ["Sunlight", "gs_north", "tgt_plains", "Mode"]
    assert widget.visible_range() == (0.0, 86400.0)


def test_empty_widget_is_harmless(qtbot) -> None:  # type: ignore[no-untyped-def]
    w = TimelineWidget()
    qtbot.addWidget(w)
    w.resize(600, 100)
    w.grab()
    assert w.rows() == [] and w.describe_at(10.0) == ""


def test_zoom_keeps_the_centre_and_is_clamped(widget: TimelineWidget) -> None:
    widget.zoom(2.0, 43200.0)
    a, b = widget.visible_range()
    assert b - a == pytest.approx(43200.0) and (a + b) / 2 == pytest.approx(43200.0)
    widget.zoom(1000.0, 1000.0)
    a, b = widget.visible_range()
    assert b - a >= 1.0 and a >= 0.0  # never below one second
    widget.zoom(0.0001, 1000.0)
    assert widget.visible_range() == (0.0, 86400.0)  # zooming out stops at the whole scenario


def test_pan_is_clamped_to_the_scenario(widget: TimelineWidget) -> None:
    widget.zoom(4.0, 10000.0)
    width = widget.visible_range()[1] - widget.visible_range()[0]
    widget.pan(-1e9)
    assert widget.visible_range() == (0.0, pytest.approx(width))
    widget.pan(1e9)
    assert widget.visible_range()[1] == pytest.approx(86400.0)
    widget.reset_view()
    assert widget.visible_range() == (0.0, 86400.0)


def test_describe_at_names_mode_eclipse_and_pass(widget: TimelineWidget, run: ScenarioRun) -> None:
    eclipse = run.env.eclipses[1]
    text = widget.describe_at((eclipse.start_s + eclipse.end_s) / 2.0)
    assert "Eclipse" in text and "Mode:" in text
    p = run.env.sites["gs_north"].passes[1]
    text = widget.describe_at((p.aos_s + p.los_s) / 2.0)
    assert "gs_north" in text and "downlink" in text
    sunlit = next(
        t
        for t in range(0, 86400, 60)
        if not any(e.start_s <= t <= e.end_s for e in run.env.eclipses)
    )
    assert "Sunlit" in widget.describe_at(float(sunlit))


def test_range_selection_is_clipped_and_ordered(widget: TimelineWidget, qtbot) -> None:  # type: ignore[no-untyped-def]
    with qtbot.waitSignal(widget.range_selected) as blocker:
        widget.select_range(500.0, 100.0)
    assert blocker.args == [100.0, 500.0]
    with qtbot.waitSignal(widget.range_selected) as blocker:
        widget.select_range(-50.0, 999999.0)
    assert blocker.args == [0.0, 86400.0]


def test_time_and_pixel_conversion_round_trip(widget: TimelineWidget) -> None:
    for t in (0.0, 1234.5, 86400.0):
        assert widget.x_to_time(widget.time_to_x(t)) == pytest.approx(t, abs=1e-6)


def test_painting_shows_eclipses_passes_and_several_mode_colours(widget: TimelineWidget) -> None:
    image = widget.grab().toImage()
    colours = {
        image.pixelColor(x, y).name()
        for x in range(0, image.width(), 3)
        for y in range(0, image.height(), 3)
    }
    assert QColor("#525252").name() in colours  # eclipse shading
    assert QColor("#0f62fe").name() in colours  # pass bars
    used = {widget.colour_for(m).name() for m in ("charging", "nominal", "downlink")}
    assert len(used) == 3 and used <= colours
