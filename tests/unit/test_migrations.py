from typing import Any

from budget_core.io.migrations import DEFAULT_REGISTRY, MigrationRegistry
from budget_core.io.project_loader import load_project
from budget_core.model import CURRENT_VERSIONS
from tests.helpers import edit, write_valid_project


def _rename(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    if "weight_kg" in out:
        out["mass_kg"] = out.pop("weight_kg")
    out["schema_version"] = 2
    return out


def test_default_registry_matches_model_versions() -> None:
    for kind, version in CURRENT_VERSIONS.items():
        assert DEFAULT_REGISTRY.current(kind) == version


def test_current_version_passes_through() -> None:
    data = {"schema_version": 1, "kind": "orbit"}
    out, problem = DEFAULT_REGISTRY.migrate("orbit", data)
    assert out == data and problem is None


def test_newer_version_fails_with_upgrade_message() -> None:
    _, problem = DEFAULT_REGISTRY.migrate("unit", {"schema_version": 99, "kind": "unit"})
    assert problem is not None and problem.code == "SCHEMA_TOO_NEW"
    assert "newer" in problem.message and "upgrade" in problem.hint.lower()


def test_older_version_without_migration_fails() -> None:
    reg = MigrationRegistry({"unit": 2}, {})
    _, problem = reg.migrate("unit", {"schema_version": 1})
    assert problem is not None and problem.code == "SCHEMA_MIGRATION_MISSING"


def test_chain_of_migrations_applies_in_order() -> None:
    reg = MigrationRegistry(
        {"unit": 3},
        {
            ("unit", 1): lambda d: {**d, "schema_version": 2, "trail": "a"},
            ("unit", 2): lambda d: {**d, "schema_version": 3, "trail": d["trail"] + "b"},
        },
    )
    out, problem = reg.migrate("unit", {"schema_version": 1})
    assert problem is not None and problem.severity.value == "info"
    assert out["schema_version"] == 3 and out["trail"] == "ab"


def test_loader_migrates_old_file_in_memory(tmp_path: Any) -> None:
    write_valid_project(tmp_path)
    edit(tmp_path, "units/obc.yaml", "mass_kg:", "weight_kg:")
    edit(tmp_path, "units/obc.yaml", "schema_version: 2", "schema_version: 1")
    reg = MigrationRegistry(
        {**CURRENT_VERSIONS, "unit": 3},
        {("unit", 1): _rename, ("unit", 2): lambda d: {**d, "schema_version": 3}},
    )
    result = load_project(tmp_path, registry=reg)
    codes = [p.code for p in result.problems]
    assert "FILE_MIGRATED" in codes
    assert not [p for p in result.problems if p.severity.value == "error"]
    assert result.project is not None
    assert result.project.units["obc"].mass_kg == 0.2


def test_failing_migration_is_a_problem_not_a_crash() -> None:
    def boom(data: dict[str, Any]) -> dict[str, Any]:
        raise KeyError("SECRETVALUE")

    reg = MigrationRegistry({"unit": 2}, {("unit", 1): boom})
    _, problem = reg.migrate("unit", {"schema_version": 1})
    assert problem is not None and problem.code == "SCHEMA_MIGRATION_FAILED"
    assert "SECRETVALUE" not in problem.format()
