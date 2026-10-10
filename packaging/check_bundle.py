#!/usr/bin/env python3
"""Check a built bundle folder before it is released (standard library only).

    python packaging/check_bundle.py dist/system-budget-studio

Fails (exit 1) when development code such as hypothesis, mypy or pytest was bundled, or when the
licence material the licences require is missing: the licence texts, `licences.md` and the SBOM.
"""

from __future__ import annotations

import sys
from pathlib import Path

FORBIDDEN = (
    "hypothesis",
    "mypy",
    "mypyc",
    "pytest",
    "_pytest",
    "pytestqt",
    "pip",
    "setuptools",
    "PyInstaller",
    "ruff",
    "IPython",
    "chardet",  # not a dependency of the tool; pulled in only because it was installed
)
REQUIRED_FILES = (
    "licences.md",
    "sbom.cdx.json",
    "licences/INDEX.md",
    "licences/pyside6-essentials/LGPL-3.0.txt",
)


def executables(bundle: Path) -> list[str]:
    suffix = ".exe" if (bundle / "budget.exe").exists() or sys.platform == "win32" else ""
    return [f"system-budget-studio{suffix}", f"budget{suffix}"]


def check(bundle: Path) -> list[str]:
    problems: list[str] = []
    internal = bundle / "_internal"
    roots = [internal, bundle]
    for name in FORBIDDEN:
        for root in roots:
            if (root / name).exists() or (root / f"{name}.py").exists():
                problems.append(f"development code in the bundle: {name}")
                break
    for rel in REQUIRED_FILES:
        if not (bundle / rel).is_file():
            problems.append(f"missing from the bundle: {rel}")
    for exe in executables(bundle):
        if not (bundle / exe).is_file():
            problems.append(f"missing executable: {exe}")
    return problems


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or not Path(args[0]).is_dir():
        print("usage: check_bundle.py <bundle folder>")
        return 2
    problems = check(Path(args[0]))
    for problem in problems:
        print(f"FAILED: {problem}")
    print("Bundle check passed." if not problems else f"{len(problems)} problem(s).")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
