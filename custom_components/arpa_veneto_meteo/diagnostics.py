"""Diagnostics support for the ARPA Veneto Meteo integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import ArpaVenetoDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics snapshot for a config entry."""
    coordinator: ArpaVenetoDataUpdateCoordinator = entry.runtime_data
    data = coordinator.data

    snapshot: dict[str, Any] = {
        "entry_data": dict(entry.data),
        "entry_options": dict(entry.options),
        "last_update_success": coordinator.last_update_success,
        "update_interval_seconds": (
            coordinator.update_interval.total_seconds() if coordinator.update_interval else None
        ),
    }

    if data is not None:
        snapshot["data"] = {
            "station_name": data.station_name,
            "observed_at": data.observed_at,
            "last_update": data.last_update,
            "sensors": dict(data.sensors),
            "sources": {k: v.as_attributes() for k, v in data.sources.items()},
            "forecast_count": len(data.forecast),
            "has_bulletin": data.bulletin is not None,
            "bulletin_has_alert": data.bulletin.has_alert if data.bulletin else False,
            "summary_24h": asdict(data.summary_24h) if data.summary_24h else None,
            "air_quality": asdict(data.air_quality) if data.air_quality else None,
            "hydro": asdict(data.hydro) if data.hydro else None,
            "avalanche_active": data.avalanche.is_active if data.avalanche else None,
            "pollen_station": data.pollen.station_code if data.pollen else None,
            "pollen_max_risk": data.pollen.max_risk_level if data.pollen else None,
            "metar_icao": data.metar.icao if data.metar else None,
        }

    return snapshot
