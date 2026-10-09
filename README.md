# System Budget Studio

Offline desktop tool for satellite power budgets and RF link budgets: one spacecraft model, versioned YAML inputs, sourced equations, reproducible reports. No cloud, no telemetry, no background network access.

Status: **M2a Static power budget** (model, validation, power table with margins, XLSX/PDF/JSON/CSV reports). See `docs/SPEC.md`, `docs/ARCHITECTURE.md` and `docs/PLAN.md`.

## Install (Python 3.11 to 3.13)

```
pip install -e .            # runtime only; yields a runnable GUI
system-budget-studio        # launch the GUI
budget --version            # CLI
budget export-examples demo # three synthetic example projects
budget validate demo/cubesat_3u
budget run demo/cubesat_3u --out out   # static power budget: XLSX, PDF, JSON, CSV
```

Developers: `pip install -e ".[dev]"` then `pytest`, `ruff check .`, `mypy`.

## Offline use

Everything (fonts, assets, help, examples) ships with the tool. For an air-gapped machine install from the hashed lock files and a mirrored wheel set:

```
pip install --no-index --find-links wheelhouse --require-hashes -r requirements.lock
```

The only permitted network use is a user-started reference-data download (later milestones). An automated test (`tests/offline`) fails if networking modules are imported or sockets opened.

## Fonts

IBM Plex (SIL Open Font License 1.1), bundled in `assets/fonts/` with its licence.

File format: `docs/FILE_FORMAT.md`.
