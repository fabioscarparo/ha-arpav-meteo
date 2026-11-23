"""Entry point for the ARPA Veneto Meteo integration.

Sets up config entries, registers integration services, forwards platforms
(weather, sensor, binary_sensor, image), and schedules optional night sky
brightness statistics archiving.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_change

from .api import ArpaVenetoApiError
from .brightness_statistics import async_archive_brightness
from .const import (
    BRIGHTNESS_ARCHIVE_HOUR,
    BRIGHTNESS_ARCHIVE_MINUTE,
    CONF_ARCHIVE_BRIGHTNESS,
    DOMAIN,
)
from .coordinator import ArpaVenetoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: tuple[Platform, ...] = (
    Platform.WEATHER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.IMAGE,
)

type ArpaVenetoConfigEntry = ConfigEntry[ArpaVenetoDataUpdateCoordinator]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register domain-level services once."""

    async def handle_refresh_data(call: ServiceCall) -> None:
        """Handle the refresh_data service call."""
        for coordinator in _target_coordinators(hass, call):
            await coordinator.async_force_refresh()

    async def handle_archive_brightness(call: ServiceCall) -> None:
        """Handle the archive_brightness service call."""
        for coordinator in _target_coordinators(hass, call):
            imported = await async_archive_brightness(
                hass, coordinator.latitude, coordinator.longitude
            )
            _LOGGER.debug(
                "Archived %s hourly brightness statistics for station %s",
                imported,
                coordinator.station_id,
            )

    if not hass.services.has_service(DOMAIN, "refresh_data"):
        hass.services.async_register(DOMAIN, "refresh_data", handle_refresh_data)
    if not hass.services.has_service(DOMAIN, "archive_brightness"):
        hass.services.async_register(DOMAIN, "archive_brightness", handle_archive_brightness)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ArpaVenetoConfigEntry) -> bool:
    """Set up ARPA Veneto Meteo from a config entry."""
    coordinator = ArpaVenetoDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    if entry.options.get(CONF_ARCHIVE_BRIGHTNESS):
        _schedule_brightness_archive(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ArpaVenetoConfigEntry) -> bool:
    """Unload an ARPA Veneto Meteo config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: ArpaVenetoConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _schedule_brightness_archive(
    hass: HomeAssistant,
    entry: ArpaVenetoConfigEntry,
    coordinator: ArpaVenetoDataUpdateCoordinator,
) -> None:
    """Schedule daily brightness statistics import after ARPAV's 09:30 batch."""

    async def _run_archive(_now=None) -> None:
        """Run one brightness statistics import without failing integration setup."""
        try:
            imported = await async_archive_brightness(
                hass, coordinator.latitude, coordinator.longitude
            )
        except (ArpaVenetoApiError, HomeAssistantError) as err:
            _LOGGER.warning("Unable to archive night sky brightness: %s", err)
            return
        _LOGGER.debug("Archived %s hourly night sky brightness statistics", imported)

    entry.async_on_unload(
        async_track_time_change(
            hass,
            _run_archive,
            hour=BRIGHTNESS_ARCHIVE_HOUR,
            minute=BRIGHTNESS_ARCHIVE_MINUTE,
            second=0,
        )
    )
    entry.async_create_background_task(hass, _run_archive(), f"{DOMAIN}_archive_brightness")


def _target_coordinators(
    hass: HomeAssistant,
    call: ServiceCall,
) -> list[ArpaVenetoDataUpdateCoordinator]:
    """Resolve config entry coordinators targeted by a service call."""
    target_id = call.data.get("entry_id")
    entries = hass.config_entries.async_entries(DOMAIN)
    coordinators: list[ArpaVenetoDataUpdateCoordinator] = []
    for entry in entries:
        if target_id and entry.entry_id != target_id:
            continue
        runtime_data = getattr(entry, "runtime_data", None)
        if isinstance(runtime_data, ArpaVenetoDataUpdateCoordinator):
            coordinators.append(runtime_data)
    return coordinators
