"""Constants for the ARPA Veneto Meteo integration."""

from __future__ import annotations

from datetime import timedelta, timezone

DOMAIN = "arpa_veneto_meteo"

ATTRIBUTION = "Data provided by ARPA Veneto (CC BY 4.0)"
ATTRIBUTION_METAR = (
    "Data provided by ARPA Veneto (CC BY 4.0), "
    "METAR by NOAA Aviation Weather Center"
)

# ARPAV API and resource base URLs
API_REST_BASE = "https://api.arpa.veneto.it/REST/v1"
PORTAL_BASE = "https://meteo.arpa.veneto.it"
WWW_BASE = "https://www.arpa.veneto.it"

# Radar & static resource URLs
RADAR_MOSAIC_PNG_URL = f"{PORTAL_BASE}/meteo/radar/imgs_geo/mosaico_mbasemax_G.png"
AVALANCHE_XML_URL = f"{PORTAL_BASE}/meteo/bollettini_nv/it/xml/dolomiti_nevevalanghe.xml"
POLLEN_INDEX_URL = f"{WWW_BASE}/risorse/data-meteo/pollini/pollini.json"
POLLEN_DATA_BASE_URL = f"{WWW_BASE}/risorse/data-meteo/pollini"

# ARPAV timestamps are always fixed solar time (UTC+1) all year round
ARPAV_TZ = timezone(timedelta(hours=1))
LOCAL_TIMEZONE_NAME = "Europe/Rome"

# HTTP configuration
DEFAULT_HTTP_TIMEOUT = 20.0
DEFAULT_CONNECT_TIMEOUT = 10.0

# Coordinator update intervals & tiered cache TTLs
DEFAULT_UPDATE_INTERVAL_MINUTES = 10
MIN_UPDATE_INTERVAL_MINUTES = 5
MAX_UPDATE_INTERVAL_MINUTES = 60

FORECAST_CACHE_TTL = timedelta(minutes=30)
BULLETIN_CACHE_TTL = timedelta(minutes=30)
AIR_QUALITY_CACHE_TTL = timedelta(minutes=30)
AVALANCHE_CACHE_TTL = timedelta(hours=3)
POLLEN_CACHE_TTL = timedelta(hours=6)
BRIGHTNESS_STATIONS_CACHE_TTL = timedelta(hours=12)
RADAR_MIN_FETCH_INTERVAL = timedelta(minutes=5)

# Night sky brightness parameters
BRIGHTNESS_MAX_STATIONS = 5
BRIGHTNESS_MAX_AGE_HOURS = 6
BRIGHTNESS_ARCHIVE_HOUR = 11
BRIGHTNESS_ARCHIVE_MINUTE = 15

# Air quality API parameter codes and EU/ARPAV statutory thresholds
AQ_PARAM_OZONE = 7
AQ_PARAM_PM10 = 25
AQ_PARAM_PM25 = 39
AQ_MIN_VALID_FLAG = 9
# Broken/duplicate sensor excluded by ARPAV's official web client
AQ_EXCLUDED_CODSEQS: frozenset[int] = frozenset({500014236})
AQ_PM10_DAILY_LIMIT = 50.0  # µg/m³ daily mean limit
AQ_OZONE_INFO_THRESHOLD = 180.0  # µg/m³ hourly information threshold

# Forecast zone classification
# Zone IDs >= 100 are internal map overlay markers (ADRIATICO, EXTRA_*, TEMP_*, VCOSTA_*)
MAX_REAL_ZONE_ID = 99
MOUNTAIN_ZONE_IDS: frozenset[int] = frozenset({1, 2, 3, 4, 8})

# Config entry data keys
CONF_COMUNE_ID = "comune_id"
CONF_COMUNE_NAME = "comune_name"
CONF_ZONE_ID = "zone_id"
CONF_ZONE_NAME = "zone_name"
CONF_STATION_ID = "station_id"
CONF_STATION_NAME = "station_name"
CONF_STATION_LAT = "station_latitude"
CONF_STATION_LON = "station_longitude"
CONF_STATION_ALTITUDE = "station_altitude"

# Options keys
CONF_UPDATE_INTERVAL = "update_interval"
CONF_FORECAST_LANGUAGE = "forecast_language"
CONF_FORECAST_LANG_AUTO = "auto"
CONF_FORECAST_LANG_IT = "it"
CONF_FORECAST_LANG_EN = "en"

CONF_INFER_CONDITION = "infer_condition"
CONF_INFER_CONDITION_AUTO = "auto"
CONF_INFER_CONDITION_CUSTOM = "custom_thresholds"
CONF_INFER_CONDITION_DISABLED = "disabled"

CONF_DAY_CLEAR_THRESHOLD = "day_clear_threshold"
CONF_DAY_CLEAR_THRESHOLD_DEFAULT = 0.75
CONF_DAY_PARTLY_THRESHOLD = "day_partly_threshold"
CONF_DAY_PARTLY_THRESHOLD_DEFAULT = 0.40
CONF_NIGHT_CLEAR_THRESHOLD = "night_clear_threshold"
CONF_NIGHT_CLEAR_THRESHOLD_DEFAULT = 20.5
CONF_NIGHT_PARTLY_THRESHOLD = "night_partly_threshold"
CONF_NIGHT_PARTLY_THRESHOLD_DEFAULT = 18.5

CONF_DAY_CONDITION = "day_condition"
CONF_DAY_CONDITION_RADIATION = "radiation"
CONF_DAY_CONDITION_RADIATION_OR_METAR = "radiation_or_metar"
CONF_DAY_CONDITION_RADIATION_OR_FORECAST = "radiation_or_forecast"
CONF_DAY_CONDITION_METAR = "metar"
CONF_DAY_CONDITION_FORECAST = "forecast"
CONF_DAY_CONDITION_UNKNOWN = "unknown"

CONF_NIGHT_CONDITION = "night_condition"
CONF_NIGHT_CONDITION_BRIGHTNESS_OR_FORECAST = "brightness_or_forecast"
CONF_NIGHT_CONDITION_BRIGHTNESS = "brightness"
CONF_NIGHT_CONDITION_METAR = "metar"
CONF_NIGHT_CONDITION_FORECAST = "forecast"
CONF_NIGHT_CONDITION_UNKNOWN = "unknown"

CONF_RADAR_SOURCE = "radar_source"
CONF_RADAR_NONE = "none"
CONF_RADAR_MOSAIC = "mosaic"
CONF_RADAR_TEOLO = "teolo"
CONF_RADAR_CONCORDIA = "concordia"

CONF_ENABLE_BULLETIN = "enable_bulletin"
CONF_ENABLE_AVALANCHE = "enable_avalanche"
CONF_ARCHIVE_BRIGHTNESS = "archive_brightness"

# Collapsible option sections
CONF_SECTION_METAR = "metar"
CONF_METAR_STATION = "metar_station"
CONF_METAR_FILL_MISSING = "metar_fill_missing"

CONF_SECTION_AIR_QUALITY = "air_quality"
CONF_PM10_STATION = "pm10_station"
CONF_PM25_STATION = "pm25_station"
CONF_OZONE_STATION = "ozone_station"

CONF_SECTION_HYDRO = "hydrology"
CONF_HYDRO_STATION = "hydro_station"

CONF_SECTION_POLLEN = "pollen"
CONF_POLLEN_STATION = "pollen_station"

OPTION_NONE = "none"

# Provenance source identifiers
SOURCE_STATION = "station"
SOURCE_SUMMARY_24H = "station_24h"
SOURCE_AIR_QUALITY = "air_quality_station"
SOURCE_BRIGHTNESS = "sky_brightness_station"
SOURCE_HYDRO = "hydro_station"
SOURCE_POLLEN = "pollen_station"
SOURCE_AVALANCHE = "avalanche_bulletin"
SOURCE_BULLETIN = "forecast_bulletin"
SOURCE_FORECAST = "forecast"
SOURCE_METAR = "metar"
SOURCE_UNKNOWN = "unknown"

# Condition decision rules
RULE_PRECIPITATION = "precipitation"
RULE_VISIBILITY = "visibility"
RULE_WIND = "wind"
RULE_SOLAR_RADIATION = "solar_radiation"
RULE_SKY_BRIGHTNESS = "sky_brightness"
RULE_CLOUD_COVER = "cloud_cover"
RULE_FORECAST = "forecast"

# Wind direction cardinal sectors (index 0..15, modulo 16)
CARDINAL_DIRECTIONS: tuple[str, ...] = (
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
)

# ARPAV forecast symbol prefix/filename -> Home Assistant weather condition.
# Ordered carefully so more specific patterns (e.g. a1N) match before shorter prefixes (a1).
FORECAST_CONDITION_SYMBOLS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("pouring", ("b6.png", "b7.png", "b8.png", "b9.png", "b10.png")),
    ("clear-night", ("a1N", "a2N")),
    ("cloudy", ("a4", "a5", "a6")),
    ("partlycloudy", ("a3",)),
    ("fog", ("f1.png", "f2.png", "f3.png", "f4.png")),
    (
        "lightning-rainy",
        (
            "c1.png",
            "c2.png",
            "c3.png",
            "c4.png",
            "c5.png",
            "c6.png",
            "c7.png",
            "c8.png",
            "c9.png",
            "c10.png",
        ),
    ),
    ("rainy", ("b1.png", "b2.png", "b3.png", "b4.png", "b5.png")),
    (
        "snowy",
        (
            "d1.png",
            "d2.png",
            "d3.png",
            "d4.png",
            "d5.png",
            "d6.png",
            "d7.png",
            "d8.png",
            "d9.png",
            "d10.png",
        ),
    ),
    (
        "snowy-rainy",
        (
            "e1.png",
            "e2.png",
            "e3.png",
            "e4.png",
            "e5.png",
            "e6.png",
            "e7.png",
            "e8.png",
            "e9.png",
            "e10.png",
        ),
    ),
    ("sunny", ("a1", "a2")),
)

# Pollen Italian risk labels -> canonical enum keys and numeric rank
POLLEN_RISK_MAP: dict[str, tuple[str, int]] = {
    "assente": ("absent", 0),
    "bassa": ("low", 1),
    "basso": ("low", 1),
    "media": ("moderate", 2),
    "medio": ("moderate", 2),
    "elevata": ("high", 3),
    "elevato": ("high", 3),
    "alta": ("high", 3),
    "alto": ("high", 3),
}

POLLEN_RANK_TO_LEVEL: dict[int, str] = {
    0: "absent",
    1: "low",
    2: "moderate",
    3: "high",
}

POLLEN_LEVEL_OPTIONS: list[str] = ["absent", "low", "moderate", "high"]

# AINEVA 5-level avalanche danger scale
AVALANCHE_LEVEL_MAP: dict[str, str] = {
    "1": "1_low",
    "2": "2_moderate",
    "3": "3_considerable",
    "4": "4_high",
    "5": "5_very_high",
    "debole": "1_low",
    "moderato": "2_moderate",
    "marcato": "3_considerable",
    "forte": "4_high",
    "molto forte": "5_very_high",
}

AVALANCHE_LEVEL_OPTIONS: list[str] = [
    "not_issued",
    "1_low",
    "2_moderate",
    "3_considerable",
    "4_high",
    "5_very_high",
]

# Known pollen species metadata (code -> slug)
POLLEN_SPECIES_SLUGS: dict[str, str] = {
    "501": "betulaceae",
    "502": "compositae",
    "503": "corylaceae",
    "504": "fagaceae",
    "505": "poaceae",
    "506": "oleaceae",
    "507": "plantaginaceae",
    "508": "urticaceae",
    "509": "cupressaceae",
    "510": "amaranthaceae",
    "515": "platanaceae",
    "517": "pinaceae",
    "548": "alternaria",
}
