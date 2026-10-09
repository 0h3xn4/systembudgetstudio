"""Base model: strict, frozen, unit-aware. All project and config models derive from it."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from pydantic_core import PydanticCustomError

from budget_core.units.quantity import UnitError, has_unit_suffix, parse_quantity


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
        if has_unit_suffix(name) and isinstance(value, str):
            try:
                return parse_quantity(value, name)
            except UnitError as exc:
                raise PydanticCustomError(
                    "unit_invalid", "{reason}", {"reason": str(exc)}
                ) from None
        return value


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
