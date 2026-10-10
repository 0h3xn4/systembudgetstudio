"""CSV writing that cannot be turned into a formula when opened in a spreadsheet."""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from typing import Any

DANGEROUS_START = ("=", "+", "-", "@", "\t", "\r")
# "-0.5", "+3", "1e-9", and a number with a short unit as the tool writes it: "+2.500 W", "+20.0 %"
_NUMBER = re.compile(
    r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?(?: ?[A-Za-z%][A-Za-z%/^0-9.]{0,11})?$"
)


def _is_number(text: str) -> bool:
    return _NUMBER.match(text) is not None


def defuse(value: Any) -> Any:
    """Prefix text that a spreadsheet would run as a formula with an apostrophe. Numbers written
    as text ("-0.5", "+3", "1e-9") are left alone."""
    if isinstance(value, str) and value.startswith(DANGEROUS_START) and not _is_number(value):
        return "'" + value
    return value


class _Writer:
    def __init__(self, handle: Any) -> None:
        self._writer = csv.writer(handle, lineterminator="\n")

    def writerow(self, row: Iterable[Any]) -> None:
        self._writer.writerow([defuse(v) for v in row])

    def writerows(self, rows: Iterable[Iterable[Any]]) -> None:
        for row in rows:
            self.writerow(row)


def csv_writer(handle: Any) -> _Writer:
    return _Writer(handle)
