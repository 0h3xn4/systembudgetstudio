"""Release checks: licence texts are collected, the bundle holds no development code."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "packaging" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


licence_check = load("licence_check")
check_bundle = load("check_bundle")


# ---- licence texts ---------------------------------------------------------------------------
def test_collect_writes_the_licence_text_of_every_runtime_package(tmp_path: Path) -> None:
    written = licence_check.collect(tmp_path)
    names = {p.name for p in tmp_path.iterdir() if p.is_dir()}
    assert {"numpy", "reportlab", "pydantic", "pyside6-essentials", "shiboken6"} <= names
    assert written >= len(names)
    for folder in tmp_path.iterdir():
        if folder.is_dir():
            assert any(folder.iterdir()), f"{folder.name} has no licence text"


def test_qt_bindings_get_the_lgpl_text_from_the_repository(tmp_path: Path) -> None:
    licence_check.collect(tmp_path)
    text = (tmp_path / "pyside6-essentials" / "LGPL-3.0.txt").read_text(encoding="utf-8")
    assert "GNU LESSER GENERAL PUBLIC LICENSE" in text
    assert (tmp_path / "pyside6-essentials" / "GPL-3.0.txt").is_file()


def test_the_shipped_lgpl_text_is_the_real_one() -> None:
    text = (ROOT / "assets" / "licences" / "LGPL-3.0.txt").read_text(encoding="utf-8")
    assert "Version 3, 29 June 2007" in text and "GNU LESSER GENERAL PUBLIC LICENSE" in text
    assert len(text.splitlines()) > 150


# ---- bundle contents -------------------------------------------------------------------------
def fake_bundle(tmp_path: Path, extra: tuple[str, ...] = (), skip: tuple[str, ...] = ()) -> Path:
    bundle = tmp_path / "system-budget-studio"
    internal = bundle / "_internal"
    for name in ("PySide6", "numpy", "budget_core", *extra):
        (internal / name).mkdir(parents=True)
    for rel in (
        "licences/INDEX.md",
        "licences/pyside6-essentials/LGPL-3.0.txt",
        "licences.md",
        "sbom.cdx.json",
    ):
        if rel not in skip:
            target = bundle / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x", encoding="utf-8")
    for exe in ("system-budget-studio", "budget"):
        (bundle / exe).write_text("x", encoding="utf-8")
    return bundle


def test_a_clean_bundle_passes(tmp_path: Path) -> None:
    assert check_bundle.check(fake_bundle(tmp_path)) == []


@pytest.mark.parametrize("module", ["hypothesis", "mypy", "pytest", "_pytest", "pytestqt", "pip"])
def test_development_code_in_the_bundle_is_reported(tmp_path: Path, module: str) -> None:
    problems = check_bundle.check(fake_bundle(tmp_path, extra=(module,)))
    assert any(module in p for p in problems)


@pytest.mark.parametrize(
    "missing", ["licences.md", "sbom.cdx.json", "licences/pyside6-essentials/LGPL-3.0.txt"]
)
def test_missing_licence_material_is_reported(tmp_path: Path, missing: str) -> None:
    problems = check_bundle.check(fake_bundle(tmp_path, skip=(missing,)))
    assert any(missing.split("/")[-1] in p for p in problems)


def test_missing_executables_are_reported(tmp_path: Path) -> None:
    bundle = fake_bundle(tmp_path)
    (bundle / "budget").unlink()
    assert any("budget" in p for p in check_bundle.check(bundle))


def test_cli_exit_codes(tmp_path: Path) -> None:
    assert check_bundle.main([str(fake_bundle(tmp_path / "ok"))]) == 0
    assert check_bundle.main([str(fake_bundle(tmp_path / "bad", extra=("hypothesis",)))]) == 1
    assert check_bundle.main([str(tmp_path / "missing")]) == 2


def test_lgpl_texts_are_shipped_even_when_the_wheel_has_its_own_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On Windows the Qt wheels carry licence files of their own; the LGPL text must still ship."""
    real = licence_check.distribution

    class WithOwnFile:
        def __init__(self, dist: object) -> None:
            self._dist = dist
            self.files = [Path("x.dist-info/LICENSE")]

        def locate_file(self, _file: object) -> Path:
            own = tmp_path / "own-licence.txt"
            own.write_text("wheel licence", encoding="utf-8")
            return own

        def __getattr__(self, name: str) -> object:
            return getattr(self._dist, name)

    monkeypatch.setattr(
        licence_check,
        "distribution",
        lambda name: WithOwnFile(real(name)) if name == "pyside6-essentials" else real(name),
    )
    out = tmp_path / "out"
    licence_check.collect(out)
    folder = out / "pyside6-essentials"
    assert (folder / "LGPL-3.0.txt").is_file() and (folder / "GPL-3.0.txt").is_file()
    assert any(p.name.endswith("own-licence.txt") for p in folder.iterdir())
