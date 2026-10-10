"""Assemble the user guide: the shipped chapters plus the generated "Equations and sources"."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from budget_core import APP_NAME, __version__
from budget_core.environment import constants as env_constants
from budget_core.equations import EQUATIONS, SOURCE_MISSING, Equation
from budget_core.guide.markdown import (
    Block,
    GuideError,
    Heading,
    Inline,
    Paragraph,
    Span,
    TableBlock,
    parse,
    slug,
)
from budget_core.link import constants as link_constants
from budget_core.model import Project, Sourced

GENERATED_TITLE = "Equations and sources"
GROUPS = (
    ("PWR", "Static power budget"),
    ("MASS", "Mass budget"),
    ("TH", "Thermal budget"),
    ("TDP", "Time-domain power budget"),
    ("ENV", "Environment: orbit, eclipse and passes"),
    ("LNK", "Link budget"),
)


@dataclass(frozen=True)
class Chapter:
    title: str
    anchor: str
    blocks: tuple[Block, ...]


@dataclass(frozen=True)
class Guide:
    title: str
    version: str
    chapters: tuple[Chapter, ...]


def chapter_files() -> list[Path]:
    return sorted((Path(__file__).parent / "chapters").glob("*.md"))


def _plain(text: str) -> Inline:
    return (Span(text),)


def _code(text: str) -> Inline:
    return (Span(text, "code"),)


def _bold(text: str) -> Inline:
    return (Span(text, "bold"),)


def _chapter(blocks: list[Block], name: str) -> Chapter:
    titles = [b for b in blocks if isinstance(b, Heading) and b.level == 1]
    if len(titles) != 1:
        raise GuideError(f"chapter file {name} must have exactly one '# ' title")
    title = "".join(s.text for s in titles[0].inline)
    return Chapter(title, titles[0].anchor, tuple(blocks))


def _equation_row(e: Equation) -> tuple[Inline, ...]:
    source = _bold(SOURCE_MISSING) if e.source is None else _plain(e.source)
    return (_code(e.id), _plain(e.name), _code(e.formula), source, _plain(e.notes))


def _equation_blocks() -> list[Block]:
    blocks: list[Block] = []
    known = {prefix for prefix, _ in GROUPS}
    groups = list(GROUPS) + sorted(
        {
            (e.id.split("-")[0], e.id.split("-")[0])
            for e in EQUATIONS.values()
            if e.id.split("-")[0] not in known
        }
    )
    for prefix, title in groups:
        equations = [e for e in EQUATIONS.values() if e.id.split("-")[0] == prefix]
        if not equations:
            continue
        blocks.append(Heading(2, _plain(title), slug(f"equations {title}")))
        blocks.append(
            TableBlock(
                tuple(_plain(h) for h in ("ID", "Name", "Formula", "Source", "Notes")),
                tuple(_equation_row(e) for e in equations),
            )
        )
    return blocks


def _constants_block() -> list[Block]:
    rows: list[tuple[Inline, ...]] = [
        (_plain(c.name), _plain(f"{c.value:.10g}"), _plain(c.unit), _plain(c.source))
        for c in env_constants.ALL
    ]
    rows += [
        (
            _plain("Speed of light"),
            _plain(f"{link_constants.SPEED_OF_LIGHT_MS:.10g}"),
            _plain("m/s"),
            _plain(link_constants.SPEED_OF_LIGHT_SOURCE),
        ),
        (
            _plain("Boltzmann constant"),
            _plain(f"{link_constants.BOLTZMANN_JK:.10g}"),
            _plain("J/K"),
            _plain(link_constants.BOLTZMANN_SOURCE),
        ),
    ]
    return [
        Heading(2, _plain("Constants shipped with the tool"), "constants"),
        Paragraph(
            _plain(
                "These are definitional or reference constants. Every other number comes from "
                "your project's configuration files, each with its own source."
            )
        ),
        TableBlock(tuple(_plain(h) for h in ("Constant", "Value", "Unit", "Source")), tuple(rows)),
    ]


def sourced_numbers(obj: Any, path: str = "") -> list[tuple[str, Sourced]]:
    """Every `Sourced` number inside a model, dataclass, dict or list, with its field path."""
    if isinstance(obj, Sourced):
        return [(path, obj)]
    found: list[tuple[str, Sourced]] = []
    children: list[tuple[str, Any]] = []
    if isinstance(obj, BaseModel):
        children = [(name, getattr(obj, name)) for name in type(obj).model_fields]
    elif dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        children = [(f.name, getattr(obj, f.name)) for f in dataclasses.fields(obj)]
    elif isinstance(obj, dict):
        children = [(str(k), v) for k, v in obj.items()]
    elif isinstance(obj, (list, tuple)):
        children = [(str(i), v) for i, v in enumerate(obj)]
    for name, value in children:
        found += sourced_numbers(value, f"{path}.{name}" if path else name)
    return found


def _project_blocks(project: Project) -> list[Block]:
    rows: list[tuple[Inline, ...]] = []
    sources: list[tuple[str, Any]] = [("config", project.config)]
    sources += [(f"links/{link_id}", link) for link_id, link in sorted(project.links.items())]
    for where, model in sources:
        for path, number in sorted(sourced_numbers(model), key=lambda item: item[0]):
            rows.append(
                (
                    _code(where),
                    _code(path),
                    _plain("n/a" if number.value is None else f"{number.value:.10g}"),
                    _plain(number.source),
                    _bold("PLACEHOLDER") if number.is_placeholder else _plain("sourced"),
                )
            )
    return [
        Heading(
            2, _plain(f"Numbers in the configuration of {project.meta.name}"), "project-numbers"
        ),
        Paragraph(
            _plain(
                "Every sourced number of the configuration files and links of the open project. "
                "PLACEHOLDER means the value is missing or its source is TBD: results that depend "
                "on it are shown as n/a and the report is marked INCOMPLETE."
            )
        ),
        TableBlock(
            tuple(_plain(h) for h in ("File", "Field", "Value", "Source", "Status")), tuple(rows)
        ),
    ]


def generated_chapter(project: Project | None = None) -> Chapter:
    blocks: list[Block] = [
        Heading(1, _plain(GENERATED_TITLE), slug(GENERATED_TITLE)),
        Paragraph(
            _plain(
                "This chapter is generated from the tool's equation registry and configuration; "
                "it changes whenever they do. An equation whose reference text is not available "
                f"to the tool is marked {SOURCE_MISSING}: the formula is a textbook relation or "
                "project convention that the owner still has to confirm against a cited source."
            )
        ),
        *_equation_blocks(),
        *_constants_block(),
    ]
    if project is not None:
        blocks += _project_blocks(project)
    else:
        blocks.append(
            Paragraph(
                _plain(
                    "To list the numbers and sources of one project, build the guide with "
                    "'budget guide --project <folder>' or Help > User guide with a project open."
                )
            )
        )
    return Chapter(GENERATED_TITLE, slug(GENERATED_TITLE), tuple(blocks))


def build_guide(project: Project | None = None) -> Guide:
    chapters = [
        _chapter(parse(path.read_text(encoding="utf-8")), path.name) for path in chapter_files()
    ]
    chapters.append(generated_chapter(project))
    return Guide(f"{APP_NAME} user guide", __version__, tuple(chapters))
