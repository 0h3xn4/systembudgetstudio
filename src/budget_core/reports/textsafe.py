"""Remove characters that XML-based formats (XLSX, DOCX) cannot hold from every string of a
report document, so project text such as a name with a control character cannot crash a renderer."""

from __future__ import annotations

import re
from dataclasses import replace

from budget_core.provenance import Provenance
from budget_core.reports.document import Cell, Figure, ReportDocument, Section, Table

_ILLEGAL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


def xml_safe(text: str) -> str:
    return _ILLEGAL.sub("", text)


def _cell(value: Cell) -> Cell:
    return xml_safe(value) if isinstance(value, str) else value


def _table(table: Table) -> Table:
    columns = tuple(
        replace(c, header=xml_safe(c.header), unit=xml_safe(c.unit)) for c in table.columns
    )
    rows = tuple(tuple(_cell(v) for v in row) for row in table.rows)
    return replace(
        table, title=xml_safe(table.title), columns=columns, rows=rows, note=xml_safe(table.note)
    )


def _figure(figure: Figure) -> Figure:
    return replace(figure, title=xml_safe(figure.title), alt=xml_safe(figure.alt))


def _section(section: Section) -> Section:
    return replace(
        section,
        title=xml_safe(section.title),
        sheet_name=xml_safe(section.sheet_name),
        paragraphs=tuple(xml_safe(p) for p in section.paragraphs),
        tables=tuple(_table(t) for t in section.tables),
        figures=tuple(_figure(f) for f in section.figures),
    )


def _provenance(prov: Provenance) -> Provenance:
    return replace(
        prov,
        tool=xml_safe(prov.tool),
        tool_version=xml_safe(prov.tool_version),
        project_name=xml_safe(prov.project_name),
        project_revision=xml_safe(prov.project_revision),
        scenario=xml_safe(prov.scenario),
        user=xml_safe(prov.user),
    )


def clean_document(doc: ReportDocument) -> ReportDocument:
    return replace(
        doc,
        title=xml_safe(doc.title),
        provenance=_provenance(doc.provenance),
        sections=tuple(_section(s) for s in doc.sections),
        banner=xml_safe(doc.banner),
    )
