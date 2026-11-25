"""Config flow, reconfigure flow, and options flow for ARPA Veneto Meteo."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import metar
from .api import ArpaVenetoApiClient, ArpaVenetoApiError, haversine_km
from .const import (
    CONF_ARCHIVE_BRIGHTNESS,
    CONF_COMUNE_ID,
    CONF_COMUNE_NAME,
    CONF_DAY_CLEAR_THRESHOLD,
    CONF_DAY_CLEAR_THRESHOLD_DEFAULT,
    CONF_DAY_CONDITION,
    CONF_DAY_CONDITION_FORECAST,
    CONF_DAY_CONDITION_METAR,
    CONF_DAY_CONDITION_RADIATION,
    CONF_DAY_CONDITION_RADIATION_OR_FORECAST,
    CONF_DAY_CONDITION_RADIATION_OR_METAR,
    CONF_DAY_CONDITION_UNKNOWN,
    CONF_DAY_PARTLY_THRESHOLD,
    CONF_DAY_PARTLY_THRESHOLD_DEFAULT,
    CONF_ENABLE_AVALANCHE,
    CONF_ENABLE_BULLETIN,
    CONF_FORECAST_LANG_AUTO,
    CONF_FORECAST_LANG_EN,
    CONF_FORECAST_LANG_IT,
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
    CONF_NIGHT_CONDITION_BRIGHTNESS,
    CONF_NIGHT_CONDITION_BRIGHTNESS_OR_FORECAST,
    CONF_NIGHT_CONDITION_FORECAST,
    CONF_NIGHT_CONDITION_METAR,
    CONF_NIGHT_CONDITION_UNKNOWN,
    CONF_NIGHT_PARTLY_THRESHOLD,
    CONF_NIGHT_PARTLY_THRESHOLD_DEFAULT,
    CONF_OZONE_STATION,
    CONF_PM10_STATION,
    CONF_PM25_STATION,
    CONF_POLLEN_STATION,
    CONF_RADAR_CONCORDIA,
    CONF_RADAR_MOSAIC,
    CONF_RADAR_NONE,
    CONF_RADAR_SOURCE,
    CONF_RADAR_TEOLO,
    CONF_SECTION_AIR_QUALITY,
    CONF_SECTION_HYDRO,
    CONF_SECTION_METAR,
    CONF_SECTION_POLLEN,
    CONF_STATION_ALTITUDE,
    CONF_STATION_ID,
    CONF_STATION_LAT,
    CONF_STATION_LON,
    CONF_STATION_NAME,
    CONF_UPDATE_INTERVAL,
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
    MAX_UPDATE_INTERVAL_MINUTES,
    MIN_UPDATE_INTERVAL_MINUTES,
    MOUNTAIN_ZONE_IDS,
    OPTION_NONE,
)
from .models import GeoStation

_LOGGER = logging.getLogger(__name__)


def _dropdown_options(mapping: dict[str, str], include_none: bool = False) -> list[dict[str, str]]:
    """Convert an id-to-label mapping into Home Assistant dropdown selector options."""
    opts: list[dict[str, str]] = []
    if include_none:
        opts.append({"value": OPTION_NONE, "label": "-"})
    opts.extend({"value": k, "label": v} for k, v in mapping.items())
    return opts


def _ensure_current_option(options: dict[str, str], current: str) -> dict[str, str]:
    """Preserve a previously configured value in a dropdown even if the catalog fetch failed."""
    if current and current != OPTION_NONE and current not in options:
        return {current: current} | options
    return options


# Optional catalogs of the options flow, in the order they are fetched: what each one lists and
# where it comes from. Sources are proper names, shown to the user as they are in every language.
_CATALOGS: tuple[tuple[str, str], ...] = (
    ("PM10 stations", "ARPAV"),
    ("PM2.5 stations", "ARPAV"),
    ("ozone stations", "ARPAV"),
    ("hydrometric stations", "ARPAV"),
    ("pollen stations", "ARPAV"),
    ("METAR aerodromes", "NOAA aviationweather.gov"),
)


def _describe_error(err: BaseException) -> str:
    """Return an exception as 'Type: message', also when the message is empty (timeouts)."""
    message = str(err)
    return f"{type(err).__name__}: {message}" if message else type(err).__name__


def _failed_catalog_sources(results: list[Any]) -> list[str]:
    """Log every catalog that could not be loaded and return their sources, each once.

    A failed catalog leaves its dropdown with only the current choice: the options form says so
    instead of showing a silently empty list, and the log keeps the reason.
    """
    failed: list[str] = []
    for (name, source), result in zip(_CATALOGS, results, strict=True):
        if isinstance(result, asyncio.CancelledError):
            raise result
        if not isinstance(result, BaseException):
            continue
        _LOGGER.warning("Unable to load %s from %s: %s", name, source, _describe_error(result))
        if source not in failed:
            failed.append(source)
    return failed


class ArpaVenetoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle initial setup and reconfiguration for ARPA Veneto Meteo."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize ephemeral flow state."""
        self._comuni: dict[int, str] = {}
        self._comune_to_zone: dict[int, int] = {}
        self._zones: dict[int, str] = {}
        self._zone_coords: dict[int, tuple[float, float]] = {}
        self._stations: dict[str, GeoStation] = {}
        self._selected_comune_id: int | None = None
        self._selected_comune_name: str = ""
        self._reconfigure_entry: config_entries.ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ArpaVenetoOptionsFlowHandler:
        """Return the options flow handler."""
        return ArpaVenetoOptionsFlowHandler()

    def _api(self) -> ArpaVenetoApiClient:
        """Return an API client backed by Home Assistant's shared HTTP session."""
        return ArpaVenetoApiClient(async_get_clientsession(self.hass))

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Step 1: choose municipality to auto-select forecast zone."""
        errors: dict[str, str] = {}

        if not self._comuni:
            try:
                self._comuni, self._comune_to_zone = await self._api().async_get_comuni()
            except ArpaVenetoApiError as err:
                _LOGGER.warning("Failed to fetch ARPAV municipalities: %s", err)
                errors["base"] = "cannot_connect"

        if user_input is not None and not errors:
            comune_id = int(user_input[CONF_COMUNE_ID])
            if comune_id not in self._comuni:
                errors[CONF_COMUNE_ID] = "invalid_comune"
            else:
                self._selected_comune_id = comune_id
                self._selected_comune_name = self._comuni[comune_id]
                return await self.async_step_station()

        comune_opts = _dropdown_options({str(k): v for k, v in self._comuni.items()})
        schema = vol.Schema(
            {
                vol.Required(CONF_COMUNE_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=comune_opts,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_station(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Step 2: confirm forecast zone and pick a distance-sorted weather station."""
        errors: dict[str, str] = {}

        preselected_zone = (
            self._comune_to_zone.get(self._selected_comune_id)
            if self._selected_comune_id is not None
            else (
                int(self._reconfigure_entry.data[CONF_ZONE_ID])
                if self._reconfigure_entry is not None
                else None
            )
        )

        if not self._zones or not self._stations:
            try:
                self._zones, self._zone_coords = await self._api().async_get_zones()
                ref_lat, ref_lon = (
                    self._zone_coords.get(preselected_zone, (None, None))
                    if preselected_zone is not None
                    else (None, None)
                )
                if ref_lat is None and self.hass.config.latitude:
                    ref_lat = self.hass.config.latitude
                    ref_lon = self.hass.config.longitude
                stations_list = await self._api().async_get_meteo_stations(ref_lat, ref_lon)
                self._stations = {st.station_id: st for st in stations_list}
            except ArpaVenetoApiError as err:
                _LOGGER.warning("Failed to fetch ARPAV zones/stations: %s", err)
                errors["base"] = "cannot_connect"

        if user_input is not None and not errors:
            zone_id = int(user_input[CONF_ZONE_ID])
            station_id_str = str(user_input[CONF_STATION_ID])
            station = self._stations.get(station_id_str)
            if station is None:
                errors[CONF_STATION_ID] = "invalid_station"
            else:
                zone_name = self._zones.get(zone_id, f"Zona {zone_id}")
                station_id = int(station_id_str)
                station_label = station.display_name()
                comune_id = (
                    self._selected_comune_id
                    if self._selected_comune_id is not None
                    else (
                        self._reconfigure_entry.data.get(CONF_COMUNE_ID)
                        if self._reconfigure_entry
                        else None
                    )
                )
                comune_name = (
                    self._selected_comune_name
                    or (
                        self._reconfigure_entry.data.get(CONF_COMUNE_NAME, zone_name)
                        if self._reconfigure_entry
                        else zone_name
                    )
                )

                entry_data = {
                    CONF_COMUNE_ID: comune_id,
                    CONF_COMUNE_NAME: comune_name,
                    CONF_ZONE_ID: zone_id,
                    CONF_ZONE_NAME: zone_name,
                    CONF_STATION_ID: station_id,
                    CONF_STATION_NAME: station_label,
                    CONF_STATION_LAT: station.latitude,
                    CONF_STATION_LON: station.longitude,
                    CONF_STATION_ALTITUDE: station.altitude,
                }
                unique_id = f"{zone_id}_{station_id}"

                if self._reconfigure_entry is not None:
                    if unique_id != self._reconfigure_entry.unique_id:
                        await self.async_set_unique_id(unique_id)
                        self._abort_if_unique_id_configured()
                        self.hass.config_entries.async_update_entry(
                            self._reconfigure_entry,
                            unique_id=unique_id,
                        )
                    return self.async_update_reload_and_abort(
                        self._reconfigure_entry,
                        title=f"{comune_name} - {station.name}",
                        data=entry_data,
                    )

                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                # Enable the avalanche bulletin automatically for mountain zones
                default_options = {
                    CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL_MINUTES,
                    CONF_FORECAST_LANGUAGE: CONF_FORECAST_LANG_AUTO,
                    CONF_INFER_CONDITION: CONF_INFER_CONDITION_AUTO,
                    CONF_DAY_CONDITION: CONF_DAY_CONDITION_RADIATION_OR_FORECAST,
                    CONF_NIGHT_CONDITION: CONF_NIGHT_CONDITION_BRIGHTNESS_OR_FORECAST,
                    CONF_RADAR_SOURCE: CONF_RADAR_MOSAIC,
                    CONF_ENABLE_BULLETIN: True,
                    CONF_ENABLE_AVALANCHE: zone_id in MOUNTAIN_ZONE_IDS,
                    CONF_ARCHIVE_BRIGHTNESS: False,
                }

                return self.async_create_entry(
                    title=f"{comune_name} - {station.name}",
                    data=entry_data,
                    options=default_options,
                )

        zone_opts = _dropdown_options({str(k): v for k, v in self._zones.items()})
        station_opts = _dropdown_options(
            {st.station_id: st.label() for st in self._stations.values()}
        )

        default_zone = (
            str(preselected_zone)
            if preselected_zone is not None and str(preselected_zone) in {o["value"] for o in zone_opts}
            else (zone_opts[0]["value"] if zone_opts else "")
        )
        default_station = (
            str(self._reconfigure_entry.data[CONF_STATION_ID])
            if self._reconfigure_entry is not None
            else (station_opts[0]["value"] if station_opts else "")
        )

        schema = vol.Schema(
            {
                vol.Required(CONF_ZONE_ID, default=default_zone): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=zone_opts,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_STATION_ID, default=default_station): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=station_opts,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="station",
            data_schema=schema,
            errors=errors,
            description_placeholders={"comune": self._selected_comune_name or "Veneto"},
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Allow reconfiguring forecast zone and weather station."""
        self._reconfigure_entry = self._get_reconfigure_entry()
        self._selected_comune_id = self._reconfigure_entry.data.get(CONF_COMUNE_ID)
        self._selected_comune_name = str(self._reconfigure_entry.data.get(CONF_COMUNE_NAME) or "")
        return await self.async_step_station(user_input)


class ArpaVenetoOptionsFlowHandler(config_entries.OptionsFlow):
    """Manage all modular options (polling, radar, alerts, AQ, hydrology, pollen, METAR)."""

    def __init__(self) -> None:
        """Initialize transient options state."""
        self._stored_options: dict[str, Any] = {}

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Show main options form with collapsible sections."""
        if user_input is not None:
            self._stored_options = dict(user_input)
            if user_input.get(CONF_INFER_CONDITION) == CONF_INFER_CONDITION_CUSTOM:
                return await self.async_step_thresholds()
            return self.async_create_entry(title="", data=self._stored_options)

        opts = self.config_entry.options
        lat = self.config_entry.data.get(CONF_STATION_LAT)
        lon = self.config_entry.data.get(CONF_STATION_LON)
        ref_lat = float(lat) if lat is not None else None
        ref_lon = float(lon) if lon is not None else None
        # A station listed without coordinates: sort from Home Assistant's location instead, so
        # the METAR catalog (which needs a position) isn't left empty
        if (ref_lat is None or ref_lon is None) and (
            self.hass.config.latitude or self.hass.config.longitude
        ):
            ref_lat = float(self.hass.config.latitude)
            ref_lon = float(self.hass.config.longitude)

        session = async_get_clientsession(self.hass)
        api = ArpaVenetoApiClient(session)

        # Fetch all optional station catalogs in parallel with graceful fallback
        catalog_tasks = [
            api.async_get_air_quality_stations("pm10", ref_lat, ref_lon),
            api.async_get_air_quality_stations("pm25", ref_lat, ref_lon),
            api.async_get_air_quality_stations("o3", ref_lat, ref_lon),
            api.async_get_hydro_stations(ref_lat, ref_lon),
            api.async_get_pollen_stations(ref_lat, ref_lon),
            (
                metar.async_fetch_stations(
                    session,
                    ref_lat,
                    ref_lon,
                    lambda a, b: haversine_km(a, b, ref_lat, ref_lon),
                )
                if ref_lat is not None and ref_lon is not None
                else asyncio.sleep(0, result=[])
            ),
        ]
        results = await asyncio.gather(*catalog_tasks, return_exceptions=True)
        failed_sources = _failed_catalog_sources(results)

        def _stations_map(res: Any) -> dict[str, str]:
            """Convert a station list result into an id-to-label map (empty when it failed)."""
            if isinstance(res, BaseException):
                return {}
            return {st.station_id: st.label() for st in res}

        def _metar_map(res: Any) -> dict[str, str]:
            """Convert a METAR aerodrome list into an ICAO-to-label map (empty when it failed)."""
            if isinstance(res, BaseException):
                return {}
            return {st.icao: st.label for st in res}

        aq_opts = opts.get(CONF_SECTION_AIR_QUALITY) or {}
        hydro_opts = opts.get(CONF_SECTION_HYDRO) or {}
        pollen_opts = opts.get(CONF_SECTION_POLLEN) or {}
        metar_opts = opts.get(CONF_SECTION_METAR) or {}

        cur_pm10 = str(aq_opts.get(CONF_PM10_STATION) or OPTION_NONE)
        cur_pm25 = str(aq_opts.get(CONF_PM25_STATION) or OPTION_NONE)
        cur_o3 = str(aq_opts.get(CONF_OZONE_STATION) or OPTION_NONE)
        cur_hydro = str(hydro_opts.get(CONF_HYDRO_STATION) or OPTION_NONE)
        cur_pollen = str(pollen_opts.get(CONF_POLLEN_STATION) or OPTION_NONE)
        cur_metar = str(metar_opts.get(CONF_METAR_STATION) or OPTION_NONE)

        pm10_map = _ensure_current_option(_stations_map(results[0]), cur_pm10)
        pm25_map = _ensure_current_option(_stations_map(results[1]), cur_pm25)
        o3_map = _ensure_current_option(_stations_map(results[2]), cur_o3)
        hydro_map = _ensure_current_option(_stations_map(results[3]), cur_hydro)
        pollen_map = _ensure_current_option(_stations_map(results[4]), cur_pollen)
        metar_map = _ensure_current_option(_metar_map(results[5]), cur_metar)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=int(opts.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MINUTES)),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_UPDATE_INTERVAL_MINUTES,
                        max=MAX_UPDATE_INTERVAL_MINUTES,
                        step=1,
                        unit_of_measurement="min",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_FORECAST_LANGUAGE,
                    default=opts.get(CONF_FORECAST_LANGUAGE, CONF_FORECAST_LANG_AUTO),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            CONF_FORECAST_LANG_AUTO,
                            CONF_FORECAST_LANG_IT,
                            CONF_FORECAST_LANG_EN,
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_FORECAST_LANGUAGE,
                    )
                ),
                vol.Optional(
                    CONF_RADAR_SOURCE,
                    default=opts.get(CONF_RADAR_SOURCE, CONF_RADAR_MOSAIC),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            CONF_RADAR_MOSAIC,
                            CONF_RADAR_TEOLO,
                            CONF_RADAR_CONCORDIA,
                            CONF_RADAR_NONE,
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_RADAR_SOURCE,
                    )
                ),
                vol.Optional(
                    CONF_ENABLE_BULLETIN,
                    default=bool(opts.get(CONF_ENABLE_BULLETIN, True)),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_AVALANCHE,
                    default=bool(opts.get(CONF_ENABLE_AVALANCHE, False)),
                ): bool,
                vol.Optional(
                    CONF_INFER_CONDITION,
                    default=opts.get(CONF_INFER_CONDITION, CONF_INFER_CONDITION_AUTO),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            CONF_INFER_CONDITION_AUTO,
                            CONF_INFER_CONDITION_CUSTOM,
                            CONF_INFER_CONDITION_DISABLED,
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_INFER_CONDITION,
                    )
                ),
                vol.Optional(
                    CONF_DAY_CONDITION,
                    default=opts.get(CONF_DAY_CONDITION, CONF_DAY_CONDITION_RADIATION_OR_FORECAST),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            CONF_DAY_CONDITION_RADIATION_OR_FORECAST,
                            CONF_DAY_CONDITION_RADIATION,
                            CONF_DAY_CONDITION_RADIATION_OR_METAR,
                            CONF_DAY_CONDITION_METAR,
                            CONF_DAY_CONDITION_FORECAST,
                            CONF_DAY_CONDITION_UNKNOWN,
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_DAY_CONDITION,
                    )
                ),
                vol.Optional(
                    CONF_NIGHT_CONDITION,
                    default=opts.get(
                        CONF_NIGHT_CONDITION,
                        CONF_NIGHT_CONDITION_BRIGHTNESS_OR_FORECAST,
                    ),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            CONF_NIGHT_CONDITION_BRIGHTNESS_OR_FORECAST,
                            CONF_NIGHT_CONDITION_BRIGHTNESS,
                            CONF_NIGHT_CONDITION_METAR,
                            CONF_NIGHT_CONDITION_FORECAST,
                            CONF_NIGHT_CONDITION_UNKNOWN,
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_NIGHT_CONDITION,
                    )
                ),
                vol.Optional(
                    CONF_ARCHIVE_BRIGHTNESS,
                    default=bool(opts.get(CONF_ARCHIVE_BRIGHTNESS, False)),
                ): bool,
                vol.Required(CONF_SECTION_AIR_QUALITY): section(
                    vol.Schema(
                        {
                            vol.Optional(
                                CONF_PM10_STATION, default=cur_pm10
                            ): selector.SelectSelector(
                                selector.SelectSelectorConfig(
                                    options=_dropdown_options(pm10_map, include_none=True),
                                    mode=selector.SelectSelectorMode.DROPDOWN,
                                )
                            ),
                            vol.Optional(
                                CONF_PM25_STATION, default=cur_pm25
                            ): selector.SelectSelector(
                                selector.SelectSelectorConfig(
                                    options=_dropdown_options(pm25_map, include_none=True),
                                    mode=selector.SelectSelectorMode.DROPDOWN,
                                )
                            ),
                            vol.Optional(
                                CONF_OZONE_STATION, default=cur_o3
                            ): selector.SelectSelector(
                                selector.SelectSelectorConfig(
                                    options=_dropdown_options(o3_map, include_none=True),
                                    mode=selector.SelectSelectorMode.DROPDOWN,
                                )
                            ),
                        }
                    ),
                    {"collapsed": True},
                ),
                vol.Required(CONF_SECTION_HYDRO): section(
                    vol.Schema(
                        {
                            vol.Optional(
                                CONF_HYDRO_STATION, default=cur_hydro
                            ): selector.SelectSelector(
                                selector.SelectSelectorConfig(
                                    options=_dropdown_options(hydro_map, include_none=True),
                                    mode=selector.SelectSelectorMode.DROPDOWN,
                                )
                            ),
                        }
                    ),
                    {"collapsed": True},
                ),
                vol.Required(CONF_SECTION_POLLEN): section(
                    vol.Schema(
                        {
                            vol.Optional(
                                CONF_POLLEN_STATION, default=cur_pollen
                            ): selector.SelectSelector(
                                selector.SelectSelectorConfig(
                                    options=_dropdown_options(pollen_map, include_none=True),
                                    mode=selector.SelectSelectorMode.DROPDOWN,
                                )
                            ),
                        }
                    ),
                    {"collapsed": True},
                ),
                vol.Required(CONF_SECTION_METAR): section(
                    vol.Schema(
                        {
                            vol.Optional(
                                CONF_METAR_STATION, default=cur_metar
                            ): selector.SelectSelector(
                                selector.SelectSelectorConfig(
                                    options=_dropdown_options(metar_map, include_none=True),
                                    mode=selector.SelectSelectorMode.DROPDOWN,
                                )
                            ),
                            vol.Optional(
                                CONF_METAR_FILL_MISSING,
                                default=bool(metar_opts.get(CONF_METAR_FILL_MISSING, True)),
                            ): bool,
                        }
                    ),
                    {"collapsed": True},
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors={"base": "catalog_unavailable"} if failed_sources else {},
            description_placeholders=(
                {"sources": ", ".join(failed_sources)} if failed_sources else None
            ),
        )

    async def async_step_thresholds(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Configure custom sky condition thresholds."""
        if user_input is not None:
            self._stored_options.update(user_input)
            return self.async_create_entry(title="", data=self._stored_options)

        opts = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_DAY_CLEAR_THRESHOLD,
                    default=float(
                        opts.get(CONF_DAY_CLEAR_THRESHOLD, CONF_DAY_CLEAR_THRESHOLD_DEFAULT)
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=1, step=0.01, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_DAY_PARTLY_THRESHOLD,
                    default=float(
                        opts.get(CONF_DAY_PARTLY_THRESHOLD, CONF_DAY_PARTLY_THRESHOLD_DEFAULT)
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=1, step=0.01, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_NIGHT_CLEAR_THRESHOLD,
                    default=float(
                        opts.get(CONF_NIGHT_CLEAR_THRESHOLD, CONF_NIGHT_CLEAR_THRESHOLD_DEFAULT)
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=50, step=0.5, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_NIGHT_PARTLY_THRESHOLD,
                    default=float(
                        opts.get(CONF_NIGHT_PARTLY_THRESHOLD, CONF_NIGHT_PARTLY_THRESHOLD_DEFAULT)
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=50, step=0.5, mode=selector.NumberSelectorMode.BOX
                    )
                ),
            }
        )
        return self.async_show_form(step_id="thresholds", data_schema=schema)
