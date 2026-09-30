"""Fetch MeDaCo data and import it as long-term statistics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .aggregate import to_hourly_rows
from .api import Interval, Line, MedacoAuthError, MedacoClient, MedacoError, MeteringPoint
from .const import (
    DOMAIN,
    FETCH_CHUNK,
    INITIAL_HISTORY,
    OBIS_NAMES,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class RegisterState:
    """Latest known values of one register, exposed through sensors."""

    metering_point: MeteringPoint
    line: Line
    statistic_id: str
    last_hour: datetime | None = None
    total_kwh: float | None = None


def statistic_id_for(mp_id: str, obis: str) -> str:
    """Build a valid external statistic id like ``medaco:1234_1_8_0``."""
    slug = "".join(c if c.isalnum() else "_" for c in f"{mp_id}_{obis}").lower()
    return f"{DOMAIN}:{slug}"


def _metadata(statistic_id: str, name: str) -> StatisticMetaData:
    meta: dict = {
        "source": DOMAIN,
        "statistic_id": statistic_id,
        "name": name,
        "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
        "has_mean": False,
        "has_sum": True,
    }
    # Newer Home Assistant versions replaced has_mean with mean_type and
    # added unit_class; set them when available.
    try:
        from homeassistant.components.recorder.models import StatisticMeanType

        meta["mean_type"] = StatisticMeanType.NONE
        meta["unit_class"] = "energy"
    except ImportError:
        pass
    return StatisticMetaData(**meta)


class MedacoCoordinator(DataUpdateCoordinator[dict[str, RegisterState]]):
    """Polls the portal and writes hourly statistics."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: MedacoClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, RegisterState]:
        try:
            points = await self.client.get_metering_points()
            states: dict[str, RegisterState] = {}
            for point in points:
                for line in point.lines:
                    state = await self._import_line(point, line)
                    states[state.statistic_id] = state
            return states
        except MedacoAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except MedacoError as err:
            raise UpdateFailed(str(err)) from err

    async def _import_line(self, point: MeteringPoint, line: Line) -> RegisterState:
        statistic_id = statistic_id_for(point.id, line.obis)
        state = RegisterState(point, line, statistic_id)

        last = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics, self.hass, 1, statistic_id, True, {"sum"}
        )
        now = dt_util.utcnow()
        if last.get(statistic_id):
            row = last[statistic_id][0]
            last_hour = datetime.fromtimestamp(row["start"], tz=timezone.utc)
            last_sum = row["sum"] or 0.0
            start = last_hour + timedelta(hours=1)
        else:
            last_hour = None
            last_sum = 0.0
            start = (now - INITIAL_HISTORY).replace(
                minute=0, second=0, microsecond=0
            )

        state.last_hour, state.total_kwh = last_hour, last_sum
        if start >= now:
            return state

        intervals: list[Interval] = []
        chunk_start = start
        while chunk_start < now:
            chunk_end = min(chunk_start + FETCH_CHUNK, now)
            intervals += await self.client.get_intervals(
                point.id, line.id, chunk_start, chunk_end
            )
            chunk_start = chunk_end
        rows = to_hourly_rows(intervals, last_sum=last_sum, after=last_hour)
        if not rows:
            return state

        name = f"MeDaCo {point.name} {OBIS_NAMES.get(line.obis, line.obis)}"
        async_add_external_statistics(
            self.hass,
            _metadata(statistic_id, name),
            [StatisticData(start=r.start, state=r.state, sum=r.sum) for r in rows],
        )
        _LOGGER.debug("Imported %d hours for %s", len(rows), statistic_id)
        state.last_hour, state.total_kwh = rows[-1].start, rows[-1].sum
        return state
