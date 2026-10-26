"""Turn interval values into hourly long-term statistics rows.

Kept free of Home Assistant imports so it can be unit tested on its own.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone

from .api import Interval


@dataclass(frozen=True)
class HourRow:
    """One hourly statistics row: energy in the hour and running total."""

    start: datetime
    state: float
    sum: float


def to_hourly_rows(
    intervals: Iterable[Interval],
    last_sum: float = 0.0,
    after: datetime | None = None,
) -> list[HourRow]:
    """Group intervals by UTC hour and accumulate a running sum.

    Only hours strictly after ``after`` are returned; ``last_sum`` must be the
    running total at the end of that hour. Intervals with the same start are
    counted once (the last one wins), so overlapping or repeated values never
    double count. The newest hour is left out until all of its quarter hours
    arrived; gaps further back are imported as they are and get corrected
    when the coordinator re-imports its refresh window.
    """
    by_start: dict[datetime, float] = {}
    for interval in intervals:
        start = interval.start.astimezone(timezone.utc)
        hour = start.replace(minute=0, second=0, microsecond=0)
        if after is not None and hour <= after:
            continue
        by_start[start] = interval.kwh

    buckets: dict[datetime, list[float]] = {}
    for start, kwh in by_start.items():
        hour = start.replace(minute=0, second=0, microsecond=0)
        buckets.setdefault(hour, []).append(kwh)

    hours = sorted(buckets)
    quarter_hourly = any(len(v) > 1 for v in buckets.values())
    if hours and quarter_hourly and len(buckets[hours[-1]]) < 4:
        hours.pop()

    rows: list[HourRow] = []
    running = last_sum
    for hour in hours:
        energy = round(sum(buckets[hour]), 6)
        running = round(running + energy, 6)
        rows.append(HourRow(start=hour, state=energy, sum=running))
    return rows
