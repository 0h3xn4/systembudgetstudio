# Developer docs

This page is for people who change System Budget Studio: how the repository is laid out, how to test and lint, how generated files are kept in step, how to keep the documentation true, and how to cut a release. For the first set-up see [CONTRIBUTING](../../CONTRIBUTING.md).

**Contents:** [Layout](#layout) · [Test, lint, type-check](#test-lint-type-check) · [Generated files](#generated-files) · [Golden files](#golden-files) · [The offline test](#the-offline-test) · [Keep the documentation true](#keep-the-documentation-true) · [Build the installers](#build-the-installers) · [Cut a release](#cut-a-release) · [Upstream documents](#upstream-documents)

## Layout

```text
src/budget_core/   the headless core: model, units, environment, power, mass, thermal, link, reports, guide
src/budget_cli/    the `budget` command (depends only on the core)
src/budget_gui/    the PySide6 window (depends only on the core)
tests/             unit, regression, golden, gui, offline
docs/              this documentation; docs/demo = milestone notes
examples/          the four example projects (generated; invented data)
packaging/         PyInstaller spec, Linux and Windows installers, licence and bundle checks
assets/            bundled fonts and licence texts
```

The [architecture overview](../ARCHITECTURE.md) explains the design: pure solvers over NumPy arrays, `Problem` records instead of exceptions for user errors, configuration with sources, and the decision numbers ([DECISIONS.md](../DECISIONS.md)) behind each choice. The rule that matters most when you add code: **the core imports neither the GUI nor anything networked**, and the CLI and GUI call the same core functions, so they cannot disagree.

## Test, lint, type-check

```bash
pip install -e ".[dev]"
QT_QPA_PLATFORM=offscreen pytest                 # everything (about 6 minutes)
QT_QPA_PLATFORM=offscreen pytest tests/unit      # one folder
pytest tests/offline                             # the no-network test
ruff check . && ruff format --check . && mypy    # lint, format, strict types
```

Tests are in five groups: `unit`, `regression` (hand-calculated reference cases, with the working in comments), `golden` (stored expected reports), `gui` (pytest-qt, offscreen) and `offline`. Properties are checked with Hypothesis. Tests marked `perf` time the one-week stress case; they fail only above three times the target (`tests/perf_limits.py`).

CI ([`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)) runs ruff, mypy and pytest on Ubuntu and Windows with Python 3.11 and 3.13, and checks that a runtime-only install (`pip install -e .`) gives a runnable `budget`. Actions are pinned to commit SHAs.

## Generated files

Some files are produced by code and checked by tests, so they cannot drift:

| File | Regenerate with | After changing |
|---|---|---|
| `src/budget_core/schemas/*.schema.json` | `budget export-schemas src/budget_core/schemas` | the model |
| `examples/` | `budget export-examples examples` | the example builders |
| `docs/LICENCES.md` | `python packaging/licence_check.py --markdown docs/LICENCES.md` | the dependencies |
| `requirements.lock`, `requirements-dev.lock` | `packaging/lock.sh` (uses `uv`; needs a network) | `pyproject.toml` dependencies |
| `tests/golden/*` | `UPDATE_GOLDEN=1 pytest tests/golden`, then **read the diff** | a deliberate change of a report |

## Golden files

A golden test builds a report, dumps its content as text (cell values, PDF text, DOCX paragraphs, JSON) and compares it with a stored copy. Compressed bytes are never compared (they differ between zlib builds). Numbers that depend on the platform's floating point are rounded in the dump (6 or 9 significant digits; values below 1e-6 count as zero in the thermal goldens). When a golden changes, review the diff and explain it in the pull request.

## The offline test

`tests/offline/test_offline.py` runs the CLI and the offscreen window in a fresh interpreter with sockets blocked, and fails if a networking module (`http.client`, `urllib.request`, `ssl`, `requests`, `PySide6.QtNetwork`, …) is imported. ReportLab's networking modules are imported lazily for this reason. Keep it green: it is the proof of the no-network promise.

## Keep the documentation true

When behaviour changes, change these in the same pull request:

| If you change… | Update |
|---|---|
| a CLI option or exit code | `--help` text, [command-line reference](../user-manual/command-line.md), [getting started](../getting-started.md) if shown there |
| the file format | [FILE_FORMAT.md](../FILE_FORMAT.md), the schema version and a migration, the matching [user manual](../user-manual/README.md) page and the **in-app guide chapter** ([`src/budget_core/guide/chapters/`](../../src/budget_core/guide/chapters/)) |
| a problem code | [FILE_FORMAT.md](../FILE_FORMAT.md) code list, guide chapter 11, [read and fix problems](../user-manual/read-and-fix-problems.md) |
| an example project | [examples/README.md](../../examples/README.md): its expected output |
| a menu, tab or shortcut | [use the window](../user-manual/use-the-window.md), the screenshots in [`docs/images/`](../images/) |
| any decision or simplification | [DECISIONS.md](../DECISIONS.md) / [DEVIATIONS.md](../DEVIATIONS.md) and the [CHANGELOG](../../CHANGELOG.md) |

The manual pages (task-oriented) and the in-app guide chapters (topic-oriented, shipped with the tool) overlap on purpose; change both. Check links before you push, with [lychee](https://github.com/lycheeverse/lychee):

```bash
lychee --offline --include-fragments --no-progress README.md CONTRIBUTING.md CHANGELOG.md 'docs/**/*.md' 'examples/**/*.md'
```

To regenerate the screenshots run the window offscreen (`QT_QPA_PLATFORM=offscreen`), open `examples/cubesat_3u_eps`, show the tab, and save `window.grab()` to `docs/images/`. Run every command in [getting started](../getting-started.md) in a fresh virtual environment now and then; the commands there are the documentation's tests.

## Build the installers

The installers are built by CI ([`release.yml`](../../.github/workflows/release.yml)); locally:

```bash
pip install -e ".[dev]"
packaging/build.sh                        # one-folder bundle in dist/, SBOM, licence report, bundle check
packaging/linux/build_in_container.sh     # the Linux release, inside rockylinux:8 (old glibc)
```

`packaging/check_bundle.py` fails the build if development code is bundled, or licence material is missing. `system-budget-studio --smoke` creates the window and exits; CI runs it on every platform. See the decisions D-088, D-089, D-095 and D-096.

## Cut a release

1. Decide the version `X.Y.Z`. Set it in **both** `pyproject.toml` (`version`) and `src/budget_core/__init__.py` (`__version__`): a test checks they agree.
2. If dependencies changed run `packaging/lock.sh` and `python packaging/licence_check.py --markdown docs/LICENCES.md`.
3. Update [CHANGELOG.md](../../CHANGELOG.md): move *Unreleased* under the new version with the date.
4. Merge to `main` through a pull request with CI green.
5. Tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`. The **Installers** workflow runs: it refuses a tag that differs from the `pyproject.toml` version, builds the Linux bundle on Rocky 8 and the Windows installer and portable zip, installs and uninstalls each as an ordinary user, and uploads the artefacts: the installers, `SHA256SUMS.txt`, `sbom.cdx.json` and `licences.md`.
6. Download the artefacts and carry out the manual steps of the [clean-machine checklist](../INSTALL_CHECKLIST.md) on a clean Windows and a clean Rocky 8 machine.
7. Publish: the workflow uploads build artefacts but does **not** create the GitHub Release; attach the files to a release for the tag yourself. (Who publishes is an open decision for the owner.)

## Upstream documents

This repository is not a fork and was not derived from another project, so there is no upstream README to keep in step: `README.md` is the only README of the project.

Next: [Architecture](../ARCHITECTURE.md) · [Decisions](../DECISIONS.md) · [Docs index](../README.md).
