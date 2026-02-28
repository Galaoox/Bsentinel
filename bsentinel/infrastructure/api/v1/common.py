"""Shared helpers for v1 API routers."""

from __future__ import annotations

from datetime import UTC, date, datetime, time


def to_datetime(day: date | None, end_of_day: bool = False) -> datetime | None:
    """Convert a date into an UTC datetime boundary."""
    if not day:
        return None
    clock = time.max if end_of_day else time.min
    return datetime.combine(day, clock).replace(tzinfo=UTC)
