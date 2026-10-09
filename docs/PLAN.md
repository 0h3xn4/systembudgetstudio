# System Budget Studio — Plan (proposal)

Rules for every milestone: tests first; ruff + mypy strict clean; no network; each ends with a demo note in `docs/demo/Mx.md`. Estimates are relative (S/M/L).

## M0 Foundation (M)
Scope: repo setup per SPEC §Repository setup; Carbon-styled empty window ("System Budget Studio"); PyInstaller build of the empty app on Windows and Linux; offline test; lock files; CI.
Acceptance: (1) `pip install -e .` launches the empty window; (2) `pip install -e ".[dev]" && pytest` passes; (3) setup PR green on {win, linux}×{3.11, 3.13}; (4) offline test fails when a socket is opened (negative test proves it); (5) installer/portable build launches on a clean machine without admin rights; (6) SBOM and licence report generated from the dev extra only; (7) `pip install -e .` pulls no dev tooling.
Needs from you: confirm repo is private; apply branch protection (list provided).

## M1 Model and units (M)
Scope: pydantic models, YAML IO, schema versions + migration framework (with a v1→v2 test migration), unit parsing/dB helpers, config files with `source` + JSON Schemas (margin policy, Eb/N0, attenuation, array, battery, converters — all placeholders), `Problem` type, `budget validate`, three reference projects' skeletons.
Acceptance: invalid/missing/newer-schema files give located, plain-language problems; placeholders raise `CONFIG_PLACEHOLDER`; round-trip load→save is byte-identical; Hypothesis unit round-trips pass.

## M2 Static power budget (M)
Scope: static per-mode table with maturity margins and converter losses; Problems panel (GUI, wired to validate); table editors for units/modes; XLSX and PDF reports with provenance and assumptions list; reproducible-output mode.
Acceptance: ≥10 hand-calculated cases pass; XLSX/PDF golden tests byte-identical on re-run; GUI flow: open example → edit unit → Problems update → export.

## M3 Environment (L)
Scope: `Environment` interface; `ElementsPropagator` (TLE/Keplerian, shadow model, passes); `SpaceMissionStudioImport` (needs sample files); scenario model, rule-based generation (downlink on pass); timeline editor.
Acceptance: eclipse fraction and pass count/duration for textbook circular LEO cases match hand calculation within stated tolerance; adapters interchangeable behind the interface in solver tests; timeline editor creates/edits/validates scenarios.
Needs from you: SpaceMissionStudio sample export files.

## M4 Time-domain power budget (L)
Scope: array and battery models, converter/distribution losses, SoC integration, violations with timestamps, result plots with eclipse/pass shading and cursors, CSV/JSON export, worker-thread runs, DOCX report.
Acceptance: ≥10 regression cases (e.g. orbit-average balance with known eclipse fraction); monotonic properties pass; 1-week/1 s stress case < 10 s; GUI responsive during run; violations jump to inputs.

## M5 Link budget (L)
Scope: link models (uplink/downlink, multiple links), static table at chosen elevation/range, pass time series, margin-constrained data rate and data volume per pass/day, attenuation tables from config (empty until supplied), link reports.
Acceptance: textbook S-band 2 GHz/1000 km case within tolerance, ≥10 cases; margin monotonic in range; golden reports for micro-sat with two links.

## M6 Polish (M)
Scope: comparison view (scenarios/revisions), guided wizard (orbit → first budget < 10 min on sample), user guide with generated "Equations and sources" chapter (offline HTML + PDF), installer hardening (no-admin install, uninstall, RHEL 8 test), performance pass, final licence/SBOM review.
Acceptance: all three reference projects produce golden reports; wizard timed test; clean-machine install checklist signed off.

## Critical path / external inputs
SpaceMissionStudio sample exports (M3); margin policy and Eb/N0/attenuation sources (before M2/M5 reports are meaningful, not blocking development); confirmation of repository privacy and branch protection (M0).
