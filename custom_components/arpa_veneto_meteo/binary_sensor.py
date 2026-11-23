"""Binary sensor platform for weather alerts and air quality statutory exceedances."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    AQ_OZONE_INFO_THRESHOLD,
    AQ_PM10_DAILY_LIMIT,
    SOURCE_AIR_QUALITY,
    SOURCE_BULLETIN,
)
from .coordinator import ArpaVenetoDataUpdateCoordinator
from .entity import ArpaVenetoEntity
from .models import ArpaVenetoData


@dataclass(frozen=True, kw_only=True)
class ArpaVenetoBinarySensorDescription(BinarySensorEntityDescription):
    """Describes an ARPA Veneto binary sensor."""

    is_on_fn: Callable[[ArpaVenetoData], bool | None]
    attrs_fn: Callable[[ArpaVenetoData], dict[str, Any]]
    include_fn: Callable[[ArpaVenetoDataUpdateCoordinator], bool]


def _weather_alert_is_on(data: ArpaVenetoData) -> bool | None:
    """Return True when the regional bulletin reports an active alert."""
    if data.bulletin is None:
        return None
    return data.bulletin.has_alert


def _weather_alert_attrs(data: ArpaVenetoData) -> dict[str, Any]:
    """Return bulletin metadata and alert text as state attributes."""
    b = data.bulletin
    if b is None:
        return {}
    return {
        "source": SOURCE_BULLETIN,
        "bulletin_code": b.bulletin_code,
        "issued_at": b.issued_at,
        "updated_at": b.updated_at,
        "alert": b.alert,
        "special_phenomena": b.special_phenomena,
    }


def _pm10_exceedance_is_on(data: ArpaVenetoData) -> bool | None:
    """Return True when the daily mean PM10 exceeds the 50 ug/m3 limit."""
    if data.air_quality is None or data.air_quality.pm10_daily is None:
        return None
    return data.air_quality.pm10_daily > AQ_PM10_DAILY_LIMIT


def _pm10_exceedance_attrs(data: ArpaVenetoData) -> dict[str, Any]:
    """Return PM10 station details and limit threshold as state attributes."""
    aq = data.air_quality
    if aq is None:
        return {}
    return {
        "source": SOURCE_AIR_QUALITY,
        "station_name": aq.pm10_station_name,
        "pm10_daily": aq.pm10_daily,
        "limit_ug_m3": AQ_PM10_DAILY_LIMIT,
        "observed_at": aq.pm10_daily_at,
    }


def _ozone_exceedance_is_on(data: ArpaVenetoData) -> bool | None:
    """Return True when hourly ozone exceeds the 180 ug/m3 threshold."""
    if data.air_quality is None or data.air_quality.ozone_hourly is None:
        return None
    return data.air_quality.ozone_hourly > AQ_OZONE_INFO_THRESHOLD


def _ozone_exceedance_attrs(data: ArpaVenetoData) -> dict[str, Any]:
    """Return ozone station details and threshold as state attributes."""
    aq = data.air_quality
    if aq is None:
        return {}
    return {
        "source": SOURCE_AIR_QUALITY,
        "station_name": aq.ozone_station_name,
        "ozone_hourly": aq.ozone_hourly,
        "threshold_ug_m3": AQ_OZONE_INFO_THRESHOLD,
        "observed_at": aq.ozone_hourly_at,
    }


BINARY_SENSOR_DESCRIPTIONS: tuple[ArpaVenetoBinarySensorDescription, ...] = (
    ArpaVenetoBinarySensorDescription(
        key="weather_alert",
        translation_key="weather_alert",
        device_class=BinarySensorDeviceClass.SAFETY,
        is_on_fn=_weather_alert_is_on,
        attrs_fn=_weather_alert_attrs,
        include_fn=lambda coord: coord.enable_bulletin,
    ),
    ArpaVenetoBinarySensorDescription(
        key="pm10_exceedance",
        translation_key="pm10_exceedance",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=_pm10_exceedance_is_on,
        attrs_fn=_pm10_exceedance_attrs,
        include_fn=lambda coord: coord.pm10_station_id is not None,
    ),
    ArpaVenetoBinarySensorDescription(
        key="ozone_exceedance",
        translation_key="ozone_exceedance",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=_ozone_exceedance_is_on,
        attrs_fn=_ozone_exceedance_attrs,
        include_fn=lambda coord: coord.ozone_station_id is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up enabled ARPA Veneto binary sensors."""
    coordinator: ArpaVenetoDataUpdateCoordinator = config_entry.runtime_data
    entities = [
        ArpaVenetoBinarySensorEntity(coordinator, config_entry, desc)
        for desc in BINARY_SENSOR_DESCRIPTIONS
        if desc.include_fn(coordinator)
    ]
    async_add_entities(entities)


class ArpaVenetoBinarySensorEntity(ArpaVenetoEntity, BinarySensorEntity):
    """Binary sensor representing weather alerts or air quality threshold exceedances."""

    entity_description: ArpaVenetoBinarySensorDescription

    def __init__(
        self,
        coordinator: ArpaVenetoDataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: ArpaVenetoBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, config_entry)
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return True if the alert or threshold exceedance is active."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.is_on_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return alert details and metadata."""
        if self.coordinator.data is None:
            return {}
        attrs = self.entity_description.attrs_fn(self.coordinator.data)
        return {k: v for k, v in attrs.items() if v is not None}
