"""Stacked time plots with eclipse and pass shading, zoom, pan and cursors.

Draws a `PlotSpec` (the same description the report renderer uses). The wheel zooms around the
pointer, dragging pans, double-click shows everything, hovering moves a cursor with a readout of
every series, a click pins a second cursor and the readout then shows the differences, and
Escape or a right click unpins.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFontMetrics,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPolygonF,
    QWheelEvent,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from budget_core.plots.spec import (
    Panel,
    PlotSpec,
    nice_ticks,
    plot_points,
    time_axis,
    value_at,
    visible_range,
)

LEFT, RIGHT, TOP, BOTTOM, GAP, TITLE = 64, 14, 8, 36, 26, 18
GRID, INK, MUTED = "#e0e0e0", "#161616", "#525252"
MIN_PANEL_HEIGHT = 110


def _hms_full(seconds: float) -> str:
    total = int(round(abs(seconds)))
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    prefix = "-" if seconds < 0 else ""
    return prefix + (f"{days}d " if days else "") + f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _number(value: float) -> str:
    if value != 0 and (abs(value) >= 10000 or abs(value) < 0.01):
        return f"{value:.3g}"
    return f"{value:.3f}".rstrip("0").rstrip(".") or "0"


class PlotWidget(QWidget):
    view_changed = Signal()
    cursor_changed = Signal(object)  # seconds, or None when the pointer leaves

    def __init__(self) -> None:
        super().__init__()
        self._spec: PlotSpec | None = None
        self._view = (0.0, 1.0)
        self._cursor: float | None = None
        self._pinned: float | None = None
        self._drag: tuple[float, float, float] | None = None
        self._moved = False
        self._info: Callable[[float], str] | None = None
        self._shading = True
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(220)

    # ---- data --------------------------------------------------------------------------------
    def set_spec(self, spec: PlotSpec | None) -> None:
        self._spec = spec
        if spec is not None:
            self._view = (spec.x_min_s, spec.x_max_s)
            self.setMinimumHeight(TOP + BOTTOM + len(spec.panels) * (MIN_PANEL_HEIGHT + GAP) - GAP)
        self._cursor = self._pinned = None
        self.update()
        self.view_changed.emit()

    def spec(self) -> PlotSpec | None:
        return self._spec

    def set_shading(self, enabled: bool) -> None:
        self._shading = enabled
        self.update()

    def set_info_provider(self, provider: Callable[[float], str] | None) -> None:
        """Extra text for the readout at a time (for example the spacecraft mode)."""
        self._info = provider

    # ---- view --------------------------------------------------------------------------------
    def view(self) -> tuple[float, float]:
        return self._view

    def _limits(self) -> tuple[float, float]:
        return (self._spec.x_min_s, self._spec.x_max_s) if self._spec else (0.0, 1.0)

    def set_view(self, start: float, end: float) -> None:
        lo, hi = self._limits()
        width = min(max(end - start, 1.0), hi - lo)
        start = min(max(start, lo), hi - width)
        self._view = (start, start + width)
        self.update()
        self.view_changed.emit()

    def zoom(self, factor: float, center_s: float | None = None) -> None:
        start, end = self._view
        center = (start + end) / 2.0 if center_s is None else center_s
        width = (end - start) / factor
        ratio = (center - start) / (end - start) if end > start else 0.5
        self.set_view(center - ratio * width, center - ratio * width + width)

    def pan(self, delta_s: float) -> None:
        start, end = self._view
        self.set_view(start + delta_s, end + delta_s)

    def reset_view(self) -> None:
        self.set_view(*self._limits())

    def _plot_width(self) -> float:
        return max(self.width() - LEFT - RIGHT, 1)

    def time_to_x(self, t: float) -> float:
        start, end = self._view
        return LEFT + (t - start) / max(end - start, 1e-9) * self._plot_width()

    def x_to_time(self, x: float) -> float:
        start, end = self._view
        return start + (x - LEFT) / self._plot_width() * (end - start)

    def _panel_rects(self) -> list[QRectF]:
        count = len(self._spec.panels) if self._spec else 0
        if count == 0:
            return []
        height = (self.height() - TOP - BOTTOM - (GAP * (count - 1))) / count
        return [
            QRectF(
                LEFT,
                TOP + i * (height + GAP) + TITLE,
                self._plot_width(),
                height - TITLE,
            )
            for i in range(count)
        ]

    # ---- cursors -----------------------------------------------------------------------------
    def cursor_s(self) -> float | None:
        return self._cursor

    def pinned_s(self) -> float | None:
        return self._pinned

    def set_cursor(self, t: float | None) -> None:
        self._cursor = t
        self.cursor_changed.emit(t)
        self.update()

    def pin_cursor(self, t: float | None) -> None:
        self._pinned = t
        self.update()

    def readout_lines(self, t: float) -> list[str]:
        """What the readout shows at time `t`: time, the info provider's text, every series. With a
        pinned cursor the values are those at `t` with the change since the pinned time."""
        spec = self._spec
        if spec is None:
            return []
        lines = [f"t = {_hms_full(t)}"]
        if self._pinned is not None:
            lines.append(
                f"pinned {_hms_full(self._pinned)}, difference {_hms_full(t - self._pinned)}"
            )
        if self._info is not None:
            lines.extend(self._info(t).splitlines())
        for panel in spec.panels:
            for series in panel.series:
                value = value_at(series, t, spec.x_max_s)
                if value is None:
                    continue
                text = f"{series.label}: {_number(value * panel.y_scale)}"
                if self._pinned is not None:
                    before = value_at(series, self._pinned, spec.x_max_s)
                    if before is not None:
                        text += f" ({(value - before) * panel.y_scale:+.4g})"
                lines.append(text)
        return lines

    # ---- painting ----------------------------------------------------------------------------
    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        spec = self._spec
        if spec is None:
            painter.setPen(QColor("#6f6f6f"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No results to show")
            return
        rects = self._panel_rects()
        divisor, unit = time_axis(self._view[1] - self._view[0])
        for index, (panel, rect) in enumerate(zip(spec.panels, rects, strict=True)):
            self._paint_panel(painter, spec, panel, rect, index == len(rects) - 1, divisor, unit)
        self._paint_cursors(painter, rects)

    def _paint_panel(
        self,
        painter: QPainter,
        spec: PlotSpec,
        panel: Panel,
        rect: QRectF,
        last: bool,
        divisor: float,
        unit: str,
    ) -> None:
        lo, hi = visible_range(
            [s.y * panel.y_scale for s in panel.series]
            + [np.array([h.y * panel.y_scale]) for h in panel.hlines],
            None if panel.y_min is None else panel.y_min * panel.y_scale,
            None if panel.y_max is None else panel.y_max * panel.y_scale,
        )

        def sy(v: float) -> float:
            return rect.bottom() - (v - lo) / (hi - lo) * rect.height()

        painter.save()
        painter.setClipRect(rect)
        if self._shading:
            for band in spec.bands:
                colour = QColor(band.color)
                colour.setAlpha(140)
                for a, b in band.intervals:
                    x0, x1 = self.time_to_x(a), self.time_to_x(b)
                    if x1 >= rect.left() and x0 <= rect.right():
                        painter.fillRect(
                            QRectF(x0, rect.top(), max(x1 - x0, 1.0), rect.height()), colour
                        )
        painter.setPen(QPen(QColor(GRID), 1))
        for tick in nice_ticks(lo, hi, 4):
            painter.drawLine(QPointF(rect.left(), sy(tick)), QPointF(rect.right(), sy(tick)))
        start, end = self._view
        for tick in nice_ticks(start / divisor, end / divisor, 8):
            x = self.time_to_x(tick * divisor)
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        buckets = max(int(rect.width()), 50)
        for series in panel.series:
            px, py = plot_points(series, start, end, spec.x_max_s, buckets)
            if len(px) < 2:
                continue
            painter.setPen(QPen(QColor(series.color), 1.6))
            painter.drawPolyline(
                QPolygonF(
                    [
                        QPointF(self.time_to_x(float(a)), sy(float(b) * panel.y_scale))
                        for a, b in zip(px, py, strict=True)
                    ]
                )
            )
        for hline in panel.hlines:
            pen = QPen(QColor(hline.color), 1.2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            y = sy(hline.y * panel.y_scale)
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        painter.restore()

        painter.setPen(QPen(QColor(INK), 1))
        painter.drawRect(rect)
        metrics = QFontMetrics(painter.font())
        for tick in nice_ticks(lo, hi, 4):
            painter.drawText(
                QRectF(0, sy(tick) - 9, LEFT - 6, 18),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                _number(tick),
            )
        painter.setPen(QColor(INK))
        title_y = rect.top() - 5
        painter.drawText(QPointF(rect.left(), title_y), panel.y_label)
        x = rect.left() + metrics.horizontalAdvance(panel.y_label) + 24
        for label, legend_colour in [(s.label, s.color) for s in panel.series] + [
            (h.label, h.color) for h in panel.hlines
        ]:
            painter.setPen(QPen(QColor(legend_colour), 3))
            painter.drawLine(QPointF(x, title_y - 4), QPointF(x + 16, title_y - 4))
            painter.setPen(QColor(MUTED))
            painter.drawText(QPointF(x + 21, title_y), label)
            x += 21 + metrics.horizontalAdvance(label) + 18
        if last:
            painter.setPen(QColor(INK))
            for tick in nice_ticks(start / divisor, end / divisor, 8):
                x_tick = self.time_to_x(tick * divisor)
                if rect.left() - 1 <= x_tick <= rect.right() + 1:
                    painter.drawText(
                        QRectF(x_tick - 30, rect.bottom() + 4, 60, 16),
                        Qt.AlignmentFlag.AlignHCenter,
                        _number(tick),
                    )
            painter.drawText(
                QRectF(rect.left(), rect.bottom() + 18, rect.width(), 16),
                Qt.AlignmentFlag.AlignHCenter,
                f"Time since scenario start ({unit})",
            )

    def _paint_cursors(self, painter: QPainter, rects: list[QRectF]) -> None:
        if not rects:
            return
        top, bottom = rects[0].top(), rects[-1].bottom()
        for t, dash in (
            (self._pinned, Qt.PenStyle.SolidLine),
            (self._cursor, Qt.PenStyle.DashLine),
        ):
            if t is None:
                continue
            x = self.time_to_x(t)
            if rects[0].left() <= x <= rects[0].right():
                painter.setPen(QPen(QColor(INK), 1, dash))
                painter.drawLine(QPointF(x, top), QPointF(x, bottom))
        if self._cursor is None:
            return
        lines = self.readout_lines(self._cursor)
        metrics = QFontMetrics(painter.font())
        width = max(metrics.horizontalAdvance(t) for t in lines) + 16
        height = len(lines) * metrics.height() + 10
        x = self.time_to_x(self._cursor) + 12
        if x + width > self.width() - RIGHT:
            x = self.time_to_x(self._cursor) - width - 12
        box = QRectF(max(x, LEFT + 2), top + 4, width, height)
        painter.fillRect(box, QColor(255, 255, 255, 235))
        painter.setPen(QPen(QColor("#8d8d8d"), 1))
        painter.drawRect(box)
        painter.setPen(QColor(INK))
        for i, text in enumerate(lines):
            painter.drawText(
                QPointF(box.left() + 8, box.top() + 5 + (i + 1) * metrics.height() - 4), text
            )

    # ---- mouse -------------------------------------------------------------------------------
    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if self._spec is None:
            return
        self.zoom(1.25 ** (event.angleDelta().y() / 120.0), self.x_to_time(event.position().x()))
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._spec is None:
            return
        if event.button() == Qt.MouseButton.RightButton:
            self.pin_cursor(None)
        elif event.button() == Qt.MouseButton.LeftButton:
            self._drag = (event.position().x(), *self._view)
            self._moved = False

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._spec is None:
            return
        x = event.position().x()
        if self._drag is not None:
            x0, start, end = self._drag
            if abs(x - x0) > 3:
                self._moved = True
            if self._moved:
                shift = -(x - x0) / self._plot_width() * (end - start)
                self.set_view(start + shift, end + shift)
            return
        inside = LEFT <= x <= self.width() - RIGHT
        self.set_cursor(self.x_to_time(x) if inside else None)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag is not None and not self._moved and self._spec is not None:
            x = event.position().x()
            if LEFT <= x <= self.width() - RIGHT:
                self.pin_cursor(self.x_to_time(x))
        self._drag = None

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.reset_view()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.pin_cursor(None)
        else:
            super().keyPressEvent(event)

    def leaveEvent(self, event: object) -> None:  # noqa: N802
        self.set_cursor(None)
