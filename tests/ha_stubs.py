"""Lightweight stubs for Home Assistant, aiohttp, and astral when running tests offline."""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any


def install_stubs_if_needed() -> None:
    """Install minimal module stubs only for packages not present in the environment."""
    if "aiohttp" not in sys.modules:
        try:
            import aiohttp  # noqa: F401
        except ImportError:
            _install_aiohttp_stub()

    if "homeassistant" not in sys.modules:
        try:
            import homeassistant  # noqa: F401
        except ImportError:
            _install_ha_stubs()

    if "voluptuous" not in sys.modules:
        try:
            import voluptuous  # noqa: F401
        except ImportError:
            _install_vol_stub()


def _install_aiohttp_stub() -> None:
    mod = types.ModuleType("aiohttp")

    class ClientError(Exception):
        pass

    @dataclass
    class ClientTimeout:
        total: float | None = None
        connect: float | None = None

    class ClientSession:
        pass

    mod.ClientError = ClientError  # type: ignore[attr-defined]
    mod.ClientTimeout = ClientTimeout  # type: ignore[attr-defined]
    mod.ClientSession = ClientSession  # type: ignore[attr-defined]
    sys.modules["aiohttp"] = mod


def _install_vol_stub() -> None:
    mod = types.ModuleType("voluptuous")
    mod.Schema = lambda x: x  # type: ignore[attr-defined]
    mod.Required = lambda k, default=None: k  # type: ignore[attr-defined]
    mod.Optional = lambda k, default=None: k  # type: ignore[attr-defined]
    mod.In = lambda x: x  # type: ignore[attr-defined]
    sys.modules["voluptuous"] = mod


def _install_ha_stubs() -> None:
    def _pkg(name: str) -> types.ModuleType:
        m = types.ModuleType(name)
        m.__path__ = []  # type: ignore[attr-defined]
        sys.modules[name] = m
        return m

    ha = _pkg("homeassistant")
    _pkg("homeassistant.components")
    _pkg("homeassistant.helpers")

    # homeassistant.const
    ha_const = types.ModuleType("homeassistant.const")

    class Platform(StrEnum):
        WEATHER = "weather"
        SENSOR = "sensor"
        BINARY_SENSOR = "binary_sensor"
        IMAGE = "image"

    class UnitOfTemperature(StrEnum):
        CELSIUS = "°C"

    class UnitOfPressure(StrEnum):
        HPA = "hPa"

    class UnitOfSpeed(StrEnum):
        KILOMETERS_PER_HOUR = "km/h"

    class UnitOfLength(StrEnum):
        KILOMETERS = "km"
        METERS = "m"
        CENTIMETERS = "cm"

    class UnitOfPrecipitationDepth(StrEnum):
        MILLIMETERS = "mm"

    class UnitOfVolumetricFlux(StrEnum):
        MILLIMETERS_PER_HOUR = "mm/h"

    class UnitOfIrradiance(StrEnum):
        WATTS_PER_SQUARE_METER = "W/m²"

    class UnitOfVolumeFlowRate(StrEnum):
        CUBIC_METERS_PER_SECOND = "m³/s"

    class UnitOfDensity(StrEnum):
        MICROGRAMS_PER_CUBIC_METER = "µg/m³"

    ha_const.Platform = Platform  # type: ignore[attr-defined]
    ha_const.PERCENTAGE = "%"  # type: ignore[attr-defined]
    ha_const.DEGREE = "°"  # type: ignore[attr-defined]
    ha_const.UnitOfDensity = UnitOfDensity  # type: ignore[attr-defined]
    ha_const.UnitOfTemperature = UnitOfTemperature  # type: ignore[attr-defined]
    ha_const.UnitOfPressure = UnitOfPressure  # type: ignore[attr-defined]
    ha_const.UnitOfSpeed = UnitOfSpeed  # type: ignore[attr-defined]
    ha_const.UnitOfLength = UnitOfLength  # type: ignore[attr-defined]
    ha_const.UnitOfPrecipitationDepth = UnitOfPrecipitationDepth  # type: ignore[attr-defined]
    ha_const.UnitOfVolumetricFlux = UnitOfVolumetricFlux  # type: ignore[attr-defined]
    ha_const.UnitOfIrradiance = UnitOfIrradiance  # type: ignore[attr-defined]
    ha_const.UnitOfVolumeFlowRate = UnitOfVolumeFlowRate  # type: ignore[attr-defined]
    sys.modules["homeassistant.const"] = ha_const

    # homeassistant.components.frontend & homeassistant.components.http
    ha_frontend = types.ModuleType("homeassistant.components.frontend")

    def add_extra_js_url(hass: Any, url: str, es5: bool = False) -> None:
        urls = getattr(hass, "_extra_js_urls", None)
        if urls is None:
            urls = []
            hass._extra_js_urls = urls
        urls.append((url, es5))

    ha_frontend.add_extra_js_url = add_extra_js_url  # type: ignore[attr-defined]
    sys.modules["homeassistant.components.frontend"] = ha_frontend

    ha_http = types.ModuleType("homeassistant.components.http")

    @dataclass
    class StaticPathConfig:
        url_path: str
        path: str
        cache_headers: bool = True

    ha_http.StaticPathConfig = StaticPathConfig  # type: ignore[attr-defined]
    sys.modules["homeassistant.components.http"] = ha_http

    # homeassistant.core
    ha_core = types.ModuleType("homeassistant.core")

    class HomeAssistant:
        def __init__(self) -> None:
            self.data: dict[str, Any] = {}
            self.config = types.SimpleNamespace(
                language="it",
                latitude=45.4,
                longitude=11.88,
                components=set(),
            )

        async def async_add_executor_job(self, target: Any, *args: Any) -> Any:
            return target(*args)

    class ServiceCall:
        def __init__(self, data: dict[str, Any] | None = None) -> None:
            self.data = data or {}

    ha_core.HomeAssistant = HomeAssistant  # type: ignore[attr-defined]
    ha_core.ServiceCall = ServiceCall  # type: ignore[attr-defined]
    ha_core.callback = lambda fn: fn  # type: ignore[attr-defined]
    sys.modules["homeassistant.core"] = ha_core

    # homeassistant.exceptions
    ha_exc = types.ModuleType("homeassistant.exceptions")

    class HomeAssistantError(Exception):
        pass

    ha_exc.HomeAssistantError = HomeAssistantError  # type: ignore[attr-defined]
    sys.modules["homeassistant.exceptions"] = ha_exc

    # homeassistant.config_entries
    ha_ce = types.ModuleType("homeassistant.config_entries")

    class ConfigEntry:
        def __class_getitem__(cls, _item: Any) -> type[ConfigEntry]:
            return cls

        def __init__(
            self,
            entry_id: str = "entry_1",
            data: dict[str, Any] | None = None,
            options: dict[str, Any] | None = None,
        ) -> None:
            self.entry_id = entry_id
            self.data = data or {}
            self.options = options or {}
            self.runtime_data: Any = None

    class ConfigFlow:
        def __init_subclass__(cls, **kwargs: Any) -> None:
            super().__init_subclass__()

    class OptionsFlow:
        pass

    ha_ce.ConfigEntry = ConfigEntry  # type: ignore[attr-defined]
    ha_ce.ConfigFlow = ConfigFlow  # type: ignore[attr-defined]
    ha_ce.OptionsFlow = OptionsFlow  # type: ignore[attr-defined]
    ha_ce.ConfigFlowResult = dict  # type: ignore[attr-defined]
    sys.modules["homeassistant.config_entries"] = ha_ce

    # homeassistant.data_entry_flow
    ha_def = types.ModuleType("homeassistant.data_entry_flow")
    ha_def.section = lambda schema, opts=None: schema  # type: ignore[attr-defined]
    sys.modules["homeassistant.data_entry_flow"] = ha_def

    # homeassistant.util
    ha_util = types.ModuleType("homeassistant.util")
    ha_util.slugify = lambda s: "".join(c if c.isalnum() else "_" for c in s.lower()).strip("_")  # type: ignore[attr-defined]
    sys.modules["homeassistant.util"] = ha_util

    # helpers.aiohttp_client
    ha_aio = types.ModuleType("homeassistant.helpers.aiohttp_client")
    ha_aio.async_get_clientsession = lambda hass: object()  # type: ignore[attr-defined]
    sys.modules["homeassistant.helpers.aiohttp_client"] = ha_aio

    # helpers.device_registry
    ha_dr = types.ModuleType("homeassistant.helpers.device_registry")

    class DeviceEntryType(StrEnum):
        SERVICE = "service"

    class DeviceInfo(dict):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

    ha_dr.DeviceEntryType = DeviceEntryType  # type: ignore[attr-defined]
    ha_dr.DeviceInfo = DeviceInfo  # type: ignore[attr-defined]
    sys.modules["homeassistant.helpers.device_registry"] = ha_dr

    # helpers.entity_platform
    ha_ep = types.ModuleType("homeassistant.helpers.entity_platform")
    ha_ep.AddEntitiesCallback = Any  # type: ignore[attr-defined]
    sys.modules["homeassistant.helpers.entity_platform"] = ha_ep

    # helpers.event
    ha_ev = types.ModuleType("homeassistant.helpers.event")
    ha_ev.async_track_time_change = lambda *a, **kw: (lambda: None)  # type: ignore[attr-defined]
    sys.modules["homeassistant.helpers.event"] = ha_ev

    # helpers.selector
    ha_sel = types.ModuleType("homeassistant.helpers.selector")
    ha_sel.SelectSelector = lambda cfg: cfg  # type: ignore[attr-defined]
    ha_sel.SelectSelectorConfig = lambda **kw: kw  # type: ignore[attr-defined]
    ha_sel.SelectSelectorMode = types.SimpleNamespace(DROPDOWN="dropdown", LIST="list")  # type: ignore[attr-defined]
    ha_sel.NumberSelector = lambda cfg: cfg  # type: ignore[attr-defined]
    ha_sel.NumberSelectorConfig = lambda **kw: kw  # type: ignore[attr-defined]
    ha_sel.NumberSelectorMode = types.SimpleNamespace(BOX="box")  # type: ignore[attr-defined]
    sys.modules["homeassistant.helpers.selector"] = ha_sel

    # helpers.update_coordinator
    ha_uc = types.ModuleType("homeassistant.helpers.update_coordinator")

    class UpdateFailed(Exception):
        pass

    class DataUpdateCoordinator:
        def __class_getitem__(cls, _item: Any) -> type[DataUpdateCoordinator]:
            return cls

        def __init__(
            self,
            hass: Any,
            logger: Any,
            *,
            name: str,
            update_interval: timedelta | None = None,
            config_entry: Any = None,
        ) -> None:
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_interval = update_interval
            self.config_entry = config_entry
            self.data: Any = None
            self.last_update_success = True

        async def async_request_refresh(self) -> None:
            self.data = await self._async_update_data()

    class CoordinatorEntity:
        def __class_getitem__(cls, _item: Any) -> type[CoordinatorEntity]:
            return cls

        def __init__(self, coordinator: Any) -> None:
            self.coordinator = coordinator

        @property
        def available(self) -> bool:
            return bool(self.coordinator.last_update_success)

        def _handle_coordinator_update(self) -> None:
            pass

    ha_uc.UpdateFailed = UpdateFailed  # type: ignore[attr-defined]
    ha_uc.DataUpdateCoordinator = DataUpdateCoordinator  # type: ignore[attr-defined]
    ha_uc.CoordinatorEntity = CoordinatorEntity  # type: ignore[attr-defined]
    sys.modules["homeassistant.helpers.update_coordinator"] = ha_uc

    # components.weather
    ha_w = types.ModuleType("homeassistant.components.weather")

    class WeatherEntityFeature:
        FORECAST_DAILY = 1
        FORECAST_TWICE_DAILY = 4

    class WeatherEntity:
        pass

    ha_w.Forecast = dict  # type: ignore[attr-defined]
    ha_w.WeatherEntity = WeatherEntity  # type: ignore[attr-defined]
    ha_w.WeatherEntityFeature = WeatherEntityFeature  # type: ignore[attr-defined]
    sys.modules["homeassistant.components.weather"] = ha_w

    # components.sensor
    ha_s = types.ModuleType("homeassistant.components.sensor")

    class SensorDeviceClass(StrEnum):
        TEMPERATURE = "temperature"
        HUMIDITY = "humidity"
        ATMOSPHERIC_PRESSURE = "atmospheric_pressure"
        DISTANCE = "distance"
        WIND_SPEED = "wind_speed"
        WIND_DIRECTION = "wind_direction"
        IRRADIANCE = "irradiance"
        PRECIPITATION = "precipitation"
        PRECIPITATION_INTENSITY = "precipitation_intensity"
        MOISTURE = "moisture"
        PM10 = "pm10"
        PM25 = "pm25"
        OZONE = "ozone"
        VOLUME_FLOW_RATE = "volume_flow_rate"
        ENUM = "enum"

    class SensorStateClass(StrEnum):
        MEASUREMENT = "measurement"
        MEASUREMENT_ANGLE = "measurement_angle"
        TOTAL_INCREASING = "total_increasing"

    @dataclass(frozen=True, kw_only=True)
    class SensorEntityDescription:
        key: str
        translation_key: str | None = None
        device_class: Any = None
        state_class: Any = None
        native_unit_of_measurement: Any = None
        suggested_display_precision: int | None = None
        options: list[str] | None = None

    class SensorEntity:
        pass

    ha_s.SensorDeviceClass = SensorDeviceClass  # type: ignore[attr-defined]
    ha_s.SensorStateClass = SensorStateClass  # type: ignore[attr-defined]
    ha_s.SensorEntityDescription = SensorEntityDescription  # type: ignore[attr-defined]
    ha_s.SensorEntity = SensorEntity  # type: ignore[attr-defined]
    sys.modules["homeassistant.components.sensor"] = ha_s

    # components.binary_sensor
    ha_bs = types.ModuleType("homeassistant.components.binary_sensor")

    class BinarySensorDeviceClass(StrEnum):
        SAFETY = "safety"
        PROBLEM = "problem"

    @dataclass(frozen=True, kw_only=True)
    class BinarySensorEntityDescription:
        key: str
        translation_key: str | None = None
        device_class: Any = None

    class BinarySensorEntity:
        pass

    ha_bs.BinarySensorDeviceClass = BinarySensorDeviceClass  # type: ignore[attr-defined]
    ha_bs.BinarySensorEntityDescription = BinarySensorEntityDescription  # type: ignore[attr-defined]
    ha_bs.BinarySensorEntity = BinarySensorEntity  # type: ignore[attr-defined]
    sys.modules["homeassistant.components.binary_sensor"] = ha_bs

    # components.image
    ha_img = types.ModuleType("homeassistant.components.image")

    class ImageEntity:
        def __init__(self, hass: Any) -> None:
            self.hass = hass
            self._attr_image_last_updated: datetime | None = None

    ha_img.ImageEntity = ImageEntity  # type: ignore[attr-defined]
    sys.modules["homeassistant.components.image"] = ha_img

    # components.recorder
    _pkg("homeassistant.components.recorder")
    ha_rm = types.ModuleType("homeassistant.components.recorder.models")
    ha_rm.StatisticMeanType = types.SimpleNamespace(ARITHMETIC="arithmetic")  # type: ignore[attr-defined]
    ha_rm.StatisticMetaData = dict  # type: ignore[attr-defined]
    sys.modules["homeassistant.components.recorder.models"] = ha_rm

    ha_rs = types.ModuleType("homeassistant.components.recorder.statistics")
    ha_rs.async_add_external_statistics = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["homeassistant.components.recorder.statistics"] = ha_rs
    _ = ha
