"""DataUpdateCoordinator with tiered TTL caching and graceful partial degradation."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import metar
from .api import ArpaVenetoApiClient, ArpaVenetoApiError, select_bulletin_code_for_zone
from .conditions import async_classify_condition, nearest_forecast
from .const import (
    AIR_QUALITY_CACHE_TTL,
    AVALANCHE_CACHE_TTL,
    BRIGHTNESS_MAX_STATIONS,
    BRIGHTNESS_STATIONS_CACHE_TTL,
    BULLETIN_CACHE_TTL,
    CONF_DAY_CLEAR_THRESHOLD,
    CONF_DAY_CLEAR_THRESHOLD_DEFAULT,
    CONF_DAY_CONDITION,
    CONF_DAY_CONDITION_RADIATION_OR_FORECAST,
    CONF_DAY_PARTLY_THRESHOLD,
    CONF_DAY_PARTLY_THRESHOLD_DEFAULT,
    CONF_ENABLE_AVALANCHE,
    CONF_ENABLE_BULLETIN,
    CONF_FORECAST_LANG_AUTO,
    CONF_FORECAST_LANGUAGE,
    CONF_HYDRO_STATION,
    CONF_INFER_CONDITION,
    CONF_INFER_CONDITION_AUTO,
    CONF_INFER_CONDITION_CUSTOM,
    CONF_INFER_CONDITION_DISABLED,
    CONF_METAR_FILL_MISSING,
    CONF_METAR_STATION,
    CONF_NIGHT_CLEAR_THRESHOLD,
    CONF_NIGHT_CLEAR_THRESHOLD_DEFAULT,
    CONF_NIGHT_CONDITION,
    CONF_NIGHT_CONDITION_BRIGHTNESS_OR_FORECAST,
    CONF_NIGHT_PARTLY_THRESHOLD,
    CONF_NIGHT_PARTLY_THRESHOLD_DEFAULT,
    CONF_OZONE_STATION,
    CONF_PM10_STATION,
    CONF_PM25_STATION,
    CONF_POLLEN_STATION,
    CONF_RADAR_MOSAIC,
    CONF_RADAR_SOURCE,
    CONF_SECTION_AIR_QUALITY,
    CONF_SECTION_HYDRO,
    CONF_SECTION_METAR,
    CONF_SECTION_POLLEN,
    CONF_STATION_ID,
    CONF_STATION_LAT,
    CONF_STATION_LON,
    CONF_STATION_NAME,
    CONF_UPDATE_INTERVAL,
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
    FORECAST_CACHE_TTL,
    OPTION_NONE,
    POLLEN_CACHE_TTL,
    SOURCE_AIR_QUALITY,
    SOURCE_FORECAST,
    SOURCE_HYDRO,
    SOURCE_METAR,
    SOURCE_SUMMARY_24H,
)
from .models import (
    AirQualityData,
    ArpaVenetoData,
    AvalancheBulletin,
    BulletinSummary,
    DayThresholds,
    ForecastEntry,
    GeoStation,
    HydroReading,
    MetarObservation,
    NightThresholds,
    PollenReport,
    Provenance,
    SkyBrightnessReading,
    StationObservation,
    StationSummary24h,
)

_LOGGER = logging.getLogger(__name__)


def _opt_station_int(section_dict: dict[str, Any], key: str) -> int | None:
    """Return an integer station ID from an options section, or None if unset."""
    val = section_dict.get(key)
    if val in (None, "", OPTION_NONE, "None"):
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _opt_station_str(section_dict: dict[str, Any], key: str) -> str | None:
    """Return a string station code from an options section, or None if unset."""
    val = section_dict.get(key)
    if val in (None, "", OPTION_NONE, "None"):
        return None
    return str(val).strip() or None


class ArpaVenetoDataUpdateCoordinator(DataUpdateCoordinator[ArpaVenetoData]):
    """Coordinator fetching and aggregating all configured ARPA Veneto sources."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator and its tiered caches."""
        self.config_entry = config_entry
        self.session = async_get_clientsession(hass)
        self.api = ArpaVenetoApiClient(self.session)

        data = config_entry.data
        options = config_entry.options

        self.station_id: int = int(data[CONF_STATION_ID])
        self.station_name: str = str(data.get(CONF_STATION_NAME) or self.station_id)
        self.zone_id: int = int(data[CONF_ZONE_ID])
        self.zone_name: str = str(data.get(CONF_ZONE_NAME) or f"Zona {self.zone_id}")
        self.latitude: float | None = (
            float(data[CONF_STATION_LAT]) if data.get(CONF_STATION_LAT) is not None else None
        )
        self.longitude: float | None = (
            float(data[CONF_STATION_LON]) if data.get(CONF_STATION_LON) is not None else None
        )

        # General options
        interval_min = int(options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MINUTES))
        self.forecast_language_opt: str = str(
            options.get(CONF_FORECAST_LANGUAGE, CONF_FORECAST_LANG_AUTO)
        )
        self.infer_condition: str = str(
            options.get(CONF_INFER_CONDITION, CONF_INFER_CONDITION_AUTO)
        )
        self.day_condition: str = str(
            options.get(CONF_DAY_CONDITION, CONF_DAY_CONDITION_RADIATION_OR_FORECAST)
        )
        self.night_condition: str = str(
            options.get(CONF_NIGHT_CONDITION, CONF_NIGHT_CONDITION_BRIGHTNESS_OR_FORECAST)
        )
        self.enable_bulletin: bool = bool(options.get(CONF_ENABLE_BULLETIN, True))
        self.enable_avalanche: bool = bool(options.get(CONF_ENABLE_AVALANCHE, False))
        self.radar_source: str = str(options.get(CONF_RADAR_SOURCE, CONF_RADAR_MOSAIC))

        # Section options
        aq_opts = options.get(CONF_SECTION_AIR_QUALITY) or {}
        self.pm10_station_id = _opt_station_int(aq_opts, CONF_PM10_STATION)
        self.pm25_station_id = _opt_station_int(aq_opts, CONF_PM25_STATION)
        self.ozone_station_id = _opt_station_int(aq_opts, CONF_OZONE_STATION)

        hydro_opts = options.get(CONF_SECTION_HYDRO) or {}
        self.hydro_station_id = _opt_station_int(hydro_opts, CONF_HYDRO_STATION)

        pollen_opts = options.get(CONF_SECTION_POLLEN) or {}
        self.pollen_station_code = _opt_station_str(pollen_opts, CONF_POLLEN_STATION)

        metar_opts = options.get(CONF_SECTION_METAR) or {}
        self.metar_station = _opt_station_str(metar_opts, CONF_METAR_STATION)
        self.metar_fill_missing: bool = bool(metar_opts.get(CONF_METAR_FILL_MISSING, True))

        # Tiered caches (value, fetched_at_utc)
        self._forecast_cache: tuple[list[ForecastEntry], datetime] | None = None
        self._bulletin_cache: tuple[BulletinSummary | None, datetime] | None = None
        self._aq_cache: tuple[AirQualityData, datetime] | None = None
        self._avalanche_cache: tuple[AvalancheBulletin, datetime] | None = None
        self._pollen_cache: tuple[PollenReport | None, datetime] | None = None
        self._brightness_stations_cache: tuple[list[GeoStation], datetime] | None = None
        self._metar_obs: MetarObservation | None = None
        self._metar_fetched_at: datetime | None = None

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{self.station_id}",
            update_interval=timedelta(minutes=interval_min),
        )

    def clear_caches(self) -> None:
        """Invalidate all tiered caches so the next refresh reloads every source."""
        self._forecast_cache = None
        self._bulletin_cache = None
        self._aq_cache = None
        self._avalanche_cache = None
        self._pollen_cache = None
        self._brightness_stations_cache = None
        self._metar_fetched_at = None

    async def async_force_refresh(self) -> None:
        """Invalidate caches and request an immediate refresh."""
        self.clear_caches()
        await self.async_request_refresh()

    @property
    def resolved_forecast_language(self) -> str:
        """Resolve `auto` forecast language against Home Assistant's configured language."""
        if self.forecast_language_opt != CONF_FORECAST_LANG_AUTO:
            return self.forecast_language_opt
        ha_lang = (getattr(self.hass.config, "language", None) or "it").lower()
        return "it" if ha_lang.startswith("it") else "en"

    @staticmethod
    def _is_fresh(cache: tuple[Any, datetime] | None, ttl: timedelta, now: datetime) -> bool:
        """Return True if a cached entry exists and is younger than its TTL."""
        return cache is not None and (now - cache[1]) < ttl

    async def _async_update_data(self) -> ArpaVenetoData:
        """Fetch due tiers in parallel and assemble a clean ArpaVenetoData snapshot."""
        now = datetime.now(UTC)
        _LOGGER.debug(
            "Updating ARPA Veneto Meteo data for station=%s zone=%s",
            self.station_id,
            self.zone_id,
        )

        # Build parallel task dictionary for every tier due on this tick
        tasks: dict[str, asyncio.Future[Any] | Any] = {
            "station": self.api.async_get_station_observations(self.station_id),
            "ultime24": self.api.async_get_ultime24ore(),
        }

        if not self._is_fresh(self._forecast_cache, FORECAST_CACHE_TTL, now):
            tasks["forecast"] = self.api.async_get_forecast_symbols(
                self.zone_id,
                language=self.resolved_forecast_language,
            )

        if self.enable_bulletin and not self._is_fresh(
            self._bulletin_cache, BULLETIN_CACHE_TTL, now
        ):
            bulletin_code = select_bulletin_code_for_zone(self.zone_id)
            tasks["bulletin"] = self.api.async_get_bulletin_text(bulletin_code)

        if any((self.pm10_station_id, self.pm25_station_id, self.ozone_station_id)) and (
            not self._is_fresh(self._aq_cache, AIR_QUALITY_CACHE_TTL, now)
        ):
            tasks["air_quality"] = self.api.async_get_air_quality_for_stations(
                pm10_station_id=self.pm10_station_id,
                pm25_station_id=self.pm25_station_id,
                ozone_station_id=self.ozone_station_id,
            )

        if self.hydro_station_id is not None:
            tasks["hydro"] = self.api.async_get_hydro_reading(self.hydro_station_id)

        if self.enable_avalanche and not self._is_fresh(
            self._avalanche_cache, AVALANCHE_CACHE_TTL, now
        ):
            tasks["avalanche"] = self.api.async_get_avalanche_bulletin()

        if self.pollen_station_code and not self._is_fresh(
            self._pollen_cache, POLLEN_CACHE_TTL, now
        ):
            tasks["pollen"] = self.api.async_get_pollen_report(self.pollen_station_code)

        if self.metar_station and (
            self._metar_fetched_at is None
            or (now - self._metar_fetched_at) >= metar.MIN_FETCH_INTERVAL
        ):
            tasks["metar"] = metar.async_fetch_observation(self.session, self.metar_station)

        keys = list(tasks.keys())
        raw_results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        results = dict(zip(keys, raw_results, strict=True))

        # Primary station observation (required)
        station_res = results["station"]
        if isinstance(station_res, BaseException):
            raise UpdateFailed(
                f"Failed to fetch ARPA Veneto station {self.station_id}: {station_res}"
            ) from station_res
        station_obs: StationObservation = station_res

        # 24h summary (optional enrichment)
        summary_24h: StationSummary24h | None = None
        u24_res = results.get("ultime24")
        if isinstance(u24_res, BaseException):
            _LOGGER.warning("Unable to fetch 24h summary (meteo_ultime24ore): %s", u24_res)
            summary_24h = self.data.summary_24h if self.data else None
        elif isinstance(u24_res, dict):
            summary_24h = u24_res.get(self.station_id)

        # Forecast symbols (cached 30m)
        forecasts: list[ForecastEntry]
        if "forecast" in results:
            fc_res = results["forecast"]
            if isinstance(fc_res, BaseException):
                _LOGGER.warning("Unable to fetch forecast for zone %s: %s", self.zone_id, fc_res)
                forecasts = self._forecast_cache[0] if self._forecast_cache else []
            else:
                forecasts = fc_res
                self._forecast_cache = (forecasts, now)
        else:
            forecasts = self._forecast_cache[0] if self._forecast_cache else []

        # Textual bulletin & weather alerts (cached 30m)
        bulletin: BulletinSummary | None = None
        if self.enable_bulletin:
            if "bulletin" in results:
                b_res = results["bulletin"]
                if isinstance(b_res, BaseException):
                    _LOGGER.warning("Unable to fetch textual weather bulletin: %s", b_res)
                    bulletin = self._bulletin_cache[0] if self._bulletin_cache else None
                elif b_res is not None:
                    bulletin = b_res
                    self._bulletin_cache = (bulletin, now)
                else:
                    bulletin = self._bulletin_cache[0] if self._bulletin_cache else None
            else:
                bulletin = self._bulletin_cache[0] if self._bulletin_cache else None

        # Air quality (cached 30m)
        air_quality: AirQualityData | None = None
        if any((self.pm10_station_id, self.pm25_station_id, self.ozone_station_id)):
            if "air_quality" in results:
                aq_res = results["air_quality"]
                if isinstance(aq_res, BaseException):
                    _LOGGER.warning("Unable to fetch air quality data: %s", aq_res)
                    air_quality = self._aq_cache[0] if self._aq_cache else None
                else:
                    air_quality = aq_res
                    self._aq_cache = (air_quality, now)
            else:
                air_quality = self._aq_cache[0] if self._aq_cache else None

        # Hydrology (optional)
        hydro: HydroReading | None = None
        if self.hydro_station_id is not None:
            h_res = results.get("hydro")
            if isinstance(h_res, BaseException):
                _LOGGER.warning(
                    "Unable to fetch hydrology data for station %s: %s",
                    self.hydro_station_id,
                    h_res,
                )
                hydro = self.data.hydro if self.data else None
            else:
                hydro = h_res

        # Avalanche bulletin (cached 3h)
        avalanche: AvalancheBulletin | None = None
        if self.enable_avalanche:
            if "avalanche" in results:
                av_res = results["avalanche"]
                if isinstance(av_res, BaseException):
                    _LOGGER.warning("Unable to fetch avalanche bulletin: %s", av_res)
                    avalanche = self._avalanche_cache[0] if self._avalanche_cache else None
                else:
                    avalanche = av_res
                    self._avalanche_cache = (avalanche, now)
            else:
                avalanche = self._avalanche_cache[0] if self._avalanche_cache else None

        # Pollen report (cached 6h)
        pollen: PollenReport | None = None
        if self.pollen_station_code:
            if "pollen" in results:
                p_res = results["pollen"]
                if isinstance(p_res, BaseException):
                    _LOGGER.warning("Unable to fetch pollen report: %s", p_res)
                    pollen = self._pollen_cache[0] if self._pollen_cache else None
                elif p_res is not None:
                    pollen = p_res
                    self._pollen_cache = (pollen, now)
                else:
                    pollen = self._pollen_cache[0] if self._pollen_cache else None
            else:
                pollen = self._pollen_cache[0] if self._pollen_cache else None

        # METAR observation (self-throttled >= 10m)
        if "metar" in results:
            self._metar_fetched_at = now
            m_res = results["metar"]
            if not isinstance(m_res, BaseException) and m_res is not None:
                self._metar_obs = m_res
        active_metar = (
            self._metar_obs if metar.is_observation_current(self._metar_obs, now) else None
        )

        # Assemble unified sensors dictionary + provenance
        sensors: dict[str, Any] = dict(station_obs.values)
        sources: dict[str, Provenance] = dict(station_obs.sources)

        if summary_24h is not None:
            self._merge_summary_24h(sensors, sources, summary_24h)

        if air_quality is not None:
            self._merge_air_quality(sensors, sources, air_quality)

        if hydro is not None:
            self._merge_hydro(sensors, sources, hydro)

        if active_metar is not None and self.metar_fill_missing:
            for key, val in active_metar.values.items():
                if val is not None and sensors.get(key) is None:
                    sensors[key] = val
                    sources[key] = Provenance(
                        source=SOURCE_METAR,
                        name=active_metar.name,
                        observed_at=active_metar.observed_at,
                    )

        # Forecast-derived values (precipitation probability, snow line)
        nearest_fc = nearest_forecast(now, forecasts)
        if nearest_fc is not None:
            if nearest_fc.precipitation_probability is not None:
                sensors["precipitation_probability"] = nearest_fc.precipitation_probability
                sources["precipitation_probability"] = Provenance(
                    source=SOURCE_FORECAST,
                    name=self.zone_name,
                    observed_at=nearest_fc.dt.isoformat(),
                )
            if nearest_fc.snow_line:
                sensors["snow_line"] = nearest_fc.snow_line
                sources["snow_line"] = Provenance(
                    source=SOURCE_FORECAST,
                    name=self.zone_name,
                    observed_at=nearest_fc.dt.isoformat(),
                )

        # Infer current sky condition
        if self.infer_condition != CONF_INFER_CONDITION_DISABLED:
            day_th, night_th = self._thresholds()
            ref_dt = station_obs.observed_at or now
            cond, cond_prov = await async_classify_condition(
                latitude=self.latitude,
                longitude=self.longitude,
                dt=ref_dt,
                sensors=sensors,
                sources=sources,
                forecasts=forecasts,
                zone_name=self.zone_name,
                day_strategy=self.day_condition,
                night_strategy=self.night_condition,
                day_thresholds=day_th,
                night_thresholds=night_th,
                metar_obs=active_metar,
                fetch_brightness=self._async_nearest_brightness_reading,
            )
            sensors["condition"] = cond
            sources["condition"] = cond_prov

        available_keys = frozenset(k for k, v in sensors.items() if v is not None)

        return ArpaVenetoData(
            sensors=sensors,
            sources=sources,
            available_sensors=available_keys,
            station_name=station_obs.station_name or self.station_name,
            observed_at=station_obs.observed_at_iso,
            measured_temp_date=station_obs.measured_temp_date,
            measured_temp_min=station_obs.measured_temp_min,
            measured_temp_max=station_obs.measured_temp_max,
            summary_24h=summary_24h,
            forecast=forecasts,
            bulletin=bulletin,
            air_quality=air_quality,
            hydro=hydro,
            avalanche=avalanche,
            pollen=pollen,
            metar=active_metar,
            last_update=now.isoformat(),
        )

    def _thresholds(self) -> tuple[DayThresholds, NightThresholds]:
        """Return configured or default condition thresholds."""
        if self.infer_condition != CONF_INFER_CONDITION_CUSTOM:
            return DayThresholds(), NightThresholds()

        opts = self.config_entry.options
        return (
            DayThresholds(
                clear=float(opts.get(CONF_DAY_CLEAR_THRESHOLD, CONF_DAY_CLEAR_THRESHOLD_DEFAULT)),
                partly_cloudy=float(
                    opts.get(CONF_DAY_PARTLY_THRESHOLD, CONF_DAY_PARTLY_THRESHOLD_DEFAULT)
                ),
            ),
            NightThresholds(
                clear=float(
                    opts.get(CONF_NIGHT_CLEAR_THRESHOLD, CONF_NIGHT_CLEAR_THRESHOLD_DEFAULT)
                ),
                partly_cloudy=float(
                    opts.get(CONF_NIGHT_PARTLY_THRESHOLD, CONF_NIGHT_PARTLY_THRESHOLD_DEFAULT)
                ),
            ),
        )

    @staticmethod
    def _merge_summary_24h(
        sensors: dict[str, Any],
        sources: dict[str, Provenance],
        summary: StationSummary24h,
    ) -> None:
        """Merge 24h extremes, wind gust, snow depth fallback, and comfort indices."""
        prov = Provenance(
            source=SOURCE_SUMMARY_24H,
            name=summary.station_name,
            observed_at=summary.updated_at,
        )
        mapping = {
            "temperature_min_24h": summary.temp_min,
            "temperature_max_24h": summary.temp_max,
            "wind_speed_max_24h": summary.wind_speed_max_kmh,
            "wind_gust_24h": summary.wind_gust_kmh,
        }
        for key, val in mapping.items():
            if val is not None:
                sensors[key] = val
                sources[key] = prov

        # Apparent temperature: prefer windchill when cold, humidex when warm
        apparent = summary.windchill if summary.windchill is not None else summary.humidex
        if apparent is not None:
            sensors["apparent_temperature"] = round(apparent, 1)
            sources["apparent_temperature"] = prov

        if summary.snow_depth_cm is not None and sensors.get("snow_depth") is None:
            sensors["snow_depth"] = summary.snow_depth_cm
            sources["snow_depth"] = prov

    @staticmethod
    def _merge_air_quality(
        sensors: dict[str, Any],
        sources: dict[str, Provenance],
        aq: AirQualityData,
    ) -> None:
        """Merge validated hourly and daily air quality readings."""
        entries = (
            ("pm10_hourly", aq.pm10_hourly, aq.pm10_station_name, aq.pm10_hourly_at),
            ("pm10_daily", aq.pm10_daily, aq.pm10_station_name, aq.pm10_daily_at),
            ("pm25_hourly", aq.pm25_hourly, aq.pm25_station_name, aq.pm25_hourly_at),
            ("pm25_daily", aq.pm25_daily, aq.pm25_station_name, aq.pm25_daily_at),
            ("ozone", aq.ozone_hourly, aq.ozone_station_name, aq.ozone_hourly_at),
        )
        for key, val, st_name, obs_at in entries:
            if val is not None:
                sensors[key] = val
                sources[key] = Provenance(
                    source=SOURCE_AIR_QUALITY,
                    name=st_name,
                    observed_at=obs_at,
                )

    @staticmethod
    def _merge_hydro(
        sensors: dict[str, Any],
        sources: dict[str, Provenance],
        hydro: HydroReading,
    ) -> None:
        """Merge configured hydrometric station level and discharge."""
        prov = Provenance(
            source=SOURCE_HYDRO,
            name=hydro.station_name,
            observed_at=hydro.observed_at,
        )
        if hydro.level_m is not None:
            sensors["river_level"] = hydro.level_m
            sources["river_level"] = prov
        if hydro.discharge_m3s is not None:
            sensors["river_discharge"] = hydro.discharge_m3s
            sources["river_discharge"] = prov

    async def _async_nearest_brightness_reading(self) -> SkyBrightnessReading | None:
        """Fetch a fresh night sky brightness reading from the closest reporting station."""
        if self.latitude is None or self.longitude is None:
            return None

        now = datetime.now(UTC)
        if not self._is_fresh(self._brightness_stations_cache, BRIGHTNESS_STATIONS_CACHE_TTL, now):
            try:
                stations = await self.api.async_get_brightness_stations(
                    self.latitude, self.longitude
                )
                self._brightness_stations_cache = (stations, now)
            except ArpaVenetoApiError as err:
                _LOGGER.debug("Unable to fetch brightness station list: %s", err)
                return None

        stations = self._brightness_stations_cache[0] if self._brightness_stations_cache else []
        for st in stations[:BRIGHTNESS_MAX_STATIONS]:
            try:
                reading = await self.api.async_get_station_brightness(
                    int(st.station_id),
                    station_name=st.name,
                )
            except ArpaVenetoApiError as err:
                _LOGGER.debug("Unable to fetch brightness from %s: %s", st.station_id, err)
                continue
            if reading is not None:
                return reading

        return None
