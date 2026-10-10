"""Current schema version of every file kind. Bump with a migration (see io/migrations.py)."""

CURRENT_VERSIONS: dict[str, int] = {
    "project": 1,
    "spacecraft": 1,
    "unit": 2,
    "expendable": 1,
    "orbit": 1,
    "ground_station": 1,
    "target": 1,
    "scenario": 2,
    "link": 1,
    "spacecraft_mode": 1,
    "margin_policy": 2,
    "power_config": 1,
    "power_system": 1,
    "thermal_model": 1,
    "thermal_environment": 1,
    "mass_limits": 1,
    "ebn0_table": 1,
    "attenuation_table": 1,
}
