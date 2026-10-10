# Describe the spacecraft

This page shows how to put the spacecraft into the project: its buses and phases, its units with their power modes, and the spacecraft modes that say what every unit is doing.

**Contents:** [Buses, phases, body frame](#how-do-i-set-the-buses-mission-phases-and-body-frame) · [A unit](#how-do-i-add-a-unit) · [Units in numbers](#how-do-i-write-units) · [A spacecraft mode](#how-do-i-add-a-spacecraft-mode) · [The table editor](#how-do-i-edit-power-modes-in-a-table)

## How do I set the buses, mission phases and body frame?

These live in `spacecraft.yaml`:

```yaml
schema_version: 1
kind: spacecraft
name: CubeSat 3U
buses:
  - name: main
    nominal_voltage_v: 5.0
mission_phases:
  - launch
  - eol
body_frame: 'Right-handed body frame. Origin: centre of the launch-vehicle interface plane. +Z: along the launch axis, away from the interface. X and Y: in the interface plane. Positions are item centres of mass in metres.'
```

- A [**bus**](../glossary.md#bus) is a power supply line; each unit names the bus it draws from.
- [**Mission phases**](../glossary.md#mission-phase) are names you choose (for example `launch`, `bol`, `eol`). None are assumed. They select the mass in [the mass budget](mass-budget.md) and the allowed depth of discharge in [the power budget](power-budget.md).
- The **body frame** is described in words, once: positions in the project mean the same axes and origin everywhere.

## How do I add a unit?

A *unit* is one piece of equipment (the on-board computer, a radio, a camera). Create `units/<id>.yaml`; the file name (without `.yaml`) is the unit's id, used everywhere else:

```yaml
schema_version: 2
kind: unit
name: UHF/VHF radio
subsystem: TTC
mass_kg: 0.09
bus: main
maturity: class_b
modes:
  - name: off
    avg_power_w: 0.0
    peak_power_w: 0.0
  - name: downlink
    avg_power_w: 1.8
    peak_power_w: 4.0
    duty_cycle_ratio: 0.5
    heat_dissipation_ratio: 0.7
```

| Field | Meaning |
|---|---|
| `subsystem` | A label you choose; the budgets roll up by it. |
| `mass_kg` | Mass of the unit. |
| `bus` | A bus from `spacecraft.yaml`. |
| `maturity` | A [**maturity class**](../glossary.md#maturity-class) from the margin policy (`class_a`, …). It selects the margin added to this unit's power and mass. |
| `modes` | The unit's [**power modes**](../glossary.md#power-mode). Each has an average power, a peak power (not below the average), an optional [duty cycle](../glossary.md#duty-cycle) (0 to 1, default 1) and, for the thermal budget, the share of the power that becomes heat. |

Effective average power is `avg_power_w × duty_cycle_ratio`. Optional extras: `mass_properties` (position and inertia, for the [mass budget](mass-budget.md)), `temperature_limits` and `thermal_node` (for the [thermal budget](thermal-budget.md)). Everything is listed in the [file format](../FILE_FORMAT.md).

## How do I write units?

The unit is part of the field name: `avg_power_w` is in watts, `freq_hz` in hertz, `gain_dbi` in dBi. You can write the value with a unit and the tool converts it:

```yaml
mass_kg: 200 g          # saved as 0.2
frequency_hz: 2.2 GHz
```

The tool never converts a logarithmic unit to a linear one for you: `3 dBW` in a field that is in watts is an error (`UNIT_INVALID`), because that is the classic spreadsheet mistake this tool exists to prevent.

## How do I add a spacecraft mode?

A [**spacecraft mode**](../glossary.md#spacecraft-mode) (safe, nominal, imaging, downlink, charging) says which power mode each unit is in. Create `modes/<id>.yaml`:

```yaml
schema_version: 1
kind: spacecraft_mode
name: Downlink
description: Radio transmitting.
assignments:
  adcs: downlink
  camera: off
  obc: downlink
  radio: downlink
```

Keys are unit ids, values are power-mode names of that unit. Every unit must appear in every spacecraft mode, otherwise you get `UNIT_NOT_MAPPED` naming the unit. A scenario then says [which spacecraft mode is active when](scenarios.md).

## How do I edit power modes in a table?

In the window, select a unit in the project tree and choose **File → Edit unit power modes** (Ctrl+M), or double-click the unit. You get a table with one row per power mode; typing a value with a unit works there too. **Ctrl+S** saves.

Next: [Placeholders and sources](placeholders-and-sources.md), then the [power budget](power-budget.md).
