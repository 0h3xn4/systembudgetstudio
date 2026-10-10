# Introduction

System Budget Studio computes power, mass, thermal and RF link budgets for a spacecraft from one model of the spacecraft kept in plain files. It runs on your own computer. Nothing is sent anywhere: there are no cloud services, no telemetry, no update checks and no online help.

## What you get

- **Power budget**: average and peak power per spacecraft mode, with unit and system margins, converter and distribution losses, and a time-domain budget over a scenario (solar array, battery, depth of discharge, orbit balance, peak power).
- **Mass budget**: mass with maturity margins, centre of gravity and inertia, per mission phase, checked against mass limits.
- **Thermal budget**: heat dissipation by unit, subsystem, node and mode, and a steady-state node model with hot and cold cases checked against unit temperature limits.
- **Link budget**: EIRP, path loss, G/T, C/N0, Eb/N0 and margin in a table at chosen elevations, and over every ground-station pass with the margin-constrained data rate and the data volume per pass and per day.
- **Reports and exports** in XLSX, PDF and DOCX, plus CSV for every table and time series and JSON for other tools.
- **Comparison** of two project revisions, or two scenarios, with the differences highlighted.

## Principles you can rely on

- **No invented numbers.** The tool ships no standards values. Every number in your configuration is written as a value with a `source`. A value with `source: TBD` (or no value) is a *placeholder*: results that depend on it are shown as **n/a** and the report carries an **INCOMPLETE** banner. A missing input is never turned into a silent zero.
- **Units are in the names.** A field called `power_w` is in watts, `freq_hz` in hertz, `gain_dbi` in dBi. You may type `2.2 GHz` or `200 g`; the tool converts and stores the canonical unit.
- **Same input, same output.** Reports and exports are reproducible: the same project, scenario, user name and generation time give the same files.
- **Provenance on every output.** Each report, plot and CSV records the tool version, library versions, project revision, scenario, generation time and the user's name.
- **Plain-language problems.** The Problems panel and the command line name the file and field, say what is wrong and what to change. Messages never repeat values read from your project files.

> The example projects delivered with the tool contain invented data only. Their numbers are not those of a real spacecraft or a real standard.
