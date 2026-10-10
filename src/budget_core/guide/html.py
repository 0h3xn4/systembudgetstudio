"""Offline HTML for the user guide: one self-contained page, no scripts, no external resources.

With `embed_fonts` the bundled IBM Plex files are inlined as data URLs so the page looks the same
on a machine without the fonts; the GUI help viewer passes False (it uses the application font)."""

from __future__ import annotations

import base64
from html import escape

from budget_core.assets import font_path
from budget_core.guide.build import Chapter, Guide
from budget_core.guide.markdown import (
    Block,
    Bullets,
    Code,
    Heading,
    Inline,
    Paragraph,
    Quote,
)

CSS = """
body { font-family: "IBM Plex Sans", "Segoe UI", sans-serif; color: #161616; background: #ffffff;
       max-width: 62rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; font-size: 15px; }
h1, h2, h3 { font-weight: 600; }
h1 { border-top: 4px solid #0f62fe; padding-top: .6rem; margin-top: 2.5rem; font-size: 1.9rem; }
h1.doc-title { border-top: none; margin-top: 0; }
h2 { margin-top: 1.8rem; font-size: 1.35rem; }
h3 { margin-top: 1.2rem; font-size: 1.1rem; }
code, pre { font-family: "IBM Plex Mono", Consolas, monospace; font-size: .9em; }
code { background: #f4f4f4; padding: 0 .25em; }
pre { background: #f4f4f4; border-left: 3px solid #0f62fe; padding: .7rem 1rem; overflow-x: auto; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: .9em; }
th { background: #e0e0e0; text-align: left; }
th, td { border-bottom: 1px solid #c6c6c6; padding: .35rem .5rem; vertical-align: top; }
blockquote { margin: 1rem 0; padding: .5rem 1rem; background: #edf5ff;
             border-left: 3px solid #0f62fe; }
nav ul { list-style: none; padding-left: 1rem; }
.meta { color: #525252; }
"""

FONTS = (
    ("IBM Plex Sans", 400, "IBMPlexSans-Regular.ttf"),
    ("IBM Plex Sans", 600, "IBMPlexSans-SemiBold.ttf"),
    ("IBM Plex Mono", 400, "IBMPlexMono-Regular.ttf"),
)


def _font_css() -> str:
    faces = []
    for family, weight, file in FONTS:
        data = base64.b64encode(font_path(file).read_bytes()).decode("ascii")
        faces.append(
            f'@font-face {{ font-family: "{family}"; font-weight: {weight}; '
            f'src: url("data:font/ttf;base64,{data}") format("truetype"); }}'
        )
    return "\n".join(faces)


def _inline(spans: Inline) -> str:
    out: list[str] = []
    for span in spans:
        text = escape(span.text, quote=False)
        if span.style == "bold":
            text = f"<strong>{text}</strong>"
        elif span.style == "italic":
            text = f"<em>{text}</em>"
        elif span.style == "code":
            text = f"<code>{text}</code>"
        out.append(text)
    return "".join(out)


def _block(block: Block, chapter: Chapter) -> str:
    if isinstance(block, Heading):
        anchor = chapter.anchor if block.level == 1 else f"{chapter.anchor}--{block.anchor}"
        return f'<h{block.level} id="{anchor}">{_inline(block.inline)}</h{block.level}>'
    if isinstance(block, Paragraph):
        return f"<p>{_inline(block.inline)}</p>"
    if isinstance(block, Bullets):
        tag = "ol" if block.ordered else "ul"
        items = "".join(f"<li>{_inline(item)}</li>" for item in block.items)
        return f"<{tag}>{items}</{tag}>"
    if isinstance(block, Code):
        return f"<pre>{escape(block.text, quote=False)}</pre>"
    if isinstance(block, Quote):
        return f"<blockquote>{_inline(block.inline)}</blockquote>"
    head = "".join(f"<th>{_inline(h)}</th>" for h in block.header)
    rows = "".join(
        "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row) + "</tr>" for row in block.rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"


def render_html(guide: Guide, *, embed_fonts: bool = True) -> str:
    contents: list[str] = []
    for chapter in guide.chapters:
        contents.append(f'<li><a href="#{chapter.anchor}">{escape(chapter.title)}</a></li>')
    body = [
        f'<h1 class="doc-title">{escape(guide.title)}</h1>',
        f'<p class="meta">Version {escape(guide.version)}. This guide works offline.</p>',
        f"<nav><h2>Contents</h2><ul>{''.join(contents)}</ul></nav>",
    ]
    for chapter in guide.chapters:
        body.extend(_block(b, chapter) for b in chapter.blocks)
    fonts = _font_css() if embed_fonts else ""
    return (
        '<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
        f"<title>{escape(guide.title)}</title><style>\n{fonts}\n{CSS}</style></head>\n<body>\n"
        + "\n".join(body)
        + "\n</body></html>\n"
    )
