#!/usr/bin/env python3
"""Licence review of the runtime dependency closure (standard library only).

Reads `[project.dependencies]` from pyproject.toml, follows the installed distributions'
requirements, classifies each licence and exits 1 when one is not permissive or LGPL (spec
constraint 7: only permissively licensed or LGPL dependencies that allow closed internal use).

    python packaging/licence_check.py                    # table, exit code
    python packaging/licence_check.py --markdown docs/LICENCES.md
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from dataclasses import dataclass
from importlib.metadata import Distribution, PackageNotFoundError, distribution
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Order matters: the first matching rule wins, strongest copyleft first.
RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "disallowed",
        re.compile(r"\bAGPL|Affero|\bGPL(?!.*\bLGPL)|(?<!Lesser )General Public License", re.I),
    ),
    ("lgpl", re.compile(r"\bLGPL|Lesser General Public", re.I)),
    ("review", re.compile(r"\bMPL|Mozilla Public|EPL|Eclipse Public|CDDL", re.I)),
    (
        "permissive",
        re.compile(
            r"\bMIT\b|MIT-CMU|\bBSD|Apache|\bISC\b|HPND|\bZlib\b|\bPSF\b|Python Software"
            r"|Unlicense|CC0|Public Domain|PIL Software License",
            re.I,
        ),
    ),
)
ALLOWED = ("permissive", "lgpl")


@dataclass(frozen=True)
class Entry:
    name: str
    licence: str
    category: str


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def runtime_requirements(pyproject: Path = ROOT / "pyproject.toml") -> list[str]:
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return [
        re.split(r"[ ;<>=!~\[(]", dep, maxsplit=1)[0] for dep in data["project"]["dependencies"]
    ]


def closure(names: list[str]) -> dict[str, Distribution]:
    found: dict[str, Distribution] = {}
    todo = list(names)
    while todo:
        name = todo.pop()
        key = normalise(name)
        if key in found:
            continue
        found[key] = distribution(name)  # PackageNotFoundError: the environment is incomplete
        for requirement in found[key].requires or []:
            if "extra ==" not in requirement:
                todo.append(re.split(r"[ ;<>=!~\[(]", requirement, maxsplit=1)[0])
    return found


def licence_text(dist: Distribution) -> str:
    meta = dist.metadata
    expression = meta.get("License-Expression")
    if expression:
        return expression
    classifiers = [
        c.split("::")[-1].strip()
        for c in meta.get_all("Classifier") or []
        if c.startswith("License")
    ]
    text = (meta.get("License") or "").strip()
    if len(text) > 80 or "\n" in text:  # a full licence text, not a name
        text = ""
    return " OR ".join(classifiers) if (classifiers and not text) else (text or "unknown")


def classify(text: str) -> tuple[str, str]:
    """(category, chosen option). A dual-licensed 'A OR B' takes the most permissive option."""
    best = ("unknown", text)
    rank = {"permissive": 0, "lgpl": 1, "review": 2, "disallowed": 3, "unknown": 4}
    for option in re.split(r"\s+OR\s+", text):
        category = next((c for c, rule in RULES if rule.search(option)), "unknown")
        if rank[category] < rank[best[0]]:
            best = (category, option.strip())
    return best


def review() -> list[Entry]:
    entries = []
    for key, dist in sorted(closure(runtime_requirements()).items()):
        text = licence_text(dist)
        category, chosen = classify(text)
        entries.append(Entry(key, chosen if category != "unknown" else text, category))
    return entries


NOTES = """
## Obligations

- **LGPL (PySide6-Essentials, shiboken6; Qt).** Used under the LGPL-3.0 option of their dual
  licence. The Windows and Linux builds are one-folder bundles in which the Qt and PySide6 libraries
  stay separate shared files, so a user can replace them (the LGPL relinking condition). The bundle
  ships the licence texts (`licences/<package>/`, with the LGPL and GPL texts from
  `assets/licences/` for the Qt bindings, whose wheels carry none), `licences.md` and the SBOM
  next to the program; `packaging/check_bundle.py` fails a build that lacks them. Do not modify Qt.
- **Permissive licences** (MIT, BSD, Apache, PSF, HPND/MIT-CMU): keep the copyright notices; the
  bundle ships them with the package metadata.
- **IBM Plex fonts** (`assets/fonts`): SIL Open Font License 1.1, the licence text is bundled in
  `assets/fonts/OFL-IBM-Plex.txt`. The fonts are not sold on their own.
- **Development tools** (pytest, mypy, ruff, PyInstaller, hypothesis, pip-licenses,
  cyclonedx-bom and others) are in the `dev` extra only and are not part of the installed tool.
  PyInstaller is GPL-2.0 with an exception that allows distributing the bundles it builds.
"""


def markdown(entries: list[Entry]) -> str:
    rows = "\n".join(f"| {e.name} | {e.licence} | {e.category} |" for e in entries)
    return (
        "# Licence review of the runtime dependencies\n\n"
        "Generated by `python packaging/licence_check.py --markdown docs/LICENCES.md` from "
        "`[project.dependencies]` and the installed package metadata; versions are pinned in "
        "`requirements.lock`. Allowed: permissive and LGPL (spec constraint 7). The release "
        "also carries the CycloneDX SBOM and `licences.md` from `packaging/build.sh`.\n\n"
        "| Package | Licence (option used) | Category |\n|---|---|---|\n"
        f"{rows}\n{NOTES}"
    )


LICENCE_FILE = re.compile(r"(^|/)(licen[cs]es?|copying|notice|authors)([^/]*)$", re.I)
QT_TEXTS = ("LGPL-3.0.txt", "GPL-3.0.txt")


def collect(out: Path) -> int:
    """Copy the licence texts of every runtime package into `out/<package>/`; return how many
    files were written. The LGPL and GPL texts kept in `assets/licences/` are always copied for
    the LGPL packages (the Qt bindings), whether or not their wheel carries texts. Writes
    `INDEX.md` too."""
    out.mkdir(parents=True, exist_ok=True)
    written = 0
    index = [
        "# Licence texts of the bundled packages",
        "",
        "| Package | Licence | Files |",
        "|---|---|---|",
    ]
    for entry in review():
        dist = distribution(entry.name)
        folder = out / entry.name
        files: list[str] = []
        for file in dist.files or []:
            if LICENCE_FILE.search(str(file).replace("\\", "/")) and "/fonts/" not in str(file):
                source = Path(str(dist.locate_file(file)))
                if source.is_file():
                    target = folder / f"{len(files):02d}-{source.name}"
                    folder.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(source.read_bytes())
                    files.append(target.name)
                    written += 1
        if entry.category == "lgpl":
            # always ship the LGPL and GPL texts for the LGPL packages: some wheels (Windows) carry
            # their own licence files, others (Linux) carry none
            folder.mkdir(parents=True, exist_ok=True)
            for name in QT_TEXTS:
                (folder / name).write_bytes((ROOT / "assets" / "licences" / name).read_bytes())
                files.append(name)
                written += 1
        if not files:  # never ship a package without its licence text
            raise SystemExit(f"No licence text found for {entry.name}")
        index.append(f"| {entry.name} | {entry.licence} | {', '.join(files)} |")
    (out / "INDEX.md").write_text("\n".join(index) + "\n", encoding="utf-8", newline="\n")
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--markdown", type=Path, help="Write the review as Markdown.")
    parser.add_argument("--collect", type=Path, help="Copy every package's licence text here.")
    args = parser.parse_args(argv)
    try:
        entries = review()
    except PackageNotFoundError as exc:
        print(f"A runtime dependency is not installed: {exc}")
        return 2
    for e in entries:
        print(f"{e.name:24} {e.category:11} {e.licence}")
    if args.markdown:
        args.markdown.write_text(markdown(entries), encoding="utf-8", newline="\n")
    if args.collect:
        print(f"Wrote {collect(args.collect)} licence file(s) to {args.collect}")
    bad = [e for e in entries if e.category not in ALLOWED]
    for e in bad:
        print(f"NOT ALLOWED: {e.name} ({e.licence}): {e.category}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
