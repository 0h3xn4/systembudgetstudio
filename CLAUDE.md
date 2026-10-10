# System Budget Studio — working notes

Docs index: `docs/README.md` (change the docs with the code: `docs/developer/README.md#keep-the-documentation-true`). Spec: `docs/SPEC.md` (authoritative). Plan: `docs/PLAN.md`. Architecture: `docs/ARCHITECTURE.md`. Record decisions in `docs/DECISIONS.md`, physics simplifications in `docs/DEVIATIONS.md`.

## Commands
- Install: `pip install -e ".[dev]"`
- Test: `QT_QPA_PLATFORM=offscreen pytest` (offline test: `pytest tests/offline`)
- Lint/type: `ruff check . && ruff format --check . && mypy`
- Lock: `packaging/lock.sh` (uv, hashes)
- Regenerate generated files after model changes: `budget export-schemas src/budget_core/schemas` and `budget export-examples examples` (tests fail on drift)
- Package: `pyinstaller packaging/system_budget_studio.spec` (Linux release: `packaging/linux/build_in_container.sh` in `rockylinux:8`)
- Licences: `python packaging/licence_check.py --markdown docs/LICENCES.md` (permissive or LGPL only); user guide: `budget guide --out guide`

## Conventions
- Core (`budget_core`) has no GUI or networking imports; GUI and CLI depend only on the core.
- Units explicit in field names (`power_w`, `freq_hz`, `gain_dbi`).
- Never invent standards values: numbers live in config files with a `source` field; unknown = `source: TBD`.
- No project content in logs, temp files outside the project folder, or crash dumps.
- Tests first; no warnings on main. Work on a branch and open a PR; never push to `main`.
- Runtime deps only in `[project.dependencies]`; all tooling in the `dev` extra.
- Example projects: invented data only.
- Problems/messages never contain values read from project files (field names, ids and units only).
- File format: `docs/FILE_FORMAT.md`. Schema changes need a version bump and a migration.
