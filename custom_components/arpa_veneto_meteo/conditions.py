"""Current weather condition inference engine.

Determines the current Home Assistant weather condition from station sensors
(precipitation rate, visibility, wind, daytime solar radiation, nighttime sky
brightness), optional METAR reports, and forecast fallbacks.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime
from math import cos, radians, sin
from typing import Any

from .const import (
    CONF_DAY_CONDITION_FORECAST,
    CONF_DAY_CONDITION_METAR,
    CONF_DAY_CONDITION_RADIATION,
    CONF_DAY_CONDITION_RADIATION_OR_FORECAST,
    CONF_DAY_CONDITION_RADIATION_OR_METAR,
    CONF_DAY_CONDITION_UNKNOWN,
    CONF_NIGHT_CONDITION_BRIGHTNESS,
    CONF_NIGHT_CONDITION_BRIGHTNESS_OR_FORECAST,
    CONF_NIGHT_CONDITION_FORECAST,
    CONF_NIGHT_CONDITION_METAR,
    CONF_NIGHT_CONDITION_UNKNOWN,
    RULE_CLOUD_COVER,
    RULE_FORECAST,
    RULE_PRECIPITATION,
    RULE_SKY_BRIGHTNESS,
    RULE_SOLAR_RADIATION,
    RULE_VISIBILITY,
    RULE_WIND,
    SOURCE_BRIGHTNESS,
    SOURCE_FORECAST,
    SOURCE_METAR,
    SOURCE_STATION,
    SOURCE_UNKNOWN,
)
from .metar import metar_condition
from .models import (
    DayThresholds,
    ForecastEntry,
    MetarObservation,
    NightThresholds,
    Provenance,
    SkyBrightnessReading,
)

# Below 5° sun elevation, GHI/sin(elev) ratio is dominated by atmospheric refraction & shading
MIN_SOLAR_ELEVATION_DEG = 5.0
POURING_MM_PER_HOUR = 10.0
WINDY_KMH_THRESHOLD = 35.0


def _sun_is_day_and_elevation(lat: float, lon: float, dt: datetime) -> tuple[bool, float]:
    """Return (is_day, solar_elevation_deg) using astral if installed."""
    from astral import LocationInfo
    from astral.sun import elevation, sun

    city = LocationInfo(latitude=lat, longitude=lon)
    aware = dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
    s = sun(city.observer, date=aware.date(), tzinfo=aware.tzinfo)
    elev = float(elevation(city.observer, aware))
    return (s["sunrise"] <= aware <= s["sunset"]), elev


def moon_illumination(dt: datetime) -> float:
    """Return approximate Moon illumination percentage (0..100)."""
    from astral.moon import phase

    p = float(phase(dt))  # 0 = new, ~14.76 = full
    return (1.0 - cos(radians(p * 360.0 / 29.53))) / 2.0 * 100.0


def nearest_forecast(
    target_dt: datetime,
    forecasts: list[ForecastEntry],
) -> ForecastEntry | None:
    """Return the forecast entry closest to `target_dt` (preferring twice-daily entries)."""
    candidates = [f for f in forecasts if f.condition]
    twice_daily = [f for f in candidates if f.forecast_type == "twice_daily"]
    pool = twice_daily or candidates
    if not pool:
        return None

    ref_utc = target_dt.astimezone(UTC) if target_dt.tzinfo else target_dt.replace(tzinfo=UTC)
    return min(pool, key=lambda f: abs(f.dt.astimezone(UTC) - ref_utc))


async def async_classify_condition(
    *,
    latitude: float | None,
    longitude: float | None,
    dt: datetime,
    sensors: dict[str, Any],
    sources: dict[str, Provenance],
    forecasts: list[ForecastEntry],
    zone_name: str | None,
    day_strategy: str = CONF_DAY_CONDITION_RADIATION_OR_FORECAST,
    night_strategy: str = CONF_NIGHT_CONDITION_BRIGHTNESS_OR_FORECAST,
    day_thresholds: DayThresholds = DayThresholds(),
    night_thresholds: NightThresholds = NightThresholds(),
    metar_obs: MetarObservation | None = None,
    fetch_brightness: Callable[[], Awaitable[SkyBrightnessReading | None]] | None = None,
) -> tuple[str | None, Provenance]:
    """Compute the current Home Assistant weather condition and its provenance."""
    aware_dt = dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)

    temperature = sensors.get("temperature")
    humidity = sensors.get("humidity")
    wind_speed = sensors.get("wind_speed")
    precip_5m = sensors.get("precipitation_5m")
    precip_intensity = sensors.get("precipitation_intensity")
    visibility = sensors.get("visibility")
    ghi = sensors.get("solar_radiation")

    def _measured(rule: str, key: str) -> Provenance:
        """Build a Provenance object tagged with the rule that decided the condition."""
        prov = sources.get(key)
        if prov is not None:
            return replace(prov, rule=rule)
        return Provenance(source=SOURCE_STATION, observed_at=aware_dt.isoformat(), rule=rule)

    # 1. Active precipitation overrides sky cover
    if precip_5m is not None and precip_5m > 0:
        prov = _measured(RULE_PRECIPITATION, "precipitation_5m")
        if temperature is not None:
            if temperature <= 0.0:
                return "snowy", prov
            if temperature <= 2.5:
                return "snowy-rainy", prov
        if precip_intensity is not None and precip_intensity >= POURING_MM_PER_HOUR:
            return "pouring", prov
        return "rainy", prov

    # 2. Fog / very low visibility overrides wind and sky cover
    if visibility is not None:
        if visibility < 1.0 or (visibility < 2.0 and humidity is not None and humidity >= 98):
            return "fog", _measured(RULE_VISIBILITY, "visibility")

    # 3. Strong wind
    if wind_speed is not None and wind_speed > WINDY_KMH_THRESHOLD:
        return "windy", _measured(RULE_WIND, "wind_speed")

    # 4. Determine day vs night
    if latitude is None or longitude is None:
        return _forecast_condition(aware_dt, forecasts, zone_name, night=False)

    is_day, solar_elev = _sun_is_day_and_elevation(latitude, longitude, aware_dt)

    if is_day:
        return _day_condition(
            strategy=day_strategy,
            dt=aware_dt,
            solar_elev=solar_elev,
            ghi=ghi,
            thresholds=day_thresholds,
            metar_obs=metar_obs,
            forecasts=forecasts,
            zone_name=zone_name,
            measured=_measured,
        )

    return await _async_night_condition(
        strategy=night_strategy,
        dt=aware_dt,
        thresholds=night_thresholds,
        metar_obs=metar_obs,
        forecasts=forecasts,
        zone_name=zone_name,
        fetch_brightness=fetch_brightness,
    )


def _day_condition(
    *,
    strategy: str,
    dt: datetime,
    solar_elev: float,
    ghi: float | None,
    thresholds: DayThresholds,
    metar_obs: MetarObservation | None,
    forecasts: list[ForecastEntry],
    zone_name: str | None,
    measured: Callable[[str, str], Provenance],
) -> tuple[str | None, Provenance]:
    """Determine daytime sky condition according to user strategy."""
    if strategy == CONF_DAY_CONDITION_UNKNOWN:
        return None, Provenance(source=SOURCE_UNKNOWN)

    if strategy == CONF_DAY_CONDITION_FORECAST:
        return _forecast_condition(dt, forecasts, zone_name, night=False)

    if strategy == CONF_DAY_CONDITION_METAR:
        cond, prov = _metar_sky(metar_obs, is_day=True)
        if cond is not None:
            return cond, prov
        return _forecast_condition(dt, forecasts, zone_name, night=False)

    # Radiation-based strategies
    rad_cond, rad_prov = _radiation_condition(solar_elev, ghi, thresholds, measured)
    if rad_cond is not None and rad_prov is not None:
        return rad_cond, rad_prov

    if strategy == CONF_DAY_CONDITION_RADIATION_OR_METAR:
        cond, prov = _metar_sky(metar_obs, is_day=True)
        if cond is not None:
            return cond, prov
        return None, Provenance(source=SOURCE_UNKNOWN)

    if strategy == CONF_DAY_CONDITION_RADIATION_OR_FORECAST:
        cond, prov = _metar_sky(metar_obs, is_day=True)
        if cond is not None:
            return cond, prov
        return _forecast_condition(dt, forecasts, zone_name, night=False)

    # CONF_DAY_CONDITION_RADIATION
    return None, Provenance(source=SOURCE_UNKNOWN)


def _radiation_condition(
    solar_elev: float,
    ghi: float | None,
    thresholds: DayThresholds,
    measured: Callable[[str, str], Provenance],
) -> tuple[str | None, Provenance | None]:
    """Classify daytime sky from Global Horizontal Irradiance normalized by solar elevation."""
    if ghi is None or solar_elev < MIN_SOLAR_ELEVATION_DEG:
        return None, None

    ghi_clear = 1000.0 * sin(radians(solar_elev))
    if ghi_clear <= 0:
        return None, None

    ratio = ghi / ghi_clear
    prov = measured(RULE_SOLAR_RADIATION, "solar_radiation")

    if ratio > thresholds.clear:
        return "sunny", prov
    if ratio > thresholds.partly_cloudy:
        return "partlycloudy", prov
    return "cloudy", prov


async def _async_night_condition(
    *,
    strategy: str,
    dt: datetime,
    thresholds: NightThresholds,
    metar_obs: MetarObservation | None,
    forecasts: list[ForecastEntry],
    zone_name: str | None,
    fetch_brightness: Callable[[], Awaitable[SkyBrightnessReading | None]] | None,
) -> tuple[str | None, Provenance]:
    """Determine nighttime sky condition according to user strategy."""
    if strategy == CONF_NIGHT_CONDITION_UNKNOWN:
        return None, Provenance(source=SOURCE_UNKNOWN)

    if strategy == CONF_NIGHT_CONDITION_FORECAST:
        return _forecast_condition(dt, forecasts, zone_name, night=True)

    if strategy == CONF_NIGHT_CONDITION_METAR:
        cond, prov = _metar_sky(metar_obs, is_day=False)
        if cond is not None:
            return cond, prov
        return _forecast_condition(dt, forecasts, zone_name, night=True)

    if fetch_brightness is not None:
        reading = await fetch_brightness()
        if reading is not None:
            return _brightness_condition(reading, dt, thresholds)

    if strategy == CONF_NIGHT_CONDITION_BRIGHTNESS:
        return None, Provenance(source=SOURCE_UNKNOWN)

    # CONF_NIGHT_CONDITION_BRIGHTNESS_OR_FORECAST
    return _forecast_condition(dt, forecasts, zone_name, night=True)


def _brightness_condition(
    reading: SkyBrightnessReading,
    dt: datetime,
    thresholds: NightThresholds,
) -> tuple[str, Provenance]:
    """Classify nighttime sky from sky brightness (mag/arcsec²) adjusted for Moon phase."""
    prov = Provenance(
        source=SOURCE_BRIGHTNESS,
        name=reading.station_name,
        observed_at=reading.observed_at,
        rule=RULE_SKY_BRIGHTNESS,
    )
    illum = moon_illumination(dt)
    offset = -2.0 if illum > 50.0 else (-1.0 if illum > 10.0 else 0.0)
    adjusted = reading.value + offset

    if adjusted > thresholds.clear:
        return "clear-night", prov
    if adjusted > thresholds.partly_cloudy:
        return "partlycloudy", prov
    return "cloudy", prov


def _metar_sky(
    observation: MetarObservation | None,
    *,
    is_day: bool,
) -> tuple[str | None, Provenance]:
    """Classify sky from a current METAR report."""
    cond = metar_condition(observation, is_day)
    if cond is None or observation is None:
        return None, Provenance(source=SOURCE_UNKNOWN)
    return cond, Provenance(
        source=SOURCE_METAR,
        name=observation.name,
        observed_at=observation.observed_at,
        rule=RULE_CLOUD_COVER,
    )


def _forecast_condition(
    dt: datetime,
    forecasts: list[ForecastEntry],
    zone_name: str | None,
    *,
    night: bool,
) -> tuple[str | None, Provenance]:
    """Fall back to the nearest forecast bulletin condition."""
    nearest = nearest_forecast(dt, forecasts)
    if nearest is None or not nearest.condition:
        return None, Provenance(source=SOURCE_UNKNOWN)

    cond = nearest.condition
    if night and cond == "sunny":
        cond = "clear-night"

    return cond, Provenance(
        source=SOURCE_FORECAST,
        name=zone_name,
        observed_at=nearest.dt.isoformat(),
        rule=RULE_FORECAST,
    )
