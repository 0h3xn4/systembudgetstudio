# System Budget Studio — Specification

> **Scope changes (owner requests, D-033, D-036):** mass budgets and thermal budgets (dissipation and limits, steady-state node model) are in version 1 (see "Mass budget" and "Thermal budget" below); they were out of scope in the original text. Data storage budgets remain out of scope. Transient thermal simulation is not in v1.
>
> Renamed from "Budget Studio" (see DECISIONS.md D-001). Technical identifiers (`budget_core`, `budget_cli`, `budget_gui`, the `budget` console script) are unchanged.

## Role and context

You are a senior software engineer building **System Budget Studio**, an offline desktop application for satellite power, mass, thermal and RF link budgets at a small satellite company. Treat this file as the specification. Before writing code, read it completely, ask your clarifying questions in one batch, and propose an architecture and milestone plan. Where the spec is silent, choose the simplest option, record it in `docs/DECISIONS.md` with a one-line rationale, and continue. Where the spec is ambiguous in a way that affects the data model or file format, stop and ask.

### Product goal

Replace the fragile spreadsheets every subsystem team keeps for power modes, eclipse cycles, battery depth of discharge and link margins with one tool that has a proper data model, versioned inputs, traceable assumptions and reproducible results. Engineers define a spacecraft (units, their power modes, solar array, battery, transmitters, antennas), an orbit and ground stations, and the tool computes the power and link budgets over time with margins and shows where they fail.

### Base frameworks

There is no mature open-source tool to build on; the existing GitHub projects (PowerCubeSat, assorted link-budget notebooks) are student scripts and must be treated as references for equations only, not as dependencies. Use these libraries, pinned and unpatched:

- **Orbit and eclipse data:** import from SpaceMissionStudio (Basilisk) output files when available. As a fallback, compute from TLE or Keplerian elements with a well-tested propagator such as `sgp4` or `skyfield`, plus a simple cylindrical or conical shadow model. Do not write your own propagator.
- **Numerics:** NumPy, SciPy, pandas.
- **Plots:** a bundled plotting library (pyqtgraph or Matplotlib with the Qt backend).

### Users

- **Systems engineers** build the mission-level budgets, set margin policy and present results in reviews.
- **EPS engineers** size the solar array and battery and refine the unit power profiles.
- **TT&C and payload data engineers** define transmitters, antennas, modulations and ground stations and check link margins over passes.
- **Operations and mission planners** test operational scenarios (mode timelines, pass schedules) against the budgets.
- **Reviewers and customers** read exported reports without the tool installed.

## Repository setup

The GitHub repository already exists and is empty. Setting it up is your first task and the start of M0; do it after `docs/ARCHITECTURE.md` and `docs/PLAN.md` are approved, before any feature code.

1. **Branch and remote:** the GitHub repository is `origin`, the default branch is `main`. Do all setup work on a branch (assigned: `claude/blissful-maxwell-46xhwj`, see D-002) and open a pull request; never push directly to `main`.
2. **Visibility:** confirm the repository is private. If it is public, stop and ask; project data may be export-controlled.
3. **Layout:** `src/budget_core`, `src/budget_cli`, `src/budget_gui`, `tests/` (unit, regression, golden, gui, offline), `docs/`, `examples/` (the three reference projects, synthetic data only), `packaging/` (PyInstaller specs, installer scripts), `assets/` (bundled IBM Plex fonts and Carbon assets).
4. **Docs:** commit `docs/SPEC.md` as given, plus `docs/ARCHITECTURE.md`, `docs/PLAN.md`, `docs/DECISIONS.md` and `docs/DEVIATIONS.md`.
5. **pyproject.toml:** src layout, `requires-python = ">=3.11,<3.14"`, runtime dependencies only in `[project.dependencies]`, all tooling in the `dev` extra (constraint 8), and a `budget` console script for the CLI. Configure ruff, mypy (strict) and pytest in the same file.
6. **Lock file:** pin every runtime and dev dependency with hashes (e.g. `pip-tools` or `uv`), so builds are reproducible from a mirrored package set.
7. **Root files:** `README.md` (purpose, install, offline use), `CLAUDE.md` (build, test, lint and package commands, conventions, pointer to `docs/SPEC.md`), `.gitignore` (Python, Qt, PyInstaller `build/` and `dist/`, IDE files, local project folders), `.editorconfig`, `.gitattributes` (LF line endings for YAML so project files diff cleanly). Add no `LICENSE` until the licence decision below is answered.
8. **CI (GitHub Actions):** on every pull request, run ruff, mypy, pytest and the offline test on Windows and Linux with Python 3.11 and 3.13. On tags, also build the installers, the SBOM and the licence report as release artefacts. Pin each action to a commit SHA.
9. **Repository settings:** protect `main` (pull request required, CI must pass). Apply this if your token allows it; otherwise list the exact settings for me to apply.
10. **No secrets or real data:** nothing from real projects goes into the repository, issues or CI logs; examples use invented units and values.

Setup is done when a fresh clone passes three checks: `pip install -e .` launches an empty Carbon-styled window, `pip install -e ".[dev]"` followed by `pytest` passes, and the setup pull request is green in CI.

## Hard constraints and lessons learned

These rules come from two earlier tools built the same way (SpaceMissionStudio on Basilisk, Harness Design Studio on WireViz). Each one cost time once; do not relearn them.

### Offline and closed operation

1. The tool must be fully usable offline and closed: no cloud services, no AI features, and no background network access (no telemetry, analytics, crash reporting, licence checks, online help, CDNs, web fonts or automatic update checks). Bundle every dependency and asset locally.
2. The only permitted network use is downloading reference data (e.g. TLEs, ITU rain-attenuation tables) or asset updates, and only when the user starts the download or explicitly agrees to a prompt naming the source, files and size. Verify the integrity of every download (checksum or signature), keep the previous version for rollback, and always offer the same update via manual file import.
3. Add an automated test that runs the tool with networking disabled and fails if any networking module is imported or a socket is opened at runtime. It runs in CI.
4. Help, examples and templates ship with the tool, since there is no online documentation.
5. All checks, warnings and results are deterministic and traceable to a defined equation or rule. No language-model features.

### Environment and packaging

6. Runs on locked-down workstations without admin rights. Deliver a self-contained installer or portable build for Windows 10/11 and Linux (RHEL/Rocky 8+ and Ubuntu LTS). Treat macOS as optional.
7. Only permissively licensed or LGPL dependencies that allow closed internal use. Pin all versions, make builds reproducible from a vendored or mirrored package set, and produce an SBOM (CycloneDX) and licence report with every release.
8. **Keep release and dev tooling out of the runtime dependencies.** In Harness Design Studio, `cyclonedx-bom` in the install set pulled in `lxml`, which had no wheel for the newest Python and broke `pip install` for the whole app. Put pytest, mypy, ruff, pyinstaller, cyclonedx-bom, pip-licenses, pip-audit and similar under `[project.optional-dependencies] dev`, and make sure `pip install -e .` alone yields a runnable GUI.
9. State the supported Python versions explicitly (currently 3.11 to 3.13) and test the install on the newest one, since brand-new interpreters often lack prebuilt wheels for C extensions.
10. Prefer pure-Python dependencies where a C extension brings no real benefit. NumPy and SciPy are accepted exceptions because wheels are reliable.

### Data and security

11. Project files may contain export-controlled information (RF parameters, unit power data). Never write project content to logs, temp files outside the project folder, or crash dumps.
12. Project data is plain text (YAML) that diffs and merges cleanly in Git. Units, modes, ground stations and scenarios are separate files so teams work in parallel.
13. Every file carries a schema version. Loading an older version migrates it; loading a newer version fails with a clear message.
14. Regenerating an unchanged project produces byte-identical result and report files (fixed random seeds if any, stable ordering, no timestamps inside content).

### Standards and numbers

15. **Never invent values from standards or physics references.** Margin policies, degradation factors, ITU attenuation coefficients, demodulator thresholds and similar numbers must come from configuration files with a source field. Ship them as clearly marked placeholders with an open decision, never as plausible-looking defaults. Both earlier tools had to be audited for this.
16. Every equation used must be named in the documentation with its source (e.g. Friis transmission, ECSS-E-ST-20C power margin rules, ECSS-E-ST-50-05C for RF and modulation, ITU-R P.618 for rain). Where you do not have the text, leave the formula slot and flag it.
17. **Units are explicit everywhere.** Use a units library (`pint`) or a strict internal convention with unit suffixes in field names; mixing W and dBW, or Hz and MHz, is the classic spreadsheet failure this tool exists to remove.

### Design system and UX

18. Use **IBM Carbon** as the design system, with IBM Plex fonts bundled, for data-dense tables, forms, notifications and a Problems panel. Match the look of SpaceMissionStudio and Harness Design Studio so the tools feel like one family.
19. Every output (report, plot, CSV) carries provenance: tool version, library versions, project revision, scenario name, generation date and the user's name.
20. Errors speak the user's language: what is wrong, where, and what to do, with a link that jumps to the offending input. Never show raw tracebacks in the GUI.
21. If the Monaco editor or any web component is used, package it with the tool; it loads from a CDN by default.

### Working method

22. Separate a **headless core** (model, solvers, reports) from the **GUI**. The core has no GUI imports and no network imports. Expose it through a **CLI** so budgets run in scripts and CI (e.g. `budget run project/ --scenario nominal --report pdf`).
23. Keep margin policies, equation constants and report templates in **project configuration files**, not in code.
24. Propose the technology stack with a short comparison of two or three options. A strong default is Python with PySide6 (Qt, LGPL) and PyInstaller. Accept an alternative only if it is clearly better for offline packaging or plotting.
25. Record every decision in `docs/DECISIONS.md` and every simplification of physics in `docs/DEVIATIONS.md`.
26. Write tests first for every milestone, including numerical regression tests against hand-calculated reference cases. Static typing and linting enforced in CI; no warnings on the main branch.

## Functional scope

### Shared spacecraft model

- **Units:** name, subsystem, mass, supply bus, and a list of power modes (name, average power, peak power, duty cycle, duration limits). Units reference a catalogue of reusable definitions so the same OBC appears identically in every project.
- **Modes and timelines:** spacecraft modes (safe, nominal, imaging, downlink, charging) map every unit to one of its power modes. A scenario is a timeline of spacecraft modes over one or more orbits, built by hand or generated from rules (e.g. downlink during every ground station pass, imaging over targets).
- **Orbit and environment:** orbit definition (import from SpaceMissionStudio, or elements and epoch), eclipse intervals, sun angle on each array face, ground station passes with elevation profiles. Keep the environment module replaceable.
- **Margin policy:** per project, with maturity-based margins (e.g. values per equipment maturity class) read from configuration, not hard-coded.

### Power budget

- Solar array model: cells per string, strings per face, cell efficiency, temperature coefficient, degradation over life, cosine loss from sun angle, packing and harness losses. Beginning-of-life and end-of-life outputs.
- Battery model: capacity, cells in series and parallel, charge and discharge efficiency, allowed depth of discharge by mission phase, degradation. State of charge integrated over the scenario timeline.
- Power system losses: converter efficiencies per bus, distribution losses, with values from configuration.
- Results: time series of generation, consumption, battery state of charge and bus margins; summary tables of average and peak power per mode with margins; a list of violations (depth of discharge exceeded, negative energy balance over an orbit, peak power above limit) with time stamps and jump links.
- Static table mode: a classic per-mode power budget with margins for early phase work, without any orbit.

### Mass budget

- Unit masses (`mass_kg` per unit, already in the unit files) rolled up by subsystem and for the spacecraft, with maturity-based mass margins and a system margin read from configuration (placeholders until supplied).
- Mass limits (e.g. launch mass, per requirement) in configuration with sources; violations in the Problems list.
- Centre of gravity from unit positions in the spacecraft body frame; moments and products of inertia from unit inertia tensors with the parallel-axis theorem.
- Mission phases (e.g. launch, beginning of life, end of life): expendables such as propellant and jettisoned equipment make mass, centre of gravity and inertia differ per phase.
- Same reports (XLSX, PDF, DOCX), CSV/JSON export, comparison and provenance rules as the other budgets.

### Thermal budget

- **Dissipation and limits:** heat dissipated per unit and power mode (electrical power minus power radiated as RF or otherwise leaving the unit, from the power data), rolled up by subsystem and spacecraft mode; operating and survival temperature limits per unit; findings in the Problems list.
- **Steady-state node model:** a small lumped network of thermal nodes (conductances, radiators with area, emissivity and absorptivity, environment heat loads) solved for equilibrium temperatures in hot and cold cases, compared with the unit limits. Environment heat flux values, optical properties and case definitions come from configuration with sources (placeholders until supplied).
- Same reports, exports, comparison and provenance rules as the other budgets. Transient (time-domain) thermal analysis is not in v1.

### Link budget

- Transmitter: RF power, line losses, antenna gain pattern (constant, table by angle, or pattern file), polarisation, frequency, modulation, coding, data rate, required Eb/N0 from a configurable table with sources.
- Receiver and ground station: antenna gain or G/T, system noise temperature, feed losses, location, minimum elevation, tracking limits.
- Propagation: free-space path loss from range, atmospheric and rain losses from configurable models with source fields, pointing loss, polarisation loss, implementation loss.
- Results: link margin as a single table at a chosen elevation and range, and as a time series over every pass in a scenario, for uplink and downlink separately. Data volume per pass and per day from margin-constrained data rate.
- Both directions and multiple links per spacecraft (TT&C S-band, payload X-band, inter-satellite) in one project.

### Reports and exchange

- Reports in PDF, DOCX and XLSX with the classic review table layouts, plots and the full assumptions list with sources.
- CSV export of every time series; JSON export of the full result for other tools.
- Import of unit power data from CSV or XLSX templates that the tool itself generates.
- Comparison view: two scenarios or two project revisions side by side with differences highlighted.

### Views

- Tree of spacecraft, units and modes; table editors with unit-aware cells; timeline editor for scenarios; result plots with cursors and eclipse and pass shading; Problems panel listing all violations and configuration gaps.
- Guided mode (wizard from orbit to first budget in under ten minutes with a sample spacecraft) and expert mode (dense tables, keyboard shortcuts, batch runs).

### Out of scope for version 1

- Data storage budgets (reserve the model for them later), transient thermal simulation, detailed thermal modelling (finite elements, radiative view factors by ray tracing). Mass budgets (D-033) and thermal dissipation/steady-state budgets (D-036) are in scope.
- Detailed solar cell IV-curve simulation and MPPT electronics modelling.
- Interference analysis and regulatory filing support.

## Architecture, quality and milestones

### Architecture

- Packages: `budget_core` (model, units, environment adapters, power solver, link solver, reports), `budget_cli`, `budget_gui`. The GUI depends on the core; nothing depends on the GUI.
- Environment adapters behind one interface: `SpaceMissionStudioImport` (reads its exported orbit, eclipse and pass files), `ElementsPropagator` (sgp4 or skyfield fallback). Solvers only see the interface.
- Solvers are pure functions over NumPy arrays with explicit unit handling; no state, no I/O, so they are easy to test and to call from scripts.
- Constants, margin policies, Eb/N0 tables, attenuation models and report templates live in `project/config/*.yaml` with a JSON Schema each and a `source` field on every number.
- Reports use only bundled components and fonts. DOCX via python-docx, PDF via a bundled renderer, XLSX via openpyxl, plots rendered to SVG or PNG by the bundled plotting library.

### Quality

- Numerical regression tests: at least ten hand-calculated reference cases per solver (e.g. a textbook S-band link at 2 GHz and 1,000 km range; an orbit-average power balance with a known eclipse fraction), with tolerances stated.
- Property-based tests (Hypothesis) for unit conversion round trips and for monotonic behaviour (more range never increases margin, more array area never reduces generation).
- Golden-file tests for every report type on three reference projects you create: a minimal 3U CubeSat, a 150 kg microsatellite with two links, and a stress case of 200 units and a one-week scenario at 1 s resolution.
- Performance targets: one-week scenario at 1 s resolution solves in under 10 s; GUI stays responsive during runs (worker thread).
- GUI tests with pytest-qt for the main flows; the offline test runs in CI.
- A user guide (Markdown bundled as offline HTML or PDF) including an "Equations and sources" chapter generated from the configuration files.

### Milestones

Propose a detailed plan in `docs/PLAN.md` roughly in this order. Each milestone ends with working, tested software and a short demo note.

1. **M0 Foundation:** repository (see Repository setup), build, CI, packaging of an empty Carbon-styled app into an offline installer, offline test, SBOM in the dev extra only.
2. **M1 Model and units:** spacecraft, unit and mode files, unit-aware fields, schema version, config files with sources, `budget validate`.
3. **M2 Static budgets (power and mass):** per-mode power table with margins, mass roll-up with centre of gravity, inertia and phases, Problems panel, first XLSX and PDF reports.
4. **M3 Environment:** SpaceMissionStudio import, propagator fallback, eclipse and pass computation, scenario timeline editor.
5. **M4 Time-domain power budget:** array and battery models, state of charge, violations, plots.
6. **M4b Thermal budget:** dissipation and limits roll-up, steady-state node model with hot and cold cases, reports.
7. **M5 Link budget:** static table, pass time series, data volume, both directions, reports.
8. **M6 Polish:** comparison view, guided mode, user guide, installer hardening, performance pass.

## Open decisions

Answered: "defaults for all" (see DECISIONS.md D-003 to D-017 for the concrete defaults).

- [x] **Orbit source:** import primary; propagator fallback in v1 (elliptical/circular Earth orbits).
- [x] **Margin policy:** placeholders with `source: TBD` until supplied.
- [x] **Eb/N0 and attenuation tables:** empty tables with `source: TBD`, manual import, no bundled third-party data.
- [x] **Units library:** suffix convention in core, `pint` at the I/O boundary only.
- [x] **Frequency bands:** band-agnostic model; UHF, S, X, Ka as data; no optical in v1.
- [x] **Operating systems:** Windows 10/11 and Linux; macOS untested.
- [x] **Catalogue:** per-project in v1; `catalogue_ref` reserved.
- [x] **Licence and ownership:** internal only; no LICENSE file.
- [x] **Security accreditation:** CycloneDX JSON, unsigned, signing hooks reserved.
- [x] **GitHub access:** pull requests only; settings listed for the owner to apply.
