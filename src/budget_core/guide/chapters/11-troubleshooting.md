# Problems and what to do

Every problem has a code, a file and field, a plain-language message and a hint. Values from your files are not repeated in messages; look at the named field.

## Loading a project

| Code | What to do |
|---|---|
| `FILE_NOT_FOUND`, `FILE_INVALID`, `YAML_SYNTAX` | Open the named file; the line is shown when the text cannot be parsed. |
| `KIND_MISMATCH`, `SCHEMA_VERSION_MISSING`, `SCHEMA_TOO_NEW`, `SCHEMA_MIGRATION_MISSING`, `SCHEMA_MIGRATION_FAILED` | The file is of another kind or from a newer or unsupported version. Check the first two lines. |
| `FIELD_MISSING`, `FIELD_UNKNOWN`, `FIELD_INVALID`, `UNIT_INVALID`, `DUPLICATE_NAME`, `DUPLICATE_ID` | Fix the named field: it is missing, misspelled, out of range, has an unknown unit or repeats a name. |
| `SOURCE_MISSING` | A sourced number has no `source`. Write the source, or `TBD` if you do not have it yet. |
| `REF_UNKNOWN_BUS`, `REF_UNKNOWN_MATURITY`, `REF_UNKNOWN_UNIT`, `REF_UNKNOWN_UNIT_MODE`, `UNIT_NOT_MAPPED`, `REF_UNKNOWN_PHASE`, `PHASE_MASS_MISSING` | A name points to something that does not exist, or a unit is not in a spacecraft mode. |
| `CONFIG_VALUE_INVALID`, `CONFIG_MISSING`, `CONFIG_PLACEHOLDER`, `CONFIG_EMPTY_TABLE` | A configuration number is invalid, a file is absent, a number is still a placeholder, or a table is empty. |
| `THERMAL_NODE_UNKNOWN`, `REF_UNKNOWN_CASE` | A thermal node or case name is not defined. |
| `REF_UNKNOWN_STATION`, `REF_UNKNOWN_ATTENUATION`, `REF_UNKNOWN_MODULATION`, `LINK_ANTENNA_PATTERN_GROUND`, `LINK_PATTERN_FILE_MISSING`, `LINK_INPUT_INVALID` | A link points to something missing, or a ground antenna has a pattern, or a pattern file cannot be read. |
| `REF_UNKNOWN_ORBIT`, `REF_UNKNOWN_SITE`, `REF_UNKNOWN_MODE`, `IMPORT_DIR_MISSING`, `ORBIT_INVALID` | A scenario points to an orbit, site or mode that does not exist, or the imported environment folder is missing. |
| `FILE_MIGRATED` | Information only: an older file was upgraded in memory. |

## Running

| Code | What to do |
|---|---|
| `SCENARIO_UNKNOWN`, `ENV_INPUT_INVALID`, `ENV_PROPAGATION_FAILED` | The scenario does not exist, or its orbit or time grid cannot be propagated. |
| `RESULT_INCOMPLETE` | A result needs a placeholder number and is shown as n/a. Replace the number with a sourced value. |
| `MASS_LIMIT_EXCEEDED`, `MASS_PROPS_MISSING`, `MASS_FRAME_UNDEFINED`, `MASS_INERTIA_POINT_MASS` | The mass total is above its limit, or centre of gravity or inertia inputs are missing. |
| `THERMAL_LIMIT_EXCEEDED`, `THERMAL_MARGIN_INSUFFICIENT`, `THERMAL_NO_LIMITS`, `THERMAL_SOLVE_FAILED` | A unit is outside or too close to its limits, has no limits, or the network could not be solved. |
| `PEAK_POWER_EXCEEDED`, `BATTERY_DEPLETED`, `BATTERY_DOD_EXCEEDED`, `ORBIT_BALANCE_NEGATIVE` | The time-domain power budget found a violation. Its time stamp and the input to change are listed. |
| `LINK_ATTENUATION_FREQUENCY`, `LINK_SITE_NOT_IN_SCENARIO`, `LINK_NO_STATIC_POINTS` | An attenuation entry was defined at another frequency, the link's station is not in the scenario, or the link has no static points. |
| `LINK_NOT_CLOSED` | No listed data rate meets the required margin at any static point, or at any active sample of the passes. Lower the data rates, raise the transmit power or gain, or check the losses and the required margin. |
| `INTERNAL_ERROR` | An unexpected error; the message names only its kind. Run `budget validate` on the folder to see the details, then report it. |

## The report says INCOMPLETE

At least one number it needs is a placeholder. The **Configuration numbers used** table lists every number with its source and its status. Replace each `PLACEHOLDER` with a sourced value; the banner disappears when none remain.

## The window does not start

Run `budget self-test`. It computes and renders a small budget with the installed libraries and prints what failed.
