"""Typed data models for the ARPA Veneto Meteo integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .const import (
    CONF_DAY_CLEAR_THRESHOLD_DEFAULT,
    CONF_DAY_PARTLY_THRESHOLD_DEFAULT,
    CONF_NIGHT_CLEAR_THRESHOLD_DEFAULT,
    CONF_NIGHT_PARTLY_THRESHOLD_DEFAULT,
)


@dataclass(frozen=True, slots=True)
class Provenance:
    """Origin and observation timestamp of a sensor or condition value."""

    source: str
    name: str | None = None
    observed_at: str | None = None
    rule: str | None = None

    def as_attributes(self) -> dict[str, str]:
        """Return non-empty provenance fields suitable for HA extra_state_attributes."""
        attrs = {
            "source": self.source,
            "source_name": self.name,
            "source_observed_at": self.observed_at,
            "source_rule": self.rule,
        }
        return {k: v for k, v in attrs.items() if v is not None}


@dataclass(frozen=True, slots=True)
class DayThresholds:
    """Irradiance ratio thresholds for daytime sky condition inference."""

    clear: float = CONF_DAY_CLEAR_THRESHOLD_DEFAULT
    partly_cloudy: float = CONF_DAY_PARTLY_THRESHOLD_DEFAULT


@dataclass(frozen=True, slots=True)
class NightThresholds:
    """Sky brightness (mag/arcsec²) thresholds for nighttime sky condition inference."""

    clear: float = CONF_NIGHT_CLEAR_THRESHOLD_DEFAULT
    partly_cloudy: float = CONF_NIGHT_PARTLY_THRESHOLD_DEFAULT


@dataclass(frozen=True, slots=True)
class GeoStation:
    """Generic geolocated ARPAV monitoring station."""

    station_id: str
    name: str
    province: str = ""
    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None
    distance_km: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def label(self) -> str:
        """Build a readable dropdown label with province and distance when available."""
        base = f"{self.name} ({self.province})" if self.province else self.name
        if self.distance_km is not None:
            return f"{base} - {self.distance_km:.1f} km"
        return base


@dataclass(slots=True)
class StationObservation:
    """Parsed real-time observations from meteo_meteogrammi_tabella."""

    station_id: int
    station_name: str | None = None
    observed_at: datetime | None = None
    observed_at_iso: str | None = None
    values: dict[str, Any] = field(default_factory=dict)
    sources: dict[str, Provenance] = field(default_factory=dict)
    measured_temp_date: str | None = None
    measured_temp_min: float | None = None
    measured_temp_max: float | None = None
    raw_latest: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class StationSummary24h:
    """24-hour extremes and comfort indices from meteo_ultime24ore."""

    station_id: int
    station_name: str | None = None
    updated_at: str | None = None
    temp_last: float | None = None
    temp_min: float | None = None
    temp_max: float | None = None
    precipitation_24h: float | None = None
    wind_speed_max_kmh: float | None = None
    wind_gust_kmh: float | None = None
    snow_depth_cm: float | None = None
    humidex: float | None = None
    windchill: float | None = None


@dataclass(frozen=True, slots=True)
class ForecastEntry:
    """Single forecast period (twice-daily or daily) from bollettini_meteo_simboli."""

    dt: datetime
    forecast_type: str  # "twice_daily" or "daily"
    is_daytime: bool | None
    condition: str | None
    symbol: str | None = None
    temp_min: float | None = None
    temp_max: float | None = None
    precipitation_probability: int | None = None
    reliability: str | None = None
    weather_description: str | None = None
    precipitation_description: str | None = None
    snow_line: str | None = None
    temp_1500m: str | None = None
    temp_2000m: str | None = None
    temp_3000m: str | None = None
    wind: str | None = None
    issued_at: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class BulletinDayText:
    """Single day narrative entry from bollettini_meteo_testi."""

    date: str
    forecast_text: str
    reliability: str | None = None


@dataclass(frozen=True, slots=True)
class BulletinSummary:
    """Textual regional bulletin and weather alerts from bollettini_meteo_testi."""

    bulletin_code: str
    issued_at: str | None = None
    updated_at: str | None = None
    general_evolution: str | None = None
    alert: str | None = None
    special_phenomena: str | None = None
    days: list[BulletinDayText] = field(default_factory=list)

    @property
    def has_alert(self) -> bool:
        """Return True if an active weather alert or special phenomenon is reported."""
        return bool((self.alert and self.alert.strip()) or (
            self.special_phenomena and self.special_phenomena.strip()
        ))

    @property
    def alert_text(self) -> str | None:
        """Combine alert and special phenomena texts into one string."""
        parts = [
            p.strip()
            for p in (self.alert, self.special_phenomena)
            if p and p.strip()
        ]
        return " - ".join(parts) if parts else None


@dataclass(slots=True)
class AirQualityData:
    """Validated hourly and daily air quality readings."""

    pm10_hourly: float | None = None
    pm10_daily: float | None = None
    pm10_station_name: str | None = None
    pm10_hourly_at: str | None = None
    pm10_daily_at: str | None = None

    pm25_hourly: float | None = None
    pm25_daily: float | None = None
    pm25_station_name: str | None = None
    pm25_hourly_at: str | None = None
    pm25_daily_at: str | None = None

    ozone_hourly: float | None = None
    ozone_daily_max: float | None = None
    ozone_station_name: str | None = None
    ozone_hourly_at: str | None = None


@dataclass(frozen=True, slots=True)
class HydroReading:
    """Hydrometric river level, trend, and optional discharge reading."""

    station_id: int
    station_name: str
    province: str = ""
    level_m: float | None = None
    trend: str | None = None  # "=", "+", "-"
    discharge_m3s: float | None = None
    observed_at: str | None = None


@dataclass(frozen=True, slots=True)
class AvalancheArea:
    """Avalanche forecast for a mountain area (DOLOMITI or PREALPI)."""

    area: str
    danger_level: str  # canonical enum key (not_issued, 1_low..5_very_high)
    danger_raw: str | None = None
    fresh_snow: str | None = None
    dangerous_locations: str | None = None
    elevation_info: str | None = None
    date_label: str | None = None


@dataclass(frozen=True, slots=True)
class AvalancheBulletin:
    """Parsed Dolomiti Neve e Valanghe XML bulletin."""

    issued_at: str | None = None
    situation: str | None = None
    forecast: str | None = None
    guidance: str | None = None
    areas: dict[str, AvalancheArea] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        """Return True if at least one area carries an active AINEVA danger rating."""
        return any(a.danger_level != "not_issued" for a in self.areas.values())


@dataclass(frozen=True, slots=True)
class PollenSpecies:
    """Single monitored pollen/spore allergen species."""

    code: str
    slug: str
    name: str
    risk_level: str  # absent, low, moderate, high
    risk_raw: str | None = None
    forecast_level: str | None = None
    forecast_raw: str | None = None
    latest_value: float | None = None
    latest_date: str | None = None


@dataclass(frozen=True, slots=True)
class PollenReport:
    """Provincial allergen pollen bulletin report."""

    station_code: str
    station_name: str
    province: str = ""
    site: str | None = None
    period: str | None = None
    bulletin_number: int | None = None
    year: int | None = None
    comment: str | None = None
    max_risk_level: str = "absent"
    max_forecast_level: str = "absent"
    species: list[PollenSpecies] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SkyBrightnessReading:
    """Single night sky brightness measurement."""

    value: float
    station_name: str | None = None
    observed_at: str | None = None


@dataclass(slots=True)
class MetarStation:
    """Aerodrome issuing METAR reports near the configured ARPAV station."""

    icao: str
    name: str
    latitude: float
    longitude: float
    distance_km: float
    reporting: bool = True

    @property
    def label(self) -> str:
        """Build a dropdown label with distance and offline status."""
        base = f"{self.icao} - {self.name} ({self.distance_km:.1f} km)"
        if not self.reporting:
            return f"{base} - offline"
        return base


@dataclass(slots=True)
class MetarObservation:
    """Parsed NOAA Aviation Weather Center METAR report."""

    icao: str
    observed_at: str | None = None
    cloud_coverage: int | None = None
    weather: str | None = None
    values: dict[str, Any] = field(default_factory=dict)
    raw: str | None = None

    @property
    def name(self) -> str:
        """Return provenance display name."""
        return f"METAR {self.icao}"


@dataclass(frozen=True, slots=True)
class RadarFrame:
    """Latest weather radar image payload."""

    source: str
    content_type: str
    image_bytes: bytes
    observed_at: datetime


@dataclass(slots=True)
class ArpaVenetoData:
    """Top-level immutable-like snapshot returned by ArpaVenetoDataUpdateCoordinator."""

    sensors: dict[str, Any] = field(default_factory=dict)
    sources: dict[str, Provenance] = field(default_factory=dict)
    available_sensors: frozenset[str] = field(default_factory=frozenset)
    station_name: str | None = None
    observed_at: str | None = None
    measured_temp_date: str | None = None
    measured_temp_min: float | None = None
    measured_temp_max: float | None = None
    summary_24h: StationSummary24h | None = None
    forecast: list[ForecastEntry] = field(default_factory=list)
    bulletin: BulletinSummary | None = None
    air_quality: AirQualityData | None = None
    hydro: HydroReading | None = None
    avalanche: AvalancheBulletin | None = None
    pollen: PollenReport | None = None
    metar: MetarObservation | None = None
    last_update: str | None = None
