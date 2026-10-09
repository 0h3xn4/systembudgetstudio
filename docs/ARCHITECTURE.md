# System Budget Studio — Architecture (proposal)

## 1. Technology stack

| Concern | Option A (chosen) | Option B | Option C | Rationale |
|---|---|---|---|---|
| GUI | **PySide6** (LGPL) | PyQt6 (GPL/commercial) | Electron/web UI | PySide6: LGPL, same family as the sibling tools, no browser to bundle. PyQt6 licence conflicts with closed use. Electron is heavy and invites CDN/network habits. |
| Packaging | **PyInstaller** (onedir + installer wrapper) | Nuitka | briefcase/MSIX | PyInstaller is proven in the sibling tools, works without admin rights, onedir zip = portable build. |
| Plots | **pyqtgraph** (GUI) + **Matplotlib Agg** (reports) | Matplotlib only | Qt Charts | pyqtgraph handles 600k-point series interactively; Matplotlib gives report-quality SVG/PNG. |
| PDF | **ReportLab** | QPdfWriter | WeasyPrint | Pure Python, good tables; WeasyPrint needs native Pango/Cairo. |
| Units | suffix convention + `pint` at I/O edge | `pint` everywhere | none | Speed in solvers, explicit units where humans type. |
| Orbit | **sgp4** | skyfield | own | sgp4 is small and pure-Python-capable; skyfield needs ephemeris files (extra data to bundle). |
| Data | **ruamel.yaml**, **jsonschema**, **pydantic v2** | PyYAML + dataclasses | | ruamel preserves order/comments for clean diffs; pydantic gives typed model plus migration hooks. (pydantic-core is a Rust wheel; acceptable, reliable wheels.) |
| Reports | python-docx, openpyxl | | | As specified. |

Runtime deps: PySide6, pyqtgraph, numpy, scipy, pandas, matplotlib, sgp4, pint, pydantic, ruamel.yaml, jsonschema, reportlab, python-docx, openpyxl, markdown (user guide HTML). Dev extra: pytest, pytest-qt, hypothesis, mypy, ruff, pyinstaller, cyclonedx-bom, pip-licenses, pip-audit, pip-tools/uv.

## 2. Package structure

```
src/budget_core/      no GUI, no network imports (enforced by import-linter test)
  model/              pydantic models: Project, Spacecraft, Unit, PowerMode, SpacecraftMode,
                      Scenario, Array, Battery, Link, Transmitter, Receiver, GroundStation
  io/                 YAML load/save, schema versioning + migrations, CSV/XLSX unit import
  units/              suffix conventions, pint parse/format, dB helpers
  config/             schemas (*.schema.json) and loaders; every number carries `source`
  environment/        Environment interface; SpaceMissionStudioImport; ElementsPropagator (sgp4)
  power/              static_budget.py; time domain: array.py, battery.py, attitude.py, orbits.py,
                      signals.py, time_domain.py (pure functions over NumPy arrays)
  plots/              PlotSpec (neutral), power plot builder, Pillow PNG renderer (reports)
  mass/               static_mass.py (roll-up, margins, limits), mass_properties.py (CG, inertia, phases)
  thermal/            dissipation.py (heat by unit/mode, limits), steady_state.py (nodal heat balance)
  link/               link_budget.py, propagation.py, passes.py, data_volume.py (pure functions)
  scenario/           timeline model, rule-based generation (downlink-on-pass, ...)
  problems/           Problem(severity, code, message, location) — shared by validate/solvers
  reports/            xlsx, docx, pdf, csv, json; provenance block; figures
  provenance.py       tool/library versions, project revision, scenario, date, user
src/budget_cli/       `budget validate | run | report | compare | import-units | template`
src/budget_gui/       PySide6 + Carbon theme; worker threads; no logic beyond presentation
```

Dependency direction: `budget_gui → budget_cli? no` — GUI and CLI both depend only on `budget_core`. Nothing depends on the GUI.

## 3. Core design rules

- **Solvers are pure**: `solve_power(inputs: PowerInputs, env: EnvironmentData) -> PowerResult`; NumPy in, NumPy out; no I/O, no globals, no clock.
- **Problems, not exceptions** for user errors: loaders and solvers return `Problem` records (`code`, `message`, `where` = file + YAML path). The GUI Problems panel and `budget validate` render the same list; `where` becomes a jump link.
- **Config with sources**: every number in `config/*.yaml` is `{value, unit, source}`. `source: TBD` produces a `CONFIG_PLACEHOLDER` problem (warning) and is flagged in every report's assumptions list.
- **Equation registry**: each solver function is registered with an ID, name, source citation (or `SOURCE_MISSING`); the "Equations and sources" chapter is generated from the registry plus config files.
- **Determinism**: stable sorting, fixed float formatting (`repr`-round-trip or fixed precision per column), no timestamps inside content except the provenance header, which is excluded when comparing for byte-identity via an explicit `--reproducible` mode (date taken from `SOURCE_DATE_EPOCH`, user name from a flag).
- **Privacy**: no logging of project content; temp files only inside the project folder; no crash dumps; error text includes file/path but never values.
- **Offline**: an import-guard test runs CLI and GUI-offscreen smoke flows with `socket` patched to raise and checks `sys.modules` for networking modules (`http.client`, `urllib.request`, `ssl`, `requests`, `socket` use). Update/download feature (TLE, tables) lives in one module `budget_core/refdata/` that is imported lazily only on explicit user action, with checksum verification, rollback copy and a manual-import alternative; the guard test whitelists only that module and asserts it is never imported in normal runs.

## 4. Data model and files

Project folder (all YAML, LF endings, schema-versioned):

```
project/
  project.yaml            schema_version, name, revision, spacecraft ref, margin_policy ref
  spacecraft.yaml         buses, array, battery, converters
  units/<unit>.yaml       name, subsystem, mass_kg, bus, maturity, catalogue_ref?, modes[]
  modes/<mode>.yaml       spacecraft mode -> {unit: unit_mode}
  scenarios/<name>.yaml   orbit ref, epoch, duration, timeline segments or rules
  ground_stations/*.yaml
  links/<name>.yaml       tx, rx, antennas, modulation, direction
  config/*.yaml + *.schema.json   margin policy, eb/n0 table, attenuation, array/battery constants, report templates
  results/                generated (git-ignored by default)
```

Fields carry unit suffixes (`avg_power_w`, `freq_hz`). Hand-typed values may be strings with units (`"2.2 GHz"`) which `pint` normalises on load; saves write canonical suffix fields. Each file: `schema_version: <int>`; loader runs ordered migrations `vN → vN+1`; newer than supported → `SCHEMA_TOO_NEW` error with upgrade instruction.

Reserved extension points: `catalogue_ref` on units; a `budgets:` registry in `project.yaml` so thermal/mass/storage budgets can be added later without breaking the schema.

## 5. Environment adapters

```python
class Environment(Protocol):
    def eclipse_intervals(self) -> Intervals          # UTC seconds from epoch
    def sun_vectors_body(self, t: ndarray) -> ndarray # for array-face incidence
    def passes(self, station: GroundStation) -> list[Pass]   # elevation/range vs time
```
- `SpaceMissionStudioImport`: reads exported orbit/eclipse/pass files. **Blocker:** the export format must be provided (sample files + field description) before M3; until then the adapter is built against a documented interim format and recorded in DECISIONS.
- `ElementsPropagator`: TLE or Keplerian → sgp4 → positions; cylindrical shadow default, conical option; pass finder via elevation root-finding (SciPy). Earth only.
- Attitude in v1: configurable per-face sun incidence from a simple attitude mode (sun-pointing, nadir-pointing, fixed inertial) — documented in DEVIATIONS.

## 6. Solvers (summary)

**Power static**: per-mode sum over units of `avg_power_w * (1+margin(maturity))` → converter-efficiency-adjusted bus load → totals, peak. **Power time domain** (M4, implemented; D-061 to D-066): scenario timeline and environment, steps from the environment grid, demand per step by exact overlap of the mode segments with the step, sunlit share by exact overlap of the eclipses; array output `P = E * sum_faces(N_cells * max(0, cos theta)) * A_cell * eta_ref * k_T * (1 - l_pack) * (1 - l_harness) * k_age * f_lit` (constants from `config/power_system.yaml`, sourced); energy-based battery with charge and discharge efficiency, full and empty saturation, depth of discharge per phase; BOL and EOL cases; violations as intervals with time stamps. Pure NumPy over steps plus one scalar loop for the battery; a 604,800-step week runs in about 1 s on top of the environment. **Link**: `Eb/N0 = EIRP − L_path − L_other + G/T − 10log10(k) − 10log10(R_b)` (Friis; ECSS-E-ST-50-05C usage flagged), margin vs table value (from config), per-time-step over passes, data volume from margin-constrained rate selection. All formulae named in the registry with sources or `SOURCE_MISSING`.

## 6a. Mass budget (added by D-033)

Inputs: unit `mass_kg`, `subsystem`, `maturity`; per unit optional `mass_properties` (position of the unit's centre of mass in the spacecraft body frame, `position_m`, and inertia tensor about that centre, `inertia_kgm2`: ixx, iyy, izz, ixy, ixz, iyz); expendables per phase; mass margins and limits from config (`source` on every number).
Equations (named in the registry, flagged `SOURCE_MISSING` until a text is cited): mass roll-up with margin `m_i (1 + margin(maturity_i))`; centre of gravity as the mass-weighted mean of positions; parallel-axis (Huygens-Steiner) theorem `I = sum(I_i + m_i (|d_i|^2 E - d_i d_i^T))` with `d_i = r_i - r_cg`.
Solvers are pure functions over NumPy arrays and return per-phase results. CG and inertia use nominal masses; margin mass has no position, see DEVIATIONS DV-M1. Missing positions or inertias give `MASS_PROPS_MISSING` warnings and exclude the unit from CG/inertia (never a silent zero).

## 6b. Thermal budget (added by D-036)

Inputs: power modes (electrical power, `duty_cycle_ratio`) with a per-mode `heat_dissipation_ratio`; unit temperature limits and node assignment; `thermal/model.yaml` (nodes, conductances, radiators); `config/thermal_environment.yaml` (fluxes, optical properties, hot/cold cases) with `source` on every number.
Solvers are pure functions: dissipation roll-up, then a steady-state nodal heat balance (conduction between nodes plus radiation to space and absorbed environment loads) solved as a nonlinear system with SciPy; results per case with margins against unit limits. Linear conduction and radiation only; no view factors beyond the user-given radiator-to-space coupling (DEVIATIONS DV-T1). Transient analysis is out of v1; the model reserves node heat capacity (`heat_capacity_j_per_k`, optional) so it can be added without a breaking change.

## 7. GUI

Carbon g100/white themes via bundled QSS + IBM Plex; main window = project tree (left), tabbed editors (table editors with unit-aware delegates, timeline editor), result plots (pyqtgraph, cursors, eclipse/pass shading), bottom Problems panel (double-click jumps to the offending editor cell). Runs execute in a `QThread` worker with cancel and progress; the GUI only touches `budget_core` public API and `Problem` objects. Guided mode = wizard over the same API. Tracebacks are caught at the top level and replaced by a message and a "save diagnostic (no project content)" option.

## 8. Packaging, CI, supply chain

- `uv`/`pip-compile --generate-hashes` lock files for runtime and dev; wheelhouse vendoring script for mirrored builds.
- PyInstaller onedir per OS; Windows per-user installer (no admin) plus portable zip; Linux tarball + AppImage-style launcher (RHEL 8 glibc baseline: build on a manylinux-like container).
- CI matrix: {windows, ubuntu} × {3.11, 3.13}: ruff, mypy --strict, pytest (unit, regression, golden, offline, gui with `QT_QPA_PLATFORM=offscreen`). Tag builds: installers, CycloneDX SBOM, licence report. Actions pinned by SHA.
- Install check on 3.13 fails the build if any runtime dependency lacks a wheel.

## 9. Testing strategy

Tests first per milestone. Per solver ≥ 10 hand-calculated regression cases with stated tolerances (hand calculations committed in `tests/regression/*.md` next to the test). Hypothesis properties: unit round-trips; margin monotonic in range; generation monotonic in array area. Golden files for each report type on three synthetic projects (3U, 150 kg micro, 200-unit week stress). pytest-qt for main flows. Performance test marks (`@pytest.mark.perf`) assert the 10 s target on CI reference runner with generous headroom reported rather than flaky-failed.

## 10. Risks

1. SpaceMissionStudio export format unknown (blocks M3 fidelity) — need samples.
2. No approved source for margin/Eb/N0/attenuation numbers — placeholders only; reports will show warnings until supplied.
3. PySide6 + PyInstaller size and RHEL 8 glibc compatibility — validate in M0 with an empty app.
4. Byte-identical PDF/DOCX/XLSX — need to neutralise embedded timestamps/IDs (ReportLab `invariant=1`, zip entry dates fixed in docx/xlsx); proven in M2.
5. Python 3.13 wheels for all runtime deps — checked in M0 CI.
