"""Base model: strict, frozen, unit-aware. All project and config models derive from it."""

from __future__ import annotations

from typing import Any, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from pydantic_core import PydanticCustomError

from budget_core.units.quantity import MAX_MAGNITUDE, UnitError, has_unit_suffix, parse_quantity


class BudgetModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    @field_validator("*", mode="before")
    @classmethod
    def _parse_units(cls, value: Any, info: ValidationInfo) -> Any:
        """Accept "2.2 GHz" for fields whose name carries a unit suffix; reject booleans."""
        name = info.field_name or ""
        numeric = has_unit_suffix(name) or name == "value"
        if numeric and isinstance(value, bool):
            raise PydanticCustomError("unit_invalid", "expected a number, not a yes/no value")
        if numeric:
            _check_magnitude(value)
        if not has_unit_suffix(name):
            return value
        if isinstance(value, str):
            return _parse(value, name)
        if not _holds_numbers(cls.model_fields[name].annotation):
            return value  # e.g. a nested model such as Sourced: its own fields parse themselves
        if isinstance(value, list):
            return [_parse(v, name) if isinstance(v, str) else v for v in value]
        if isinstance(value, dict):
            return {k: _parse(v, name) if isinstance(v, str) else v for k, v in value.items()}
        return value


def _check_magnitude(value: Any) -> None:
    """Reject numbers so large that products or squares overflow to infinity later on."""
    items = (
        value
        if isinstance(value, list)
        else list(value.values())
        if isinstance(value, dict)
        else [value]
    )
    for item in items:
        if (
            isinstance(item, int | float)
            and not isinstance(item, bool)
            and abs(item) > MAX_MAGNITUDE
        ):
            raise PydanticCustomError("value_range", "the value is far outside any physical range")


def _holds_numbers(annotation: Any) -> bool:
    """True for list[float] and dict[str, float] (the containers whose items carry the unit)."""
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is list:
        return args == (float,)
    if origin is dict:
        return len(args) == 2 and args[1] is float
    return False


def _parse(text: str, name: str) -> float:
    try:
        return parse_quantity(text, name)
    except UnitError as exc:
        raise PydanticCustomError("unit_invalid", "{reason}", {"reason": str(exc)}) from None


def duplicate_names(names: list[str]) -> bool:
    return len(set(names)) != len(names)


class Sourced(BudgetModel):
    """A number from a standard, policy or data sheet. `source: TBD` or a null value marks a
    placeholder that must be replaced before results are trusted (spec constraint 15)."""

    value: float | None
    source: str = Field(min_length=1)
    note: str = ""

    @property
    def is_placeholder(self) -> bool:
        return self.value is None or self.source.strip().upper() == "TBD"
