"""PDF of the user guide (ReportLab, bundled IBM Plex); identical guides give identical bytes."""

from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from budget_core.assets import font_path
from budget_core.guide.build import Guide
from budget_core.guide.markdown import (
    Block,
    Bullets,
    Code,
    Heading,
    Inline,
    Quote,
    TableBlock,
)
from budget_core.guide.markdown import (
    Paragraph as MdParagraph,
)
from budget_core.reports.pdf import BOLD, GREY, INK, REGULAR, _register_fonts

MONO = "IBMPlexMono"
BLUE = colors.HexColor("#0f62fe")


def _register() -> None:
    _register_fonts()
    if MONO not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(MONO, str(font_path("IBMPlexMono-Regular.ttf"))))
    pdfmetrics.registerFontFamily(
        REGULAR, normal=REGULAR, bold=BOLD, italic=REGULAR, boldItalic=BOLD
    )


def _styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("base", fontName=REGULAR, fontSize=9.5, leading=13.5, textColor=INK)
    return {
        "base": base,
        "title": ParagraphStyle("title", parent=base, fontName=BOLD, fontSize=24, leading=30),
        "h1": ParagraphStyle(
            "h1", parent=base, fontName=BOLD, fontSize=18, leading=23, spaceAfter=6
        ),
        "h2": ParagraphStyle(
            "h2", parent=base, fontName=BOLD, fontSize=13, leading=17, spaceBefore=10, spaceAfter=3
        ),
        "h3": ParagraphStyle(
            "h3", parent=base, fontName=BOLD, fontSize=11, leading=15, spaceBefore=6, spaceAfter=2
        ),
        "bullet": ParagraphStyle("bullet", parent=base, leftIndent=14, bulletIndent=3),
        "code": ParagraphStyle(
            "code",
            parent=base,
            fontName=MONO,
            fontSize=8,
            leading=10.5,
            backColor=colors.HexColor("#f4f4f4"),
            borderPadding=4,
        ),
        "quote": ParagraphStyle(
            "quote",
            parent=base,
            backColor=colors.HexColor("#edf5ff"),
            borderPadding=5,
            leftIndent=6,
        ),
        "cell": ParagraphStyle("cell", parent=base, fontSize=7.5, leading=9.5),
        "head": ParagraphStyle("head", parent=base, fontName=BOLD, fontSize=7.5, leading=9.5),
        "meta": ParagraphStyle("meta", parent=base, textColor=colors.HexColor("#525252")),
    }


def _markup(spans: Inline) -> str:
    out: list[str] = []
    for span in spans:
        text = escape(span.text)
        if span.style == "bold":
            text = f"<b>{text}</b>"
        elif span.style == "italic":
            text = f"<i>{text}</i>"
        elif span.style == "code":
            text = f'<font face="{MONO}" size="8">{text}</font>'
        out.append(text)
    return "".join(out)


def _flowables(block: Block, styles: dict[str, ParagraphStyle], width: float) -> list[object]:
    if isinstance(block, Heading):
        return [Paragraph(_markup(block.inline), styles[f"h{block.level}"])]
    if isinstance(block, MdParagraph):
        return [Paragraph(_markup(block.inline), styles["base"]), Spacer(1, 2 * mm)]
    if isinstance(block, Bullets):
        items = [
            Paragraph(_markup(item), styles["bullet"], bulletText=f"{n}." if block.ordered else "•")
            for n, item in enumerate(block.items, 1)
        ]
        return [*items, Spacer(1, 2 * mm)]
    if isinstance(block, Code):
        return [Preformatted(block.text, styles["code"]), Spacer(1, 3 * mm)]
    if isinstance(block, Quote):
        return [Paragraph(_markup(block.inline), styles["quote"]), Spacer(1, 3 * mm)]
    assert isinstance(block, TableBlock)
    return [_table(block, styles, width), Spacer(1, 3 * mm)]


def _table(block: TableBlock, styles: dict[str, ParagraphStyle], width: float) -> Table:
    data = [[Paragraph(_markup(h), styles["head"]) for h in block.header]]
    data += [[Paragraph(_markup(c), styles["cell"]) for c in row] for row in block.rows]
    rows = [block.header, *block.rows]

    def weight(column: int) -> float:
        texts = ["".join(s.text for s in row[column]) for row in rows]
        longest = max(len(t) for t in texts)
        word = max(len(w) for t in texts for w in t.split() or [""])  # never break these
        is_code = any(s.style == "code" for row in block.rows for s in row[column])
        wanted = longest * 1.7 if is_code and longest <= 14 else min(max(longest, 6), 30)
        return float(max(wanted, word * 1.8))

    weights = [weight(i) for i in range(len(block.header))]
    scale = width / sum(weights)
    table = Table(data, colWidths=[w * scale for w in weights], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), GREY),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#c6c6c6")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def render_pdf(guide: Guide) -> bytes:
    _register()
    styles = _styles()
    margin = 18 * mm
    buffer = io.BytesIO()
    template = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=18 * mm,
        title=guide.title,
        author="System Budget Studio",
        creator=f"System Budget Studio {guide.version}",
        invariant=1,
    )
    width = A4[0] - 2 * margin
    story: list[object] = [
        Spacer(1, 40 * mm),
        Paragraph(escape(guide.title), styles["title"]),
        Paragraph(f"Version {escape(guide.version)}. This guide works offline.", styles["meta"]),
        Spacer(1, 12 * mm),
        Paragraph("Contents", styles["h2"]),
    ]
    for number, chapter in enumerate(guide.chapters, 1):
        story.append(Paragraph(f"{number}. {escape(chapter.title)}", styles["base"]))
    for chapter in guide.chapters:
        story.append(PageBreak())
        for block in chapter.blocks:
            story += _flowables(block, styles, width)

    def draw(canvas, d) -> None:  # type: ignore[no-untyped-def]
        canvas.saveState()
        canvas.setFont(REGULAR, 7.5)
        canvas.setFillColor(colors.HexColor("#525252"))
        canvas.drawString(margin, 10 * mm, f"{guide.title} {guide.version}")
        canvas.drawRightString(A4[0] - margin, 10 * mm, f"Page {d.page}")
        canvas.setStrokeColor(BLUE)
        canvas.setLineWidth(1.5)
        canvas.line(margin, A4[1] - 12 * mm, A4[0] - margin, A4[1] - 12 * mm)
        canvas.restoreState()

    template.build(story, onFirstPage=draw, onLaterPages=draw)
    return buffer.getvalue()
