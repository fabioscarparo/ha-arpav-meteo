"""Async API client and pure data parsers for all ARPA Veneto endpoints.

Covers:
- REST v1 (`https://api.arpa.veneto.it/REST/v1/...`):
  - Real-time weather/snow/hydro station observations (`meteo_meteogrammi_tabella`, `meteo_meteogrammi`)
  - 24h extremes, wind gusts, humidex, windchill (`meteo_ultime24ore`)
  - Zone forecast symbols in IT and EN (`bollettini_meteo_simboli`, `bollettini_meteo_simboli_en`)
  - Textual weather bulletins and alerts (`bollettini_meteo_testi`)
  - Geolocated air quality stations (`aria_elenco_stazioni/aria_elenco_stazioni_point`)
  - Validated hourly & daily air quality (`aria_valori_orari`, `aria_valori_giornalieri`)
  - Hydrometric river levels & trends (`meteo_meteogrammilivello`)
  - Night sky brightness (`meteo_brillanza_tabella`)
  - Local radar Teolo/Concordia (`radar_imgs_base`)
- Portal (`https://meteo.arpa.veneto.it/...`):
  - Dolomiti Neve & Valanghe XML bulletin
  - Direct Radar Mosaic PNG (`mosaico_mbasemax_G.png`)
- Institutional resources (`https://www.arpa.veneto.it/risorse/...`):
  - Provincial allergen pollen stations & weekly/daily reports (`pollini.json`)
"""

from __future__ import annotations

import asyncio
import base64
import html
import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from math import asin, cos, log, radians, sin, sqrt
from typing import Any

import aiohttp

from .comuni_coords import COMUNI_COORDS
from .const import (
    API_REST_BASE,
    AQ_EXCLUDED_CODSEQS,
    AQ_MIN_VALID_FLAG,
    AQ_PARAM_OZONE,
    AQ_PARAM_PM10,
    AQ_PARAM_PM25,
    ARPAV_TZ,
    AVALANCHE_LEVEL_MAP,
    AVALANCHE_XML_URL,
    BRIGHTNESS_MAX_AGE_HOURS,
    CARDINAL_DIRECTIONS,
    CONF_RADAR_CONCORDIA,
    CONF_RADAR_MOSAIC,
    CONF_RADAR_TEOLO,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_HTTP_TIMEOUT,
    FORECAST_CONDITION_SYMBOLS,
    MAX_REAL_ZONE_ID,
    MOUNTAIN_ZONE_IDS,
    POLLEN_DATA_BASE_URL,
    POLLEN_INDEX_URL,
    POLLEN_RANK_TO_LEVEL,
    POLLEN_RISK_MAP,
    POLLEN_SPECIES_SLUGS,
    RADAR_MOSAIC_PNG_URL,
    ROME_TZ,
    SOURCE_STATION,
)
from .models import (
    AirQualityData,
    AvalancheArea,
    AvalancheBulletin,
    BulletinDayText,
    BulletinSummary,
    ForecastEntry,
    GeoStation,
    HydroReading,
    PollenReport,
    PollenSpecies,
    Provenance,
    RadarFrame,
    SkyBrightnessReading,
    StationObservation,
    StationSummary24h,
)

_LOGGER = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_SPACE_RE = re.compile(r"\s+")
_SLUG_RE = re.compile(r"[^a-z0-9]+")

_INTERVAL_TO_TYPE: dict[str, tuple[str, bool | None, str]] = {
    "night/morning": ("twice_daily", False, "08:00:00"),
    "notte/mattina": ("twice_daily", False, "08:00:00"),
    "afternoon/evening": ("twice_daily", True, "16:00:00"),
    "pom/sera": ("twice_daily", True, "16:00:00"),
    "pomeriggio/sera": ("twice_daily", True, "16:00:00"),
    "": ("daily", None, "12:00:00"),
}


class ArpaVenetoApiError(Exception):
    """Base error raised on invalid or failed ARPA Veneto API calls."""


class ArpaVenetoConnectionError(ArpaVenetoApiError):
    """Error raised on HTTP transport or timeout failure."""


# ---------------------------------------------------------------------------
# Pure helper utilities
# ---------------------------------------------------------------------------


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in kilometers between two WGS84 coordinates."""
    rlat1, rlon1, rlat2, rlon2 = map(radians, (lat1, lon1, lat2, lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    return 2 * 6371.0 * asin(min(1.0, sqrt(a)))


def select_station_reference(
    comune_istat: int | None,
    zone_coord: tuple[float, float] | None,
) -> tuple[float | None, float | None]:
    """Return the point the setup sorts weather stations from.

    The chosen municipality comes first: its coordinates are in COMUNI_COORDS,
    keyed by the ISTAT code ARPAV gives in meteo_comuni. Without them the point
    of the forecast zone is used, as before.
    """
    if comune_istat is not None and comune_istat in COMUNI_COORDS:
        return COMUNI_COORDS[comune_istat]
    if zone_coord is not None:
        return zone_coord
    return (None, None)


def parse_arpav_timestamp(raw: str | None) -> datetime | None:
    """Parse an ARPAV fixed-solar-time (+01:00) ISO timestamp into a timezone-aware datetime."""
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=ARPAV_TZ)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=ARPAV_TZ)


def arpav_isoformat(raw: str | None) -> str | None:
    """Format an ARPAV timestamp string as timezone-aware ISO-8601."""
    dt = parse_arpav_timestamp(raw)
    return dt.isoformat() if dt is not None else (str(raw) if raw else None)


def strip_html_tags(text: str | None) -> str | None:
    """Strip HTML tags and decode HTML entities from ARPAV bulletin strings."""
    if not text:
        return None
    unescaped = html.unescape(str(text))
    cleaned = _HTML_TAG_RE.sub(" ", unescaped)
    cleaned = _MULTI_SPACE_RE.sub(" ", cleaned).strip()
    return cleaned or None


def compute_dew_point(temperature_c: float, humidity_pct: float) -> float | None:
    """Compute dew point (°C) using the Magnus-Tetens formula."""
    if humidity_pct <= 0 or humidity_pct > 100:
        return None
    a, b = 17.625, 243.04
    gamma = log(humidity_pct / 100.0) + (a * temperature_c) / (b + temperature_c)
    return round((b * gamma) / (a - gamma), 1)


def degrees_to_cardinal(degrees: float) -> str:
    """Convert wind direction degrees (0..360) to 16-point compass sector."""
    normalized = degrees % 360.0
    idx = int((normalized + 11.25) / 22.5) % 16
    return CARDINAL_DIRECTIONS[idx]


def _safe_float(value: Any) -> float | None:
    """Parse a value to float, returning None when missing or invalid."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    """Parse a value to int, returning None when missing or invalid."""
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _slugify_ascii(text: str) -> str:
    """Convert text into a lowercase underscore-separated ASCII slug."""
    return _SLUG_RE.sub("_", text.lower()).strip("_")


# ---------------------------------------------------------------------------
# Pure response parsers (100% unit-testable without network)
# ---------------------------------------------------------------------------


def parse_station_observations(
    station_id: int,
    payload: dict[str, Any],
    now: datetime | None = None,
) -> StationObservation:
    """Parse `meteo_meteogrammi_tabella` payload into a StationObservation."""
    rows = payload.get("data") or []
    result = StationObservation(station_id=station_id)
    if not rows:
        return result

    latest_by_type: dict[str, dict[str, Any]] = {}
    precip_rows: list[tuple[datetime, float]] = []
    temp_rows: list[tuple[str, float]] = []
    latest_overall_dt: datetime | None = None
    latest_overall_raw: str | None = None

    for item in rows:
        tipo = item.get("tipo")
        if not tipo:
            continue

        dataora_raw = item.get("dataora") or ""
        if not result.station_name and item.get("nome_stazione"):
            result.station_name = str(item["nome_stazione"])

        if tipo == "PREC":
            dt = parse_arpav_timestamp(dataora_raw)
            val = _safe_float(item.get("valore"))
            if dt is not None and val is not None:
                precip_rows.append((dt, val))

        if tipo.startswith("TARIA"):
            val = _safe_float(item.get("valore"))
            day_str = dataora_raw[:10]
            if val is not None and len(day_str) == 10:
                temp_rows.append((day_str, val))

        prev = latest_by_type.get(tipo)
        if prev is None or dataora_raw > (prev.get("dataora") or ""):
            latest_by_type[tipo] = item

        dt_item = parse_arpav_timestamp(dataora_raw)
        if dt_item is not None and (latest_overall_dt is None or dt_item > latest_overall_dt):
            latest_overall_dt = dt_item
            latest_overall_raw = dataora_raw

    result.observed_at = latest_overall_dt
    result.observed_at_iso = arpav_isoformat(latest_overall_raw)
    result.raw_latest = list(latest_by_type.values())

    for entry in latest_by_type.values():
        mapped = _map_meteogram_observation(entry)
        if not mapped:
            continue
        result.values.update(mapped)
        obs_iso = arpav_isoformat(entry.get("dataora"))
        st_name = entry.get("nome_stazione") or result.station_name
        for key in mapped:
            result.sources[key] = Provenance(
                source=SOURCE_STATION,
                name=str(st_name) if st_name else None,
                observed_at=obs_iso,
            )

    # Compute dew point when temperature and humidity are available
    temp_val = result.values.get("temperature")
    hum_val = result.values.get("humidity")
    if temp_val is not None and hum_val is not None:
        dp = compute_dew_point(float(temp_val), float(hum_val))
        if dp is not None:
            result.values["dew_point"] = dp
            result.sources["dew_point"] = Provenance(
                source=SOURCE_STATION,
                name=result.station_name,
                observed_at=result.sources.get("temperature", Provenance(SOURCE_STATION)).observed_at,
            )

    # Precipitation aggregates (rolling windows + today since Europe/Rome midnight)
    if precip_rows:
        precip_rows.sort(key=lambda pair: pair[0], reverse=True)
        latest_prec_dt, latest_prec_val = precip_rows[0]

        ref_now = now if now is not None else datetime.now(UTC)
        if ref_now.tzinfo is None:
            ref_now = ref_now.replace(tzinfo=UTC)
        ref_arpav = ref_now.astimezone(ARPAV_TZ)
        rome_midnight = ref_now.astimezone(ROME_TZ).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        computed_prec = {
            "precipitation_intensity": round(latest_prec_val * 12.0, 2),
            "precipitation_1h": _sum_since(precip_rows, ref_arpav - timedelta(hours=1)),
            "precipitation_3h": _sum_since(precip_rows, ref_arpav - timedelta(hours=3)),
            "precipitation_6h": _sum_since(precip_rows, ref_arpav - timedelta(hours=6)),
            "precipitation_12h": _sum_since(precip_rows, ref_arpav - timedelta(hours=12)),
            "precipitation_24h": _sum_since(precip_rows, ref_arpav - timedelta(hours=24)),
            "precipitation_today": _sum_since(precip_rows, rome_midnight),
        }
        result.values.update(computed_prec)
        prec_iso = latest_prec_dt.isoformat()
        for key in computed_prec:
            result.sources[key] = Provenance(
                source=SOURCE_STATION,
                name=result.station_name,
                observed_at=prec_iso,
            )

    # Measured temperature extremes for the latest day reported by the station
    if temp_rows:
        by_day: dict[str, list[float]] = {}
        for day_str, val in temp_rows:
            by_day.setdefault(day_str, []).append(val)
        latest_day = max(by_day)
        day_vals = by_day[latest_day]
        result.measured_temp_date = latest_day
        result.measured_temp_min = min(day_vals)
        result.measured_temp_max = max(day_vals)

    return result


def _map_meteogram_observation(entry: dict[str, Any]) -> dict[str, Any]:
    """Map a single meteogram table row to normalized metric keys."""
    tipo = str(entry.get("tipo") or "")
    raw_val = entry.get("valore")
    unit = str(entry.get("unitnm") or "").strip().lower()

    if not tipo or raw_val is None or raw_val == "":
        return {}

    if tipo.startswith("TARIA"):
        val = _safe_float(raw_val)
        return {"temperature": round(val, 1)} if val is not None else {}

    if tipo.startswith("UMID"):
        val = _safe_int(raw_val)
        return {"humidity": val} if val is not None else {}

    if tipo == "VISIB":
        val = _safe_float(raw_val)
        if val is None:
            return {}
        # Handle both meters ("m") and kilometers ("km") safely
        km = val if unit == "km" else val / 1000.0
        return {"visibility": round(km, 2)}

    if tipo == "PRESS":
        val = _safe_float(raw_val)
        return {"pressure": round(val, 1)} if val is not None else {}

    if tipo == "PREC":
        val = _safe_float(raw_val)
        return {"precipitation_5m": round(val, 2)} if val is not None else {}

    if tipo.startswith("DVENTO"):
        deg = _safe_int(raw_val)
        if deg is None:
            return {}
        deg_norm = deg % 360
        return {
            "wind_bearing": deg_norm,
            "wind_bearing_cardinal": degrees_to_cardinal(deg_norm),
        }

    if tipo.startswith("VVENTO"):
        val = _safe_float(raw_val)
        if val is None:
            return {}
        kmh = val * 3.6 if unit in ("m/s", "") else val
        return {"wind_speed": round(kmh, 1)}

    if tipo == "RADSOL":
        val = _safe_float(raw_val)
        if val is None:
            return {}
        if unit == "mj/m2":
            wm2 = round((val * 1_000_000.0) / 3600.0, 1)
            uv = round(val * 0.06 * 40.0, 1)
            return {"solar_radiation": wm2, "uv_index": max(0.0, uv)}
        if unit == "w/m2":
            wm2 = round(val, 1)
            uv = round(val * 0.06 * 0.04, 1)
            return {"solar_radiation": wm2, "uv_index": max(0.0, uv)}
        return {}

    if tipo == "BFOGL":
        val = _safe_float(raw_val)
        return {"leaf_wetness": round(val, 1)} if val is not None else {}

    if tipo == "NIVOM":
        val = _safe_float(raw_val)
        return {"snow_depth": round(val, 1)} if val is not None else {}

    if tipo in ("LIDRO", "LIVIDRO"):
        val = _safe_float(raw_val)
        return {"river_level": round(val, 2)} if val is not None else {}

    if tipo == "PORT":
        val = _safe_float(raw_val)
        return {"river_discharge": round(val, 2)} if val is not None else {}

    return {}


def _sum_since(rows: list[tuple[datetime, float]], since: datetime) -> float:
    """Sum precipitation samples whose aware timestamp is >= `since`."""
    return round(sum(val for dt, val in rows if dt >= since), 2)


def parse_ultime24ore(payload: dict[str, Any]) -> dict[int, StationSummary24h]:
    """Parse `meteo_ultime24ore` payload keyed by `codseqst`."""
    summaries: dict[int, StationSummary24h] = {}
    for item in payload.get("data") or []:
        codseqst = _safe_int(item.get("codseqst"))
        if codseqst is None:
            continue

        wind_max = _safe_float(item.get("velo_vento_max"))
        wind_gust = _safe_float(item.get("velo_vento_raffica"))

        summaries[codseqst] = StationSummary24h(
            station_id=codseqst,
            station_name=item.get("nome_stazione"),
            updated_at=arpav_isoformat(item.get("dataora_aggiornamento")),
            temp_last=_safe_float(item.get("ultima_temp_aria")),
            temp_min=_safe_float(item.get("temp_aria_min")),
            temp_max=_safe_float(item.get("temp_aria_max")),
            precipitation_24h=_safe_float(item.get("precipitazione")),
            wind_speed_max_kmh=round(wind_max * 3.6, 1) if wind_max is not None else None,
            wind_gust_kmh=round(wind_gust * 3.6, 1) if wind_gust is not None else None,
            snow_depth_cm=_safe_float(item.get("altezza_neve")),
            humidex=_safe_float(item.get("humidex")),
            windchill=_safe_float(item.get("windchill")),
        )
    return summaries


def map_symbol_to_condition(symbol: str | None) -> str | None:
    """Map an ARPAV symbol filename (e.g. `b7.png`, `a3.png`) to an HA condition."""
    if not symbol:
        return None
    for condition, patterns in FORECAST_CONDITION_SYMBOLS:
        if any(pat in symbol for pat in patterns):
            return condition
    return None


def parse_forecast_symbols(payload: dict[str, Any]) -> list[ForecastEntry]:
    """Parse `bollettini_meteo_simboli` (IT or EN) into ordered ForecastEntry objects."""
    entries: list[ForecastEntry] = []
    for raw in payload.get("data") or []:
        scadenza = str(raw.get("scadenza") or "").strip()
        if not scadenza:
            continue

        intervallo_raw = str(raw.get("intervallo") or "").strip().lower()
        mapping = _INTERVAL_TO_TYPE.get(intervallo_raw)
        if mapping is None:
            _LOGGER.debug("Skipping unknown forecast intervallo: %r", intervallo_raw)
            continue

        forecast_type, is_daytime, time_part = mapping
        try:
            dt = datetime.strptime(f"{scadenza} {time_part}", "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=ARPAV_TZ
            )
        except ValueError:
            continue

        temp_min, temp_max = _parse_forecast_temperature(raw)

        prob_raw = str(raw.get("prob precipitazioni") or "").strip().rstrip("%").strip()
        prob = _safe_int(prob_raw) if prob_raw else None

        def _clean(val: Any) -> str | None:
            """Return a stripped string or None if empty."""
            if val is None:
                return None
            s = str(val).strip()
            return s or None

        entries.append(
            ForecastEntry(
                dt=dt,
                forecast_type=forecast_type,
                is_daytime=is_daytime,
                condition=map_symbol_to_condition(raw.get("simbolo")),
                symbol=_clean(raw.get("simbolo")),
                temp_min=temp_min,
                temp_max=temp_max,
                precipitation_probability=prob,
                reliability=_clean(raw.get("attendibilita")),
                weather_description=_clean(raw.get("testo")),
                precipitation_description=_clean(raw.get("precipitazioni")),
                snow_line=_clean(raw.get("quota neve")),
                temp_1500m=_clean(raw.get("temperatura 1500m")),
                temp_2000m=_clean(raw.get("temperatura 2000m")),
                temp_3000m=_clean(raw.get("temperatura 3000m")),
                wind=_clean(raw.get("vento")),
                issued_at=arpav_isoformat(raw.get("dataemissione")),
                updated_at=arpav_isoformat(raw.get("aggiornamento")),
            )
        )

    entries.sort(key=lambda e: e.dt)
    return entries


def _parse_forecast_temperature(entry: dict[str, Any]) -> tuple[float | None, float | None]:
    """Extract (temp_min, temp_max) from the first populated `temperatura*` key."""
    # Prefer plain `temperatura`; fall back to altitude temperatures for mountain zones
    ordered_keys = (
        "temperatura",
        "temperatura 1500m",
        "temperatura 2000m",
        "temperatura 3000m",
    )
    first_val: str | None = None
    for key in ordered_keys:
        val = entry.get(key)
        if val not in (None, ""):
            first_val = str(val).strip()
            break

    if not first_val:
        return None, None

    if "/" in first_val:
        parts = first_val.split("/", 1)
        lo = _safe_float(parts[0])
        hi = _safe_float(parts[1])
        if lo is not None and hi is not None:
            return min(lo, hi), max(lo, hi)
        return lo, hi

    single = _safe_float(first_val)
    return None, single


def parse_bulletin_text(bulletin_code: str, payload: dict[str, Any]) -> BulletinSummary | None:
    """Parse `bollettini_meteo_testi` payload into a BulletinSummary."""
    rows = payload.get("data") or []
    if not rows:
        return None

    first = rows[0]
    days: list[BulletinDayText] = []
    for row in sorted(rows, key=lambda r: (r.get("giorno") or 0, r.get("scadenza") or "")):
        text = strip_html_tags(row.get("previsione"))
        if text:
            days.append(
                BulletinDayText(
                    date=str(row.get("scadenza") or ""),
                    forecast_text=text,
                    reliability=(str(row.get("attendibilita") or "").strip() or None),
                )
            )

    return BulletinSummary(
        bulletin_code=str(first.get("bollettino") or bulletin_code),
        issued_at=arpav_isoformat(first.get("dataemissione")),
        updated_at=arpav_isoformat(first.get("aggiornamento")),
        general_evolution=strip_html_tags(first.get("evoluzionegenerale")),
        alert=strip_html_tags(first.get("avviso")),
        special_phenomena=strip_html_tags(first.get("fenomeniparticolari")),
        days=days,
    )


def parse_air_quality_latest(
    payload: dict[str, Any],
    cod_parametro: int,
) -> dict[str, Any] | None:
    """Extract the latest valid (`FLAG >= 9`) air quality record for a parameter code."""
    latest: dict[str, Any] | None = None
    latest_key = ""

    for item in payload.get("data") or []:
        codseq = _safe_int(item.get("CODSEQ"))
        if codseq in AQ_EXCLUDED_CODSEQS:
            continue

        param = _safe_int(item.get("COD_PARAMETRO"))
        if param != cod_parametro:
            continue

        flag = _safe_int(item.get("FLAG"))
        if flag is None or flag < AQ_MIN_VALID_FLAG:
            continue

        val = _safe_float(item.get("MEDIA"))
        if val is None:
            continue

        ts_key = str(item.get("DATA_ORA") or item.get("DATA") or "")
        if ts_key > latest_key:
            latest_key = ts_key
            latest = item

    return latest


def parse_air_quality_stations(
    payload: dict[str, Any],
    ref_lat: float | None = None,
    ref_lon: float | None = None,
) -> list[GeoStation]:
    """Parse `aria_elenco_stazioni/aria_elenco_stazioni_point` into distance-sorted GeoStations."""
    stations: list[GeoStation] = []
    for item in payload.get("data") or []:
        codseqst = _safe_int(item.get("codseqst"))
        if codseqst is None:
            continue
        if str(item.get("attiva") or "s").lower() != "s":
            continue

        lat = _safe_float(item.get("latitudine"))
        lon = _safe_float(item.get("longitudine"))
        dist = (
            haversine_km(ref_lat, ref_lon, lat, lon)
            if (ref_lat is not None and ref_lon is not None and lat is not None and lon is not None)
            else None
        )

        stations.append(
            GeoStation(
                station_id=str(codseqst),
                name=str(item.get("name") or codseqst),
                province=str(item.get("prov") or "").upper(),
                latitude=lat,
                longitude=lon,
                altitude=_safe_float(item.get("altitude")),
                distance_km=dist,
                extra={
                    "comune": item.get("comune"),
                    "address": item.get("address"),
                    "pm10": bool(item.get("pm10")),
                    "pm25": bool(item.get("pm2_5")),
                    "o3": bool(item.get("o3")),
                },
            )
        )

    stations.sort(key=lambda s: (s.distance_km if s.distance_km is not None else 9999.0, s.name))
    return stations


def parse_hydro_stations(
    payload: dict[str, Any],
    ref_lat: float | None = None,
    ref_lon: float | None = None,
) -> list[GeoStation]:
    """Parse `meteo_meteogrammilivello` into distance-sorted GeoStations with current level."""
    stations: list[GeoStation] = []
    for item in payload.get("data") or []:
        codseqst = _safe_int(item.get("codseqst"))
        if codseqst is None:
            continue
        lat = _safe_float(item.get("latitudine"))
        lon = _safe_float(item.get("longitudine"))
        dist = (
            haversine_km(ref_lat, ref_lon, lat, lon)
            if (ref_lat is not None and ref_lon is not None and lat is not None and lon is not None)
            else None
        )
        stations.append(
            GeoStation(
                station_id=str(codseqst),
                name=str(item.get("nome_stazione") or codseqst),
                province=str(item.get("provincia") or "").title(),
                latitude=lat,
                longitude=lon,
                altitude=_safe_float(item.get("quota")),
                distance_km=dist,
                extra={
                    "livello": _safe_float(item.get("livello")),
                    "trend": item.get("trend"),
                    "dataora": arpav_isoformat(item.get("dataora")),
                },
            )
        )

    stations.sort(key=lambda s: (s.distance_km if s.distance_km is not None else 9999.0, s.name))
    return stations


def parse_hydro_reading(
    station_id: int,
    livello_payload: dict[str, Any],
    tabella_payload: dict[str, Any] | None = None,
) -> HydroReading | None:
    """Extract a single station's HydroReading (level, trend, optional discharge)."""
    match: dict[str, Any] | None = None
    for item in livello_payload.get("data") or []:
        if _safe_int(item.get("codseqst")) == station_id:
            match = item
            break

    discharge: float | None = None
    fallback_level: float | None = None
    fallback_obs: str | None = None
    fallback_name: str | None = None

    if tabella_payload:
        obs = parse_station_observations(station_id, tabella_payload)
        discharge = obs.values.get("river_discharge")
        fallback_level = obs.values.get("river_level")
        fallback_obs = obs.observed_at_iso
        fallback_name = obs.station_name

    if match is None and fallback_level is None and discharge is None:
        return None

    return HydroReading(
        station_id=station_id,
        station_name=str(
            (match or {}).get("nome_stazione") or fallback_name or f"Station {station_id}"
        ),
        province=str((match or {}).get("provincia") or "").title(),
        level_m=_safe_float((match or {}).get("livello"))
        if match is not None
        else fallback_level,
        trend=(str(match["trend"]).strip() if match and match.get("trend") else None),
        discharge_m3s=discharge,
        observed_at=arpav_isoformat((match or {}).get("dataora")) or fallback_obs,
    )


def parse_avalanche_xml(xml_text: str) -> AvalancheBulletin:
    """Parse `dolomiti_nevevalanghe.xml` into an AvalancheBulletin."""
    root = ET.fromstring(xml_text)

    issued_node = root.find("data_emissione")
    issued_at = issued_node.attrib.get("date") if issued_node is not None else None

    bol = root.find("bollettino")
    if bol is None:
        return AvalancheBulletin(issued_at=issued_at)

    situation = strip_html_tags(bol.findtext("situazione"))
    forecast = strip_html_tags(bol.findtext("previsione"))
    guidance = strip_html_tags(bol.findtext("indicazioni"))

    areas: dict[str, AvalancheArea] = {}
    # Take the first (most current) <scadenza> block
    first_scadenza = bol.find("scadenza")
    if first_scadenza is not None:
        date_label = first_scadenza.attrib.get("data")
        for area_node in first_scadenza.findall("area"):
            name = (area_node.attrib.get("nome") or "").strip().upper()
            if not name:
                continue
            pericolo_raw = strip_html_tags(area_node.findtext("pericolo"))
            danger_level = _parse_avalanche_danger(pericolo_raw)
            areas[name] = AvalancheArea(
                area=name,
                danger_level=danger_level,
                danger_raw=pericolo_raw,
                fresh_snow=strip_html_tags(area_node.findtext("neve_fresca")),
                dangerous_locations=strip_html_tags(area_node.findtext("luoghi_pericolosi")),
                elevation_info=strip_html_tags(area_node.findtext("quote")),
                date_label=date_label,
            )

    return AvalancheBulletin(
        issued_at=issued_at,
        situation=situation,
        forecast=forecast,
        guidance=guidance,
        areas=areas,
    )


def _parse_avalanche_danger(raw: str | None) -> str:
    """Map an AINEVA danger label or number (1-5) to a canonical enum key."""
    if not raw:
        return "not_issued"
    lowered = raw.strip().lower()
    # Look for explicit leading digit 1..5 first
    digit_match = re.search(r"\b([1-5])\b", lowered)
    if digit_match:
        return AVALANCHE_LEVEL_MAP[digit_match.group(1)]
    for token, mapped in AVALANCHE_LEVEL_MAP.items():
        if len(token) > 1 and token in lowered:
            return mapped
    return "not_issued"


def parse_pollen_index(
    payload: dict[str, Any],
    ref_lat: float | None = None,
    ref_lon: float | None = None,
) -> list[GeoStation]:
    """Parse `pollini.json` index into distance-sorted provincial pollen stations."""
    stations: list[GeoStation] = []
    for item in payload.get("data") or []:
        code = str(item.get("codice_stazione") or "").strip()
        if not code:
            continue
        lat = _safe_float(item.get("latitudine"))
        lon = _safe_float(item.get("longitudine"))
        dist = (
            haversine_km(ref_lat, ref_lon, lat, lon)
            if (ref_lat is not None and ref_lon is not None and lat is not None and lon is not None)
            else None
        )
        stations.append(
            GeoStation(
                station_id=code,
                name=str(item.get("nome_stazione") or code),
                province=str(item.get("provincia") or "").upper(),
                latitude=lat,
                longitude=lon,
                distance_km=dist,
                extra={
                    "sede": item.get("sede"),
                    "file_dati": item.get("file_dati"),
                },
            )
        )

    stations.sort(key=lambda s: (s.distance_km if s.distance_km is not None else 9999.0, s.name))
    return stations


def parse_pollen_report(payload: dict[str, Any]) -> PollenReport | None:
    """Parse a provincial `pollini-XX-YYYY-WW.json` station report."""
    rows = payload.get("data") or []
    if not rows:
        return None

    st = rows[0]
    species_list: list[PollenSpecies] = []
    max_risk_rank = 0
    max_forecast_rank = 0

    for g in st.get("grafici") or []:
        code = str(g.get("codice_specie") or "").strip()
        name = str(g.get("nome_specie") or code).strip()
        if not code:
            continue

        slug = POLLEN_SPECIES_SLUGS.get(code) or _slugify_ascii(name.split("(")[0])
        risk_raw = (str(g.get("giudizio") or "").strip() or None)
        forecast_raw = (str(g.get("previsione") or "").strip() or None)

        risk_level, risk_rank = POLLEN_RISK_MAP.get(
            (risk_raw or "").lower(), ("absent", 0)
        )
        forecast_level, forecast_rank = POLLEN_RISK_MAP.get(
            (forecast_raw or "").lower(), ("absent", 0)
        )
        max_risk_rank = max(max_risk_rank, risk_rank)
        max_forecast_rank = max(max_forecast_rank, forecast_rank)

        misure = g.get("misure") or []
        latest_val: float | None = None
        latest_date: str | None = None
        if misure:
            # Find latest non-empty measurement
            for m in reversed(misure):
                val = _safe_float(m.get("valore"))
                if val is not None:
                    latest_val = val
                    latest_date = str(m.get("dataora") or "")[:10] or None
                    break

        species_list.append(
            PollenSpecies(
                code=code,
                slug=slug,
                name=name,
                risk_level=risk_level,
                risk_raw=risk_raw,
                forecast_level=forecast_level,
                forecast_raw=forecast_raw,
                latest_value=latest_val,
                latest_date=latest_date,
            )
        )

    return PollenReport(
        station_code=str(st.get("codice_stazione") or ""),
        station_name=str(st.get("nome_stazione") or ""),
        province=str(st.get("provincia") or "").upper(),
        site=st.get("sede"),
        period=st.get("periodo"),
        bulletin_number=_safe_int(st.get("numboll")),
        year=_safe_int(st.get("anno")),
        comment=strip_html_tags(st.get("commento")),
        max_risk_level=POLLEN_RANK_TO_LEVEL[max_risk_rank],
        max_forecast_level=POLLEN_RANK_TO_LEVEL[max_forecast_rank],
        species=species_list,
    )


def parse_radar_base_frame(source: str, payload: dict[str, Any]) -> RadarFrame | None:
    """Extract the latest JPEG radar frame for `teolo` or `concordia` from `radar_imgs_base`."""
    candidates = [
        item
        for item in (payload.get("data") or [])
        if str(item.get("radar") or "").lower() == source.lower() and item.get("image")
    ]
    if not candidates:
        return None

    latest = max(candidates, key=lambda x: str(x.get("date") or ""))
    try:
        raw_bytes = base64.b64decode(latest["image"])
    except (ValueError, TypeError) as err:
        raise ArpaVenetoApiError(f"Invalid base64 radar frame for {source}: {err}") from err

    obs_dt = parse_arpav_timestamp(latest.get("date")) or datetime.now(UTC)
    return RadarFrame(
        source=source,
        content_type="image/jpeg",
        image_bytes=raw_bytes,
        observed_at=obs_dt.astimezone(UTC),
    )


def parse_brightness_reading(
    payload: dict[str, Any],
    station_name: str | None = None,
    now: datetime | None = None,
) -> SkyBrightnessReading | None:
    """Extract the latest fresh (> 0, <= 6h old) night sky brightness reading."""
    latest: dict[str, Any] | None = None
    latest_raw = ""
    for item in payload.get("data") or []:
        ts = str(item.get("dataora") or "")
        if ts > latest_raw:
            latest_raw = ts
            latest = item

    if not latest:
        return None

    val = _safe_float(latest.get("valore"))
    if val is None or val <= 0:
        return None

    reading_dt = parse_arpav_timestamp(latest.get("dataora"))
    if reading_dt is None:
        return None

    ref_now = now if now is not None else datetime.now(UTC)
    if ref_now.tzinfo is None:
        ref_now = ref_now.replace(tzinfo=UTC)

    if (ref_now.astimezone(UTC) - reading_dt.astimezone(UTC)) > timedelta(
        hours=BRIGHTNESS_MAX_AGE_HOURS
    ):
        return None

    return SkyBrightnessReading(
        value=val,
        station_name=station_name or latest.get("nome_stazione"),
        observed_at=reading_dt.isoformat(),
    )


def select_bulletin_code_for_zone(zone_id: int) -> str:
    """Select the most specific ARPAV textual bulletin code for a forecast zone."""
    if zone_id in MOUNTAIN_ZONE_IDS:
        return "DM"
    return "MV"


# ---------------------------------------------------------------------------
# Async HTTP Client
# ---------------------------------------------------------------------------


class ArpaVenetoApiClient:
    """Async HTTP client wrapping all ARPA Veneto endpoints using a shared ClientSession."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        timeout: float = DEFAULT_HTTP_TIMEOUT,
    ) -> None:
        """Initialize the API client with an injected aiohttp ClientSession."""
        self._session = session
        self._timeout = aiohttp.ClientTimeout(
            total=timeout,
            connect=min(DEFAULT_CONNECT_TIMEOUT, timeout),
        )

    async def _get_json(self, url: str, *, strip_bom: bool = False) -> dict[str, Any]:
        """Perform an HTTP GET and decode JSON (supporting optional UTF-8 BOM)."""
        try:
            async with self._session.get(url, timeout=self._timeout) as response:
                if response.status != 200:
                    raise ArpaVenetoApiError(f"HTTP {response.status} from {url}")
                if strip_bom:
                    raw = await response.read()
                    return json.loads(raw.decode("utf-8-sig"))
                return await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ArpaVenetoConnectionError(f"Connection error fetching {url}: {err}") from err
        except (ValueError, UnicodeDecodeError) as err:
            raise ArpaVenetoApiError(f"Invalid JSON from {url}: {err}") from err

    async def _get_text(self, url: str) -> str:
        """Perform an HTTP GET and decode UTF-8 text."""
        try:
            async with self._session.get(url, timeout=self._timeout) as response:
                if response.status != 200:
                    raise ArpaVenetoApiError(f"HTTP {response.status} from {url}")
                raw = await response.read()
                return raw.decode("utf-8-sig", errors="replace")
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ArpaVenetoConnectionError(f"Connection error fetching {url}: {err}") from err

    async def _get_bytes(self, url: str) -> tuple[bytes, str]:
        """Perform an HTTP GET and return (bytes, content_type)."""
        try:
            async with self._session.get(url, timeout=self._timeout) as response:
                if response.status != 200:
                    raise ArpaVenetoApiError(f"HTTP {response.status} from {url}")
                data = await response.read()
                ctype = response.headers.get("Content-Type", "application/octet-stream").split(";")[0]
                return data, ctype
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ArpaVenetoConnectionError(f"Connection error fetching {url}: {err}") from err

    # -- Discovery / Registry endpoints --

    async def async_get_comuni(self) -> tuple[dict[int, str], dict[int, int], dict[int, int]]:
        """Fetch municipalities: (comune_id -> display_name, -> zone_id, -> ISTAT code)."""
        payload = await self._get_json(f"{API_REST_BASE}/meteo_comuni")
        rows = sorted(payload.get("data") or [], key=lambda x: str(x.get("comune") or ""))
        id_to_name = {
            int(r["id"]): f"{r['comune']} ({str(r.get('provincia') or '').title()})"
            for r in rows
            if r.get("id") is not None
        }
        id_to_zone = {
            int(r["id"]): int(r["zonaid"])
            for r in rows
            if r.get("id") is not None and r.get("zonaid") is not None
        }
        id_to_istat = {
            int(r["id"]): istat
            for r in rows
            if r.get("id") is not None and (istat := _safe_int(r.get("istat"))) is not None
        }
        return id_to_name, id_to_zone, id_to_istat

    async def async_get_zones(self) -> tuple[dict[int, str], dict[int, tuple[float, float]]]:
        """Fetch the 18 real Veneto forecast zones (excluding internal zonaid >= 100)."""
        payload = await self._get_json(f"{API_REST_BASE}/bollettini_meteo_simboli")
        zone_names: dict[int, str] = {}
        zone_coords: dict[int, tuple[float, float]] = {}

        for entry in payload.get("data") or []:
            zid = _safe_int(entry.get("zonaid"))
            if zid is None or zid > MAX_REAL_ZONE_ID:
                continue
            if zid not in zone_names and entry.get("zona"):
                zone_names[zid] = str(entry["zona"])
            lat = _safe_float(entry.get("lat"))
            lon = _safe_float(entry.get("lon"))
            if zid not in zone_coords and lat is not None and lon is not None:
                zone_coords[zid] = (lat, lon)

        sorted_zones = dict(sorted(zone_names.items(), key=lambda kv: kv[1]))
        return sorted_zones, zone_coords

    async def async_get_meteo_stations(
        self,
        ref_lat: float | None = None,
        ref_lon: float | None = None,
    ) -> list[GeoStation]:
        """Fetch all weather stations from MGRAMMI network, optionally sorted by distance."""
        payload = await self._get_json(
            f"{API_REST_BASE}/meteo_meteogrammi?rete=MGRAMMI&coordcd=18&orario=0"
        )
        stations: list[GeoStation] = []
        for item in payload.get("data") or []:
            codseqst = _safe_int(item.get("codseqst"))
            if codseqst is None:
                continue
            lat = _safe_float(item.get("latitudine"))
            lon = _safe_float(item.get("longitudine"))
            dist = (
                haversine_km(ref_lat, ref_lon, lat, lon)
                if (
                    ref_lat is not None
                    and ref_lon is not None
                    and lat is not None
                    and lon is not None
                )
                else None
            )
            stations.append(
                GeoStation(
                    station_id=str(codseqst),
                    name=str(item.get("nome_stazione") or codseqst),
                    province=str(item.get("provincia") or "").title(),
                    latitude=lat,
                    longitude=lon,
                    altitude=_safe_float(item.get("quota")),
                    distance_km=dist,
                )
            )
        stations.sort(key=lambda s: (s.distance_km if s.distance_km is not None else 9999.0, s.name))
        return stations

    async def async_get_air_quality_stations(
        self,
        pollutant: str | None = None,
        ref_lat: float | None = None,
        ref_lon: float | None = None,
    ) -> list[GeoStation]:
        """Fetch geolocated air quality stations (`pm10`, `pm25`, `o3`, or all)."""
        query = {
            "pm10": "?pm10=a",
            "pm25": "?pm25=a",
            "o3": "?o3=s",
        }.get(pollutant or "", "")
        payload = await self._get_json(
            f"{API_REST_BASE}/aria_elenco_stazioni/aria_elenco_stazioni_point{query}"
        )
        return parse_air_quality_stations(payload, ref_lat, ref_lon)

    async def async_get_hydro_stations(
        self,
        ref_lat: float | None = None,
        ref_lon: float | None = None,
    ) -> list[GeoStation]:
        """Fetch geolocated river hydrometric stations sorted by distance."""
        payload = await self._get_json(
            f"{API_REST_BASE}/meteo_meteogrammilivello?coordcd=20005&orario=0&rete=MGRAMMI"
        )
        return parse_hydro_stations(payload, ref_lat, ref_lon)

    async def async_get_pollen_stations(
        self,
        ref_lat: float | None = None,
        ref_lon: float | None = None,
    ) -> list[GeoStation]:
        """Fetch geolocated provincial pollen stations sorted by distance."""
        payload = await self._get_json(POLLEN_INDEX_URL, strip_bom=True)
        return parse_pollen_index(payload, ref_lat, ref_lon)

    async def async_get_brightness_stations(
        self,
        ref_lat: float,
        ref_lon: float,
    ) -> list[GeoStation]:
        """Fetch night sky brightness stations sorted nearest-first."""
        payload = await self._get_json(
            f"{API_REST_BASE}/meteo_meteogrammi?rete=MGRAMMIBRI&coordcd=20067&orario=0"
        )
        stations: list[GeoStation] = []
        for item in payload.get("data") or []:
            codseqst = _safe_int(item.get("codseqst"))
            lat = _safe_float(item.get("latitudine"))
            lon = _safe_float(item.get("longitudine"))
            if codseqst is None or lat is None or lon is None:
                continue
            stations.append(
                GeoStation(
                    station_id=str(codseqst),
                    name=str(item.get("nome_stazione") or codseqst),
                    province=str(item.get("provincia") or "").title(),
                    latitude=lat,
                    longitude=lon,
                    distance_km=haversine_km(ref_lat, ref_lon, lat, lon),
                )
            )
        stations.sort(key=lambda s: s.distance_km if s.distance_km is not None else 9999.0)
        return stations

    # -- Live observation & bulletin endpoints --

    async def async_get_station_observations(self, station_id: int) -> StationObservation:
        """Fetch real-time observations for a weather station."""
        payload = await self._get_json(
            f"{API_REST_BASE}/meteo_meteogrammi_tabella?codseqst={station_id}"
        )
        return parse_station_observations(station_id, payload)

    async def async_get_ultime24ore(self) -> dict[int, StationSummary24h]:
        """Fetch 24-hour extremes, wind gusts, and comfort indices for all stations."""
        payload = await self._get_json(f"{API_REST_BASE}/meteo_ultime24ore")
        return parse_ultime24ore(payload)

    async def async_get_forecast_symbols(
        self,
        zone_id: int,
        language: str = "it",
    ) -> list[ForecastEntry]:
        """Fetch zone forecast symbols in Italian (`it`) or English (`en`)."""
        endpoint = (
            "bollettini_meteo_simboli"
            if language.lower().startswith("it")
            else "bollettini_meteo_simboli_en"
        )
        payload = await self._get_json(f"{API_REST_BASE}/{endpoint}?zona={zone_id}")
        return parse_forecast_symbols(payload)

    async def async_get_bulletin_text(self, bulletin_code: str = "MV") -> BulletinSummary | None:
        """Fetch regional textual bulletin including active weather alerts."""
        payload = await self._get_json(
            f"{API_REST_BASE}/bollettini_meteo_testi?bollettino={bulletin_code}"
        )
        return parse_bulletin_text(bulletin_code, payload)

    async def async_get_air_quality_for_stations(
        self,
        pm10_station_id: int | None = None,
        pm25_station_id: int | None = None,
        ozone_station_id: int | None = None,
    ) -> AirQualityData:
        """Fetch validated hourly and daily air quality readings, deduplicating station calls."""
        aq = AirQualityData()
        station_ids = {
            sid for sid in (pm10_station_id, pm25_station_id, ozone_station_id) if sid is not None
        }
        if not station_ids:
            return aq

        ordered_ids = sorted(station_ids)
        fetches = await asyncio.gather(
            *(
                asyncio.gather(
                    self._get_json(f"{API_REST_BASE}/aria_valori_orari?codseqst={sid}"),
                    self._get_json(f"{API_REST_BASE}/aria_valori_giornalieri?codseqst={sid}"),
                )
                for sid in ordered_ids
            )
        )
        hourly_cache = {sid: pair[0] for sid, pair in zip(ordered_ids, fetches, strict=True)}
        daily_cache = {sid: pair[1] for sid, pair in zip(ordered_ids, fetches, strict=True)}

        if pm10_station_id is not None:
            h = parse_air_quality_latest(hourly_cache[pm10_station_id], AQ_PARAM_PM10)
            d = parse_air_quality_latest(daily_cache[pm10_station_id], AQ_PARAM_PM10)
            if h:
                aq.pm10_hourly = round(float(h["MEDIA"]), 1)
                aq.pm10_station_name = h.get("STAZIONE")
                aq.pm10_hourly_at = arpav_isoformat(h.get("DATA"))
            if d:
                aq.pm10_daily = round(float(d["MEDIA"]), 1)
                aq.pm10_station_name = aq.pm10_station_name or d.get("STAZIONE")
                aq.pm10_daily_at = arpav_isoformat(d.get("DATA"))

        if pm25_station_id is not None:
            h = parse_air_quality_latest(hourly_cache[pm25_station_id], AQ_PARAM_PM25)
            d = parse_air_quality_latest(daily_cache[pm25_station_id], AQ_PARAM_PM25)
            if h:
                aq.pm25_hourly = round(float(h["MEDIA"]), 1)
                aq.pm25_station_name = h.get("STAZIONE")
                aq.pm25_hourly_at = arpav_isoformat(h.get("DATA"))
            if d:
                aq.pm25_daily = round(float(d["MEDIA"]), 1)
                aq.pm25_station_name = aq.pm25_station_name or d.get("STAZIONE")
                aq.pm25_daily_at = arpav_isoformat(d.get("DATA"))

        if ozone_station_id is not None:
            h = parse_air_quality_latest(hourly_cache[ozone_station_id], AQ_PARAM_OZONE)
            d = parse_air_quality_latest(daily_cache[ozone_station_id], AQ_PARAM_OZONE)
            if h:
                aq.ozone_hourly = round(float(h["MEDIA"]), 1)
                aq.ozone_station_name = h.get("STAZIONE")
                aq.ozone_hourly_at = arpav_isoformat(h.get("DATA"))
            if d:
                aq.ozone_daily_max = _safe_float(d.get("MASSIMO"))
                aq.ozone_station_name = aq.ozone_station_name or d.get("STAZIONE")

        return aq

    async def async_get_hydro_reading(self, station_id: int) -> HydroReading | None:
        """Fetch latest river level, trend, and discharge for a hydrometric station."""
        livello_payload = await self._get_json(
            f"{API_REST_BASE}/meteo_meteogrammilivello?coordcd=20005&orario=0&rete=MGRAMMI"
        )
        tabella_payload: dict[str, Any] | None = None
        try:
            tabella_payload = await self._get_json(
                f"{API_REST_BASE}/meteo_meteogrammi_tabella?codseqst={station_id}"
            )
        except ArpaVenetoApiError as err:
            _LOGGER.debug("Optional discharge tabella unavailable for hydro %s: %s", station_id, err)
        return parse_hydro_reading(station_id, livello_payload, tabella_payload)

    async def async_get_avalanche_bulletin(self) -> AvalancheBulletin:
        """Fetch and parse Dolomiti Neve & Valanghe XML bulletin."""
        xml_text = await self._get_text(AVALANCHE_XML_URL)
        try:
            return parse_avalanche_xml(xml_text)
        except ET.ParseError as err:
            raise ArpaVenetoApiError(f"Invalid avalanche XML: {err}") from err

    async def async_get_pollen_report(self, station_code: str) -> PollenReport | None:
        """Fetch latest provincial pollen report by resolving its file_dati from pollini.json."""
        index_payload = await self._get_json(POLLEN_INDEX_URL, strip_bom=True)
        file_dati: str | None = None
        for item in index_payload.get("data") or []:
            if str(item.get("codice_stazione") or "").upper() == station_code.upper():
                file_dati = item.get("file_dati")
                break
        if not file_dati:
            return None

        report_payload = await self._get_json(
            f"{POLLEN_DATA_BASE_URL}/{file_dati}",
            strip_bom=True,
        )
        return parse_pollen_report(report_payload)

    async def async_get_station_brightness(
        self,
        station_id: int,
        station_name: str | None = None,
    ) -> SkyBrightnessReading | None:
        """Fetch latest fresh night sky brightness reading for a station."""
        payload = await self._get_json(
            f"{API_REST_BASE}/meteo_brillanza_tabella?codseqst={station_id}"
        )
        return parse_brightness_reading(payload, station_name=station_name)

    async def async_get_station_brightness_raw(self, station_id: int) -> list[dict[str, Any]]:
        """Fetch raw 72-hour brightness readings for long-term statistics archiving."""
        payload = await self._get_json(
            f"{API_REST_BASE}/meteo_brillanza_tabella?codseqst={station_id}"
        )
        return list(payload.get("data") or [])

    async def async_get_radar_frame(self, source: str) -> RadarFrame | None:
        """Fetch the latest radar image frame (`mosaic`, `teolo`, or `concordia`)."""
        if source == CONF_RADAR_MOSAIC:
            img_bytes, ctype = await self._get_bytes(RADAR_MOSAIC_PNG_URL)
            return RadarFrame(
                source=CONF_RADAR_MOSAIC,
                content_type=ctype if ctype.startswith("image/") else "image/png",
                image_bytes=img_bytes,
                observed_at=datetime.now(UTC),
            )
        if source in (CONF_RADAR_TEOLO, CONF_RADAR_CONCORDIA):
            payload = await self._get_json(f"{API_REST_BASE}/radar_imgs_base")
            return parse_radar_base_frame(source, payload)
        return None
