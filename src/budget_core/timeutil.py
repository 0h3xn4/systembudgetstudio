"""UTC time strings: ISO 8601 without a UTC offset other than Z (project files use UTC only)."""

from __future__ import annotations

from datetime import UTC, datetime


def parse_utc(text: str) -> datetime:
    """Parse "2026-01-02T03:04:05Z" (also with a space instead of T, or fractional seconds)."""
    cleaned = text.strip().replace(" ", "T", 1)
    if cleaned.endswith(("Z", "z")):
        cleaned = cleaned[:-1]
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        raise ValueError("expected a UTC time such as 2026-01-02T03:04:05Z") from None
    if parsed.tzinfo is not None:
        raise ValueError("times are UTC; write them with a trailing Z and no offset")
    return parsed.replace(tzinfo=UTC)


def format_utc(moment: datetime) -> str:
    utc = moment.astimezone(UTC)
    text = utc.strftime("%Y-%m-%dT%H:%M:%S")
    if utc.microsecond:
        text += f".{utc.microsecond:06d}".rstrip("0")
    return text + "Z"


def normalise_utc(text: str) -> str:
    return format_utc(parse_utc(text))
