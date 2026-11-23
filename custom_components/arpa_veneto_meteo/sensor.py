"""Sensor platform for ARPA Veneto Meteo.

Defines all weather, precipitation, air quality, hydrology, avalanche, and
pollen sensors, creating only entities supported by the configured station and
enabled options.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    DEGREE,
    PERCENTAGE,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    AVALANCHE_LEVEL_OPTIONS,
    POLLEN_LEVEL_OPTIONS,
    SOURCE_AVALANCHE,
    SOURCE_BULLETIN,
    SOURCE_POLLEN,
)
from .coordinator import ArpaVenetoDataUpdateCoordinator
from .entity import ArpaVenetoEntity
from .models import ArpaVenetoData, PollenSpecies

# Compatibility across HA 2025.1..2026.x for WIND_DIRECTION / MEASUREMENT_ANGLE
_WIND_DIR_DEVICE_CLASS = getattr(SensorDeviceClass, "WIND_DIRECTION", None)
_ANGLE_STATE_CLASS = getattr(SensorStateClass, "MEASUREMENT_ANGLE", None)

MAX_HA_STATE_LEN = 255


def _truncate_state(text: str | None) -> str | None:
    """Shorten long text to fit Home Assistant's 255-character state limit."""
    if not text:
        return None
    if len(text) <= MAX_HA_STATE_LEN:
        return text
    return text[: MAX_HA_STATE_LEN - 1].rstrip() + "..."


@dataclass(frozen=True, kw_only=True)
class ArpaVenetoSensorDescription(SensorEntityDescription):
    """Describes an ARPA Veneto sensor entity."""

    value_fn: Callable[[ArpaVenetoData], Any]
    attrs_fn: Callable[[ArpaVenetoData], dict[str, Any]] | None = None
    include_fn: Callable[[ArpaVenetoDataUpdateCoordinator, ArpaVenetoData], bool] | None = None
    provenance_key: str | None = None


def _sensor_val(key: str) -> Callable[[ArpaVenetoData], Any]:
    """Return a value getter reading `key` from coordinator sensor data."""
    return lambda data: data.sensors.get(key)


def _has_sensor(key: str) -> Callable[[ArpaVenetoDataUpdateCoordinator, ArpaVenetoData], bool]:
    """Return an inclusion check that enables a sensor only when reported by the station."""
    return lambda _coord, data: key in data.available_sensors


def _bulletin_summary_value(data: ArpaVenetoData) -> str | None:
    """Return a short summary string from the regional weather bulletin."""
    if data.bulletin is None:
        return None
    if data.bulletin.alert_text:
        return _truncate_state(data.bulletin.alert_text)
    if data.bulletin.general_evolution:
        return _truncate_state(data.bulletin.general_evolution)
    if data.bulletin.days:
        return _truncate_state(data.bulletin.days[0].forecast_text)
    return None


def _bulletin_summary_attrs(data: ArpaVenetoData) -> dict[str, Any]:
    """Return full textual bulletin fields as sensor attributes."""
    b = data.bulletin
    if b is None:
        return {}
    return {
        "source": SOURCE_BULLETIN,
        "bulletin_code": b.bulletin_code,
        "issued_at": b.issued_at,
        "updated_at": b.updated_at,
        "has_alert": b.has_alert,
        "alert": b.alert,
        "special_phenomena": b.special_phenomena,
        "general_evolution": b.general_evolution,
        "daily_forecasts": [
            {"date": d.date, "text": d.forecast_text, "reliability": d.reliability}
            for d in b.days
        ],
    }


def _avalanche_value(area_key: str) -> Callable[[ArpaVenetoData], str | None]:
    """Build a getter for the avalanche danger enum of a mountain area."""

    def _get(data: ArpaVenetoData) -> str | None:
        """Return the danger level enum for the target area."""
        if data.avalanche is None:
            return None
        area = data.avalanche.areas.get(area_key)
        return area.danger_level if area else "not_issued"

    return _get


def _avalanche_attrs(area_key: str) -> Callable[[ArpaVenetoData], dict[str, Any]]:
    """Build an attribute getter for a mountain area's avalanche bulletin."""

    def _get(data: ArpaVenetoData) -> dict[str, Any]:
        """Return avalanche details and bulletin text for the target area."""
        av = data.avalanche
        if av is None:
            return {}
        area = av.areas.get(area_key)
        return {
            "source": SOURCE_AVALANCHE,
            "issued_at": av.issued_at,
            "bulletin_active": av.is_active,
            "situation": av.situation,
            "forecast": av.forecast,
            "guidance": av.guidance,
            "danger_raw": area.danger_raw if area else None,
            "fresh_snow": area.fresh_snow if area else None,
            "dangerous_locations": area.dangerous_locations if area else None,
            "elevation_info": area.elevation_info if area else None,
            "date_label": area.date_label if area else None,
        }

    return _get


def _pollen_risk_attrs(data: ArpaVenetoData) -> dict[str, Any]:
    """Return full provincial pollen metadata and per-species breakdown."""
    p = data.pollen
    if p is None:
        return {}
    return {
        "source": SOURCE_POLLEN,
        "station_code": p.station_code,
        "station_name": p.station_name,
        "province": p.province,
        "site": p.site,
        "period": p.period,
        "bulletin_number": p.bulletin_number,
        "year": p.year,
        "comment": p.comment,
        "forecast_max_risk": p.max_forecast_level,
        "species": {
            sp.slug: {
                "name": sp.name,
                "risk": sp.risk_level,
                "risk_label": sp.risk_raw,
                "forecast": sp.forecast_level,
                "value": sp.latest_value,
                "date": sp.latest_date,
            }
            for sp in p.species
        },
    }


SENSOR_DESCRIPTIONS: tuple[ArpaVenetoSensorDescription, ...] = (
    # --- Core real-time weather ---
    ArpaVenetoSensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=_sensor_val("temperature"),
        provenance_key="temperature",
    ),
    ArpaVenetoSensorDescription(
        key="temperature_min_24h",
        translation_key="temperature_min_24h",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=_sensor_val("temperature_min_24h"),
        include_fn=_has_sensor("temperature_min_24h"),
        provenance_key="temperature_min_24h",
    ),
    ArpaVenetoSensorDescription(
        key="temperature_max_24h",
        translation_key="temperature_max_24h",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=_sensor_val("temperature_max_24h"),
        include_fn=_has_sensor("temperature_max_24h"),
        provenance_key="temperature_max_24h",
    ),
    ArpaVenetoSensorDescription(
        key="dew_point",
        translation_key="dew_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=_sensor_val("dew_point"),
        include_fn=_has_sensor("dew_point"),
        provenance_key="dew_point",
    ),
    ArpaVenetoSensorDescription(
        key="apparent_temperature",
        translation_key="apparent_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=_sensor_val("apparent_temperature"),
        include_fn=_has_sensor("apparent_temperature"),
        provenance_key="apparent_temperature",
    ),
    ArpaVenetoSensorDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=_sensor_val("humidity"),
        provenance_key="humidity",
    ),
    ArpaVenetoSensorDescription(
        key="pressure",
        translation_key="pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.HPA,
        suggested_display_precision=1,
        value_fn=_sensor_val("pressure"),
        include_fn=_has_sensor("pressure"),
        provenance_key="pressure",
    ),
    ArpaVenetoSensorDescription(
        key="visibility",
        translation_key="visibility",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=2,
        value_fn=_sensor_val("visibility"),
        include_fn=_has_sensor("visibility"),
        provenance_key="visibility",
    ),
    # --- Wind ---
    ArpaVenetoSensorDescription(
        key="wind_speed",
        translation_key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=1,
        value_fn=_sensor_val("wind_speed"),
        include_fn=_has_sensor("wind_speed"),
        provenance_key="wind_speed",
    ),
    ArpaVenetoSensorDescription(
        key="wind_speed_max_24h",
        translation_key="wind_speed_max_24h",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=1,
        value_fn=_sensor_val("wind_speed_max_24h"),
        include_fn=_has_sensor("wind_speed_max_24h"),
        provenance_key="wind_speed_max_24h",
    ),
    ArpaVenetoSensorDescription(
        key="wind_gust_24h",
        translation_key="wind_gust_24h",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=1,
        value_fn=_sensor_val("wind_gust_24h"),
        include_fn=_has_sensor("wind_gust_24h"),
        provenance_key="wind_gust_24h",
    ),
    ArpaVenetoSensorDescription(
        key="wind_bearing",
        translation_key="wind_bearing",
        device_class=_WIND_DIR_DEVICE_CLASS,
        state_class=_ANGLE_STATE_CLASS,
        native_unit_of_measurement=DEGREE,
        value_fn=_sensor_val("wind_bearing"),
        attrs_fn=lambda data: (
            {"cardinal": data.sensors["wind_bearing_cardinal"]}
            if data.sensors.get("wind_bearing_cardinal")
            else {}
        ),
        include_fn=_has_sensor("wind_bearing"),
        provenance_key="wind_bearing",
    ),
    # --- Solar radiation & UV ---
    ArpaVenetoSensorDescription(
        key="solar_radiation",
        translation_key="solar_radiation",
        device_class=SensorDeviceClass.IRRADIANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        suggested_display_precision=1,
        value_fn=_sensor_val("solar_radiation"),
        include_fn=_has_sensor("solar_radiation"),
        provenance_key="solar_radiation",
    ),
    ArpaVenetoSensorDescription(
        key="uv_index",
        translation_key="uv_index",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="UV index",
        suggested_display_precision=1,
        value_fn=_sensor_val("uv_index"),
        include_fn=_has_sensor("uv_index"),
        provenance_key="uv_index",
    ),
    # --- Precipitation (valid units & state classes!) ---
    ArpaVenetoSensorDescription(
        key="precipitation_5m",
        translation_key="precipitation_5m",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        suggested_display_precision=2,
        value_fn=_sensor_val("precipitation_5m"),
        include_fn=_has_sensor("precipitation_5m"),
        provenance_key="precipitation_5m",
    ),
    ArpaVenetoSensorDescription(
        key="precipitation_intensity",
        translation_key="precipitation_intensity",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        suggested_display_precision=2,
        value_fn=_sensor_val("precipitation_intensity"),
        include_fn=_has_sensor("precipitation_intensity"),
        provenance_key="precipitation_intensity",
    ),
    ArpaVenetoSensorDescription(
        key="precipitation_1h",
        translation_key="precipitation_1h",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        suggested_display_precision=2,
        value_fn=_sensor_val("precipitation_1h"),
        include_fn=_has_sensor("precipitation_1h"),
        provenance_key="precipitation_1h",
    ),
    ArpaVenetoSensorDescription(
        key="precipitation_3h",
        translation_key="precipitation_3h",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        suggested_display_precision=2,
        value_fn=_sensor_val("precipitation_3h"),
        include_fn=_has_sensor("precipitation_3h"),
        provenance_key="precipitation_3h",
    ),
    ArpaVenetoSensorDescription(
        key="precipitation_6h",
        translation_key="precipitation_6h",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        suggested_display_precision=2,
        value_fn=_sensor_val("precipitation_6h"),
        include_fn=_has_sensor("precipitation_6h"),
        provenance_key="precipitation_6h",
    ),
    ArpaVenetoSensorDescription(
        key="precipitation_12h",
        translation_key="precipitation_12h",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        suggested_display_precision=2,
        value_fn=_sensor_val("precipitation_12h"),
        include_fn=_has_sensor("precipitation_12h"),
        provenance_key="precipitation_12h",
    ),
    ArpaVenetoSensorDescription(
        key="precipitation_24h",
        translation_key="precipitation_24h",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        suggested_display_precision=2,
        value_fn=_sensor_val("precipitation_24h"),
        include_fn=_has_sensor("precipitation_24h"),
        provenance_key="precipitation_24h",
    ),
    ArpaVenetoSensorDescription(
        key="precipitation_today",
        translation_key="precipitation_today",
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        suggested_display_precision=2,
        value_fn=_sensor_val("precipitation_today"),
        include_fn=_has_sensor("precipitation_today"),
        provenance_key="precipitation_today",
    ),
    ArpaVenetoSensorDescription(
        key="precipitation_probability",
        translation_key="precipitation_probability",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=_sensor_val("precipitation_probability"),
        provenance_key="precipitation_probability",
    ),
    # --- Agrometeo & Snow ---
    ArpaVenetoSensorDescription(
        key="leaf_wetness",
        translation_key="leaf_wetness",
        device_class=SensorDeviceClass.MOISTURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=_sensor_val("leaf_wetness"),
        include_fn=_has_sensor("leaf_wetness"),
        provenance_key="leaf_wetness",
    ),
    ArpaVenetoSensorDescription(
        key="snow_depth",
        translation_key="snow_depth",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        suggested_display_precision=1,
        value_fn=_sensor_val("snow_depth"),
        include_fn=_has_sensor("snow_depth"),
        provenance_key="snow_depth",
    ),
    ArpaVenetoSensorDescription(
        key="snow_line",
        translation_key="snow_line",
        value_fn=_sensor_val("snow_line"),
        include_fn=_has_sensor("snow_line"),
        provenance_key="snow_line",
    ),
    # --- Regional textual bulletin ---
    ArpaVenetoSensorDescription(
        key="bulletin_summary",
        translation_key="bulletin_summary",
        value_fn=_bulletin_summary_value,
        attrs_fn=_bulletin_summary_attrs,
        include_fn=lambda coord, _data: coord.enable_bulletin,
    ),
    # --- Air quality (validated FLAG >= 9, hourly + official daily mean) ---
    ArpaVenetoSensorDescription(
        key="pm10_hourly",
        translation_key="pm10_hourly",
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        suggested_display_precision=1,
        value_fn=_sensor_val("pm10_hourly"),
        include_fn=lambda coord, _data: coord.pm10_station_id is not None,
        provenance_key="pm10_hourly",
    ),
    ArpaVenetoSensorDescription(
        key="pm10_daily",
        translation_key="pm10_daily",
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        suggested_display_precision=1,
        value_fn=_sensor_val("pm10_daily"),
        include_fn=lambda coord, _data: coord.pm10_station_id is not None,
        provenance_key="pm10_daily",
    ),
    ArpaVenetoSensorDescription(
        key="pm25_hourly",
        translation_key="pm25_hourly",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        suggested_display_precision=1,
        value_fn=_sensor_val("pm25_hourly"),
        include_fn=lambda coord, _data: coord.pm25_station_id is not None,
        provenance_key="pm25_hourly",
    ),
    ArpaVenetoSensorDescription(
        key="pm25_daily",
        translation_key="pm25_daily",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        suggested_display_precision=1,
        value_fn=_sensor_val("pm25_daily"),
        include_fn=lambda coord, _data: coord.pm25_station_id is not None,
        provenance_key="pm25_daily",
    ),
    ArpaVenetoSensorDescription(
        key="ozone",
        translation_key="ozone",
        device_class=SensorDeviceClass.OZONE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        suggested_display_precision=1,
        value_fn=_sensor_val("ozone"),
        attrs_fn=lambda data: (
            {"daily_max": data.air_quality.ozone_daily_max}
            if data.air_quality and data.air_quality.ozone_daily_max is not None
            else {}
        ),
        include_fn=lambda coord, _data: coord.ozone_station_id is not None,
        provenance_key="ozone",
    ),
    # --- Hydrology ---
    ArpaVenetoSensorDescription(
        key="river_level",
        translation_key="river_level",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=2,
        value_fn=_sensor_val("river_level"),
        attrs_fn=lambda data: (
            {
                "trend": data.hydro.trend,
                "hydro_station_id": data.hydro.station_id,
                "hydro_station_name": data.hydro.station_name,
            }
            if data.hydro is not None
            else {}
        ),
        include_fn=lambda coord, data: (
            coord.hydro_station_id is not None or "river_level" in data.available_sensors
        ),
        provenance_key="river_level",
    ),
    ArpaVenetoSensorDescription(
        key="river_discharge",
        translation_key="river_discharge",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_SECOND,
        suggested_display_precision=2,
        value_fn=_sensor_val("river_discharge"),
        include_fn=_has_sensor("river_discharge"),
        provenance_key="river_discharge",
    ),
    # --- Snow & Avalanches ---
    ArpaVenetoSensorDescription(
        key="avalanche_dolomiti",
        translation_key="avalanche_dolomiti",
        device_class=SensorDeviceClass.ENUM,
        options=AVALANCHE_LEVEL_OPTIONS,
        value_fn=_avalanche_value("DOLOMITI"),
        attrs_fn=_avalanche_attrs("DOLOMITI"),
        include_fn=lambda coord, _data: coord.enable_avalanche,
    ),
    ArpaVenetoSensorDescription(
        key="avalanche_prealpi",
        translation_key="avalanche_prealpi",
        device_class=SensorDeviceClass.ENUM,
        options=AVALANCHE_LEVEL_OPTIONS,
        value_fn=_avalanche_value("PREALPI"),
        attrs_fn=_avalanche_attrs("PREALPI"),
        include_fn=lambda coord, _data: coord.enable_avalanche,
    ),
    # --- Pollen overall summary ---
    ArpaVenetoSensorDescription(
        key="pollen_risk",
        translation_key="pollen_risk",
        device_class=SensorDeviceClass.ENUM,
        options=POLLEN_LEVEL_OPTIONS,
        value_fn=lambda data: data.pollen.max_risk_level if data.pollen else None,
        attrs_fn=_pollen_risk_attrs,
        include_fn=lambda coord, _data: coord.pollen_station_code is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create only sensors supported by the selected station and enabled modules."""
    coordinator: ArpaVenetoDataUpdateCoordinator = config_entry.runtime_data
    data = coordinator.data

    entities: list[SensorEntity] = []
    for desc in SENSOR_DESCRIPTIONS:
        if desc.include_fn is None or (data is not None and desc.include_fn(coordinator, data)):
            entities.append(ArpaVenetoSensorEntity(coordinator, config_entry, desc))

    # Add per-species pollen sensors when a pollen station is configured and reported species
    if coordinator.pollen_station_code and data and data.pollen:
        for species in data.pollen.species:
            entities.append(ArpaVenetoPollenSpeciesSensor(coordinator, config_entry, species))

    async_add_entities(entities)


class ArpaVenetoSensorEntity(ArpaVenetoEntity, SensorEntity):
    """Standard sensor backed by ArpaVenetoDataUpdateCoordinator."""

    entity_description: ArpaVenetoSensorDescription

    def __init__(
        self,
        coordinator: ArpaVenetoDataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: ArpaVenetoSensorDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, config_entry)
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the native sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return provenance and any sensor-specific metadata."""
        data = self.coordinator.data
        if data is None:
            return {}

        attrs: dict[str, Any] = {
            "station_id": self.coordinator.station_id,
            "last_update": data.last_update,
        }

        if self.entity_description.provenance_key:
            prov = data.sources.get(self.entity_description.provenance_key)
            if prov is not None:
                attrs.update(prov.as_attributes())

        if self.entity_description.attrs_fn is not None:
            attrs.update(self.entity_description.attrs_fn(data))

        return {k: v for k, v in attrs.items() if v is not None}


class ArpaVenetoPollenSpeciesSensor(ArpaVenetoEntity, SensorEntity):
    """Numeric pollen concentration sensor (granuli/m³) for a single monitored species."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "granuli/m³"
    _attr_icon = "mdi:flower-pollen-outline"

    def __init__(
        self,
        coordinator: ArpaVenetoDataUpdateCoordinator,
        config_entry: ConfigEntry,
        species: PollenSpecies,
    ) -> None:
        """Initialize the per-species pollen sensor."""
        super().__init__(coordinator, config_entry)
        self._species_code = species.code
        self._species_slug = species.slug
        self._attr_unique_id = f"{config_entry.entry_id}_pollen_{species.slug}"
        self._attr_name = f"Pollen {species.name}"

    def _find_species(self) -> PollenSpecies | None:
        """Look up this sensor's species entry in the latest pollen report."""
        data = self.coordinator.data
        if data is None or data.pollen is None:
            return None
        for sp in data.pollen.species:
            if sp.code == self._species_code:
                return sp
        return None

    @property
    def native_value(self) -> float | None:
        """Return latest pollen/spore grain concentration."""
        sp = self._find_species()
        return sp.latest_value if sp is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return species risk level, forecast, and observation date."""
        sp = self._find_species()
        if sp is None:
            return {}
        data = self.coordinator.data
        return {
            "source": SOURCE_POLLEN,
            "station_code": data.pollen.station_code if data and data.pollen else None,
            "species_code": sp.code,
            "species_name": sp.name,
            "risk_level": sp.risk_level,
            "risk_label": sp.risk_raw,
            "forecast_level": sp.forecast_level,
            "forecast_label": sp.forecast_raw,
            "observed_date": sp.latest_date,
        }
