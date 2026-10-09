"""Report parts shared by every budget: sheet names, assumptions, problems, provenance."""

from __future__ import annotations

import re
from collections.abc import Sequence

from budget_core.assumptions import Assumption
from budget_core.equations import EQUATIONS
from budget_core.problems import Problem, sort_problems
from budget_core.provenance import Provenance
from budget_core.reports.document import Column, Section, Table

BANNER = (
    "INCOMPLETE: some inputs are placeholders (source TBD or missing). Entries marked n/a depend "
    "on them and are not computed. Do not use this report as evidence until the placeholders are "
    "replaced with sourced values."
)


def sheet_name(raw: str, used: set[str]) -> str:
    base = re.sub(r"[\[\]:*?/\\]", "_", raw)[:31]
    name, i = base, 2
    while name in used:
        suffix = f" {i}"
        name = base[: 31 - len(suffix)] + suffix
        i += 1
    used.add(name)
    return name


def closing_sections(
    used: set[str],
    assumptions: Sequence[Assumption],
    equation_prefix: str,
    problems: Sequence[Problem],
    provenance: Provenance,
) -> list[Section]:
    """Assumptions (numbers and equations), Problems and Provenance sections."""
    assumption_table = Table(
        "Configuration numbers used",
        (
            Column("Name"),
            Column("Value", "number", 4),
            Column("Unit"),
            Column("Source"),
            Column("Status"),
        ),
        tuple(
            (a.name, a.value, a.unit, a.source, "PLACEHOLDER" if a.placeholder else "sourced")
            for a in assumptions
        ),
    )
    equation_table = Table(
        "Equations",
        (Column("ID"), Column("Name"), Column("Formula"), Column("Source")),
        tuple(
            (e.id, e.name, e.formula, e.source_text)
            for e in EQUATIONS.values()
            if e.id.startswith(equation_prefix)
        ),
        note="SOURCE_MISSING: the formula is a project convention or textbook definition whose "
        "reference text is not available to the tool yet (see docs/DECISIONS.md).",
    )
    problem_table = Table(
        "Problems and open items",
        (Column("Severity"), Column("Code"), Column("Location"), Column("Message")),
        tuple(
            (
                p.severity.value,
                p.code,
                (p.file or "") + (f":{p.line}" if p.line is not None else ""),
                p.message,
            )
            for p in sort_problems(problems)
        ),
    )
    provenance_table = Table(
        "Provenance", (Column("Item"), Column("Value")), tuple(provenance.rows())
    )
    return [
        Section(
            "Assumptions",
            sheet_name("Assumptions", used),
            tables=(assumption_table, equation_table),
        ),
        Section("Problems", sheet_name("Problems", used), tables=(problem_table,)),
        Section("Provenance", sheet_name("Provenance", used), tables=(provenance_table,)),
    ]
