from __future__ import annotations

import re
from pathlib import Path

from budget_core.equations import EQUATIONS, SOURCE_MISSING
from budget_core.guide.build import build_guide, chapter_files
from budget_core.guide.html import render_html
from budget_core.guide.markdown import Heading, TableBlock
from budget_core.io.project_loader import load_project

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def test_chapters_are_numbered_files_with_one_title_each() -> None:
    files = chapter_files()
    assert len(files) >= 8
    assert [f.name for f in files] == sorted(f.name for f in files)
    guide = build_guide()
    titles = [c.title for c in guide.chapters]
    assert titles[-1] == "Equations and sources"
    assert len(set(titles)) == len(titles)
    for chapter in guide.chapters:
        h1 = [b for b in chapter.blocks if isinstance(b, Heading) and b.level == 1]
        assert len(h1) == 1, chapter.title


def test_every_equation_is_in_the_generated_chapter() -> None:
    guide = build_guide()
    chapter = guide.chapters[-1]
    ids = {
        row[0][0].text
        for b in chapter.blocks
        if isinstance(b, TableBlock) and b.header[0][0].text == "ID"
        for row in b.rows
    }
    assert ids == set(EQUATIONS)


def test_missing_sources_are_flagged_not_hidden() -> None:
    html = render_html(build_guide())
    assert html.count(SOURCE_MISSING) >= sum(1 for e in EQUATIONS.values() if e.source is None)


def test_constants_have_sources() -> None:
    chapter = build_guide().chapters[-1]
    tables = [b for b in chapter.blocks if isinstance(b, TableBlock)]
    constants = next(t for t in tables if t.header[0][0].text == "Constant")
    names = {r[0][0].text for r in constants.rows}
    assert {"Speed of light", "Boltzmann constant", "Earth equatorial radius"} <= names
    assert all(r[3][0].text for r in constants.rows)  # source column never empty


def project_text(name: str) -> str:
    project = load_project(EXAMPLES / name).project
    assert project is not None
    chapter = build_guide(project).chapters[-1]
    return " ".join(
        s.text
        for b in chapter.blocks
        if isinstance(b, TableBlock)
        for r in b.rows
        for c in r
        for s in c
    )


def test_project_numbers_are_listed_with_status() -> None:
    placeholders = project_text("cubesat_3u")
    assert "PLACEHOLDER" in placeholders and "margin_policy" in placeholders
    assert "sourced" in project_text("cubesat_3u_eps")


def test_html_is_self_contained_and_offline() -> None:
    html = render_html(build_guide())
    assert "<script" not in html.lower()
    assert not re.search(r"(src|href)=\"(https?:)?//", html)
    assert "@import" not in html
    assert "url(http" not in html
    assert html.count("<h1") == len(build_guide().chapters) + 1  # chapters plus the title


def test_html_is_deterministic_and_has_a_contents_list() -> None:
    one, two = render_html(build_guide()), render_html(build_guide())
    assert one == two
    assert 'id="equations-and-sources"' in one
    assert 'href="#equations-and-sources"' in one


def test_html_escapes_text() -> None:
    from budget_core.guide.markdown import Paragraph, Span

    guide = build_guide()
    chapter = guide.chapters[0]
    from dataclasses import replace

    hostile = replace(chapter, blocks=(*chapter.blocks, Paragraph((Span("<b>&</b>"),))))
    html = render_html(replace(guide, chapters=(hostile,)))
    assert "&lt;b&gt;&amp;&lt;/b&gt;" in html


def test_pdf_renders_with_all_chapter_titles() -> None:
    import io

    from pypdf import PdfReader

    from budget_core.guide.pdf import render_pdf

    guide = build_guide()
    data = render_pdf(guide)
    reader = PdfReader(io.BytesIO(data))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    for chapter in guide.chapters:
        assert chapter.title in text.replace("\n", " ") or chapter.title.split()[0] in text
    assert len(reader.pages) > 8
    assert render_pdf(guide) == data


def test_troubleshooting_covers_every_documented_problem_code() -> None:
    doc = (Path(__file__).resolve().parents[2] / "docs" / "FILE_FORMAT.md").read_text("utf-8")
    section = doc.split("## Problem codes", 1)[1].split("## Schema versions", 1)[0]
    codes = set(re.findall(r"`([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)`", section))
    guide = build_guide()
    chapter = next(c for c in guide.chapters if c.title == "Problems and what to do")
    text = " ".join(
        s.text
        for b in chapter.blocks
        if isinstance(b, TableBlock)
        for r in b.rows
        for c in r
        for s in c
    )
    missing = sorted(code for code in codes if code not in text)
    assert missing == []
