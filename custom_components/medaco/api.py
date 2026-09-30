"""Client for the MeDaCo web portal.

The portal is a single page app that loads its data as JSON from its own
backend. The endpoint paths and payloads below are placeholders until they
are confirmed from a browser recording (HAR) of a real session; everything
outside this module only relies on the public methods and dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

# TODO(HAR): confirm these paths against a recorded portal session.
LOGIN_PATH = "/api/auth/login"
METERING_POINTS_PATH = "/api/meteringpoints"
READINGS_PATH = "/api/meteringpoints/{mp_id}/values"


class MedacoError(Exception):
    """Base error for the MeDaCo client."""


class MedacoAuthError(MedacoError):
    """Login rejected or session expired."""


class MedacoConnectionError(MedacoError):
    """Portal not reachable or returned something unexpected."""


@dataclass(frozen=True)
class MeteringPoint:
    """A meter (Messlokation) and the registers it reports."""

    id: str
    name: str
    obis_codes: tuple[str, ...]


@dataclass(frozen=True)
class Interval:
    """Energy measured in one interval, typically 15 minutes."""

    start: datetime  # timezone aware, UTC
    kwh: float


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
        self._token: str | None = None

    async def login(self) -> None:
        """Log in and keep the session token."""
        # TODO(HAR): the real flow may be a Keycloak/OIDC redirect dance
        # instead of a single JSON POST.
        data = await self._request(
            "POST",
            LOGIN_PATH,
            json={"username": self._username, "password": self._password},
            authenticated=False,
        )
        token = data.get("token") or data.get("access_token")
        if not token:
            raise MedacoAuthError("Login response contained no token")
        self._token = token

    async def get_metering_points(self) -> list[MeteringPoint]:
        """Return all metering points of the account."""
        data = await self._request("GET", METERING_POINTS_PATH)
        return [
            MeteringPoint(
                id=str(item["id"]),
                name=item.get("name") or str(item["id"]),
                obis_codes=tuple(item.get("obisCodes") or ("1.8.0",)),
            )
            for item in data
        ]

    async def get_intervals(
        self, mp_id: str, obis: str, start: datetime, end: datetime
    ) -> list[Interval]:
        """Return interval values for one register between start and end."""
        data = await self._request(
            "GET",
            READINGS_PATH.format(mp_id=mp_id),
            params={
                "obis": obis,
                "from": start.astimezone(timezone.utc).isoformat(),
                "to": end.astimezone(timezone.utc).isoformat(),
            },
        )
        return [
            Interval(
                start=datetime.fromisoformat(item["timestamp"]).astimezone(
                    timezone.utc
                ),
                kwh=float(item["value"]),
            )
            for item in data
            if item.get("value") is not None
        ]

    async def _request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = True,
        retry_auth: bool = True,
        **kwargs: Any,
    ) -> Any:
        if authenticated and self._token is None:
            await self.login()
        headers = {"Accept": "application/json"}
        if authenticated:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            async with self._session.request(
                method, self._base_url + path, headers=headers, **kwargs
            ) as resp:
                if resp.status in (401, 403):
                    if authenticated and retry_auth:
                        self._token = None
                        return await self._request(
                            method, path, retry_auth=False, **kwargs
                        )
                    raise MedacoAuthError(f"HTTP {resp.status} for {path}")
                if resp.status >= 400:
                    raise MedacoConnectionError(f"HTTP {resp.status} for {path}")
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise MedacoConnectionError(str(err)) from err
