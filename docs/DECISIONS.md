# Decisions

One line each: decision, rationale.

| ID | Decision | Rationale |
|----|----------|-----------|
| D-001 | Product name is **System Budget Studio**. Code identifiers keep the spec names (`budget_core`, `budget_cli`, `budget_gui`, `budget` command). | User request; short stable identifiers avoid churn. User-visible strings, window titles, docs and installers use the full name. |
| D-002 | Work on the assigned branch `claude/blissful-maxwell-46xhwj` instead of `setup/repo`; never push to `main`. | User instruction. |
| D-003 | Orbit: SpaceMissionStudio import is primary; `ElementsPropagator` (sgp4) fallback ships in v1 for Earth orbits only. | Spec default. |
| D-004 | Margin policy values ship as placeholders with `source: TBD`; a Problems-panel warning shows until replaced. | Constraint 15. |
| D-005 | Eb/N0, rain and gas attenuation tables ship empty (`source: TBD`) with a documented import path and CSV/YAML template. | Constraint 15; ITU licensing unchecked. |
| D-006 | Core uses unit-suffixed field names (`power_w`, `freq_hz`, `gain_dbi`) and plain floats/NumPy; `pint` only parses/formats values at file-input and GUI boundaries. | Speed and simplicity; explicit units (constraint 17). |
| D-007 | Model is band-agnostic; UHF/S/X/Ka are example data. Optical is out of v1. | Keeps the solver generic. |
| D-008 | Targets: Windows 10/11 and Linux (RHEL/Rocky 8+, Ubuntu LTS). CI on Windows and Linux, Python 3.11 and 3.13. macOS untested. | Spec. |
| D-009 | Per-project unit definitions in v1; schema reserves `catalogue_ref`. | Defers catalogue versioning complexity. |
| D-010 | Internal-only; no `LICENSE` file. Dependencies remain permissive/LGPL. | Keeps open-source option open. |
| D-011 | SBOM is CycloneDX JSON, installers unsigned; signing hooks left in packaging scripts. | Spec default. |
| D-012 | No `gh` CLI in this environment; GitHub MCP tools are used. Branch protection settings are listed for the owner to apply. | Environment limitation; D-017. |
| D-013 | PDF via ReportLab (BSD, pure Python). | Layout control without native libraries. |
| D-014 | GUI plots: pyqtgraph. Report figures: Matplotlib (Agg backend, SVG/PNG). | Performance for 600k-point series vs. report quality. |
| D-015 | Project layout: `project.yaml`, `units/`, `modes/`, `scenarios/`, `ground_stations/`, `links/`, `config/` (each with JSON Schema), `results/` (git-ignored by default). | Constraint 12: parallel team work, clean diffs. |
| D-016 | Results: summary as JSON, time series as CSV with fixed float format and sorted keys. No HDF5/Parquet. | Byte-identical output (constraint 14), no binary deps. |
| D-017 | Repo visibility is verified private before any push beyond docs; example projects use invented data only. | Constraints 10, 11. |
| D-018 | Repo stayed **public** during M0 at the owner's explicit instruction ("Proceed while public"); M0 contains no project data. Owner to make it private before real data or examples with sensitive-looking values are added. | Spec step 2 asked to stop; owner answered. |
| D-019 | `main` did not exist (default branch was the working branch); `main` was created from the docs commit, owner to set it as default and protect it. M0 goes in by PR from `claude/blissful-maxwell-46xhwj`. | A PR cannot target its own head branch. |
| D-020 | Build backend hatchling; runtime dependency in M0 is only `PySide6-Essentials` (no QtNetwork use; `PySide6.QtNetwork` excluded in the PyInstaller spec). | Smaller bundle, no networking stack. |
| D-021 | Lock files via `uv pip compile --universal --generate-hashes` (`requirements.lock`, `requirements-dev.lock`); CI installs dev tooling from the hashed lock. | Spec: reproducible, hashed pins. |
| D-022 | Actions pinned to commit SHAs resolved with `git ls-remote` (checkout v7.0.1, setup-python v7.0.0, upload-artifact v7.0.2). | Spec: pin to SHA. |
| D-023 | IBM Plex Sans (Light/Regular/SemiBold) and Mono (Regular/SemiBold) TTFs bundled with the OFL licence. Carbon colour tokens (white, g100) are a minimal hand-written QSS; a full Carbon component set is deferred to M2. | M0 only needs an empty styled window. |
