"""A small Markdown subset for the user guide (no dependency, deterministic output).

Supported: `#`..`###` headings, paragraphs, `-`/`*` and `1.` lists, fenced code, pipe tables,
`>` callouts, and inline **bold**, *italic*, `code` and [text](target). Links are shown as text:
the guide is read offline, so a target is printed in brackets, except `#anchor` targets.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

Style = Literal["plain", "bold", "italic", "code"]


class GuideError(Exception):
    """The guide source is malformed (a bug in the shipped text, not in a project)."""


@dataclass(frozen=True)
class Span:
    text: str
    style: Style = "plain"


Inline = tuple[Span, ...]


@dataclass(frozen=True)
class Heading:
    level: int
    inline: Inline
    anchor: str


@dataclass(frozen=True)
class Paragraph:
    inline: Inline


@dataclass(frozen=True)
class Bullets:
    items: tuple[Inline, ...]
    ordered: bool = False


@dataclass(frozen=True)
class Code:
    text: str


@dataclass(frozen=True)
class TableBlock:
    header: tuple[Inline, ...]
    rows: tuple[tuple[Inline, ...], ...]


@dataclass(frozen=True)
class Quote:
    inline: Inline


Block = Heading | Paragraph | Bullets | Code | TableBlock | Quote


def slug(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    out = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")
    return out or "section"


_INLINE = re.compile(
    r"(?P<code>`[^`]+`)|(?P<bold>\*\*[^*]+\*\*)|(?P<italic>\*[^*\s][^*]*\*)"
    r"|(?P<link>\[[^\]]+\]\([^)]+\))"
)


def inline(text: str) -> Inline:
    spans: list[Span] = []
    position = 0
    for match in _INLINE.finditer(text):
        if match.start() > position:
            spans.append(Span(text[position : match.start()]))
        token = match.group()
        if match.lastgroup == "code":
            spans.append(Span(token[1:-1], "code"))
        elif match.lastgroup == "bold":
            spans.append(Span(token[2:-2], "bold"))
        elif match.lastgroup == "italic":
            spans.append(Span(token[1:-1], "italic"))
        else:
            label, target = token[1:].split("](", 1)
            target = target[:-1]
            spans.append(Span(label if target.startswith("#") else f"{label} ({target})"))
        position = match.end()
    if position < len(text):
        spans.append(Span(text[position:]))
    return _merge(spans)


def _merge(spans: list[Span]) -> Inline:
    merged: list[Span] = []
    for span in spans:
        if merged and merged[-1].style == "plain" and span.style == "plain":
            merged[-1] = Span(merged[-1].text + span.text)
        else:
            merged.append(span)
    return tuple(merged)


_BULLET = re.compile(r"^\s*[-*]\s+(.*)$")
_NUMBER = re.compile(r"^\s*\d+\.\s+(.*)$")
_HEADING = re.compile(r"^(#{1,3})\s+(.*?)\s*#*$")


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_rule(line: str) -> bool:
    cells = _cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c) for c in cells)


def parse(text: str) -> list[Block]:
    lines = text.splitlines()
    blocks: list[Block] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith("```"):
            end = i + 1
            while end < len(lines) and not lines[end].startswith("```"):
                end += 1
            if end >= len(lines):
                raise GuideError("a code block is not closed")
            blocks.append(Code("\n".join(lines[i + 1 : end])))
            i = end + 1
        elif _HEADING.match(line):
            match = _HEADING.match(line)
            assert match is not None
            title = match.group(2)
            blocks.append(Heading(len(match.group(1)), inline(title), slug(title)))
            i += 1
        elif line.lstrip().startswith("|") and i + 1 < len(lines) and _is_rule(lines[i + 1]):
            header = tuple(inline(c) for c in _cells(line))
            rows: list[tuple[Inline, ...]] = []
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(tuple(inline(c) for c in _cells(lines[i])))
                i += 1
            blocks.append(TableBlock(header, tuple(rows)))
        elif line.startswith(">"):
            quoted: list[str] = []
            while i < len(lines) and lines[i].startswith(">"):
                quoted.append(lines[i][1:].strip())
                i += 1
            blocks.append(Quote(inline(" ".join(quoted))))
        elif _BULLET.match(line) or _NUMBER.match(line):
            ordered = bool(_NUMBER.match(line))
            pattern = _NUMBER if ordered else _BULLET
            items: list[Inline] = []
            while i < len(lines) and (m := pattern.match(lines[i])):
                items.append(inline(m.group(1)))
                i += 1
            blocks.append(Bullets(tuple(items), ordered))
        else:
            paragraph: list[str] = []
            while i < len(lines) and lines[i].strip() and not _starts_block(lines, i):
                paragraph.append(lines[i].strip())
                i += 1
            blocks.append(Paragraph(inline(" ".join(paragraph))))
    return blocks


def _starts_block(lines: list[str], i: int) -> bool:
    line = lines[i]
    return bool(
        line.startswith(("```", ">"))
        or _HEADING.match(line)
        or _BULLET.match(line)
        or _NUMBER.match(line)
        or (line.lstrip().startswith("|") and i + 1 < len(lines) and _is_rule(lines[i + 1]))
    )
