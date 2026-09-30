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

    Only hours strictly after ``after`` (the start of the last imported
    hour) are returned, so repeated imports never double count. Hours are
    only emitted once complete, i.e. once all four 15 minute slots arrived,
    unless the data uses a coarser resolution.
    """
    buckets: dict[datetime, list[float]] = {}
    for interval in intervals:
        hour = interval.start.astimezone(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        if after is not None and hour <= after:
            continue
        buckets.setdefault(hour, []).append(interval.kwh)

    rows: list[HourRow] = []
    running = last_sum
    for hour in sorted(buckets):
        values = buckets[hour]
        # A partial trailing hour would be imported too low and never fixed.
        if len(values) not in (1, 4):
            break
        energy = round(sum(values), 6)
        running = round(running + energy, 6)
        rows.append(HourRow(start=hour, state=energy, sum=running))
    return rows
