# System Budget Studio — Architecture

Status: built (milestones M0 to M6). This document began as the architecture proposal and has been corrected to match the code; where a decision changed it, the decision number (`D-0xx`, see [DECISIONS.md](DECISIONS.md)) is given. For using the tool see the [user manual](user-manual/README.md); for the file format see [FILE_FORMAT.md](FILE_FORMAT.md), which is authoritative.

**Contents:** [1. Technology stack](#1-technology-stack) · [2. Package structure](#2-package-structure) · [3. Core design rules](#3-core-design-rules) · [4. Data model and files](#4-data-model-and-files) · [5. Environment adapters](#5-environment-adapters) · [6. Solvers (summary)](#6-solvers-summary) · [6a. Mass budget (added by D-033)](#6a-mass-budget-added-by-d-033) · [6b. Thermal budget (added by D-036; implemented in M4b, D-071 to D-076)](#6b-thermal-budget-added-by-d-036-implemented-in-m4b-d-071-to-d-076) · [7. GUI](#7-gui) · [8. Packaging, CI, supply chain](#8-packaging-ci-supply-chain) · [9. Testing strategy](#9-testing-strategy) · [10. Risks](#10-risks)

## 1. Technology stack

| Concern | Option A (chosen) | Option B | Option C | Rationale |
|---|---|---|---|---|
| GUI | **PySide6** (LGPL) | PyQt6 (GPL/commercial) | Electron/web UI | PySide6: LGPL, same family as the sibling tools, no browser to bundle. PyQt6 licence conflicts with closed use. Electron is heavy and invites CDN/network habits. |
| Packaging | **PyInstaller** (onedir + installer wrapper) | Nuitka | briefcase/MSIX | PyInstaller is proven in the sibling tools, works without admin rights, onedir zip = portable build. |
| Plots | One neutral `PlotSpec`, a `QPainter` widget (GUI) and **Pillow** (reports) | pyqtgraph + Matplotlib | Qt Charts | Smaller bundle, fewer licences, same look in the GUI and in reports; long series are reduced to a min/max envelope per pixel (D-068, which replaced D-014). |
| PDF | **ReportLab** | QPdfWriter | WeasyPrint | Pure Python, good tables; WeasyPrint needs native Pango/Cairo. |
| Units | suffix convention + `pint` at I/O edge | `pint` everywhere | none | Speed in solvers, explicit units where humans type. |
| Orbit | **sgp4** | skyfield | own | sgp4 is small and pure-Python-capable; skyfield needs ephemeris files (extra data to bundle). |
| Data | **ruamel.yaml**, **jsonschema**, **pydantic v2** | PyYAML + dataclasses | | ruamel preserves order/comments for clean diffs; pydantic gives typed model plus migration hooks. (pydantic-core is a Rust wheel; acceptable, reliable wheels.) |
| Reports | python-docx, openpyxl | | | As specified. |

Runtime deps (`[project.dependencies]`): PySide6-Essentials, pydantic, ruamel.yaml, pint, openpyxl, reportlab, python-docx, pillow, numpy, sgp4. Everything else (pytest, pytest-qt, hypothesis, pypdf, jsonschema, mypy, ruff, pyinstaller, cyclonedx-bom, pip-licenses, pip-audit, uv) is in the `dev` extra.

## 2. Package structure

```
src/budget_core/      no GUI, no network imports (kept by convention and review; the offline test checks that no networking module is imported)
  model/              pydantic models: Project, Spacecraft, Unit, PowerMode, SpacecraftMode,
                      Scenario, Array, Battery, Link, Transmitter, Receiver, GroundStation
  io/                 YAML load/save, schema versioning + migrations, (unit import from CSV/XLSX is deferred, D-099)
  units/              suffix conventions, pint parse/format, dB helpers
  config/             schemas (*.schema.json) and loaders; every number carries `source`
  environment/        Environment interface; SpaceMissionStudioImport; ElementsPropagator (sgp4)
  power/              static_budget.py; time domain: array.py, battery.py, attitude.py, orbits.py,
                      signals.py, time_domain.py (pure functions over NumPy arrays)
  plots/              PlotSpec (neutral), power plot builder, Pillow PNG renderer (reports)
  mass/               static_mass.py (roll-up, margins, limits), mass_properties.py (CG, inertia, phases)
  thermal/            static_thermal.py (dissipation roll-up, cases, limit checks),
                      steady_state.py (nodal heat balance, pure function)
  link/               budget.py (equations, pure functions), evaluate.py (static table, pass series,
                      data volume), constants.py (c, k with sources)
  scenario/           timeline model, rule-based generation (downlink-on-pass, ...)
  problems/           Problem(severity, code, message, location) — shared by validate/solvers
  reports/            xlsx, docx, pdf, csv, json; provenance block; figures
  provenance.py       tool/library versions, project revision, scenario, date, user
src/budget_cli/       `budget validate | run | scenario | power-timeline | link-passes | compare | guide | self-test | export-schemas | export-examples`
src/budget_gui/       PySide6 + Carbon theme; worker threads; no logic beyond presentation
```

Dependency direction: the GUI and the CLI both depend only on `budget_core`. Nothing depends on the GUI.

## 3. Core design rules

- **Solvers are pure**: `solve_power(inputs: PowerInputs, env: EnvironmentData) -> PowerResult`; NumPy in, NumPy out; no I/O, no globals, no clock.
- **Problems, not exceptions** for user errors: loaders and solvers return `Problem` records (`code`, `message`, `where` = file + YAML path). The GUI Problems panel and `budget validate` render the same list; `where` becomes a jump link.
- **Config with sources**: every number in `config/*.yaml` is `{value, unit, source}`. `source: TBD` produces a `CONFIG_PLACEHOLDER` problem (warning) and is flagged in every report's assumptions list.
- **Equation registry**: each solver function is registered with an ID, name, source citation (or `SOURCE_MISSING`); the "Equations and sources" chapter is generated from the registry plus config files.
- **Determinism**: stable sorting, fixed float formatting (`repr`-round-trip or fixed precision per column), no timestamps inside content except the provenance header, so the same inputs plus the same generation time and user give the same bytes: `--date` (or `SOURCE_DATE_EPOCH`) and `--user` (or `BUDGET_USER`) fix the two values that vary.
- **Privacy**: no logging of project content; temp files only inside the project folder; no crash dumps; error text includes file/path but never values.
- **Offline**: `tests/offline/test_offline.py` runs the CLI and the offscreen window in a fresh interpreter with sockets blocked and fails if a networking module (`http.client`, `urllib.request`, `ssl`, `requests`, `PySide6.QtNetwork`, …) is imported. No download feature exists in version 0.1.0. If one is added (reference data such as TLEs or tables), it must live in one module that is imported only on explicit user action, verify a checksum, keep a rollback copy and offer a manual-import alternative (spec constraint 2); the offline test would whitelist only that module.

## 4. Data model and files

Project folder (all YAML, LF endings, schema-versioned):

```
project/
  project.yaml            schema_version, kind, name, revision, description
  spacecraft.yaml         buses, mission phases, body frame
  units/<unit>.yaml       name, subsystem, mass_kg, bus, maturity, catalogue_ref?, modes[], mass properties, temperature limits
  modes/<mode>.yaml       spacecraft mode -> {unit: unit power mode}
  orbits/  ground_stations/  targets/  scenarios/  expendables/
  links/<name>.yaml       tx, rx, antennas, modulation, direction
  config/*.yaml           margin policy, power config, power system (array, battery, attitude, limits),
                          mass limits, thermal model and environment, Eb/N0 table, attenuation table
  results/                generated (git-ignored by default)
```

The complete, current field list is in [FILE_FORMAT.md](FILE_FORMAT.md). JSON Schemas of every kind are generated (`budget export-schemas`) into `src/budget_core/schemas/`.

Fields carry unit suffixes (`avg_power_w`, `freq_hz`). Hand-typed values may be strings with units (`"2.2 GHz"`) which `pint` normalises on load; saves write canonical suffix fields. Each file: `schema_version: <int>`; loader runs ordered migrations `vN → vN+1`; newer than supported → `SCHEMA_TOO_NEW` error with upgrade instruction.

Reserved extension point: `catalogue_ref` on units (decision D-009). Storage budgets are out of scope for version 1 and no registry for them exists yet.

## 5. Environment adapters

```python
class Environment(Protocol):
    def eclipse_intervals(self) -> Intervals          # UTC seconds from epoch
    def sun_vectors_body(self, t: ndarray) -> ndarray # for array-face incidence
    def passes(self, station: GroundStation) -> list[Pass]   # elevation/range vs time
```
- `SpaceMissionStudioImport`: reads exported orbit/eclipse/pass files. **Blocker:** the export format must be provided (sample files + field description) before M3; until then the adapter is built against a documented interim format and recorded in DECISIONS.
- `ElementsPropagator`: TLE or Keplerian → sgp4 → positions; cylindrical shadow default, conical option; pass finder via elevation bisection (NumPy, no SciPy; D-058). Earth only.
- Attitude in v1: configurable per-face sun incidence from a simple attitude mode (sun-pointing, nadir-pointing, fixed inertial) — documented in DEVIATIONS.

## 6. Solvers (summary)

**Power static**: per-mode sum over units of `avg_power_w * (1+margin(maturity))` → converter-efficiency-adjusted bus load → totals, peak. **Power time domain** (M4, implemented; D-061 to D-066): scenario timeline and environment, steps from the environment grid, demand per step by exact overlap of the mode segments with the step, sunlit share by exact overlap of the eclipses; array output `P = E * sum_faces(N_cells * max(0, cos theta)) * A_cell * eta_ref * k_T * (1 - l_pack) * (1 - l_harness) * k_age * f_lit` (constants from `config/power_system.yaml`, sourced); energy-based battery with charge and discharge efficiency, full and empty saturation, depth of discharge per phase; BOL and EOL cases; violations as intervals with time stamps. Pure NumPy over steps plus one scalar loop for the battery; a 604,800-step week runs in about 1 s on top of the environment. **Link** (M5, implemented; D-077 to D-083): `Eb/N0 = EIRP − L_path − L_other + G/T − 10log10(k) − 10log10(R_b)` (Friis; ECSS-E-ST-50-05C usage flagged), margin vs table value (from config), per-time-step over passes, data volume from margin-constrained rate selection. All formulae named in the registry with sources or `SOURCE_MISSING`.

## 6a. Mass budget (added by D-033)

Inputs: unit `mass_kg`, `subsystem`, `maturity`; per unit optional `mass_properties` (position of the unit's centre of mass in the spacecraft body frame, `position_m`, and inertia tensor about that centre, `inertia_kgm2`: ixx, iyy, izz, ixy, ixz, iyz); expendables per phase; mass margins and limits from config (`source` on every number).
Equations (named in the registry, flagged `SOURCE_MISSING` until a text is cited): mass roll-up with margin `m_i (1 + margin(maturity_i))`; centre of gravity as the mass-weighted mean of positions; parallel-axis (Huygens-Steiner) theorem `I = sum(I_i + m_i (|d_i|^2 E - d_i d_i^T))` with `d_i = r_i - r_cg`.
Solvers are pure functions over NumPy arrays and return per-phase results. CG and inertia use nominal masses; margin mass has no position, see DEVIATIONS DV-M1. Missing positions or inertias give `MASS_PROPS_MISSING` warnings and exclude the unit from CG/inertia (never a silent zero).

## 6b. Thermal budget (added by D-036; implemented in M4b, D-071 to D-076)

Inputs: power modes (electrical power, `duty_cycle_ratio`) with a per-mode `heat_dissipation_ratio`; unit temperature limits and node assignment; `config/thermal_model.yaml` (nodes, conductances, surfaces); `config/thermal_environment.yaml` (fluxes, optical properties, hot/cold cases) with `source` on every number.
Solvers are pure functions: dissipation roll-up, then a steady-state nodal heat balance (conduction between nodes plus radiation to space and absorbed environment loads) solved as a nonlinear system by damped Newton iteration in NumPy (no SciPy, D-075); results per case with margins against unit limits. Linear conduction and radiation only; no view factors beyond the user-given radiator-to-space coupling (DEVIATIONS DV-T1). Transient analysis is out of v1; the model reserves node heat capacity (`heat_capacity_jperk`, optional) so it can be added without a breaking change.

## 7. GUI

Carbon g100/white themes via bundled QSS + IBM Plex; main window = project tree (left), tabbed editors (table editors with unit-aware delegates, timeline editor), result plots (a QPainter widget, cursors, eclipse/pass shading; D-068), bottom Problems panel (double-click jumps to the offending editor cell). Runs execute in a `QThread` worker with cancel and progress; the GUI only touches `budget_core` public API and `Problem` objects. Guided mode = wizard over the same API (`budget_core.wizard` builds the project, `budget_gui.guided` is the QWizard; D-086). The Compare tab runs `budget_core.compare_run` in a worker thread (D-084, D-085); Help > User guide shows `budget_core.guide` (D-087). Tracebacks are caught at the top level and replaced by a message and a "save diagnostic (no project content)" option.

## 8. Packaging, CI, supply chain

- `uv`/`pip-compile --generate-hashes` lock files for runtime and dev; wheelhouse vendoring script for mirrored builds.
- PyInstaller onedir per OS with two executables (`system-budget-studio`, `budget`); Windows per-user Inno Setup installer (no admin) plus portable zip; Linux tarball with `install.sh`/`uninstall.sh` (per user), built in a `rockylinux:8` container for the glibc 2.28 baseline (D-088). `packaging/licence_check.py` enforces permissive or LGPL runtime licences (D-089).
- CI matrix: {windows, ubuntu} × {3.11, 3.13}: ruff, mypy --strict, pytest (unit, regression, golden, offline, gui with `QT_QPA_PLATFORM=offscreen`). Tag builds: installers, CycloneDX SBOM, licence report. Actions pinned by SHA.
- Install check on 3.13 fails the build if any runtime dependency lacks a wheel.

## 9. Testing strategy

Tests first per milestone. Per solver ≥ 10 hand-calculated regression cases with stated tolerances (the hand calculation is written out in comments in the test file, with the stated tolerance). Hypothesis properties: unit round-trips; margin monotonic in range; generation monotonic in array area. Golden files for each report type on the synthetic reference projects (3U, 150 kg micro, 200-unit week stress). pytest-qt for main flows. Performance test marks (`@pytest.mark.perf`) assert the 10 s target on CI reference runner with generous headroom reported rather than flaky-failed.

## 10. Risks

1. SpaceMissionStudio export format unknown (blocks M3 fidelity) — need samples.
2. No approved source for margin/Eb/N0/attenuation numbers — placeholders only; reports will show warnings until supplied.
3. PySide6 + PyInstaller size and RHEL 8 glibc compatibility — validate in M0 with an empty app.
4. Byte-identical PDF/DOCX/XLSX — need to neutralise embedded timestamps/IDs (ReportLab `invariant=1`, zip entry dates fixed in docx/xlsx); proven in M2.
5. Python 3.13 wheels for all runtime deps — checked in M0 CI.

Next: [File format](FILE_FORMAT.md) · [Decisions](DECISIONS.md) · [Developer docs](developer/README.md) · [Docs index](README.md).
