# Project file format

A project is a folder of YAML files (LF line endings). Every file starts with `schema_version` and `kind`. All kinds are at schema version 1 except `margin_policy` and `scenario` (version 2, see below).

```
project.yaml            kind: project            name, revision, description
spacecraft.yaml         kind: spacecraft         name, buses[{name, nominal_voltage_v}], mission_phases[], body_frame
units/<id>.yaml         kind: unit               name, subsystem, mass_kg, bus, maturity, modes[], mass_properties?, phases[]?
orbits/<id>.yaml         kind: orbit              name, tle[2] or elements{...}   (see ENVIRONMENT_FORMAT.md)
ground_stations/<id>.yaml kind: ground_station   name, latitude_deg, longitude_deg, altitude_m, min_elevation_deg
targets/<id>.yaml       kind: target             same fields as a ground station (imaging target)
scenarios/<id>.yaml     kind: scenario (v2)      orbit, start_utc, duration_s, step_s, sites, mission_phase?, default_mode, rules[], segments[]
expendables/<id>.yaml   kind: expendable         name, subsystem, maturity, masses_kg{phase: kg}, mass_properties?
modes/<id>.yaml         kind: spacecraft_mode    name, description, assignments{unit id: power mode name}
config/margin_policy.yaml      kind: margin_policy (v2)  classes{name: {power_margin_ratio, mass_margin_ratio}}, system_power_margin_ratio, system_mass_margin_ratio
config/mass_limits.yaml        kind: mass_limits         limits[{name, phase?, limit_kg}]
config/power_config.yaml       kind: power_config        distribution_loss_ratio, converter_efficiency_ratio{bus}
config/power_system.yaml       kind: power_system        design_life_yr, solar_array{faces[], ...}, battery{...}, attitude{...}, limits{peak_power_w}   (optional)
config/ebn0_table.yaml         kind: ebn0_table          entries[{modulation, coding, required_ebn0_db}]
config/attenuation_table.yaml  kind: attenuation_table   entries[{name, attenuation_kind, freq_hz, elevation_deg, loss_db}]
```

Power mode: `name`, `avg_power_w`, `peak_power_w` (>= average), `duty_cycle_ratio` (0..1, default 1), optional `min_duration_s`, `max_duration_s`. Effective average power = `avg_power_w * duty_cycle_ratio` (D-024).

## Mass properties (decisions D-048 to D-050)

- One right-handed **body frame** per project, described in words in `spacecraft.yaml` (`body_frame`). Suggested: origin at the centre of the launch-vehicle interface plane, +Z along the launch axis away from the interface, X and Y in that plane. Positions are item centres of mass in metres: `mass_properties: {position_m: [x, y, z]}` (strings with units such as `"10 cm"` are accepted).
- Optional `inertia` inside `mass_properties`: `ixx_kgm2`, `iyy_kgm2`, `izz_kgm2`, `ixy_kgm2`, `ixz_kgm2`, `iyz_kgm2` about the item's own centre of mass, axes parallel to the body frame. The off-diagonal entries are **tensor elements** (minus the products of inertia). The tensor must belong to a rigid body (checked). An item without inertia is a point mass.
- `mission_phases`: ordered list of names you choose (none are assumed; without it there is one phase `all`). Units may list `phases` they are present in (default: all). Expendables give `masses_kg` for **every** phase (write `0.0` explicitly).
- Margins: item mass x (1 + `mass_margin_ratio` of its maturity class), then x (1 + `system_mass_margin_ratio`). Centre of gravity and inertia use nominal masses of items that have a position; the others are excluded and reported (`MASS_PROPS_MISSING`).
- Mass limits are checked against the system-margined total (`MASS_LIMIT_EXCEEDED` when exceeded).

## Power system (decisions D-061 to D-066)

`config/power_system.yaml` is optional; without it the static budgets work and the time-domain budget reports what is missing. Every electrical number is `{value, source, note?}` (placeholder rules as in `config/`).

```yaml
schema_version: 1
kind: power_system
design_life_yr: {value: 2.0, source: "..."}
solar_array:
  faces:                       # one entry per array panel
    - {name: plus_x, normal_body: [1, 0, 0], strings: 2, cells_per_string: 3}
  solar_irradiance_wm2: {value: ..., source: ...}
  cell_area_m2: ...            # area of one cell
  cell_efficiency_ratio: ...   # at reference_temperature_k
  reference_temperature_k: ...
  cell_temperature_k: ...      # one operating temperature for the whole array (DV-P2)
  efficiency_temp_coeff_perk: ...   # relative change per kelvin, usually negative
  packing_loss_ratio: ...
  harness_loss_ratio: ...
  annual_degradation_ratio: ...     # fraction of output lost per year
battery:
  cell_capacity_ah: ...
  cell_nominal_voltage_v: ...
  cells_in_series: 2
  cells_in_parallel: 2
  charge_efficiency_ratio: ...
  discharge_efficiency_ratio: ...
  annual_capacity_fade_ratio: ...
  initial_soc_ratio: ...
  max_dod_ratio: {launch: ..., eol: ...}     # allowed depth of discharge per mission phase
attitude:
  default: sun                  # sun or nadir; optional
  by_mode: {imaging: nadir}     # per spacecraft mode id
  sun_direction_body: [1, 0, 0] # where the Sun is in the body frame when a mode is `sun`
limits:
  peak_power_w: ...             # most power the power system can supply at the bus input
```

- `sun`: the Sun is along `sun_direction_body`. `nadir`: the body frame equals the local orbital frame (+Z to the Earth, +X along the velocity, +Y opposite the orbit normal). A face sees the Sun with the cosine of the angle between its normal and the Sun direction, zero on its back.
- The scenario's `mission_phase` selects the allowed depth of discharge; with a single mission phase it is optional.
- Results: BOL (no degradation or fade) and EOL (the design life applied). Demand is the static per-mode source power (nominal or margined) through converter and distribution losses.

## Scenario schema 2

`mission_phase` (optional) was added. Version 1 files migrate in memory unchanged (`FILE_MIGRATED`).

## Margin policy schema 2

`margin_ratio` became `power_margin_ratio` and `mass_margin_ratio` per class; `system_margin_ratio` became `system_power_margin_ratio` and `system_mass_margin_ratio`. Version 1 files migrate in memory (`FILE_MIGRATED`); the new mass values are placeholders until supplied.

Every number in `config/` is `{value, source, note?}`. `source: TBD` or `value: null` marks a placeholder and raises the warning `CONFIG_PLACEHOLDER`. Never copy standards values without a source.

Units: the field-name suffix is the unit. A value may be written with a unit (`mass_kg: 200 g`); it is saved as the canonical number. See D-025, D-026.

JSON Schemas for all kinds: `budget export-schemas <dir>` (also committed in `src/budget_core/schemas/`).

## Problem codes (`budget validate`)

Errors: `FILE_NOT_FOUND`, `FILE_INVALID`, `YAML_SYNTAX`, `KIND_MISMATCH`, `SCHEMA_VERSION_MISSING`, `SCHEMA_TOO_NEW`, `SCHEMA_MIGRATION_MISSING`, `SCHEMA_MIGRATION_FAILED`, `FIELD_MISSING`, `FIELD_UNKNOWN`, `FIELD_INVALID`, `UNIT_INVALID`, `DUPLICATE_NAME`, `SOURCE_MISSING`, `REF_UNKNOWN_BUS`, `REF_UNKNOWN_MATURITY`, `REF_UNKNOWN_UNIT`, `REF_UNKNOWN_UNIT_MODE`, `UNIT_NOT_MAPPED`.
Errors (config values): `CONFIG_VALUE_INVALID`, `REF_UNKNOWN_PHASE`, `PHASE_MASS_MISSING`.
Environment: `REF_UNKNOWN_ORBIT`, `REF_UNKNOWN_SITE`, `REF_UNKNOWN_MODE`, `DUPLICATE_ID`, `IMPORT_DIR_MISSING`, `ORBIT_INVALID` (errors at load); `SCENARIO_UNKNOWN`, `ENV_INPUT_INVALID`, `ENV_PROPAGATION_FAILED` (errors when running a scenario).
Result findings (errors): `MASS_LIMIT_EXCEEDED`; time-domain power: `BATTERY_DOD_EXCEEDED`, `BATTERY_DEPLETED`, `ORBIT_BALANCE_NEGATIVE`, `PEAK_POWER_EXCEEDED`. Warnings: `MASS_PROPS_MISSING`, `MASS_FRAME_UNDEFINED`, `RESULT_INCOMPLETE` (a result needs a placeholder number, shown as n/a), `CONFIG_MISSING`, `CONFIG_PLACEHOLDER`, `CONFIG_EMPTY_TABLE`. Info: `FILE_MIGRATED`, `MASS_INERTIA_POINT_MASS`.

## Schema versions

Older files are migrated in memory (`budget_core/io/migrations.py`, one function per version step); newer files fail with `SCHEMA_TOO_NEW`. `margin_policy` and `scenario` are at version 2; all other kinds are at version 1.
