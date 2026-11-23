"""Regression tests for HA entities, Recorder state classes, coordinator caching, and translations."""

from __future__ import annotations

import json
import pathlib
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from tests.ha_stubs import install_stubs_if_needed

install_stubs_if_needed()

from homeassistant.components.sensor import SensorStateClass  # noqa: E402
from homeassistant.config_entries import ConfigEntry  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402

from custom_components.arpa_veneto_meteo.api import ArpaVenetoConnectionError  # noqa: E402
from custom_components.arpa_veneto_meteo.binary_sensor import (  # noqa: E402
    BINARY_SENSOR_DESCRIPTIONS,
    ArpaVenetoBinarySensorEntity,
)
from custom_components.arpa_veneto_meteo.const import (  # noqa: E402
    ARPAV_TZ,
    CONF_ENABLE_BULLETIN,
    CONF_INFER_CONDITION,
    CONF_INFER_CONDITION_DISABLED,
    CONF_OZONE_STATION,
    CONF_PM10_STATION,
    CONF_POLLEN_STATION,
    CONF_SECTION_AIR_QUALITY,
    CONF_SECTION_POLLEN,
    CONF_STATION_ID,
    CONF_STATION_LAT,
    CONF_STATION_LON,
    CONF_STATION_NAME,
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
)
from custom_components.arpa_veneto_meteo.coordinator import (  # noqa: E402
    ArpaVenetoDataUpdateCoordinator,
)
from custom_components.arpa_veneto_meteo.models import (  # noqa: E402
    AirQualityData,
    ArpaVenetoData,
    BulletinSummary,
    ForecastEntry,
    StationObservation,
    StationSummary24h,
)
from custom_components.arpa_veneto_meteo.sensor import (  # noqa: E402
    SENSOR_DESCRIPTIONS,
    ArpaVenetoSensorEntity,
)
from custom_components.arpa_veneto_meteo.weather import (  # noqa: E402
    ArpaVenetoWeatherEntity,
    build_daily_forecasts,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
COMP_DIR = REPO_ROOT / "custom_components" / "arpa_veneto_meteo"


class TestRecorderAndHACompliance(unittest.TestCase):
    """Ensure every historical log warning/error from upstream cannot recur."""

    def test_rolling_precipitation_and_intensity_are_measurement_not_total_increasing(self) -> None:
        by_key = {d.key: d for d in SENSOR_DESCRIPTIONS}

        for rolling_key in (
            "precipitation_5m",
            "precipitation_intensity",
            "precipitation_1h",
            "precipitation_3h",
            "precipitation_6h",
            "precipitation_12h",
            "precipitation_24h",
        ):
            self.assertEqual(
                by_key[rolling_key].state_class,
                SensorStateClass.MEASUREMENT,
                f"{rolling_key} must use MEASUREMENT to prevent HA Recorder warnings",
            )

        # Only monotonic daily accumulation since midnight may use TOTAL_INCREASING
        self.assertEqual(
            by_key["precipitation_today"].state_class,
            SensorStateClass.TOTAL_INCREASING,
        )

    def test_valid_units_for_precipitation_and_ozone(self) -> None:
        by_key = {d.key: d for d in SENSOR_DESCRIPTIONS}
        self.assertEqual(by_key["precipitation_5m"].native_unit_of_measurement, "mm")
        self.assertEqual(by_key["ozone"].native_unit_of_measurement, "µg/m³")

    def test_sensor_uses_native_value_and_weather_does_not_override_state(self) -> None:
        self.assertIn("native_value", ArpaVenetoSensorEntity.__dict__)
        self.assertNotIn("state", ArpaVenetoSensorEntity.__dict__)
        self.assertNotIn("state", ArpaVenetoWeatherEntity.__dict__)
        self.assertNotIn("native_condition", ArpaVenetoWeatherEntity.__dict__)

    def test_no_warning_fetching_data_log_spam_in_codebase(self) -> None:
        for py_file in COMP_DIR.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            self.assertNotIn(
                '_LOGGER.warning("Fetching data")',
                content,
                f"Found debug-as-warning spam in {py_file.name}",
            )

    def test_translations_and_manifests_complete_and_valid_json(self) -> None:
        for rel in (
            REPO_ROOT / "hacs.json",
            COMP_DIR / "manifest.json",
            COMP_DIR / "icons.json",
            COMP_DIR / "strings.json",
            COMP_DIR / "translations" / "en.json",
            COMP_DIR / "translations" / "it.json",
        ):
            data = json.loads(rel.read_text(encoding="utf-8"))
            self.assertIsInstance(data, dict)

        strings = json.loads((COMP_DIR / "strings.json").read_text(encoding="utf-8"))
        en = json.loads((COMP_DIR / "translations" / "en.json").read_text(encoding="utf-8"))
        it = json.loads((COMP_DIR / "translations" / "it.json").read_text(encoding="utf-8"))
        self.assertEqual(strings, en)

        # Every sensor & binary_sensor translation_key must exist in both EN and IT
        for lang_name, doc in (("en", en), ("it", it)):
            sensor_tr = doc["entity"]["sensor"]
            for desc in SENSOR_DESCRIPTIONS:
                self.assertIn(
                    desc.translation_key,
                    sensor_tr,
                    f"Missing sensor translation {desc.translation_key} in {lang_name}.json",
                )
            bs_tr = doc["entity"]["binary_sensor"]
            for bdesc in BINARY_SENSOR_DESCRIPTIONS:
                self.assertIn(
                    bdesc.translation_key,
                    bs_tr,
                    f"Missing binary_sensor translation {bdesc.translation_key} in {lang_name}.json",
                )

    def test_no_long_dashes_anywhere_in_repository(self) -> None:
        """Ensure no em-dash or en-dash characters exist anywhere in repository files."""
        for p in REPO_ROOT.rglob("*"):
            if not p.is_file() or ".git" in p.parts or "__pycache__" in p.parts:
                continue
            txt = p.read_text(encoding="utf-8", errors="replace")
            self.assertNotIn("\u2014", txt, f"Found em-dash in {p}")
            self.assertNotIn("\u2013", txt, f"Found en-dash in {p}")

    def test_every_integration_module_class_and_function_has_docstring(self) -> None:
        """Ensure every module, class, and function in the integration is documented."""
        import ast

        for py_file in sorted(COMP_DIR.glob("*.py")):
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            self.assertIsNotNone(ast.get_docstring(tree), f"Missing module docstring in {py_file.name}")
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    self.assertIsNotNone(
                        ast.get_docstring(node),
                        f"Missing docstring on {node.name} in {py_file.name}:{node.lineno}",
                    )


class TestEntitiesAndForecastAggregation(unittest.TestCase):
    """Tests for Weather, Sensor, and BinarySensor entity outputs."""

    def _make_coordinator(self, data: ArpaVenetoData) -> tuple[ArpaVenetoDataUpdateCoordinator, ConfigEntry]:
        hass = HomeAssistant()
        entry = ConfigEntry(
            entry_id="test_entry",
            data={
                CONF_STATION_ID: 300000202,
                CONF_STATION_NAME: "Padova (PD)",
                CONF_ZONE_ID: 10,
                CONF_ZONE_NAME: "Padova e pianura centrale",
                CONF_STATION_LAT: 45.40,
                CONF_STATION_LON: 11.88,
            },
            options={
                CONF_ENABLE_BULLETIN: True,
                CONF_SECTION_AIR_QUALITY: {
                    CONF_PM10_STATION: "500000200",
                    CONF_OZONE_STATION: "500021960",
                },
            },
        )
        coord = ArpaVenetoDataUpdateCoordinator(hass, entry)
        coord.data = data
        return coord, entry

    def test_weather_entity_handles_empty_forecasts_and_exposes_gust(self) -> None:
        data = ArpaVenetoData(
            sensors={"temperature": 10.5, "wind_gust_24h": 34.2, "condition": "cloudy"},
            forecast=[],
        )
        coord, entry = self._make_coordinator(data)
        entity = ArpaVenetoWeatherEntity(coord, entry)
        self.assertEqual(entity.native_temperature, 10.5)
        self.assertEqual(entity.native_wind_gust_speed, 34.2)
        self.assertEqual(entity.condition, "cloudy")
        # Must not raise ValueError on empty forecast list
        attrs = entity.extra_state_attributes
        self.assertEqual(attrs["station_id"], 300000202)

    def test_precipitation_probability_returns_none_not_empty_string(self) -> None:
        data = ArpaVenetoData(sensors={}, forecast=[])
        coord, entry = self._make_coordinator(data)
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "precipitation_probability")
        entity = ArpaVenetoSensorEntity(coord, entry, desc)
        self.assertIsNone(entity.native_value)

    def test_binary_sensors_alert_and_exceedances(self) -> None:
        data = ArpaVenetoData(
            bulletin=BulletinSummary(
                bulletin_code="MV",
                alert="Piogge intense",
            ),
            air_quality=AirQualityData(
                pm10_daily=58.4,
                pm10_station_name="PD Granze",
                ozone_hourly=140.0,
                ozone_station_name="Este",
            ),
        )
        coord, entry = self._make_coordinator(data)
        by_key = {d.key: ArpaVenetoBinarySensorEntity(coord, entry, d) for d in BINARY_SENSOR_DESCRIPTIONS}
        self.assertTrue(by_key["weather_alert"].is_on)
        self.assertTrue(by_key["pm10_exceedance"].is_on)
        self.assertFalse(by_key["ozone_exceedance"].is_on)

    def test_daily_forecast_merges_measured_station_extremes(self) -> None:
        entries = [
            ForecastEntry(
                dt=datetime(2026, 11, 23, 16, 0, tzinfo=ARPAV_TZ),
                forecast_type="twice_daily",
                is_daytime=True,
                condition="partlycloudy",
                temp_min=11.0,
                temp_max=14.0,
                precipitation_probability=20,
            )
        ]
        daily = build_daily_forecasts(
            entries,
            measured_date="2026-11-23",
            measured_min=3.2,
            measured_max=12.0,
        )
        self.assertEqual(len(daily), 1)
        self.assertEqual(daily[0]["native_templow"], 3.2)
        self.assertEqual(daily[0]["native_temperature"], 14.0)


class TestCoordinatorTieredCachingAndDegradation(unittest.IsolatedAsyncioTestCase):
    """Verify tiered TTL caches avoid spamming slow endpoints and degrade gracefully."""

    async def test_tiered_caching_and_optional_source_failure(self) -> None:
        hass = HomeAssistant()
        entry = ConfigEntry(
            entry_id="coord_test",
            data={
                CONF_STATION_ID: 300000202,
                CONF_STATION_NAME: "Padova (PD)",
                CONF_ZONE_ID: 10,
                CONF_ZONE_NAME: "Padova e pianura centrale",
                CONF_STATION_LAT: 45.40,
                CONF_STATION_LON: 11.88,
            },
            options={
                CONF_ENABLE_BULLETIN: True,
                CONF_INFER_CONDITION: CONF_INFER_CONDITION_DISABLED,
                CONF_SECTION_POLLEN: {CONF_POLLEN_STATION: "PD01"},
            },
        )
        coord = ArpaVenetoDataUpdateCoordinator(hass, entry)

        fake_obs = StationObservation(
            station_id=300000202,
            station_name="Padova",
            values={"temperature": 10.0, "humidity": 80},
        )
        fake_u24 = {
            300000202: StationSummary24h(
                station_id=300000202,
                temp_min=3.2,
                temp_max=10.5,
                wind_gust_kmh=25.0,
            )
        }
        fake_fc = [
            ForecastEntry(
                dt=datetime(2026, 11, 23, 16, 0, tzinfo=ARPAV_TZ),
                forecast_type="twice_daily",
                is_daytime=True,
                condition="cloudy",
                precipitation_probability=30,
            )
        ]
        fake_bulletin = BulletinSummary(bulletin_code="MV", general_evolution="Variabile.")

        with (
            patch.object(coord.api, "async_get_station_observations", AsyncMock(return_value=fake_obs)) as m_st,
            patch.object(coord.api, "async_get_ultime24ore", AsyncMock(return_value=fake_u24)) as m_u24,
            patch.object(coord.api, "async_get_forecast_symbols", AsyncMock(return_value=fake_fc)) as m_fc,
            patch.object(coord.api, "async_get_bulletin_text", AsyncMock(return_value=fake_bulletin)) as m_bul,
            patch.object(
                coord.api,
                "async_get_pollen_report",
                AsyncMock(side_effect=ArpaVenetoConnectionError("pollen down")),
            ) as m_pol,
        ):
            # Tick 1: pollen fails -> must NOT crash primary update!
            data1 = await coord._async_update_data()
            self.assertEqual(data1.sensors["temperature"], 10.0)
            self.assertEqual(data1.sensors["wind_gust_24h"], 25.0)
            self.assertEqual(data1.sensors["precipitation_probability"], 30)
            self.assertIsNone(data1.pollen)
            self.assertEqual(m_st.call_count, 1)
            self.assertEqual(m_fc.call_count, 1)
            self.assertEqual(m_bul.call_count, 1)
            self.assertEqual(m_pol.call_count, 1)

            # Tick 2 immediately after: forecast & bulletin served from 30m cache!
            await coord._async_update_data()
            self.assertEqual(m_st.call_count, 2)
            self.assertEqual(m_u24.call_count, 2)
            self.assertEqual(m_fc.call_count, 1)
            self.assertEqual(m_bul.call_count, 1)

            # Force cache clear -> reloads forecast & bulletin
            coord.clear_caches()
            await coord._async_update_data()
            self.assertEqual(m_fc.call_count, 2)
            self.assertEqual(m_bul.call_count, 2)


class TestRadarImageEntityCaching(unittest.IsolatedAsyncioTestCase):
    """Verify radar image entity caches bytes for 5 minutes and falls back gracefully."""

    async def test_radar_caching_and_fallback(self) -> None:
        from datetime import UTC

        from custom_components.arpa_veneto_meteo.const import CONF_RADAR_MOSAIC, CONF_RADAR_SOURCE
        from custom_components.arpa_veneto_meteo.image import ArpaVenetoRadarImageEntity
        from custom_components.arpa_veneto_meteo.models import RadarFrame

        hass = HomeAssistant()
        entry = ConfigEntry(
            entry_id="radar_test",
            data={
                CONF_STATION_ID: 300000202,
                CONF_STATION_NAME: "Padova (PD)",
                CONF_ZONE_ID: 10,
                CONF_ZONE_NAME: "Padova e pianura centrale",
            },
            options={CONF_RADAR_SOURCE: CONF_RADAR_MOSAIC},
        )
        coord = ArpaVenetoDataUpdateCoordinator(hass, entry)
        entity = ArpaVenetoRadarImageEntity(hass, coord, entry)

        frame = RadarFrame(
            source=CONF_RADAR_MOSAIC,
            content_type="image/png",
            image_bytes=b"\x89PNGFAKE",
            observed_at=datetime.now(UTC),
        )
        with patch.object(coord.api, "async_get_radar_frame", AsyncMock(return_value=frame)) as m_rad:
            img1 = await entity.async_image()
            img2 = await entity.async_image()
            self.assertEqual(img1, b"\x89PNGFAKE")
            self.assertEqual(img2, b"\x89PNGFAKE")
            # Second call within 5 minutes must use cached bytes
            self.assertEqual(m_rad.call_count, 1)


if __name__ == "__main__":
    unittest.main()
