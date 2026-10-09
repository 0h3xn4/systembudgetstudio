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
| D-024 | `avg_power_w` is the average power while the unit is in that mode **and switched on**; the effective average is `avg_power_w * duty_cycle_ratio`. **Confirmed by the owner (D-035).** | Spec lists both fields without defining how they combine. |
| D-025 | Field names carry the unit suffix (`_w`, `_wh`, `_hz`, `_kg`, `_m`, `_s`, `_k`, `_deg`, `_v`, `_a`, `_bps`, `_bit`, `_ratio`, `_db`, `_dbi`, `_dbw`, `_dbm`). Files may write "2.2 GHz" for such fields; it is converted with pint on load and saved as the canonical number. Plain numeric strings without a unit are rejected. | Constraint 17; D-006. |
| D-026 | Logarithmic units never convert implicitly to or from linear ones ("10 dBW" in a `_w` field is an error). dBW and dBm convert only into each other. pint is not used for log units. | The classic W/dBW spreadsheet failure. |
| D-027 | Pydantic models are the single source of truth; JSON Schemas are generated from them (`budget export-schemas`), committed in `src/budget_core/schemas/` and checked by a test. `jsonschema` is a dev dependency only, not runtime. Schemas describe the canonical form (numbers, not unit strings). | Fewer runtime dependencies than loading schemas at run time (revises ARCHITECTURE section 1). |
| D-028 | Files are saved in canonical form: model field order, sorted dict keys, 2-space maps, explicit `null`, no comments. A load-save round trip of a canonical file is byte-identical; comments in hand-edited files are lost on save. | Constraint 14; comment-preserving edits can come with the GUI editors if wanted. |
| D-029 | Problems and error messages contain field names, units, ids and allowed names, never values read from files (YAML syntax errors do not echo content either). | Constraint 11: CI logs must not leak controlled data. |
| D-030 | Unit ids are the file names in `units/`; spacecraft modes map unit id to power-mode name and must cover every unit (`UNIT_NOT_MAPPED` is an error). Scenarios, ground stations and links are not in the M1 schema. | Spec: a spacecraft mode maps every unit to one of its power modes. |
| D-031 | Example projects (`budget export-examples`, committed in `examples/`, checked for drift by a test) have every configuration number set to `value: null, source: TBD`, so they produce placeholder warnings by design. Maturity classes are neutral names (`class_a..c`). | Constraint 15. |
| D-032 | `load_project` returns no project when any error exists, and never raises for user errors. `budget validate` exits 1 on errors (also on warnings with `--strict`). | Keeps GUI and CLI on the same Problem list. |
| D-033 | Mass budgets are in v1 (owner request, supersedes the spec's out-of-scope line): static roll-up with maturity margins and limits, centre of gravity, moments of inertia, and mission phases with expendables. Folded into M2 as a second PR (M2b). Thermal and data storage stay out of scope. | Owner chose all four mass options and "fold into M2". |
| D-034 | `margin_policy` goes to schema v2 in M2b (`margin_ratio` -> `power_margin_ratio`, new placeholder `mass_margin_ratio`) with a migration; unit mass properties are optional new fields (no version bump needed). | Power and mass margins differ per maturity class; uses the migration framework as designed. |
| D-035 | M2 starts only after PR #2 (M1) is merged, so M2 gets a clean PR from `main`. D-024 is confirmed by the owner: effective average power = `avg_power_w * duty_cycle_ratio`. | Owner decisions. |
| D-036 | Thermal budgets are in v1 (owner request, supersedes the spec's out-of-scope line): dissipation and limits roll-up plus a steady-state lumped node model (hot and cold cases). Transient thermal is not in v1. New milestone M4b after M4. Data storage stays out of scope. | Owner chose "Dissipation and limits" and "Steady-state node model", new milestone after M4. |
| D-037 | `heat_dissipation_ratio` is an explicit per-mode field (1.0 unless the unit radiates RF or exports power); thermal environment fluxes, optical properties and case definitions ship as `Sourced` placeholders. | Constraint 15; energy conservation is not a standards value but must be visible, not hidden. |
| D-038 | M2 and M4b depend on each other only through the power modes: M2a (power) comes first, M4b reuses its dissipation data. Optional node heat capacity is reserved in the model. | Avoids a breaking change if transient thermal is added after v1. |

