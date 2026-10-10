# Power budget

This page shows how to get the power needed in each spacecraft mode (static budget), and how to check the solar array and battery over an orbit (time-domain budget).

**Contents:** [Static budget](#how-do-i-get-the-power-per-mode) · [Time-domain budget](#how-do-i-check-the-solar-array-and-battery-over-an-orbit) · [Read the result](#how-do-i-read-the-result) · [Violations](#what-are-the-violations)

## How do I get the power per mode?

Inputs: units with power modes, spacecraft modes, `config/margin_policy.yaml`, `config/power_config.yaml` ([describe the spacecraft](describe-the-spacecraft.md)).

```bash
budget run my_satellite --budget power --out out
```

For every spacecraft mode the tool computes, in this order:

1. each unit's effective average power = average power × duty cycle;
2. the unit's [**maturity margin**](../glossary.md#maturity-class) (from the margin policy);
3. the [**system margin**](../glossary.md#system-margin) on the sum;
4. the power at the source, after the [**converter efficiency**](../glossary.md#converter-efficiency) of each bus and the **distribution loss**.

The [peak power](../glossary.md#peak-power) is the sum of the unit peak powers. The report (`power_static.xlsx`, PDF, DOCX, JSON, one CSV per mode) shows the result by mode, by subsystem and by bus. In the window it is the **Power budget** tab.

## How do I check the solar array and battery over an orbit?

You need three more things: `config/power_system.yaml` (solar array faces, battery, attitude per mode, peak power limit, design life), a [scenario](scenarios.md) with an orbit, and a mission phase for the allowed [depth of discharge](../glossary.md#dod) (`mission_phase` in the scenario, or `--phase`).

```bash
budget power-timeline my_satellite --out out
```

Options you will use: `--scenario <id>` (if the project has several), `--case bol|eol|both`, `--load-basis nominal|margined`, `--phase <name>`, `--series-every N` (thin the CSV series), `--no-plots`. In the window use the **Power timeline** tab and click **Compute**.

The tool steps through the scenario on its time grid and, for [**beginning of life** (BOL) and **end of life** (EOL)](../glossary.md#bol-eol):

- computes array output from the Sun direction on each face, the eclipse, the array temperature and its degradation;
- integrates the battery energy with charge and discharge efficiency and capacity fade;
- reports the [state of charge](../glossary.md#soc), depth of discharge and the [energy balance](../glossary.md#orbit-balance) over each complete orbit.

Pointing is `sun` (the Sun is at a fixed direction in the body frame) or `nadir` per spacecraft mode, set in `power_system.yaml` (`attitude`).

## How do I read the result?

```text
BOL: generated 99.7 Wh, lowest state of charge 89.3 %, 0 violation(s).
EOL: generated 93.8 Wh, lowest state of charge 89.0 %, 0 violation(s).
```

In the window: the top plot shows generation, demand at the source and the peak limit; then state of charge; then the margin (generation minus demand). Shaded bands are eclipses and passes. The tables below give a **Summary** per case, the **Violations**, one row per **Orbit**, and the **Modes** with their loads.

## What are the violations?

| Code | Meaning |
|---|---|
| `PEAK_POWER_EXCEEDED` | The demand at the source is above `limits.peak_power_w`. |
| `BATTERY_DOD_EXCEEDED` | The depth of discharge went above the allowed value of the mission phase. |
| `BATTERY_DEPLETED` | The battery was empty and demand was not met. |
| `ORBIT_BALANCE_NEGATIVE` | Over a complete orbit the array generated less energy than was demanded. |

Each finding has a start time, end time, worst value, limit, and the file and field to change. Findings make the command exit with code 1. Select a row in the Violations table to zoom the plot to that interval. The first minutes of [getting started](../getting-started.md#5-a-first-worked-example-find-and-fix-a-power-violation) walk through one.

The results do not depend on the time step: eclipses and mode changes are overlapped with the steps exactly, and the battery is solved on the steps cut at every eclipse edge and mode change ([decision D-097](../DECISIONS.md)).

> The array and battery relations are textbook formulas that the tool flags `SOURCE_MISSING` in the *Equations and sources* chapter until a reference is attached. Perfect pointing, no albedo and one array temperature are simplifications; see the [deviations](../DEVIATIONS.md).

Next: [Mass budget](mass-budget.md) · [Scenarios](scenarios.md).
