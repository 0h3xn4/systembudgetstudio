from __future__ import annotations

from budget_core.guide.markdown import (
    Bullets,
    Code,
    Heading,
    Paragraph,
    Quote,
    Span,
    TableBlock,
    parse,
    slug,
)


def test_headings_paragraphs_and_inline_styles() -> None:
    blocks = parse("# Title\n\nSome **bold**, *italic* and `code` text.\nSecond line.\n\n## Part\n")
    assert blocks[0] == Heading(1, (Span("Title"),), "title")
    para = blocks[1]
    assert isinstance(para, Paragraph)
    assert para.inline == (
        Span("Some "),
        Span("bold", "bold"),
        Span(", "),
        Span("italic", "italic"),
        Span(" and "),
        Span("code", "code"),
        Span(" text. Second line."),
    )
    assert blocks[2] == Heading(2, (Span("Part"),), "part")


def test_lists_ordered_and_unordered() -> None:
    blocks = parse("- one\n- two with `x`\n\n1. first\n2. second\n")
    assert isinstance(blocks[0], Bullets) and not blocks[0].ordered
    assert len(blocks[0].items) == 2
    assert isinstance(blocks[1], Bullets) and blocks[1].ordered
    assert [item[0].text for item in blocks[1].items] == ["first", "second"]


def test_code_block_keeps_text_verbatim() -> None:
    blocks = parse("```\nbudget run demo\n  --out out\n```\n")
    assert blocks == [Code("budget run demo\n  --out out")]


def test_table_with_header_and_rows() -> None:
    blocks = parse("| Name | Value |\n|---|---|\n| a | **1** |\n| b | 2 |\n")
    (table,) = blocks
    assert isinstance(table, TableBlock)
    assert [h[0].text for h in table.header] == ["Name", "Value"]
    assert table.rows[0][1] == (Span("1", "bold"),)
    assert len(table.rows) == 2


def test_quote_is_a_callout() -> None:
    (quote,) = parse("> Note: values are invented.\n> Second line.\n")
    assert isinstance(quote, Quote)
    assert quote.inline[0].text.startswith("Note: values are invented.")


def test_links_become_text_and_never_hyperlinks() -> None:
    (para,) = parse("See [the spec](https://example.invalid/spec) and [below](#part).")
    assert isinstance(para, Paragraph)
    text = "".join(s.text for s in para.inline)
    assert text == "See the spec (https://example.invalid/spec) and below."


def test_slug_is_stable_and_ascii() -> None:
    assert slug("Equations and sources") == "equations-and-sources"
    assert slug("  Ünï — code! ") == "uni-code"
    assert slug("???") == "section"


def test_unclosed_code_fence_is_an_error() -> None:
    import pytest

    from budget_core.guide.markdown import GuideError

    with pytest.raises(GuideError):
        parse("```\nnever closed\n")
