"""Optional METAR observations via NOAA Aviation Weather Center API.

Reuses the shared Home Assistant aiohttp ClientSession with explicit timeouts.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from math import exp
from typing import Any

import aiohttp

from .const import CARDINAL_DIRECTIONS, DEFAULT_CONNECT_TIMEOUT, DEFAULT_HTTP_TIMEOUT
from .models import MetarObservation, MetarStation

_LOGGER = logging.getLogger(__name__)

METAR_API_BASE = "https://aviationweather.gov/api/data"
MIN_FETCH_INTERVAL = timedelta(minutes=10)
MAX_OBSERVATION_AGE = timedelta(minutes=90)
SEARCH_RANGE_DEGREES = 1.5

CLOUD_COVER_OKTAS: dict[str, int] = {
    "SKC": 0,
    "CLR": 0,
    "NCD": 0,
    "NSC": 0,
    "CAVOK": 0,
    "FEW": 2,
    "SCT": 4,
    "BKN": 6,
    "OVC": 8,
    "OVX": 8,
    "VV": 8,
}

CLEAR_SKY_TOKENS: tuple[str, ...] = ("CAVOK", "NCD", "NSC", "SKC", "CLR")

KNOTS_TO_KMH = 1.852
STATUTE_MILES_TO_KM = 1.609344


def is_observation_current(
    observation: MetarObservation | None,
    now: datetime | None = None,
) -> bool:
    """Return True if the METAR observation is recent enough to describe current weather."""
    if observation is None or not observation.observed_at:
        return False

    try:
        observed_at = datetime.fromisoformat(observation.observed_at)
    except (TypeError, ValueError):
        return False

    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)

    ref = now if now is not None else datetime.now(UTC)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=UTC)

    return (ref - observed_at) <= MAX_OBSERVATION_AGE


async def async_fetch_stations(
    session: aiohttp.ClientSession,
    latitude: float,
    longitude: float,
    distance_fn: Callable[[float, float], float],
) -> list[MetarStation]:
    """Return aerodromes issuing METAR around coordinates, reporting & nearest first."""
    span = SEARCH_RANGE_DEGREES
    # aviationweather.gov answers 400 to coordinates with more than 6 decimals
    bbox = f"{latitude - span:.4f},{longitude - span:.4f},{latitude + span:.4f},{longitude + span:.4f}"
    url = f"{METAR_API_BASE}/stationinfo?bbox={bbox}&format=json"
    timeout = aiohttp.ClientTimeout(total=DEFAULT_HTTP_TIMEOUT, connect=DEFAULT_CONNECT_TIMEOUT)

    async with session.get(url, timeout=timeout) as response:
        response.raise_for_status()
        data = await response.json(content_type=None)

    stations: list[MetarStation] = []
    for entry in data or []:
        icao = entry.get("icaoId")
        lat = entry.get("lat")
        lon = entry.get("lon")
        if not icao or lat is None or lon is None:
            continue
        if "METAR" not in (entry.get("siteType") or []):
            continue

        stations.append(
            MetarStation(
                icao=str(icao),
                name=str(entry.get("site") or icao),
                latitude=float(lat),
                longitude=float(lon),
                distance_km=distance_fn(float(lat), float(lon)),
            )
        )

    reporting = await _async_reporting_icaos(session, [s.icao for s in stations])
    for station in stations:
        station.reporting = station.icao in reporting

    return sorted(stations, key=lambda s: (not s.reporting, s.distance_km))


async def _async_reporting_icaos(
    session: aiohttp.ClientSession,
    icaos: list[str],
) -> set[str]:
    """Return which aerodromes currently have a METAR report published."""
    if not icaos:
        return set()

    url = f"{METAR_API_BASE}/metar?ids={','.join(icaos)}&format=json"
    timeout = aiohttp.ClientTimeout(total=DEFAULT_HTTP_TIMEOUT, connect=DEFAULT_CONNECT_TIMEOUT)

    try:
        async with session.get(url, timeout=timeout) as response:
            response.raise_for_status()
            data = await response.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        _LOGGER.debug("Unable to check currently reporting METAR aerodromes: %s", err)
        return set(icaos)

    return {str(report["icaoId"]) for report in (data or []) if report.get("icaoId")}


async def async_fetch_observation(
    session: aiohttp.ClientSession,
    icao: str,
) -> MetarObservation | None:
    """Fetch the latest METAR report for an ICAO aerodrome, or None on error."""
    url = f"{METAR_API_BASE}/metar?ids={icao}&format=json"
    timeout = aiohttp.ClientTimeout(total=DEFAULT_HTTP_TIMEOUT, connect=DEFAULT_CONNECT_TIMEOUT)

    try:
        async with session.get(url, timeout=timeout) as response:
            response.raise_for_status()
            data = await response.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        _LOGGER.debug("Unable to fetch METAR report for %s: %s", icao, err)
        return None

    if not data:
        return None

    return parse_observation(data[0])


def parse_observation(report: dict[str, Any]) -> MetarObservation:
    """Parse a raw NOAA METAR JSON object into a MetarObservation."""
    raw = str(report.get("rawOb") or "")
    values: dict[str, Any] = {}

    visibility = _visibility_km(report.get("visib"))
    if visibility is not None:
        values["visibility"] = visibility

    for key, raw_val in (("pressure", report.get("altim")), ("temperature", report.get("temp"))):
        if raw_val is not None:
            with contextlib.suppress(TypeError, ValueError):
                values[key] = round(float(raw_val), 1)

    humidity = _relative_humidity(report.get("temp"), report.get("dewp"))
    if humidity is not None:
        values["humidity"] = humidity

    wind_speed = report.get("wspd")
    if wind_speed is not None:
        with contextlib.suppress(TypeError, ValueError):
            values["wind_speed"] = round(float(wind_speed) * KNOTS_TO_KMH, 1)

    wind_gust = report.get("wgst")
    if wind_gust is not None:
        with contextlib.suppress(TypeError, ValueError):
            values["wind_gust_24h"] = round(float(wind_gust) * KNOTS_TO_KMH, 1)

    bearing = report.get("wdir")
    if isinstance(bearing, (int, float)):
        deg = int(bearing) % 360
        values["wind_bearing"] = deg
        values["wind_bearing_cardinal"] = CARDINAL_DIRECTIONS[int((deg + 11.25) / 22.5) % 16]

    return MetarObservation(
        icao=str(report.get("icaoId") or ""),
        observed_at=_observed_at(report),
        cloud_coverage=_cloud_coverage(report.get("clouds"), raw),
        weather=report.get("wxString"),
        values=values,
        raw=raw or None,
    )


def metar_condition(observation: MetarObservation | None, is_day: bool) -> str | None:
    """Map a METAR observation to a Home Assistant weather condition string."""
    if observation is None:
        return None

    weather = (observation.weather or "").upper()

    if "TS" in weather:
        return (
            "lightning-rainy"
            if any(code in weather for code in ("RA", "DZ", "SN"))
            else "lightning"
        )
    if "SN" in weather or "SG" in weather:
        return "snowy-rainy" if any(code in weather for code in ("RA", "DZ")) else "snowy"
    if any(code in weather for code in ("FZRA", "FZDZ", "PL", "IC")):
        return "snowy-rainy"
    if "GR" in weather or "GS" in weather:
        return "hail"
    if "RA" in weather or "DZ" in weather:
        return "pouring" if weather.startswith("+") else "rainy"
    if any(code in weather for code in ("FG", "BR", "HZ", "FU")):
        return "fog"

    coverage = observation.cloud_coverage
    if coverage is None:
        return None

    if coverage <= 12:
        return "sunny" if is_day else "clear-night"
    if coverage <= 50:
        return "partlycloudy"
    return "cloudy"


def _cloud_coverage(layers: list[dict[str, Any]] | None, raw: str) -> int | None:
    """Return total cloud coverage as percentage (0..100), or None."""
    oktas = [
        CLOUD_COVER_OKTAS[cover]
        for layer in (layers or [])
        if (cover := str(layer.get("cover") or "").upper()) in CLOUD_COVER_OKTAS
    ]
    if oktas:
        return round(max(oktas) * 100 / 8)

    raw_upper = raw.upper()
    if any(token in raw_upper for token in CLEAR_SKY_TOKENS):
        return 0

    return None


def _visibility_km(visibility: Any) -> float | None:
    """Convert METAR statute-mile visibility to kilometers."""
    if visibility is None:
        return None
    try:
        miles = float(str(visibility).replace("+", "").strip())
    except (TypeError, ValueError):
        return None
    return round(miles * STATUTE_MILES_TO_KM, 2)


def _relative_humidity(temperature: Any, dew_point: Any) -> int | None:
    """Compute relative humidity (%) from temperature and dew point (°C)."""
    if temperature is None or dew_point is None:
        return None
    try:
        temp_c = float(temperature)
        dew_c = float(dew_point)
    except (TypeError, ValueError):
        return None

    a, b = 17.625, 243.04
    saturation = exp(a * dew_c / (b + dew_c) - a * temp_c / (b + temp_c))
    return min(100, max(0, round(100 * saturation)))


def _observed_at(report: dict[str, Any]) -> str | None:
    """Extract ISO-8601 observation timestamp from a METAR report."""
    report_time = report.get("reportTime")
    if report_time:
        with contextlib.suppress(TypeError, ValueError):
            return datetime.fromisoformat(str(report_time).replace("Z", "+00:00")).isoformat()

    obs_time = report.get("obsTime")
    if obs_time is not None:
        with contextlib.suppress(TypeError, ValueError, OSError):
            return datetime.fromtimestamp(int(obs_time), tz=UTC).isoformat()

    return None
