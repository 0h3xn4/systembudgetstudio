"""PNG rendering of a PlotSpec with Pillow and the bundled IBM Plex fonts.

Drawn at twice the size and scaled down for smooth lines. The same spec and Pillow version give
the same bytes. No files are read except the bundled fonts.
"""

from __future__ import annotations

import io
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from budget_core.assets import font_path
from budget_core.plots.spec import (
    GREY,
    INK,
    Band,
    HLine,
    Panel,
    PlotSpec,
    nice_ticks,
    plot_points,
    time_axis,
    visible_range,
)

SCALE = 2
WIDTH_PX = 1400
PANEL_HEIGHT_PX = 260
LEFT, RIGHT, TOP, BOTTOM, GAP = 96, 24, 56, 64, 36
GRID = "#e0e0e0"

Draw = Any


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(font_path(name)), size * SCALE)


def _mix(color: str, weight: float) -> str:
    """The colour blended with white (bands are light, drawn under the lines)."""
    r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return "#{:02x}{:02x}{:02x}".format(*(int(255 - (255 - c) * weight) for c in (r, g, b)))


def render_png(spec: PlotSpec, width_px: int = WIDTH_PX) -> bytes:
    panels = max(len(spec.panels), 1)
    height = TOP + panels * PANEL_HEIGHT_PX + (panels - 1) * GAP + BOTTOM
    image = Image.new("RGB", (width_px * SCALE, height * SCALE), "white")
    draw = ImageDraw.Draw(image)
    regular, bold = _font("IBMPlexSans-Regular.ttf", 13), _font("IBMPlexSans-SemiBold.ttf", 15)
    divisor, unit = time_axis(spec.x_max_s - spec.x_min_s)
    plot_w = width_px - LEFT - RIGHT

    def sx(t: float) -> float:
        span = max(spec.x_max_s - spec.x_min_s, 1e-9)
        return (LEFT + (t - spec.x_min_s) / span * plot_w) * SCALE

    draw.text((LEFT * SCALE, 14 * SCALE), spec.title, fill=INK, font=bold)
    _legend_bands(draw, spec.bands, regular, width_px)
    for index, panel in enumerate(spec.panels):
        top = TOP + index * (PANEL_HEIGHT_PX + GAP)
        last = index == len(spec.panels) - 1
        _panel(draw, panel, spec, sx, top, regular, bold, divisor, unit, last, width_px)
    out = image.resize((width_px, height), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    out.save(buffer, format="PNG", optimize=False, compress_level=6)
    return buffer.getvalue()


def _legend_bands(
    draw: Draw, bands: tuple[Band, ...], font: ImageFont.FreeTypeFont, w: int
) -> None:
    x = (w - RIGHT) * SCALE
    for band in reversed(bands):
        label = band.label
        width = draw.textlength(label, font=font)
        x -= width
        draw.text((x, 18 * SCALE), label, fill=INK, font=font)
        x -= 18 * SCALE
        draw.rectangle(
            (x, 18 * SCALE, x + 12 * SCALE, 31 * SCALE),
            fill=_mix(band.color, 1.0),
            outline=GREY,
        )
        x -= 20 * SCALE


def _panel(
    draw: Draw,
    panel: Panel,
    spec: PlotSpec,
    sx: Any,
    top: int,
    regular: ImageFont.FreeTypeFont,
    bold: ImageFont.FreeTypeFont,
    divisor: float,
    unit: str,
    last: bool,
    width_px: int,
) -> None:
    bottom = top + PANEL_HEIGHT_PX
    left_px, right_px = LEFT * SCALE, (width_px - RIGHT) * SCALE
    top_px, bottom_px = top * SCALE, bottom * SCALE
    values = [s.y * panel.y_scale for s in panel.series]
    values += [np.array([h.y * panel.y_scale]) for h in panel.hlines]
    low, high = visible_range(
        values,
        None if panel.y_min is None else panel.y_min * panel.y_scale,
        None if panel.y_max is None else panel.y_max * panel.y_scale,
    )

    def sy(v: float) -> float:
        return bottom_px - (v - low) / (high - low) * (bottom_px - top_px)

    for band in spec.bands:
        for a, b in band.intervals:
            x0, x1 = sx(max(a, spec.x_min_s)), sx(min(b, spec.x_max_s))
            if x1 > x0:
                draw.rectangle(
                    (x0, top_px, max(x1, x0 + 1), bottom_px), fill=_mix(band.color, 0.55)
                )
    for tick in nice_ticks(low, high, 5):
        y = sy(tick)
        draw.line((left_px, y, right_px, y), fill=GRID, width=SCALE)
        draw.text((left_px - 8 * SCALE, y), _fmt(tick), fill=INK, font=regular, anchor="rm")
    for tick in nice_ticks(spec.x_min_s / divisor, spec.x_max_s / divisor, 8):
        t = tick * divisor
        if not spec.x_min_s - 1e-9 <= t <= spec.x_max_s + 1e-9:
            continue
        x = sx(t)
        draw.line((x, top_px, x, bottom_px), fill=GRID, width=SCALE)
        if last:
            draw.text((x, bottom_px + 6 * SCALE), _fmt(tick), fill=INK, font=regular, anchor="ma")
    draw.rectangle((left_px, top_px, right_px, bottom_px), outline=INK, width=SCALE)
    if last:
        label = f"Time since scenario start ({unit})"
        draw.text(
            ((left_px + right_px) / 2, bottom_px + 30 * SCALE),
            label,
            fill=INK,
            font=regular,
            anchor="ma",
        )
    draw.text((left_px, top_px - 11 * SCALE), panel.y_label, fill=INK, font=bold, anchor="lm")

    for hline in panel.hlines:
        _hline(draw, hline, panel, sy, left_px, right_px)
    buckets = max(int(right_px - left_px) // SCALE, 50)
    legend_x = left_px + draw.textlength(panel.y_label, font=bold) + 36 * SCALE
    legend_y = top_px - 11 * SCALE
    shown: set[str] = set()
    for series in panel.series:
        px, py = plot_points(series, spec.x_min_s, spec.x_max_s, spec.x_max_s, buckets)
        points = [(sx(float(a)), sy(float(b) * panel.y_scale)) for a, b in zip(px, py, strict=True)]
        if len(points) >= 2:
            draw.line(points, fill=series.color, width=int(1.6 * SCALE), joint="curve")
        if series.label not in shown:
            shown.add(series.label)
            legend_x = _legend_entry(draw, legend_x, legend_y, series.label, series.color, regular)
    for hline in panel.hlines:
        _hline(draw, hline, panel, sy, left_px, right_px)
        legend_x = _legend_entry(draw, legend_x, legend_y, hline.label, hline.color, regular)


def _legend_entry(
    draw: Draw, x: float, y: float, label: str, color: str, font: ImageFont.FreeTypeFont
) -> float:
    draw.line((x, y, x + 22 * SCALE, y), fill=color, width=3 * SCALE)
    draw.text((x + 28 * SCALE, y), label, fill=INK, font=font, anchor="lm")
    return float(x + 28 * SCALE + draw.textlength(label, font=font) + 22 * SCALE)


def _hline(draw: Draw, hline: HLine, panel: Panel, sy: Any, left: float, right: float) -> None:
    y = sy(hline.y * panel.y_scale)
    x = left
    while x < right:  # dashed
        draw.line((x, y, min(x + 10 * SCALE, right), y), fill=hline.color, width=SCALE)
        x += 16 * SCALE


def _fmt(value: float) -> str:
    if abs(value) >= 1e6 or (value != 0 and abs(value) < 0.01):
        return f"{value:.3g}"
    if abs(value) >= 1000:
        return f"{value:.0f}"
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def image_size(png: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(png)) as image:
        return image.size
