"""Client for the MeDaCo web portal.

The portal is a Symfony app with a form login (CSRF token + session cookie)
and an Angular front end that loads its data as JSON. Mutating requests and
data calls carry the ``XSRF-TOKEN`` cookie back as ``X-XSRF-TOKEN`` header.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone, tzinfo
import logging
import re
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp
from yarl import URL

_LOGGER = logging.getLogger(__name__)

PORTAL_TZ = ZoneInfo("Europe/Berlin")

LOGIN_PAGE_PATH = "/login"
LOGIN_CHECK_PATH = "/login_check"
METERING_POINTS_PATH = "/sidebarMultiMp/rlm"
SERIES_PATH = "/data/mpline/genericto/{mp_id}/{line_id}/{start}/{end}/base"

# The portal sits behind Cloudflare, so look like the browser it expects.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"
)

_CSRF_RE = re.compile(r'name="_csrf_token"\s+value="([^"]+)"')
_OBIS_RE = re.compile(r"OBIS\s+(\S+)")


class MedacoError(Exception):
    """Base error for the MeDaCo client."""


class MedacoAuthError(MedacoError):
    """Login rejected or session expired."""


class MedacoConnectionError(MedacoError):
    """Portal not reachable or returned something unexpected."""


@dataclass(frozen=True)
class Line:
    """One measured register (Messreihe) of a metering point."""

    id: str
    obis: str  # e.g. "1-1:1.29.0"
    name: str


@dataclass(frozen=True)
class MeteringPoint:
    """A metering point and its registers."""

    id: str
    name: str
    lines: tuple[Line, ...]


@dataclass(frozen=True)
class Interval:
    """Energy measured in one interval, typically 15 minutes."""

    start: datetime  # timezone aware, UTC
    kwh: float


def parse_metering_points(tree: Any) -> list[MeteringPoint]:
    """Extract metering points and lines from the sidebar tree."""
    points: list[MeteringPoint] = []

    def walk(nodes: Iterable[dict[str, Any]]) -> None:
        for node in nodes:
            if node.get("type") == "mp":
                lines = []
                for child in node.get("childs") or []:
                    if child.get("type") != "line":
                        continue
                    details = child.get("details") or {}
                    match = _OBIS_RE.search(details.get("measured quantity") or "")
                    obis = match.group(1) if match else child.get("name", "")
                    lines.append(Line(str(child["id"]), obis, child.get("name", "")))
                # The name is the metering point id, often repeated twice.
                name = (node.get("name") or str(node["id"])).split()[0]
                points.append(MeteringPoint(str(node["id"]), name, tuple(lines)))
            else:
                walk(node.get("childs") or [])

    walk(tree)
    return points


def parse_series(data: dict[str, Any]) -> list[Interval]:
    """Turn a series response into intervals keyed by their start time."""
    unit = data.get("unit")
    if unit not in ("kWh", "Wh"):
        raise MedacoConnectionError(f"Unexpected unit {unit!r}")
    factor = 0.001 if unit == "Wh" else 1.0
    return [
        Interval(
            datetime.fromisoformat(ts).astimezone(timezone.utc), value * factor
        )
        for ts, value in zip(data["timestampsLeft"], data["values"], strict=True)
        if value is not None
    ]


def format_portal_time(moment: datetime, tz: tzinfo = PORTAL_TZ) -> str:
    """Format like the portal does: ``2026-8-1T00:00:00+02:00``."""
    local = moment.astimezone(tz)
    offset = local.strftime("%z")
    return (
        f"{local.year}-{local.month}-{local.day}T{local:%H:%M:%S}"
        f"{offset[:3]}:{offset[3:]}"
    )


class MedacoClient:
    """Minimal async client for the MeDaCo portal."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._logged_in = False

    async def login(self) -> None:
        """Log in with the portal's form login."""
        self._session.cookie_jar.clear()
        try:
            async with self._session.get(
                self._base_url + LOGIN_PAGE_PATH, headers=self._headers()
            ) as resp:
                if resp.status != 200:
                    raise MedacoConnectionError(f"Login page: HTTP {resp.status}")
                page = await resp.text()
            match = _CSRF_RE.search(page)
            if not match:
                raise MedacoConnectionError("No CSRF token on login page")
            async with self._session.post(
                self._base_url + LOGIN_CHECK_PATH,
                data={
                    "_username": self._username,
                    "_password": self._password,
                    "_csrf_token": match.group(1),
                    "_remember_me": "on",
                },
                headers=self._headers(),
                allow_redirects=False,
            ) as resp:
                location = resp.headers.get("Location", "")
                status = resp.status
        except aiohttp.ClientError as err:
            raise MedacoConnectionError(str(err)) from err
        # Success redirects to the start page, failure back to /login.
        if status != 302 or "login" in URL(location).path:
            raise MedacoAuthError("Login rejected")
        self._logged_in = True

    async def get_metering_points(self) -> list[MeteringPoint]:
        """Return all metering points of the account."""
        return parse_metering_points(await self._get_json(METERING_POINTS_PATH))

    async def get_intervals(
        self, mp_id: str, line_id: str, start: datetime, end: datetime
    ) -> list[Interval]:
        """Return 15 minute values of one line between start and end."""
        path = SERIES_PATH.format(
            mp_id=mp_id,
            line_id=line_id,
            start=format_portal_time(start),
            end=format_portal_time(end),
        )
        return parse_series(await self._get_json(path))

    def _headers(self, xhr: bool = False) -> dict[str, str]:
        headers = {"User-Agent": USER_AGENT, "Accept-Language": "de"}
        if xhr:
            headers["Accept"] = "application/json, text/plain, */*"
            headers["X-Requested-With"] = "XMLHttpRequest"
            for cookie in self._session.cookie_jar:
                if cookie.key == "XSRF-TOKEN":
                    headers["X-XSRF-TOKEN"] = cookie.value
        return headers

    async def _get_json(self, path: str, retry_auth: bool = True) -> Any:
        if not self._logged_in:
            await self.login()
        try:
            async with self._session.get(
                URL(self._base_url + path, encoded=True),
                headers=self._headers(xhr=True),
                allow_redirects=False,
            ) as resp:
                is_json = "json" in resp.headers.get("Content-Type", "")
                # An expired session answers with a redirect to /login.
                if resp.status in (301, 302, 401, 403) or (
                    resp.status == 200 and not is_json
                ):
                    self._logged_in = False
                    if retry_auth:
                        return await self._get_json(path, retry_auth=False)
                    raise MedacoAuthError(f"Session rejected for {path}")
                if resp.status >= 400:
                    raise MedacoConnectionError(f"HTTP {resp.status} for {path}")
                return await resp.json()
        except aiohttp.ClientError as err:
            raise MedacoConnectionError(str(err)) from err
