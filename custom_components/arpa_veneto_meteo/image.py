"""Image platform serving live ARPA Veneto weather radar frames."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import ArpaVenetoApiError
from .const import (
    CONF_RADAR_MOSAIC,
    CONF_RADAR_NONE,
    RADAR_MIN_FETCH_INTERVAL,
)
from .coordinator import ArpaVenetoDataUpdateCoordinator
from .entity import ArpaVenetoEntity
from .models import RadarFrame

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ARPA Veneto radar image entity if enabled in options."""
    coordinator: ArpaVenetoDataUpdateCoordinator = config_entry.runtime_data
    if coordinator.radar_source == CONF_RADAR_NONE:
        return
    async_add_entities([ArpaVenetoRadarImageEntity(hass, coordinator, config_entry)])


class ArpaVenetoRadarImageEntity(ArpaVenetoEntity, ImageEntity):
    """ImageEntity displaying the latest Veneto Radar Mosaic, Teolo, or Concordia radar."""

    _attr_translation_key = "radar"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ArpaVenetoDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the radar image entity."""
        ArpaVenetoEntity.__init__(self, coordinator, config_entry)
        ImageEntity.__init__(self, hass)
        self._radar_source = coordinator.radar_source
        self._attr_unique_id = f"{config_entry.entry_id}_radar_{self._radar_source}"
        self._attr_content_type = (
            "image/png" if self._radar_source == CONF_RADAR_MOSAIC else "image/jpeg"
        )
        self._cached_frame: RadarFrame | None = None
        self._fetched_at: datetime | None = None
        self._attr_image_last_updated = datetime.now(UTC)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Signal frontend to refresh the radar image on coordinator ticks."""
        self._attr_image_last_updated = datetime.now(UTC)
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """Fetch latest radar bytes with a 5-minute rate-limiting cache."""
        now = datetime.now(UTC)
        if (
            self._cached_frame is not None
            and self._fetched_at is not None
            and (now - self._fetched_at) < RADAR_MIN_FETCH_INTERVAL
        ):
            return self._cached_frame.image_bytes

        try:
            frame = await self.coordinator.api.async_get_radar_frame(self._radar_source)
        except ArpaVenetoApiError as err:
            _LOGGER.warning("Unable to fetch ARPA Veneto radar (%s): %s", self._radar_source, err)
            return self._cached_frame.image_bytes if self._cached_frame else None

        if frame is None:
            return self._cached_frame.image_bytes if self._cached_frame else None

        self._cached_frame = frame
        self._fetched_at = now
        self._attr_content_type = frame.content_type
        self._attr_image_last_updated = frame.observed_at
        return frame.image_bytes

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose radar source identifier."""
        return {"radar_source": self._radar_source}
