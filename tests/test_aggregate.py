"""Tests for the pure hourly aggregation."""

from datetime import datetime, timedelta, timezone

from custom_components.medaco.aggregate import to_hourly_rows
from custom_components.medaco.api import Interval

T0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)


def quarter_hours(count: int, kwh: float = 0.25) -> list[Interval]:
    return [Interval(T0 + timedelta(minutes=15 * i), kwh) for i in range(count)]


def test_groups_into_hours_with_running_sum():
    rows = to_hourly_rows(quarter_hours(8), last_sum=10.0)
    assert [(r.start, r.state, r.sum) for r in rows] == [
        (T0, 1.0, 11.0),
        (T0 + timedelta(hours=1), 1.0, 12.0),
    ]


def test_skips_already_imported_hours():
    rows = to_hourly_rows(quarter_hours(8), last_sum=11.0, after=T0)
    assert [(r.start, r.sum) for r in rows] == [(T0 + timedelta(hours=1), 12.0)]


def test_leaves_out_incomplete_newest_hour():
    rows = to_hourly_rows(quarter_hours(6))
    assert [r.start for r in rows] == [T0]


def test_gap_in_the_middle_does_not_stall_later_hours():
    data = quarter_hours(12)
    del data[5]  # one quarter hour missing in the second hour
    rows = to_hourly_rows(data)
    assert [(r.state, r.sum) for r in rows] == [(1.0, 1.0), (0.75, 1.75), (1.0, 2.75)]


def test_repeated_intervals_count_once():
    data = quarter_hours(8)
    rows = to_hourly_rows(data + data[2:6])
    assert [r.sum for r in rows] == [1.0, 2.0]


def test_dst_fall_back_day_has_25_hours():
    # 2026-10-25: 00:00 local (CEST) to 00:00 local (CET) is 25 hours.
    start = datetime(2026, 10, 24, 22, 0, tzinfo=timezone.utc)
    data = [Interval(start + timedelta(minutes=15 * i), 0.25) for i in range(100)]
    rows = to_hourly_rows(data)
    assert len(rows) == 25 and rows[-1].sum == 25.0


def test_local_timestamps_are_normalised_to_utc():
    cest = timezone(timedelta(hours=2))
    local = [Interval((T0 + timedelta(minutes=15 * i)).astimezone(cest), 0.5) for i in range(4)]
    rows = to_hourly_rows(local)
    assert rows[0].start == T0 and rows[0].state == 2.0
