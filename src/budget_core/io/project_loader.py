"""Load and write a project folder.

Layout: project.yaml, spacecraft.yaml, units/*.yaml, modes/*.yaml, config/<kind>.yaml.
`load_project` never raises for user errors; it returns Problems (see problems.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path as FsPath
from typing import Any, TypeVar

from pydantic import ValidationError

from budget_core.io.errors import explain
from budget_core.io.migrations import DEFAULT_REGISTRY, MigrationRegistry
from budget_core.io.yamlio import LineMap, YamlSyntaxError, dump_yaml, load_yaml_text
from budget_core.model import (
    AttenuationTable,
    BudgetModel,
    Ebn0Table,
    MarginPolicy,
    PowerConfig,
    Project,
    ProjectConfig,
    ProjectMeta,
    Spacecraft,
    SpacecraftMode,
    Unit,
)
from budget_core.problems import Problem, Severity, sort_problems

M = TypeVar("M", bound=BudgetModel)

CONFIG_FILES: dict[str, type[BudgetModel]] = {
    "margin_policy": MarginPolicy,
    "power_config": PowerConfig,
    "ebn0_table": Ebn0Table,
    "attenuation_table": AttenuationTable,
}


@dataclass(frozen=True)
class LoadResult:
    """`project` is None when any error was found; `problems` is sorted and deterministic."""

    project: Project | None
    problems: list[Problem]
    lines: dict[str, LineMap]


def model_to_data(model: BudgetModel) -> dict[str, Any]:
    """Model -> plain data in field order. Optional fields that are None or empty are omitted."""
    out: dict[str, Any] = {}
    for name, info in type(model).model_fields.items():
        value = getattr(model, name)
        if not info.is_required() and (value is None or value == ""):
            continue
        out[name] = _plain(value)
    return out


def _plain(value: Any) -> Any:
    if isinstance(value, BudgetModel):
        return model_to_data(value)
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def dump_model(model: BudgetModel) -> str:
    return dump_yaml(model_to_data(model))


def _write(path: FsPath, model: BudgetModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(dump_model(model).encode("utf-8"))


def write_project(project: Project, root: FsPath) -> None:
    """Write all project files in canonical form (stable bytes for an unchanged project)."""
    root = FsPath(root)
    _write(root / "project.yaml", project.meta)
    _write(root / "spacecraft.yaml", project.spacecraft)
    for uid, unit in project.units.items():
        _write(root / "units" / f"{uid}.yaml", unit)
    for mid, mode in project.modes.items():
        _write(root / "modes" / f"{mid}.yaml", mode)
    for kind in CONFIG_FILES:
        model = getattr(project.config, kind)
        if model is not None:
            _write(root / "config" / f"{kind}.yaml", model)


class _Loader:
    def __init__(self, root: FsPath, registry: MigrationRegistry) -> None:
        self.root = root
        self.registry = registry
        self.problems: list[Problem] = []
        self.lines: dict[str, LineMap] = {}

    def error(self, code: str, message: str, file: str | None, hint: str = "") -> None:
        self.problems.append(Problem(Severity.ERROR, code, message, file=file, hint=hint))

    def load(self, rel: str, model_cls: type[M], kind: str) -> M | None:
        path = self.root / rel
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            self.error(
                "FILE_INVALID", "The file is not valid UTF-8 text.", rel, "Save the file as UTF-8."
            )
            return None
        except OSError:
            self.error(
                "FILE_NOT_FOUND",
                "The file cannot be read.",
                rel,
                "Check that the file exists and you have permission to read it.",
            )
            return None
        try:
            loaded = load_yaml_text(text)
        except YamlSyntaxError as exc:
            self.problems.append(
                Problem(
                    Severity.ERROR,
                    "YAML_SYNTAX",
                    f"{exc}.",
                    file=rel,
                    line=exc.line,
                    hint="Check indentation, colons and quotes around this line.",
                )
            )
            return None
        self.lines[rel] = loaded.lines
        data = loaded.data
        if not isinstance(data, dict):
            self.error(
                "FILE_INVALID", "The file must contain a mapping of fields (name: value).", rel
            )
            return None
        if data.get("kind") != kind:
            self.problems.append(
                Problem(
                    Severity.ERROR,
                    "KIND_MISMATCH",
                    f"This file must have 'kind: {kind}'.",
                    file=rel,
                    path="kind",
                    line=loaded.lines.lookup(("kind",)),
                    hint=f"Set 'kind: {kind}' (the file location decides its kind).",
                )
            )
            return None
        data, problem = self.registry.migrate(kind, data)
        if problem is not None:
            self.problems.append(_located(problem, rel, loaded.lines))
            if problem.severity is Severity.ERROR:
                return None
        try:
            return model_cls.model_validate(data)
        except ValidationError as exc:
            self.problems.extend(explain(exc, model_cls, rel, loaded.lines))
            return None


def _located(problem: Problem, file: str, lines: LineMap) -> Problem:
    path = tuple(problem.path.split(".")) if problem.path else ()
    return Problem(
        problem.severity,
        problem.code,
        problem.message,
        file=file,
        path=problem.path,
        line=lines.lookup(path),
        hint=problem.hint,
    )


def load_project(root: FsPath, registry: MigrationRegistry = DEFAULT_REGISTRY) -> LoadResult:
    from budget_core.io.validation import validate_references

    root = FsPath(root)
    if not root.is_dir():
        problem = Problem(
            Severity.ERROR,
            "FILE_NOT_FOUND",
            "The project folder does not exist.",
            hint="Check the path; a project folder contains project.yaml.",
        )
        return LoadResult(None, [problem], {})

    loader = _Loader(root, registry)
    meta = loader.load("project.yaml", ProjectMeta, "project")
    spacecraft = loader.load("spacecraft.yaml", Spacecraft, "spacecraft")

    units: dict[str, Unit] = {}
    for path in sorted((root / "units").glob("*.yaml")):
        unit = loader.load(f"units/{path.name}", Unit, "unit")
        if unit is not None:
            units[path.stem] = unit
    modes: dict[str, SpacecraftMode] = {}
    for path in sorted((root / "modes").glob("*.yaml")):
        mode = loader.load(f"modes/{path.name}", SpacecraftMode, "spacecraft_mode")
        if mode is not None:
            modes[path.stem] = mode

    configs: dict[str, Any] = {}
    for kind, cls in CONFIG_FILES.items():
        rel = f"config/{kind}.yaml"
        if not (root / rel).exists():
            loader.problems.append(
                Problem(
                    Severity.WARNING,
                    "CONFIG_MISSING",
                    "Configuration file is missing.",
                    file=rel,
                    hint="Create it with every number sourced (or 'TBD').",
                )
            )
            continue
        configs[kind] = loader.load(rel, cls, kind)

    problems = loader.problems
    project: Project | None = None
    if meta is not None and spacecraft is not None:
        project = Project(root, meta, spacecraft, units, modes, ProjectConfig(**configs))
        problems = problems + validate_references(project, loader.lines)
    problems = sort_problems(problems)
    if any(p.severity is Severity.ERROR for p in problems):
        project = None
    return LoadResult(project, problems, loader.lines)
