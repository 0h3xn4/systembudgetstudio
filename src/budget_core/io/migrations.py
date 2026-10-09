"""Schema versioning: older files migrate in memory, newer files fail with a clear message.

A migration takes the raw mapping of version N and returns the mapping of version N+1 (including
the new `schema_version`). Saving a project afterwards writes the current version.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from budget_core.model.versions import CURRENT_VERSIONS
from budget_core.problems import Problem, Severity

Migration = Callable[[dict[str, Any]], dict[str, Any]]


class MigrationRegistry:
    def __init__(
        self,
        current: Mapping[str, int],
        migrations: Mapping[tuple[str, int], Migration] | None = None,
    ) -> None:
        self._current = dict(current)
        self._migrations = dict(migrations or {})

    def current(self, kind: str) -> int:
        return self._current[kind]

    def migrate(self, kind: str, data: dict[str, Any]) -> tuple[dict[str, Any], Problem | None]:
        """Return (data at the current version, problem). The problem is an info note when the
        file was migrated, an error when it cannot be, and None when nothing was needed."""
        target = self._current[kind]
        version = data.get("schema_version")
        if not isinstance(version, int) or isinstance(version, bool):
            return data, Problem(
                Severity.ERROR,
                "SCHEMA_VERSION_MISSING",
                "The file has no valid 'schema_version' (a whole number).",
                path="schema_version",
                hint=f"Add 'schema_version: {target}' as the first line.",
            )
        if version > target:
            return data, Problem(
                Severity.ERROR,
                "SCHEMA_TOO_NEW",
                f"The file uses schema version {version}, newer than this version of the tool "
                f"supports ({target}).",
                path="schema_version",
                hint="Upgrade System Budget Studio, or open the file with the tool that wrote it.",
            )
        start = version
        current = data
        while version < target:
            step = self._migrations.get((kind, version))
            if step is None:
                return data, Problem(
                    Severity.ERROR,
                    "SCHEMA_MIGRATION_MISSING",
                    f"No migration exists from schema version {version} to {version + 1}.",
                    path="schema_version",
                    hint="Open the file with an older release of the tool, save it, and retry.",
                )
            try:
                current = step(dict(current))
                version = int(current["schema_version"])
            except Exception:  # a broken migration must not crash the loader or leak content
                return data, Problem(
                    Severity.ERROR,
                    "SCHEMA_MIGRATION_FAILED",
                    f"Migrating from schema version {version} failed; the file does not match "
                    "that version's layout.",
                    path="schema_version",
                    hint="Check the file against the documentation of that version.",
                )
        if start == target:
            return current, None
        return current, Problem(
            Severity.INFO,
            "FILE_MIGRATED",
            f"The file was migrated in memory from schema version {start} to {target}.",
            path="schema_version",
            hint="Save the project to upgrade the file on disk.",
        )


DEFAULT_REGISTRY = MigrationRegistry(CURRENT_VERSIONS)
