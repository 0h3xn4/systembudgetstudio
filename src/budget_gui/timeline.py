"""Timeline widget: sunlight and eclipse, passes per site and the mode timeline over time.

Wheel zooms around the pointer, drag pans, double-click shows the whole scenario, and
Shift+drag selects a range (the scenario view turns it into a manual segment).
"""

from __future__ import annotations

from datetime import timedelta

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from budget_core.scenario.run import ScenarioRun
from budget_core.timeutil import format_utc

# IBM Carbon categorical palette (user-interface styling, not engineering data).
PALETTE = (
    "#6929c4",
    "#1192e8",
    "#005d5d",
    "#9f1853",
    "#fa4d56",
    "#198038",
    "#002d9c",
    "#ee538b",
    "#b28600",
    "#009d9a",
    "#8a3800",
    "#a56eff",
    "#570408",
    "#012749",
)
SUNLIT, ECLIPSE, UMBRA, PASS, TRACK = "#fcf4d6", "#525252", "#161616", "#0f62fe", "#e0e0e0"
TICK_STEPS = (
    1,
    2,
    5,
    10,
    30,
    60,
    120,
    300,
    600,
    1800,
    3600,
    7200,
    10800,
    21600,
    43200,
    86400,
    172800,
    432000,
    864000,
)
LEFT, RIGHT, TOP, BOTTOM, ROW, GAP = 150, 12, 30, 8, 24, 4


def nice_tick_step(range_s: float, width_px: int, min_px: int = 90) -> float:
    """Smallest 'round' tick step (seconds) that keeps ticks at least `min_px` apart."""
    per_pixel = range_s / max(width_px, 1)
    for step in TICK_STEPS:
        if step / per_pixel >= min_px:
            return float(step)
    return float(TICK_STEPS[-1])


def mode_colour(mode: str, modes: list[str]) -> QColor:
    """Stable colour of a mode: the palette entry at the mode's place in the sorted mode list."""
    ordered = sorted(set(modes) | {mode})
    return QColor(PALETTE[ordered.index(mode) % len(PALETTE)])


def _hms(seconds: float) -> str:
    total = int(round(seconds))
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    prefix = f"{days}d " if days else ""
    return f"{prefix}{hours:02d}:{minutes:02d}:{secs:02d}"


class TimelineWidget(QWidget):
    range_selected = Signal(float, float)
    view_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._run: ScenarioRun | None = None
        self._duration = 0.0
        self._view = (0.0, 0.0)
        self._modes: list[str] = []
        self._drag_start: tuple[float, float, float] | None = None  # x, view start, view end
        self._select_from: float | None = None
        self._select_to: float | None = None
        self._cursor_s: float | None = None
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    # ---- data --------------------------------------------------------------------------------
    def set_run(self, run: ScenarioRun | None, all_modes: list[str] | None = None) -> None:
        self._run = run
        self._duration = run.env.grid.duration_s if run else 0.0
        if run:
            self._modes = sorted(set(all_modes or []) | {s.mode for s in run.timeline})
        else:
            self._modes = []
        self._view = (0.0, self._duration)
        self.setMinimumHeight(TOP + BOTTOM + max(len(self.rows()), 1) * (ROW + GAP))
        self.update()
        self.view_changed.emit()

    def rows(self) -> list[str]:
        if self._run is None:
            return []
        return ["Sunlight", *sorted(self._run.env.sites), "Mode"]

    def colour_for(self, mode: str) -> QColor:
        return mode_colour(mode, self._modes)

    # ---- view --------------------------------------------------------------------------------
    def visible_range(self) -> tuple[float, float]:
        return self._view

    def _clamp(self, start: float, end: float) -> tuple[float, float]:
        width = min(max(end - start, 1.0), self._duration or 1.0)
        start = min(max(start, 0.0), max(self._duration - width, 0.0))
        return start, start + width

    def zoom(self, factor: float, center_s: float | None = None) -> None:
        if self._duration <= 0:
            return
        start, end = self._view
        center = (start + end) / 2.0 if center_s is None else center_s
        width = max((end - start) / factor, 1.0)
        width = min(width, self._duration)
        ratio = (center - start) / (end - start) if end > start else 0.5
        new_start = center - ratio * width
        self._view = self._clamp(new_start, new_start + width)
        self.update()
        self.view_changed.emit()

    def pan(self, delta_s: float) -> None:
        start, end = self._view
        self._view = self._clamp(start + delta_s, end + delta_s)
        self.update()
        self.view_changed.emit()

    def reset_view(self) -> None:
        self._view = (0.0, self._duration)
        self.update()
        self.view_changed.emit()

    def _plot_width(self) -> float:
        return max(self.width() - LEFT - RIGHT, 1)

    def time_to_x(self, t: float) -> float:
        start, end = self._view
        return LEFT + (t - start) / max(end - start, 1e-9) * self._plot_width()

    def x_to_time(self, x: float) -> float:
        start, end = self._view
        return start + (x - LEFT) / self._plot_width() * (end - start)

    def select_range(self, a: float, b: float) -> None:
        lo, hi = sorted((a, b))
        lo, hi = max(lo, 0.0), min(hi, self._duration)
        if hi > lo:
            self.range_selected.emit(lo, hi)

    # ---- text --------------------------------------------------------------------------------
    def describe_at(self, t: float) -> str:
        run = self._run
        if run is None:
            return ""
        utc = format_utc(run.env.grid.start + timedelta(seconds=t))
        lines = [f"t = {_hms(t)} ({utc})"]
        mode = next((s.mode for s in run.timeline if s.start_s <= t < s.end_s), None)
        if mode is None and run.timeline:
            mode = run.timeline[-1].mode
        lines.append(f"Mode: {mode}")
        in_eclipse = any(e.start_s <= t <= e.end_s for e in run.env.eclipses)
        lines.append("Eclipse" if in_eclipse else "Sunlit")
        for site_id, vis in sorted(run.env.sites.items()):
            for p in vis.passes:
                if p.aos_s <= t <= p.los_s:
                    lines.append(
                        f"Pass: {site_id} until {_hms(p.los_s)} "
                        f"(max elevation {p.max_elevation_deg:.1f} deg)"
                    )
        return "\n".join(lines)

    # ---- painting ----------------------------------------------------------------------------
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        run = self._run
        if run is None:
            painter.setPen(QColor("#6f6f6f"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No scenario computed")
            return
        metrics = QFontMetrics(painter.font())
        self._draw_axis(painter)
        for index, name in enumerate(self.rows()):
            y = TOP + index * (ROW + GAP)
            painter.setPen(QColor("#161616"))
            painter.drawText(QRectF(6, y, LEFT - 12, ROW), Qt.AlignmentFlag.AlignVCenter, name)
            track = QRectF(LEFT, y, self._plot_width(), ROW)
            painter.save()
            painter.setClipRect(track)
            if name == "Sunlight":
                painter.fillRect(track, QColor(SUNLIT))
                for e in run.env.eclipses:
                    self._bar(painter, e.start_s, e.end_s, y, QColor(ECLIPSE))
                for e in run.env.umbras:
                    self._bar(painter, e.start_s, e.end_s, y + 6, QColor(UMBRA), height=ROW - 12)
            elif name == "Mode":
                painter.fillRect(track, QColor(TRACK))
                for seg in run.timeline:
                    self._bar(painter, seg.start_s, seg.end_s, y, self.colour_for(seg.mode))
                    x0 = self.time_to_x(seg.start_s)
                    x1 = self.time_to_x(seg.end_s)
                    if x1 - x0 > 46 and x1 > LEFT and x0 < self.width():
                        painter.setPen(QColor("#ffffff"))
                        label = metrics.elidedText(
                            seg.mode, Qt.TextElideMode.ElideRight, int(x1 - x0 - 6)
                        )
                        painter.drawText(
                            QRectF(max(x0, LEFT) + 3, y, x1 - max(x0, LEFT), ROW),
                            Qt.AlignmentFlag.AlignVCenter,
                            label,
                        )
            else:
                painter.fillRect(track, QColor(TRACK))
                for p in run.env.sites[name].passes:
                    self._bar(painter, p.aos_s, p.los_s, y, QColor(PASS))
            painter.restore()
        self._draw_overlays(painter)

    def _bar(
        self, painter: QPainter, a: float, b: float, y: float, colour: QColor, height: float = ROW
    ) -> None:
        x0, x1 = self.time_to_x(a), self.time_to_x(b)
        if x1 < LEFT or x0 > self.width() - RIGHT:
            return
        painter.fillRect(QRectF(x0, y, max(x1 - x0, 1.0), height), colour)

    def _draw_axis(self, painter: QPainter) -> None:
        start, end = self._view
        step = nice_tick_step(end - start, int(self._plot_width()))
        painter.setPen(QPen(QColor("#8d8d8d")))
        first = int(start // step) * step
        t = first
        while t <= end + step:
            if t >= start:
                x = self.time_to_x(t)
                painter.drawLine(QPointF(x, TOP - 8), QPointF(x, TOP - 2))
                painter.drawText(QPointF(x + 3, TOP - 10), _hms(t))
            t += step

    def _draw_overlays(self, painter: QPainter) -> None:
        if self._cursor_s is not None:
            x = self.time_to_x(self._cursor_s)
            painter.setPen(QPen(QColor("#161616"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(x, TOP - 4), QPointF(x, self.height() - BOTTOM))
        if self._select_from is not None and self._select_to is not None:
            x0, x1 = sorted((self.time_to_x(self._select_from), self.time_to_x(self._select_to)))
            painter.fillRect(
                QRectF(x0, TOP, x1 - x0, self.height() - TOP - BOTTOM), QColor(15, 98, 254, 60)
            )

    # ---- mouse -------------------------------------------------------------------------------
    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._run is None:
            return
        factor = 1.25 ** (event.angleDelta().y() / 120.0)
        self.zoom(factor, self.x_to_time(event.position().x()))
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._run is None or event.button() != Qt.MouseButton.LeftButton:
            return
        t = self.x_to_time(event.position().x())
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self._select_from = self._select_to = t
        else:
            self._drag_start = (event.position().x(), *self._view)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._run is None:
            return
        x = event.position().x()
        if self._select_from is not None:
            self._select_to = self.x_to_time(x)
        elif self._drag_start is not None:
            x0, start, end = self._drag_start
            shift = -(x - x0) / self._plot_width() * (end - start)
            self._view = self._clamp(start + shift, end + shift)
            self.view_changed.emit()
        else:
            t = self.x_to_time(x)
            self._cursor_s = t if LEFT <= x <= self.width() - RIGHT else None
            if self._cursor_s is not None:
                QToolTip.showText(event.globalPosition().toPoint(), self.describe_at(t), self)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._select_from is not None and self._select_to is not None:
            a, b = self._select_from, self._select_to
            self._select_from = self._select_to = None
            if abs(self.time_to_x(a) - self.time_to_x(b)) > 3:
                self.select_range(a, b)
        self._drag_start = None
        self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.reset_view()

    def leaveEvent(self, event: object) -> None:
        self._cursor_s = None
        self.update()
