from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from bsentinel.domain import scraping_schedule as schedule

BOGOTA = ZoneInfo('America/Bogota')


@pytest.mark.parametrize('group,minute', [(0, 0), (1, 20), (2, 40)])
def test_evening_rollover_to_next_morning(group, minute):
    now = datetime(2026, 10, 8, 18, tzinfo=BOGOTA)
    assert schedule.initial_check(group, now, now) == datetime(2026, 10, 9, 13, minute, tzinfo=UTC)


def test_cutoff_and_consumed_slot_and_utc_input():
    morning = datetime(2026, 10, 8, 13, tzinfo=UTC)
    assert schedule.slot_at_or_after(0, morning) == morning
    assert schedule.initial_check(0, morning, None) == datetime(2026, 10, 8, 22, tzinfo=UTC)
    assert schedule.next_check(0, morning, morning + timedelta(seconds=90)) == datetime(2026, 10, 8, 22, tzinfo=UTC)
    assert schedule.next_check(0, morning, datetime(2026, 10, 8, 23, tzinfo=UTC)) == morning + timedelta(days=1)


@pytest.mark.parametrize('hour,minute,second,group', [
    (8, 0, 0, 0), (8, 1, 59, 0), (8, 2, 0, 0), (8, 20, 1, 1),
    (8, 19, 59, 0), (8, 20, 0, 1), (8, 39, 59, 1), (8, 40, 0, 2),
    (8, 59, 59, 2), (9, 0, 0, None),
    (17, 19, 59, 0), (17, 20, 0, 1), (17, 39, 59, 1), (17, 40, 0, 2),
    (17, 59, 59, 2), (17, 40, 50, 2), (13, 0, 0, None), (18, 0, 0, None), (7, 59, 59, None),
])
def test_bounded_group_specific_admission(hour, minute, second, group):
    now = datetime(2026, 10, 8, hour, minute, second, tzinfo=BOGOTA)
    assert schedule.admitted_group(now) == group


def test_naive_input_rejected():
    with pytest.raises(ValueError):
        schedule.admitted_group(datetime(2026, 10, 8))
