"""Shared base entity class for all ARPA Veneto Meteo platforms."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    ATTRIBUTION_METAR,
    CONF_STATION_NAME,
    CONF_ZONE_NAME,
    DOMAIN,
)
from .coordinator import ArpaVenetoDataUpdateCoordinator


class ArpaVenetoEntity(CoordinatorEntity[ArpaVenetoDataUpdateCoordinator]):
    """Base entity that attaches common device info and attribution to every platform entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ArpaVenetoDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the shared device metadata and data attribution."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        station_name = str(config_entry.data.get(CONF_STATION_NAME) or coordinator.station_id)
        zone_name = str(config_entry.data.get(CONF_ZONE_NAME) or f"Zone {coordinator.zone_id}")

        self._attr_attribution = (
            ATTRIBUTION_METAR if coordinator.metar_station else ATTRIBUTION
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=f"ARPA Veneto - {station_name}",
            manufacturer="ARPA Veneto",
            model=zone_name,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://meteo.arpa.veneto.it/",
        )
