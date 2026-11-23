"""Weather platform for the ARPA Veneto Meteo integration."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from homeassistant.components.weather import Forecast, WeatherEntity, WeatherEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .conditions import nearest_forecast
from .coordinator import ArpaVenetoDataUpdateCoordinator
from .entity import ArpaVenetoEntity
from .models import ForecastEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ARPA Veneto weather entity."""
    coordinator: ArpaVenetoDataUpdateCoordinator = config_entry.runtime_data
    async_add_entities([ArpaVenetoWeatherEntity(coordinator, config_entry)])


class ArpaVenetoWeatherEntity(ArpaVenetoEntity, WeatherEntity):
    """WeatherEntity exposing live ARPAV observations, 24h wind gusts, and forecasts."""

    _attr_translation_key = "arpav_weather"
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_TWICE_DAILY
    )
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_native_visibility_unit = UnitOfLength.KILOMETERS
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS

    def __init__(
        self,
        coordinator: ArpaVenetoDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the weather entity."""
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.entry_id}_weather"

    def _sensors(self) -> dict[str, Any]:
        """Return the latest sensor values dict, or an empty dict if unavailable."""
        return self.coordinator.data.sensors if self.coordinator.data else {}

    @property
    def condition(self) -> str | None:
        """Return the current weather condition."""
        return self._sensors().get("condition")

    @property
    def native_temperature(self) -> float | None:
        """Return current air temperature (°C)."""
        return self._sensors().get("temperature")

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return apparent temperature (windchill or humidex, °C)."""
        return self._sensors().get("apparent_temperature")

    @property
    def native_dew_point(self) -> float | None:
        """Return computed dew point (°C)."""
        return self._sensors().get("dew_point")

    @property
    def humidity(self) -> float | None:
        """Return relative humidity (%)."""
        return self._sensors().get("humidity")

    @property
    def native_pressure(self) -> float | None:
        """Return atmospheric pressure (hPa)."""
        return self._sensors().get("pressure")

    @property
    def native_wind_speed(self) -> float | None:
        """Return current wind speed (km/h)."""
        return self._sensors().get("wind_speed")

    @property
    def native_wind_gust_speed(self) -> float | None:
        """Return maximum wind gust speed (km/h) from 24h summary or METAR."""
        return self._sensors().get("wind_gust_24h")

    @property
    def wind_bearing(self) -> float | str | None:
        """Return wind bearing in degrees (0..359)."""
        return self._sensors().get("wind_bearing")

    @property
    def native_visibility(self) -> float | None:
        """Return visibility (km)."""
        return self._sensors().get("visibility")

    @property
    def uv_index(self) -> float | None:
        """Return estimated UV index."""
        return self._sensors().get("uv_index")

    @property
    def cloud_coverage(self) -> float | None:
        """Return cloud coverage (%) when METAR is configured and current."""
        data = self.coordinator.data
        if data and data.metar is not None:
            return data.metar.cloud_coverage
        return None

    async def async_forecast_twice_daily(self) -> list[Forecast] | None:
        """Return twice-daily (night/morning and afternoon/evening) forecasts."""
        if not self.coordinator.data:
            return None
        return build_twice_daily_forecasts(self.coordinator.data.forecast)

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return daily forecasts merged with today's measured temperature extremes."""
        data = self.coordinator.data
        if not data:
            return None
        return build_daily_forecasts(
            data.forecast,
            measured_date=data.measured_temp_date,
            measured_min=data.measured_temp_min,
            measured_max=data.measured_temp_max,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return provenance, forecast summary, altitude info, and active alert."""
        data = self.coordinator.data
        if not data:
            return {}

        attrs: dict[str, Any] = {
            "station_id": self.coordinator.station_id,
            "station_name": data.station_name,
            "zone_id": self.coordinator.zone_id,
            "zone_name": self.coordinator.zone_name,
            "observed_at": data.observed_at,
        }

        cond_prov = data.sources.get("condition")
        if cond_prov is not None:
            for key, val in cond_prov.as_attributes().items():
                attrs[f"condition_{key}"] = val

        nearest = nearest_forecast(datetime.now(UTC), data.forecast)
        if nearest is not None:
            if nearest.weather_description:
                attrs["forecast_description"] = nearest.weather_description
            if nearest.precipitation_description:
                attrs["forecast_precipitation"] = nearest.precipitation_description
            if nearest.precipitation_probability is not None:
                attrs["forecast_precipitation_probability"] = nearest.precipitation_probability
            if nearest.reliability:
                attrs["forecast_reliability"] = nearest.reliability
            if nearest.snow_line:
                attrs["snow_line"] = nearest.snow_line
            if nearest.temp_1500m:
                attrs["temperature_1500m"] = nearest.temp_1500m
            if nearest.temp_2000m:
                attrs["temperature_2000m"] = nearest.temp_2000m
            if nearest.temp_3000m:
                attrs["temperature_3000m"] = nearest.temp_3000m
            if nearest.issued_at:
                attrs["forecast_issued_at"] = nearest.issued_at
            if nearest.updated_at:
                attrs["forecast_updated_at"] = nearest.updated_at

        if data.bulletin is not None:
            attrs["weather_alert_active"] = data.bulletin.has_alert
            if data.bulletin.alert_text:
                attrs["weather_alert"] = data.bulletin.alert_text

        return attrs


def build_twice_daily_forecasts(entries: list[ForecastEntry]) -> list[Forecast]:
    """Convert ForecastEntry list into Home Assistant twice-daily Forecast dicts."""
    result: list[Forecast] = []
    for entry in entries:
        if entry.forecast_type != "twice_daily":
            continue
        fc: Forecast = {
            "datetime": entry.dt.isoformat(),
            "is_daytime": bool(entry.is_daytime),
        }
        if entry.condition is not None:
            fc["condition"] = entry.condition
        if entry.temp_max is not None:
            fc["native_temperature"] = entry.temp_max
        if entry.temp_min is not None:
            fc["native_templow"] = entry.temp_min
        if entry.precipitation_probability is not None:
            fc["precipitation_probability"] = entry.precipitation_probability
        result.append(fc)
    return result


def build_daily_forecasts(
    entries: list[ForecastEntry],
    *,
    measured_date: str | None = None,
    measured_min: float | None = None,
    measured_max: float | None = None,
) -> list[Forecast]:
    """Aggregate twice-daily and daily entries into one daily Forecast per calendar date."""
    grouped: dict[str, list[ForecastEntry]] = defaultdict(list)
    for entry in entries:
        grouped[entry.dt.date().isoformat()].append(entry)

    result: list[Forecast] = []
    for date_str in sorted(grouped):
        day_entries = grouped[date_str]
        daytime = [e for e in day_entries if e.forecast_type == "twice_daily" and e.is_daytime]
        primary = daytime[0] if daytime else day_entries[0]

        temps: list[float] = []
        probs: list[int] = []
        for e in day_entries:
            if e.temp_max is not None:
                temps.append(e.temp_max)
            if e.temp_min is not None:
                temps.append(e.temp_min)
            if e.precipitation_probability is not None:
                probs.append(e.precipitation_probability)

        # Include already-measured station extremes for today because ARPAV drops elapsed half-days
        if measured_date == date_str:
            if measured_min is not None:
                temps.append(measured_min)
            if measured_max is not None:
                temps.append(measured_max)

        fc: Forecast = {"datetime": date_str}
        if primary.condition is not None:
            fc["condition"] = primary.condition
        if temps:
            fc["native_temperature"] = max(temps)
            if len(temps) > 1:
                fc["native_templow"] = min(temps)
        if probs:
            fc["precipitation_probability"] = max(probs)
        result.append(fc)

    return result
