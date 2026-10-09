"""PDF renderer (ReportLab, bundled IBM Plex fonts); identical documents give identical bytes."""

from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from budget_core.assets import font_path
from budget_core.plots.render import image_size
from budget_core.reports.document import Column, Figure, ReportDocument, format_cell
from budget_core.reports.document import Table as DocTable

# ReportLab can fetch images from URLs (and imports urllib.request/ssl for it, unconditionally).
# This tool never loads remote resources (constraint 1). ReportLab only checks URLs when
# `trustedHosts` is a non-empty list, so set a host that cannot exist (RFC 2606 ".invalid") and
# allow only local file and data schemes.
rl_config.trustedHosts = ["localhost.invalid"]
rl_config.trustedSchemes = ["file", "data"]

REGULAR, BOLD = "IBMPlexSans", "IBMPlexSans-SemiBold"
INK, GREY, RED = colors.HexColor("#161616"), colors.HexColor("#e0e0e0"), colors.HexColor("#da1e28")


def _register_fonts() -> None:
    if REGULAR not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(REGULAR, str(font_path("IBMPlexSans-Regular.ttf"))))
        pdfmetrics.registerFont(TTFont(BOLD, str(font_path("IBMPlexSans-SemiBold.ttf"))))


def _styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("base", fontName=REGULAR, fontSize=8, leading=10, textColor=INK)
    return {
        "title": ParagraphStyle("title", parent=base, fontName=BOLD, fontSize=16, leading=20),
        "h1": ParagraphStyle(
            "h1", parent=base, fontName=BOLD, fontSize=12, leading=15, spaceBefore=8
        ),
        "h2": ParagraphStyle(
            "h2", parent=base, fontName=BOLD, fontSize=9, leading=12, spaceBefore=6
        ),
        "banner": ParagraphStyle("banner", parent=base, fontName=BOLD, textColor=RED, fontSize=9),
        "cell": base,
        "cell_right": ParagraphStyle("cell_right", parent=base, alignment=TA_RIGHT),
        "head": ParagraphStyle("head", parent=base, fontName=BOLD),
        "note": ParagraphStyle("note", parent=base, textColor=colors.HexColor("#525252")),
    }


def _col_widths(table: DocTable, total: float) -> list[float]:
    weights = []
    for i, column in enumerate(table.columns):
        longest = max(
            [len(column.header) // 2 + 1] + [len(format_cell(r[i], column)) for r in table.rows]
        )
        weights.append(float(min(max(longest, 6), 48)))
    scale = total / sum(weights)
    return [w * scale for w in weights]


def _flowable(table: DocTable, styles: dict[str, ParagraphStyle], width: float) -> list[object]:
    def style_for(column: Column) -> ParagraphStyle:
        return styles["cell"] if column.kind == "text" else styles["cell_right"]

    head = [Paragraph(escape(c.header), styles["head"]) for c in table.columns]
    data: list[list[Paragraph]] = [head]
    for values in table.rows:
        data.append(
            [
                Paragraph(escape(format_cell(v, c)), style_for(c))
                for v, c in zip(values, table.columns, strict=True)
            ]
        )
    t = Table(data, colWidths=_col_widths(table, width), repeatRows=1)
    commands: list[tuple[object, ...]] = [
        ("BACKGROUND", (0, 0), (-1, 0), GREY),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#c6c6c6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    if table.emphasise_last_row and table.rows:
        commands.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f4f4f4")))
    t.setStyle(TableStyle(commands))
    out: list[object] = [Paragraph(escape(table.title), styles["h2"]), t]
    if table.note:
        out.append(Paragraph(escape(table.note), styles["note"]))
    out.append(Spacer(1, 4 * mm))
    return out


def _figure_flowable(
    figure: Figure,
    styles: dict[str, ParagraphStyle],
    width: float,
    height: float,
    lead: list[object],
) -> list[object]:
    w_px, h_px = image_size(figure.png)
    scale = min(width / w_px, (height - 12 * mm) / h_px)
    image = Image(io.BytesIO(figure.png), width=w_px * scale, height=h_px * scale)
    parts: list[object] = [*lead, Paragraph(escape(figure.title), styles["h2"]), image]
    if figure.alt:
        parts.append(Paragraph(escape(figure.alt), styles["note"]))
    return [KeepTogether(parts), Spacer(1, 4 * mm)]


def render_pdf(doc: ReportDocument) -> bytes:
    _register_fonts()
    styles = _styles()
    buffer = io.BytesIO()
    page = landscape(A4)
    margin = 12 * mm
    prov = doc.provenance
    template = SimpleDocTemplate(
        buffer,
        pagesize=page,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=16 * mm,
        title=doc.title,
        author=prov.user,
        subject=prov.project_name,
        creator=f"{prov.tool} {prov.tool_version}",
        invariant=1,
    )
    width = page[0] - 2 * margin
    story: list[object] = [Paragraph(escape(doc.title), styles["title"])]
    if doc.banner:
        story += [Spacer(1, 2 * mm), Paragraph(escape(doc.banner), styles["banner"])]
    for section in doc.sections:
        lead: list[object] = [Paragraph(escape(section.title), styles["h1"])]
        lead += [Paragraph(escape(t), styles["cell"]) for t in section.paragraphs]
        if section.tables or not section.figures:
            story += lead
            lead = []
        for table in section.tables:
            story += _flowable(table, styles, width)
        for figure in section.figures:
            height = page[1] - margin - 16 * mm - 14 * mm
            story += _figure_flowable(figure, styles, width, height, lead)
            lead = []

    footer = (
        f"{prov.tool} {prov.tool_version} | {prov.project_name} rev {prov.project_revision} | "
        f"{prov.scenario} | {prov.generated} | {prov.user}"
    )

    def draw(canvas, d) -> None:  # type: ignore[no-untyped-def]
        canvas.saveState()
        canvas.setFont(REGULAR, 7)
        canvas.setFillColor(colors.HexColor("#525252"))
        canvas.drawString(margin, 8 * mm, footer)
        canvas.drawRightString(page[0] - margin, 8 * mm, f"Page {d.page}")
        canvas.restoreState()

    template.build(story, onFirstPage=draw, onLaterPages=draw)
    return buffer.getvalue()
