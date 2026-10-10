# Power budget

## Static budget

Each unit has power modes with an average power `avg_power_w`, a peak power `peak_power_w` and an optional `duty_cycle_ratio` (default 1). A spacecraft mode names the power mode each unit is in.

For every spacecraft mode the tool computes, in this order:

1. effective average power of each unit = average power x duty cycle;
2. the unit's maturity margin (from `config/margin_policy.yaml`);
3. the system margin on the sum;
4. the power at the source, after converter efficiency per bus and the distribution loss.

Peak power is the sum of unit peak powers. The report shows the result by mode, by subsystem and by bus, with the equations and the sources of all configuration numbers on the last sheets.

## Time-domain budget

Add `config/power_system.yaml` (solar array faces, battery, attitude per mode, peak power limit) and a scenario. **Power timeline > Compute** steps through the scenario on its time grid and, for both beginning of life (BOL) and end of life (EOL):

- array output from the Sun direction, the eclipse and the array temperature and degradation;
- the battery energy with charge and discharge efficiency and capacity fade;
- the state of charge, depth of discharge, and the energy balance over each complete orbit.

Findings that fail the command (exit code 1) are `PEAK_POWER_EXCEEDED`, `BATTERY_DEPLETED`, `BATTERY_DOD_EXCEEDED` and `ORBIT_BALANCE_NEGATIVE`. Each comes with its first start time, the duration and the input to change. Select a row of the violations table to zoom the plot to that interval.

## Choices you make

- **Demand basis**: nominal (default) or with unit and system margins.
- **Case**: BOL and EOL are both computed; the selector switches the display.
- **Attitude**: `sun` or `nadir` per spacecraft mode, as written in `power_system.yaml`.

> The array and battery relations are textbook formulas that the tool flags as `SOURCE_MISSING` in the Equations and sources chapter until a reference text is attached. Treat results as engineering estimates until the owner has confirmed them.
