"""SQLite returns timezone-less dates; persisted dates represent UTC."""

from datetime import UTC, datetime


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
