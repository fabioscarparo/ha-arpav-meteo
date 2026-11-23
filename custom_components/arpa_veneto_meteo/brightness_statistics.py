"""Archive ARPAV night sky brightness readings as Home Assistant external statistics."""

from __future__ import annotations

import logging
from datetime import UTC
from typing import Any

from homeassistant.components.recorder.models import StatisticMeanType, StatisticMetaData
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify

from .api import ArpaVenetoApiClient, ArpaVenetoApiError, parse_arpav_timestamp
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UNIT_OF_MEASUREMENT = "mag/arcsec²"
DEFAULT_STATIONS = 3
MAX_STATIONS_TRIED = 6
MIN_READINGS_PER_HOUR = 3


async def async_archive_brightness(
    hass: HomeAssistant,
    latitude: float | None,
    longitude: float | None,
    stations: int = DEFAULT_STATIONS,
) -> int:
    """Import hourly night sky brightness statistics for the nearest ARPAV stations."""
    if latitude is None or longitude is None:
        return 0

    if "recorder" not in hass.config.components:
        _LOGGER.debug("Recorder component not loaded; skipping brightness archive")
        return 0

    api = ArpaVenetoApiClient(async_get_clientsession(hass))
    nearest = await api.async_get_brightness_stations(latitude, longitude)

    imported = 0
    archived = 0
    for station in nearest[:MAX_STATIONS_TRIED]:
        if archived >= stations:
            break

        try:
            readings = await api.async_get_station_brightness_raw(int(station.station_id))
        except (ArpaVenetoApiError, ValueError) as err:
            _LOGGER.debug("Skipping brightness station %s: %s", station.station_id, err)
            continue

        hourly = aggregate_hourly_brightness(readings)
        if not hourly:
            continue

        metadata = StatisticMetaData(
            mean_type=StatisticMeanType.ARITHMETIC,
            has_sum=False,
            name=f"Night sky brightness in {station.name}",
            source=DOMAIN,
            statistic_id=f"{DOMAIN}:sky_brightness_{slugify(station.name)}",
            unit_class=None,
            unit_of_measurement=UNIT_OF_MEASUREMENT,
        )
        async_add_external_statistics(hass, metadata, hourly)
        imported += len(hourly)
        archived += 1

    return imported


def aggregate_hourly_brightness(readings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate valid (> 0) brightness readings into UTC hourly mean/min/max statistics."""
    by_hour: dict[Any, list[float]] = {}
    for item in readings:
        try:
            value = float(item.get("valore"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue

        if value <= 0:
            continue

        dt = parse_arpav_timestamp(item.get("dataora"))
        if dt is None:
            continue

        hour = dt.replace(minute=0, second=0, microsecond=0).astimezone(UTC)
        by_hour.setdefault(hour, []).append(value)

    return [
        {
            "start": hour,
            "mean": round(sum(values) / len(values), 2),
            "min": min(values),
            "max": max(values),
        }
        for hour, values in sorted(by_hour.items())
        if len(values) >= MIN_READINGS_PER_HOUR
    ]
