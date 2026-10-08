import importlib
from datetime import UTC, datetime, timedelta

import pytest


def calendar():
    name = "bsentinel.domain.scraping_schedule"
    assert importlib.util.find_spec(name) is not None, "pure calendar is missing"
    return importlib.import_module(name)


@pytest.mark.parametrize("group,minute", [(0, 0), (1, 20), (2, 40)])
def test_initial_schedule_respects_last_check_and_utc_slot(group, minute):
    schedule = calendar()
    now = datetime(2026, 10, 8, 23, 50, tzinfo=UTC)
    checked = now - timedelta(minutes=10)
    actual = schedule.initial_check(group, now, checked)
    assert actual == datetime(2026, 10, 9, 13, minute, tzinfo=UTC)
    assert schedule.slot_at_or_after(group, actual) == actual


def test_completion_keeps_phase_skips_long_attempt_and_consumed_slot():
    schedule = calendar()
    consumed = datetime(2026, 10, 8, 13, 20, tzinfo=UTC)
    finished = consumed + timedelta(hours=2, minutes=11)
    assert schedule.next_check(1, consumed, finished) == datetime(2026, 10, 8, 22, 20, tzinfo=UTC)
    assert schedule.next_check(
        1, consumed, consumed - timedelta(minutes=1)
    ) == consumed + timedelta(hours=9)


@pytest.mark.parametrize(
    "group,now",
    [
        (-1, datetime(2026, 1, 1, tzinfo=UTC)),
        (3, datetime(2026, 1, 1, tzinfo=UTC)),
        (0, datetime(2026, 1, 1)),
    ],
)
def test_invalid_calendar_input_is_rejected(group, now):
    schedule = calendar()
    with pytest.raises(ValueError):
        schedule.slot_at_or_after(group, now)


def test_unchecked_relation_uses_future_slot():
    schedule = calendar()
    now = datetime(2026, 10, 8, 12, tzinfo=UTC)
    assert schedule.initial_check(0, now, None) == now + timedelta(hours=1)
