"""Run config flow and statistics import against a fake portal."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from homeassistant import config_entries
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util

from custom_components.medaco.api import Interval, Line, MedacoAuthError, MeteringPoint
from custom_components.medaco.const import CONF_PORTAL, DOMAIN

POINT = MeteringPoint(
    "111",
    "DE0001234",
    (Line("201", "1-1:1.29.0", "iMS - 1-1:1.29.0"),),
)
STAT_ID = "medaco:111_1_1_1_29_0"
CLIENT = "custom_components.medaco.api.MedacoClient"


class FakePortal:
    """Serves 0.25 kWh per quarter hour up to a movable 'now'."""

    def __init__(self, end: datetime) -> None:
        self.end = end
        self.calls: list[tuple[datetime, datetime]] = []

    async def get_intervals(self, mp_id, line_id, start, end):
        self.calls.append((start, end))
        out, t = [], start
        while t < min(end, self.end):
            out.append(Interval(t, 0.25))
            t += timedelta(minutes=15)
        return out


async def test_config_flow_creates_entry(hass: HomeAssistant) -> None:
    with (
        patch(f"{CLIENT}.login", return_value=None),
        patch(f"{CLIENT}.get_metering_points", return_value=[POINT]),
        patch("custom_components.medaco.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PORTAL: "westnetz", CONF_USERNAME: "Nutzer", CONF_PASSWORD: "pw"},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == "Nutzer"


async def test_config_flow_invalid_auth(hass: HomeAssistant) -> None:
    with patch(f"{CLIENT}.login", side_effect=MedacoAuthError):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PORTAL: "westnetz", CONF_USERNAME: "Nutzer", CONF_PASSWORD: "x"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_imports_hourly_statistics_incrementally(
    hass: HomeAssistant,
) -> None:
    now = dt_util.utcnow().replace(minute=5, second=0, microsecond=0)
    portal = FakePortal(end=now - timedelta(minutes=5) - timedelta(hours=1))
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PORTAL: "westnetz", CONF_USERNAME: "Nutzer", CONF_PASSWORD: "pw"},
    )
    entry.add_to_hass(hass)

    with (
        patch(f"{CLIENT}.get_metering_points", return_value=[POINT]),
        patch(f"{CLIENT}.get_intervals", side_effect=portal.get_intervals),
        patch("homeassistant.util.dt.utcnow", return_value=now),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)

        first = await _stats(hass)
        assert len(first) == 365 * 24 - 1
        assert first[-1]["sum"] == len(first) * 1.0

        # One more hour arrives; only that hour is fetched and appended.
        portal.end += timedelta(hours=1)
        portal.calls.clear()
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)

    second = await _stats(hass)
    assert len(second) == len(first) + 1
    assert second[-1]["sum"] == first[-1]["sum"] + 1.0
    assert len(portal.calls) == 1

    total = hass.states.get("sensor.de0001234_bezug_importiert")
    assert total is not None and float(total.state) == second[-1]["sum"]


async def _stats(hass: HomeAssistant) -> list[dict]:
    result = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        datetime(2000, 1, 1, tzinfo=timezone.utc),
        None,
        {STAT_ID},
        "hour",
        None,
        {"sum", "state"},
    )
    return result.get(STAT_ID, [])
