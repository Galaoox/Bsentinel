"""Two daily Colombia windows, three stable cohorts; durable times are UTC."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

SCHEDULE_TIMEZONE = ZoneInfo('America/Bogota')
DAILY_REVIEW_COUNT = 2
SLOT_START_GRACE_SECONDS = 120
COHORT_WORK_SECONDS = 20 * 60


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("schedule requires timezone-aware timestamps")
    return value.astimezone(UTC)


def slot_at_or_after(group: int, threshold: datetime) -> datetime:
    if group not in (0, 1, 2):
        raise ValueError("scrape group must be 0, 1 or 2")
    local = _utc(threshold).astimezone(SCHEDULE_TIMEZONE)
    for day in (0, 1):
        for hour in (8, 17):
            candidate = (local + timedelta(days=day)).replace(hour=hour, minute=group * 20, second=0, microsecond=0)
            if candidate >= local:
                return candidate.astimezone(UTC)
    raise AssertionError('unreachable calendar')


def initial_check(group: int, now: datetime, last_checked: datetime | None) -> datetime:
    threshold = _utc(now)
    if last_checked is not None:
        threshold = max(threshold, _utc(last_checked))
    return slot_at_or_after(group, threshold + timedelta(microseconds=1))


def next_check(group: int, consumed: datetime, finished: datetime) -> datetime:
    threshold = max(_utc(consumed), _utc(finished)) + timedelta(microseconds=1)
    return slot_at_or_after(group, threshold)


def admitted_group(now: datetime) -> int | None:
    local = _utc(now).astimezone(SCHEDULE_TIMEZONE)
    if local.hour not in (8, 17):
        return None
    group = local.minute // 20
    slot = local.replace(minute=group * 20, second=0, microsecond=0)
    return group if (local - slot).total_seconds() < COHORT_WORK_SECONDS else None


def starting_group(now: datetime) -> int | None:
    """Admission for a new batch, not the deadline of already queued work."""
    group = admitted_group(now)
    if group is None:
        return None
    slot = current_slot(group, now)
    assert slot is not None
    return group if (_utc(now) - slot).total_seconds() < SLOT_START_GRACE_SECONDS else None


def current_slot(group: int, now: datetime) -> datetime | None:
    if admitted_group(now) != group:
        return None
    return _utc(now).replace(minute=group * 20, second=0, microsecond=0)
