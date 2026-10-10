"""Unit-suffix convention and quantity parsing.

Field names end in a unit suffix (``avg_power_w``, ``freq_hz``, ``gain_dbi``). Values are stored
in the canonical unit of that suffix. At the file/GUI boundary a value may be written with a unit
("2.2 GHz"); `parse_quantity` converts it using pint. Logarithmic units are handled here, not by
pint, and are never converted to or from linear units implicitly (W versus dBW is an error).
Error messages never contain the offending input value.
"""

from __future__ import annotations

import functools
import math
import re
from dataclasses import dataclass
from typing import Any


class UnitError(ValueError):
    """Raised with a plain-language message when a quantity cannot be parsed."""


@dataclass(frozen=True)
class _Suffix:
    label: str  # canonical unit label shown to users
    dimension: str  # human name of the quantity
    pint_unit: str | None  # None for logarithmic and dimensionless suffixes


_SUFFIXES: dict[str, _Suffix] = {
    "w": _Suffix("W", "power", "watt"),
    "wh": _Suffix("Wh", "energy", "watt_hour"),
    "hz": _Suffix("Hz", "frequency", "hertz"),
    "kg": _Suffix("kg", "mass", "kilogram"),
    "kgm2": _Suffix("kg m2", "moment of inertia", "kilogram * meter ** 2"),
    "m": _Suffix("m", "length", "meter"),
    "s": _Suffix("s", "time", "second"),
    "k": _Suffix("K", "temperature", "kelvin"),
    "perk": _Suffix("1/K", "temperature coefficient", "1 / kelvin"),
    "wk": _Suffix("W/K", "thermal conductance", "watt / kelvin"),
    "jperk": _Suffix("J/K", "heat capacity", "joule / kelvin"),
    "m2": _Suffix("m2", "area", "meter ** 2"),
    "wm2": _Suffix("W/m2", "irradiance", "watt / meter ** 2"),
    "ah": _Suffix("Ah", "electric charge", "ampere_hour"),
    "yr": _Suffix("yr", "duration in years", "year"),
    "deg": _Suffix("deg", "angle", "degree"),
    "v": _Suffix("V", "voltage", "volt"),
    "a": _Suffix("A", "current", "ampere"),
    "bps": _Suffix("bit/s", "data rate", "bit / second"),
    "bit": _Suffix("bit", "data volume", "bit"),
    "ratio": _Suffix("ratio", "dimensionless ratio", None),
    "db": _Suffix("dB", "logarithmic ratio", None),
    "dbi": _Suffix("dBi", "antenna gain", None),
    "dbw": _Suffix("dBW", "logarithmic power", None),
    "dbm": _Suffix("dBm", "logarithmic power", None),
    "dbk": _Suffix("dB/K", "receiver figure of merit (G/T)", None),
}

# Logarithmic suffix -> accepted unit tokens (lower case) and their offset to the canonical unit.
_LOG_TOKENS: dict[str, dict[str, float]] = {
    "db": {"db": 0.0},
    "dbi": {"dbi": 0.0},
    "dbw": {"dbw": 0.0, "dbm": -30.0},
    "dbm": {"dbm": 0.0, "dbw": 30.0},
    "dbk": {"dbk": 0.0, "db/k": 0.0},
}
_ALL_LOG_TOKENS = {"db", "dbi", "dbw", "dbm", "dbhz", "dbk", "db/k", "dbc"}

# Largest magnitude accepted in any unit-suffixed field (in the canonical unit). Far beyond every
# physical quantity this tool handles, but small enough that squares and products cannot overflow.
MAX_MAGNITUDE = 1.0e20

# A unit token is handed to pint's expression parser, which evaluates arithmetic: "(9**9**9)" would
# never finish. Only plain unit names with simple exponents are passed on.
_TOKEN_CHARS = re.compile(r"^[A-Za-z0-9_\u00b0\u00b5\u03bc\u03a9%/ ^*.\u00b7\-]{1,32}$")
_EXPONENT = re.compile(r"(?:\*\*|\^)\s*-?\d{1,2}(?!\d)")
_CHAINED = re.compile(r"(?:\*\*|\^)\s*-?\d+\s*(?:\*\*|\^)")


def _token_ok(token: str) -> bool:
    if not _TOKEN_CHARS.match(token) or _CHAINED.search(token):
        return False
    rest = _EXPONENT.sub("", token)
    return "**" not in rest and "^" not in rest


_NUMBER = re.compile(
    r"^\s*([+-]?(?:nan|inf(?:inity)?|\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?))\s*(.*?)\s*$",
    re.IGNORECASE,
)


def _suffix_of(field: str) -> tuple[str, _Suffix] | None:
    if "_" not in field:
        return None
    key = field.rsplit("_", 1)[1]
    info = _SUFFIXES.get(key)
    return (key, info) if info else None


def has_unit_suffix(field: str) -> bool:
    return _suffix_of(field) is not None


def canonical_unit(field: str) -> str | None:
    """Label of the canonical unit for a field name, or None when the name has no unit suffix."""
    found = _suffix_of(field)
    return found[1].label if found else None


@functools.cache
def _registry() -> Any:
    import pint

    return pint.UnitRegistry(cache_folder=None)


def parse_quantity(text: str, field: str) -> float:
    """Parse "<number> <unit>" for the field's suffix and return the canonical-unit value."""
    found = _suffix_of(field)
    if found is None:
        raise UnitError(
            "this field name has no known unit suffix, so a value with a unit cannot be read; "
            "write the plain number in the canonical unit"
        )
    key, info = found
    match = _NUMBER.match(text)
    if match is None:
        raise UnitError(f"expected a number followed by a unit such as '{_example(key)}'")
    number = float(match.group(1))
    if not math.isfinite(number):
        raise UnitError("the value must be a finite number")
    token = match.group(2)
    if token and not _token_ok(token):
        raise UnitError("the unit is not recognised; write a plain unit name such as 'kW' or 'm^2'")

    if key in _LOG_TOKENS:
        result = number + _log_offset(key, info, token)
    elif key == "ratio":
        result = _ratio(number, token)
    else:
        result = _linear(number, token, key, info)
    if abs(result) > MAX_MAGNITUDE:
        raise UnitError("the value is far outside any physical range")
    return result


def _example(key: str) -> str:
    return {"w": "2.5 W", "hz": "2.2 GHz", "kg": "1.5 kg", "s": "35 min"}.get(
        key, f"1 {_SUFFIXES[key].label}"
    )


def _log_offset(key: str, info: _Suffix, token: str) -> float:
    lowered = token.lower()
    accepted = _LOG_TOKENS[key]
    if lowered in accepted:
        return accepted[lowered]
    if lowered in _ALL_LOG_TOKENS:
        raise UnitError(f"this field expects {info.label}, but the value is given in {token}")
    raise UnitError(
        f"this field expects {info.label} (a logarithmic unit); a linear or missing unit "
        "is not converted implicitly, convert the value to dB first"
    )


def _ratio(number: float, token: str) -> float:
    if token in ("", "ratio"):
        return number
    if token == "%":
        return number / 100.0
    raise UnitError("this field is a dimensionless ratio; use a plain number or a percentage")


def _linear(number: float, token: str, key: str, info: _Suffix) -> float:
    if token == "":
        raise UnitError(
            f"a unit is missing; this field is a {info.dimension}, e.g. '{_example(key)}'"
        )
    if token.lower() in _ALL_LOG_TOKENS:
        raise UnitError(
            f"this field is a linear {info.dimension} in {info.label}; a logarithmic unit "
            f"({token}) is not converted implicitly"
        )
    import pint

    ureg = _registry()
    try:
        quantity = ureg.Quantity(number, token)
    except pint.errors.PintError as exc:
        raise UnitError("the unit is not recognised") from exc
    except Exception as exc:  # pint can raise AttributeError/TypeError for odd tokens
        raise UnitError("the unit is not recognised") from exc
    try:
        value = float(quantity.to(info.pint_unit).magnitude)
    except pint.errors.PintError as exc:
        raise UnitError(
            f"the unit is not a {info.dimension} unit; this field is a {info.dimension} "
            f"in {info.label}"
        ) from exc
    if not math.isfinite(value):
        raise UnitError("the converted value is not finite")
    return value


def format_quantity(value: float, field: str) -> str:
    """Inverse of parse_quantity for the canonical unit (used for display and round trips)."""
    found = _suffix_of(field)
    if found is None:
        raise UnitError("this field name has no known unit suffix")
    key, info = found
    if key == "ratio":
        return repr(float(value))
    return f"{float(value)!r} {info.label}"
