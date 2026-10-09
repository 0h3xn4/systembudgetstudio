"""Provenance carried by every report, plot and export (spec constraint 19).

For byte-identical regeneration (constraint 14) the generation time comes from, in order: the
`generated_at` argument, the SOURCE_DATE_EPOCH environment variable, the clock. The user comes from
the `user` argument, then BUDGET_USER, then the operating-system account.
"""

from __future__ import annotations

import getpass
import os
import platform
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version

from budget_core import APP_NAME, __version__
from budget_core.model import Project

LIBRARIES = ("openpyxl", "pint", "pydantic", "reportlab", "ruamel.yaml")


@dataclass(frozen=True)
class Provenance:
    tool: str
    tool_version: str
    python_version: str
    libraries: tuple[tuple[str, str], ...]
    project_name: str
    project_revision: str
    scenario: str
    generated: str  # ISO 8601 UTC, seconds resolution
    user: str

    def rows(self) -> list[tuple[str, str]]:
        libs = ", ".join(f"{n} {v}" for n, v in self.libraries)
        return [
            ("Tool", f"{self.tool} {self.tool_version}"),
            ("Python", self.python_version),
            ("Libraries", libs),
            ("Project", self.project_name),
            ("Project revision", self.project_revision),
            ("Scenario", self.scenario),
            ("Generated (UTC)", self.generated),
            ("User", self.user),
        ]


def _lib_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


def resolve_time(generated_at: datetime | None = None) -> datetime:
    if generated_at is not None:
        return generated_at.astimezone(UTC).replace(microsecond=0)
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch is not None and epoch.strip().isdigit():
        return datetime.fromtimestamp(int(epoch), UTC)
    return datetime.now(UTC).replace(microsecond=0)


def resolve_user(user: str | None = None) -> str:
    if user:
        return user
    env = os.environ.get("BUDGET_USER")
    if env:
        return env
    try:
        return getpass.getuser()
    except Exception:  # no account name available (containers, restricted accounts)
        return "unknown"


def make_provenance(
    project: Project,
    scenario: str = "static (no scenario)",
    *,
    user: str | None = None,
    generated_at: datetime | None = None,
) -> Provenance:
    return Provenance(
        tool=APP_NAME,
        tool_version=__version__,
        python_version=platform.python_version(),
        libraries=tuple((n, _lib_version(n)) for n in LIBRARIES),
        project_name=project.meta.name,
        project_revision=project.meta.revision,
        scenario=scenario,
        generated=resolve_time(generated_at).strftime("%Y-%m-%dT%H:%M:%SZ"),
        user=resolve_user(user),
    )
