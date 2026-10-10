# Read and fix problems

This page explains the messages the tool prints (the **Problems**), how to find the cause, and what to do about the common ones.

**Contents:** [Anatomy](#what-is-in-a-problem-message) · [Severity](#what-do-error-warning-and-info-mean) · [Jump to the cause](#how-do-i-jump-to-the-cause) · [Common problems](#common-problems-and-fixes) · [All codes](#where-are-all-the-codes)

## What is in a problem message?

```text
config/margin_policy.yaml:6: warning CONFIG_PLACEHOLDER: This number is a placeholder (no value or source 'TBD'); results that use it are not trustworthy. (at classes.class_a.power_margin_ratio)
    Replace it with a value from your margin policy, standard or data sheet and cite the source.
```

`file:line` → `severity` → `CODE` → what is wrong → `(at field)` → the hint on the next line. Messages name the **file and field**, never the value read from your files (a rule of the tool: project data may be sensitive), so look at the named field.

## What do error, warning and info mean?

| Severity | Meaning | Effect |
|---|---|---|
| **error** | The project is invalid, or a result broke a limit | The command exits with code 1. Invalid input stops the budget; a *finding* (peak power above the limit, mass above its limit…) is a computed result. |
| **warning** | Something is open or suspicious: a placeholder, an empty table, a unit without temperature limits | Exit code 0, unless you pass `--strict` (then 1). |
| **info** | For your information, such as `FILE_MIGRATED` | None. |

## How do I jump to the cause?

In the window, double-click a row of the **Problems** panel at the bottom: the file opens at the line. On the command line, open the named file and go to the line or field.

## Common problems and fixes

| You see | Why | Do this |
|---|---|---|
| `CONFIG_PLACEHOLDER`, `RESULT_INCOMPLETE`, the INCOMPLETE banner, `n/a` | A number the tool needs is `TBD` or missing | Supply the number with its source: [placeholders](placeholders-and-sources.md) |
| `FILE_NOT_FOUND` | A path is wrong, or the folder is not a project (no `project.yaml`) | Check the path; a project folder contains `project.yaml` |
| `YAML_SYNTAX` | A file cannot be parsed | Open it at the line shown; check indentation (spaces, not tabs) and colons |
| `FIELD_UNKNOWN` | A field name is misspelled or does not exist | Compare with the [file format](../FILE_FORMAT.md) |
| `UNIT_INVALID` | A unit is unknown, or of the wrong kind (a `dBW` in a watt field) | Write a plain number in the field's unit, or a value with a matching unit such as `2.5 W` |
| `UNIT_NOT_MAPPED` | A unit is missing from a spacecraft mode | Add it under `assignments` in `modes/<id>.yaml` |
| `REF_UNKNOWN_*` | A name points at something that does not exist (bus, maturity class, unit, phase, station, orbit, mode) | Fix the spelling, or create the file |
| `SOURCE_MISSING` | A sourced number has no `source` | Write the source, or `TBD` |
| `SCHEMA_TOO_NEW` | The file was written by a newer version of the tool | Upgrade the tool |
| `PEAK_POWER_EXCEEDED`, `BATTERY_DOD_EXCEEDED`, `BATTERY_DEPLETED`, `ORBIT_BALANCE_NEGATIVE` | The power timeline found a violation | [Power budget](power-budget.md#what-are-the-violations) |
| `MASS_LIMIT_EXCEEDED`, `MASS_PROPS_MISSING` | Mass above a limit; or an item without a position is left out of the centre of gravity | [Mass budget](mass-budget.md) |
| `THERMAL_LIMIT_EXCEEDED`, `THERMAL_MARGIN_INSUFFICIENT`, `THERMAL_SOLVE_FAILED` | A unit is outside, or too close to, its limits; or a node has no path to space | [Thermal budget](thermal-budget.md#how-do-i-check-unit-temperature-limits) |
| `LINK_NOT_CLOSED`, `LINK_SITE_NOT_IN_SCENARIO` | No data rate closes; or the link's station is not in the scenario's `sites` | [Link budget](link-budget.md) |
| `ENV_INPUT_INVALID`, `ENV_PROPAGATION_FAILED`, `SCENARIO_UNKNOWN` | An imported file is invalid; the orbit cannot be propagated; or no such scenario | [Scenarios](scenarios.md) |
| `INTERNAL_ERROR` | An unexpected error (a bug). The message names only the kind of error | Run `budget validate` on the folder to see the details, then report it |

## Where are all the codes?

The user guide chapter *Problems and what to do* ([source](../../src/budget_core/guide/chapters/11-troubleshooting.md)) lists every code with what to do, and the [file format](../FILE_FORMAT.md#problem-codes-budget-validate) lists them by when they occur. Problems with installing or starting the tool are in [troubleshooting](../troubleshooting.md).

Next: [Use the window](use-the-window.md) · [Command-line reference](command-line.md).
