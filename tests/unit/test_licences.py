"""Licence review (spec constraint 7): only permissive or LGPL runtime dependencies."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "licence_check", ROOT / "packaging/licence_check.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["licence_check"] = module
    spec.loader.exec_module(module)
    return module


tool = load_tool()


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("MIT", "permissive"),
        ("BSD-3-Clause", "permissive"),
        ("BSD License", "permissive"),
        ("Apache-2.0", "permissive"),
        ("PSF-2.0", "permissive"),
        ("MIT-CMU", "permissive"),
        ("LGPL-3.0-only", "lgpl"),
        ("GNU Lesser General Public License v3 (LGPLv3)", "lgpl"),
        ("LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0", "lgpl"),
        ("MPL-2.0", "review"),
        ("GPL-3.0-only", "disallowed"),
        ("GNU General Public License v3 (GPLv3)", "disallowed"),
        ("AGPL-3.0-or-later", "disallowed"),
        ("MIT AND GPL-3.0-only", "disallowed"),
        ("some home-made licence", "unknown"),
        ("unknown", "unknown"),
    ],
)
def test_classification(text: str, category: str) -> None:
    got, _ = tool.classify(text)
    assert got == category


def test_dual_licence_takes_the_most_permissive_option() -> None:
    category, chosen = tool.classify("LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0")
    assert (category, chosen) == ("lgpl", "LGPL-3.0-only")


def test_every_runtime_dependency_is_permissive_or_lgpl() -> None:
    entries = tool.review()
    names = {e.name for e in entries}
    assert {"pyside6-essentials", "numpy", "reportlab", "python-docx", "sgp4"} <= names
    bad = [(e.name, e.licence, e.category) for e in entries if e.category not in tool.ALLOWED]
    assert bad == []


def test_dev_tools_are_not_in_the_runtime_closure() -> None:
    names = {e.name for e in tool.review()}
    for dev in (
        "pytest",
        "mypy",
        "ruff",
        "pyinstaller",
        "hypothesis",
        "cyclonedx-bom",
        "pip-licenses",
    ):
        assert dev not in names


def test_committed_review_lists_the_same_packages_and_categories() -> None:
    doc = (ROOT / "docs" / "LICENCES.md").read_text(encoding="utf-8")
    listed = dict(re.findall(r"^\| ([a-z0-9-]+) \| .* \| (\w+) \|$", doc, re.M))
    current = {e.name: e.category for e in tool.review()}
    assert listed == current, (
        "regenerate: python packaging/licence_check.py --markdown docs/LICENCES.md"
    )
