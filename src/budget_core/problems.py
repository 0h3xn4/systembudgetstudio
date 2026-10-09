"""User-facing problems (errors, warnings, info) shared by loaders, validation and solvers.

A Problem says what is wrong, where (file, YAML path, line) and what to do (hint). It never
contains values read from project files (spec constraint 11); only field names and types.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Problem:
    severity: Severity
    code: str
    message: str
    file: str | None = None
    path: str = ""
    line: int | None = None
    hint: str = ""

    def format(self) -> str:
        where = self.file or "<project>"
        if self.line is not None:
            where = f"{where}:{self.line}"
        text = f"{where}: {self.severity.value} {self.code}: {self.message}"
        if self.path:
            text += f" (at {self.path})"
        if self.hint:
            text += f"\n    {self.hint}"
        return text

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "file": self.file,
            "path": self.path,
            "line": self.line,
            "hint": self.hint,
        }


def _key(p: Problem) -> tuple[str, int, str, str, str, str]:
    return (p.file or "", p.line or 0, p.path, p.code, p.severity.value, p.message)


def sort_problems(problems: Iterable[Problem]) -> list[Problem]:
    """Deterministic order: by file (project-level first), line, path, code."""
    return sorted(problems, key=_key)
