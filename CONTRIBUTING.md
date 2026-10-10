# Contributing

This page tells you how to set up a development copy of System Budget Studio, what the rules of the project are, and how to get a change merged. The details are in the [developer docs](docs/developer/README.md).

## Set up

```bash
git clone https://github.com/0h3xn4/systembudgetstudio.git
cd systembudgetstudio
python3 -m venv .venv && source .venv/bin/activate     # Windows: py -3 -m venv .venv ; .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
QT_QPA_PLATFORM=offscreen pytest                       # about 6 minutes; Windows PowerShell: $env:QT_QPA_PLATFORM="offscreen"; pytest
ruff check . && ruff format --check . && mypy
```

If the tests pass and the three checks print nothing worrying, you are ready. On Linux the window tests need the libraries listed in the [troubleshooting page](docs/troubleshooting.md#start-the-window).

## The rules of the project

These are enforced by tests and review (the full list is in [CLAUDE.md](CLAUDE.md) and the [specification](docs/SPEC.md)):

- **Tests first.** Write the failing test, then the code. Solvers need hand-calculated reference cases.
- **No warnings on `main`**: ruff, ruff format and mypy (strict) are clean.
- **Offline.** The core imports no GUI and no networking module; a test checks it.
- **Never invent standards values.** Numbers live in config files with a `source`; unknown is `source: TBD`.
- **Units are in the field names** (`power_w`, `freq_hz`, `gain_dbi`).
- **No project content in logs, temp files, crash dumps or messages**: messages name fields, ids and units only.
- **Example projects contain invented data only.**
- **Runtime dependencies only in `[project.dependencies]`**; all tooling in the `dev` extra.
- **Record decisions** in [DECISIONS.md](docs/DECISIONS.md) and physics simplifications in [DEVIATIONS.md](docs/DEVIATIONS.md). A change to the file format needs a schema version bump and a migration ([FILE_FORMAT.md](docs/FILE_FORMAT.md)).

## Make a change

1. Work on a branch; never push to `main`.
2. Make the change with tests. If you change the model or an example, regenerate the generated files (`budget export-schemas src/budget_core/schemas`, `budget export-examples examples`): the tests fail when they drift.
3. Update the documentation that describes the behaviour ([which pages](docs/developer/README.md#keep-the-documentation-true)) and add an entry to [CHANGELOG.md](CHANGELOG.md).
4. Open a pull request into `main`. CI must pass on Windows and Linux with Python 3.11 and 3.13. A change that touches `packaging/` also runs the installer workflow.

## Reporting a problem

Say what you ran (`budget --version`, the command), what you expected and the message you got. Messages never contain project values, so they are safe to paste; do not attach project files that may be sensitive.

Next: [Developer docs](docs/developer/README.md) · [Architecture](docs/ARCHITECTURE.md).
