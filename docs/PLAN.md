# System Budget Studio — Plan

Status: milestones M0 to M6 are done (see the [changelog](../CHANGELOG.md)); this file keeps the plan as it was agreed, with each milestone marked. For using the tool see the [user manual](user-manual/README.md).

**Contents:** [M0 Foundation (M)](#m0-foundation-m) · [M1 Model and units (M)](#m1-model-and-units-m) · [M2 Static budgets: power and mass (L, two PRs)](#m2-static-budgets-power-and-mass-l-two-prs) · [M3 Environment (L, two PRs: M3a core and CLI, done; M3b GUI timeline editor, done)](#m3-environment-l-two-prs-m3a-core-and-cli-done-m3b-gui-timeline-editor-done) · [M4 Time-domain power budget (L, done)](#m4-time-domain-power-budget-l-done) · [M4b Thermal budget (L, done)](#m4b-thermal-budget-l-done) · [M5 Link budget (L, done)](#m5-link-budget-l-done) · [M6 Polish (M, done)](#m6-polish-m-done) · [Critical path / external inputs](#critical-path--external-inputs)

Rules for every milestone: tests first; ruff + mypy strict clean; no network; each ends with a demo note in `docs/demo/Mx.md`. Estimates are relative (S/M/L).

## M0 Foundation (M)
Scope: repo setup per SPEC §Repository setup; Carbon-styled empty window ("System Budget Studio"); PyInstaller build of the empty app on Windows and Linux; offline test; lock files; CI.
Acceptance: (1) `pip install -e .` launches the empty window; (2) `pip install -e ".[dev]" && pytest` passes; (3) setup PR green on {win, linux}×{3.11, 3.13}; (4) offline test fails when a socket is opened (negative test proves it); (5) installer/portable build launches on a clean machine without admin rights; (6) SBOM and licence report generated from the dev extra only; (7) `pip install -e .` pulls no dev tooling.
Needs from you: confirm repo is private; apply branch protection (list provided).

## M1 Model and units (M)
Scope: pydantic models, YAML IO, schema versions + migration framework (with a v1→v2 test migration), unit parsing/dB helpers, config files with `source` + JSON Schemas (margin policy, Eb/N0, attenuation, array, battery, converters — all placeholders), `Problem` type, `budget validate`, three reference projects' skeletons.
Acceptance: invalid/missing/newer-schema files give located, plain-language problems; placeholders raise `CONFIG_PLACEHOLDER`; round-trip load→save is byte-identical; Hypothesis unit round-trips pass.

## M2 Static budgets: power and mass (L, two PRs)
Scope: shared margin handling; Problems panel (GUI, wired to validate and the budgets); table editors for units/modes; XLSX and PDF reports with provenance and assumptions list; reproducible-output mode; loader packaged in the GUI bundle (pint data, hidden imports).
- **M2a Power (first PR, done):** static per-mode table with maturity margins, converter and distribution losses, effective average = `avg_power_w * duty_cycle_ratio` (D-024).
- **M2b Mass (second PR, same milestone; done):**
  - Model: unit `mass_properties` (position in the spacecraft frame, inertia tensor about the unit's own centre), optional `phases` on units, `expendables/*.yaml` (propellant and consumables per phase), `mission_phases` and the body-frame definition in `spacecraft.yaml`, `config/mass_limits.yaml` (limits with sources). `margin_policy` goes to schema v2 with a migration: `margin_ratio` becomes `power_margin_ratio`, and a placeholder `mass_margin_ratio` is added per class (first real use of the migration framework).
  - Solver (pure functions): roll-up by subsystem and total with margins; centre of gravity `r_cg = sum(m_i r_i) / sum(m_i)` on nominal masses; inertia about the CG with the parallel-axis (Huygens-Steiner) theorem; per-phase results; limit checks.
  - Problems: `MASS_LIMIT_EXCEEDED`, `MASS_PROPS_MISSING`, `PHASE_UNKNOWN`, plus placeholder warnings.
  - Reports: mass table by subsystem, unit list, CG and inertia per phase.
Acceptance: at least 10 hand-calculated cases per solver (power table; mass roll-up; CG of point masses; inertia by parallel axis, e.g. two equal masses on an axis; phase changes) with stated tolerances; Hypothesis properties (adding mass never lowers the total, CG lies inside the bounding box of the unit positions, inertia tensor symmetric and positive semi-definite); XLSX/PDF golden tests byte-identical on re-run; GUI flow: open example, edit a unit, Problems update, export; `pip install` of the bundle still starts and can validate a project.
Needs from you: margin policy and mass margin values (placeholders otherwise), mass limits with sources, confirmation of the body-frame convention (axes and origin) when M2b starts.

## M3 Environment (L, two PRs: M3a core and CLI, done; M3b GUI timeline editor, done)
Scope: `Environment` interface; `ElementsPropagator` (TLE/Keplerian, shadow model, passes); `SpaceMissionStudioImport` (needs sample files); scenario model, rule-based generation (downlink on pass); timeline editor.
Acceptance: eclipse fraction and pass count/duration for textbook circular LEO cases match hand calculation within stated tolerance; adapters interchangeable behind the interface in solver tests; timeline editor creates/edits/validates scenarios.
Needs from you: SpaceMissionStudio sample export files.

## M4 Time-domain power budget (L, done)
Scope: array and battery models, converter/distribution losses, SoC integration, violations with timestamps, result plots with eclipse/pass shading and cursors, CSV/JSON export, worker-thread runs, DOCX report.
Acceptance: ≥10 regression cases (e.g. orbit-average balance with known eclipse fraction); monotonic properties pass; 1-week/1 s stress case < 10 s; GUI responsive during run; violations jump to inputs.

## M4b Thermal budget (L, done)
Scope: after M4 because it reuses the power modes, spacecraft modes and (for hot and cold case definitions) the environment work.
- **Model:** per power mode `heat_dissipation_ratio` (fraction of electrical power dissipated as heat, 1.0 unless the unit radiates or exports power; explicit, never silently assumed); per unit operating and survival limits (`operating_min_k`, `operating_max_k`, `survival_min_k`, `survival_max_k`) and the thermal node it is mounted on; `thermal/model.yaml` (nodes, conductances `conductance_w_per_k`, radiators with `area_m2`, `emissivity_ratio`, `absorptivity_ratio`, links to space); `config/thermal_environment.yaml` (solar flux, albedo, Earth infrared, hot/cold case definitions, every number `Sourced` with placeholders).
- **Solvers (pure functions):** dissipation roll-up by unit, subsystem, spacecraft mode; steady-state nodal heat balance `sum(G_ij (T_j - T_i)) + sigma eps A (T_space^4 - T_i^4) + Q_i = 0` solved by damped Newton iteration in NumPy, no SciPy (D-075) (Stefan-Boltzmann law, textbook source flagged `SOURCE_MISSING` until cited); margin against limits with a configurable thermal margin from config.
- **Problems:** `THERMAL_LIMIT_EXCEEDED`, `THERMAL_NODE_UNKNOWN`, `THERMAL_NO_LIMITS`, `THERMAL_SOLVE_FAILED`, plus placeholder warnings.
- **Reports:** dissipation table, node temperatures per case, unit limit margins.
Acceptance: at least 10 hand-calculated cases (single node radiating to space, two nodes in series, radiator sizing, one node with constant dissipation, ...) with stated tolerances; properties (more dissipation never lowers a node temperature, more radiator area never raises it, energy balance residual below a tolerance); golden reports; solve time for the 200-unit stress case with realistic node counts well under a second.
Needs from you: environment flux values, optical properties and hot/cold case definitions with sources; the node-network convention (how units map to nodes) when M4b starts.

## M5 Link budget (L, done)
Scope: link models (uplink/downlink, multiple links), static table at chosen elevation/range, pass time series, margin-constrained data rate and data volume per pass/day, attenuation tables from config (empty until supplied), link reports.
Acceptance: textbook S-band 2 GHz/1000 km case within tolerance, ≥10 cases; margin monotonic in range; golden reports for micro-sat with two links.

## M6 Polish (M, done)
Scope: comparison view (scenarios/revisions), guided wizard (orbit → first budget < 10 min on sample), user guide with generated "Equations and sources" chapter (offline HTML + PDF), installer hardening (no-admin install, uninstall, RHEL 8 test), performance pass, final licence/SBOM review.
Acceptance: all three reference projects produce golden reports (`tests/golden/test_golden_reference_projects.py`); wizard timed test (`tests/gui/test_guided.py`); clean-machine install checklist (`docs/INSTALL_CHECKLIST.md`: the automated parts run in CI, the manual sign-off is the owner's). Decisions D-084 to D-091.

## Critical path / external inputs
Scope changes: mass, CG, inertia and phases are in v1 and sit in M2b (D-033); thermal dissipation, limits and the steady-state node model are in v1 as M4b (D-036).
SpaceMissionStudio sample exports (M3); margin policy and Eb/N0/attenuation sources (before M2/M5 reports are meaningful, not blocking development); confirmation of repository privacy and branch protection (M0).

Next: [Changelog](../CHANGELOG.md) · [Architecture](ARCHITECTURE.md) · [Docs index](README.md).
