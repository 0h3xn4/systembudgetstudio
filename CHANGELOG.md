# Changelog

All notable changes to System Budget Studio, newest first. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); each line names the decision (`D-0xx` in [DECISIONS.md](docs/DECISIONS.md)) behind it. The project is at version 0.1.0 and has not been released or tagged yet ([how to cut a release](docs/developer/README.md#cut-a-release)).

## [Unreleased]

### Added
- Documentation restructure: [README](README.md), [docs index](docs/README.md), [getting started](docs/getting-started.md), [user manual](docs/user-manual/README.md), [examples guide](examples/README.md), [FAQ](docs/faq.md), [troubleshooting](docs/troubleshooting.md), [glossary](docs/glossary.md), [tips](docs/tips.md), [CONTRIBUTING](CONTRIBUTING.md), [developer docs](docs/developer/README.md) and the [documentation audit](docs/DOCS_AUDIT.md).

### Changed
- `docs/ARCHITECTURE.md`, `PLAN.md`, `BRANCH_PROTECTION.md`, `ENVIRONMENT_FORMAT.md`, `FILE_FORMAT.md` and the user guide chapters corrected where they described features that do not exist.

## [0.1.0] - not yet released

Everything below is in the repository at version 0.1.0.

### Honesty round
- Unit import from CSV/XLSX and a separate expert mode are recorded as deferred; documents no longer claim them (D-099).
- A `<name>_provenance.csv` is written beside every set of CSV files (D-100).
- Thermal goldens are tolerant of the last digits; wall-clock tests have 3x headroom; tests for the remaining problem codes (D-101).

### Numerics round
- The power budget no longer depends on the time step: the battery is solved on the grid refined by every eclipse and mode-change edge (D-097).
- Overlapping eclipses from imported data count once; a limit met exactly is not a finding.
- Thermal solver accepts only balanced solutions and refuses networks it cannot resolve; `ok (margin not checked)` for a placeholder margin (D-098).
- Link passes weight `active_modes` by overlap; `usable_s` is n/a when not computable; new `LINK_NOT_CLOSED` finding.
- Angle units (`rpm`) are refused in non-angle fields; temperatures below absolute zero are refused.
- A mass-limit finding points at the right entry when names repeat.

### Packaging round
- Bundles exclude development code; the SBOM and licence report describe what is shipped; licence texts travel with the program (D-095).
- Safer `install.sh`/`uninstall.sh`; Windows installer sets `ChangesEnvironment`, removes exactly its PATH entry, cleans up on upgrade (D-096).
- CI smoke-tests that the window can be created on every platform, checks tag against version, writes `SHA256SUMS.txt`.

### Hardening round
- Unit tokens are checked before pint sees them; YAML aliases and oversized files are refused; limits on number magnitude, steps and rules (D-092).
- Project paths cannot leave the project folder; output names are sanitised and written atomically; spreadsheet formulas in CSV/XLSX are defused (D-093).
- GUI data safety: no concurrent export, confirm before discarding edits, stale results cannot be exported, no tracebacks (D-094).

### M6 Polish
- Comparison of two revisions or two scenarios (`budget compare`, Compare tab) (D-084, D-085).
- Guided new-project wizard (D-086); offline user guide in HTML and PDF with a generated *Equations and sources* chapter (`budget guide`) (D-087).
- Per-user installers for Windows and Linux built and tested in CI (D-088); licence review (D-089); performance pass (D-090); golden reports for every reference project (D-091).

### M5 Link budget
- Link files per direction, antennas (constant, table, pattern file), static table, pass time series with margin-constrained data rate and data volume per pass and per day (D-077 to D-083).

### M4b Thermal budget
- Heat dissipation by unit, subsystem, node and mode; steady-state node model with hot and cold cases; unit temperature limits (D-071 to D-076).

### M4 Time-domain power budget
- Solar array and battery model over a scenario for beginning and end of life; depth of discharge, orbit balance and peak power violations with time stamps; plots with cursors (D-061 to D-070).

### M3 Environment
- Eclipses and ground-station and target passes from orbital elements or a TLE (SGP4); an importer for an interim SpaceMissionStudio format; scenario mode timelines from rules and segments; `budget scenario` and the Scenario tab (D-053 to D-060).

### M2 Static budgets
- Static power budget with maturity and system margins and converter and distribution losses (M2a); static mass budget with centre of gravity, inertia and phases (M2b); XLSX, PDF, DOCX, CSV and JSON reports with provenance; Problems panel (D-040 to D-052).

### M1 Model and units
- Project model, unit-suffix convention with `pint` at the file boundary, schema versions with migrations, sourced configuration with placeholders, `budget validate`.

### M0 Foundation
- Repository, CI, an empty Carbon-styled window, packaging, the offline test.

Next: [Docs index](docs/README.md).
