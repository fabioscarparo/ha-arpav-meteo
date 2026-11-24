"""Regression tests for HA entities, Recorder state classes, coordinator caching, and translations."""

from __future__ import annotations

import json
import pathlib
import unittest
from datetime import datetime
from typing import Any
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
    MAX_HA_STATE_LEN,
    SENSOR_DESCRIPTIONS,
    ArpaVenetoSensorEntity,
    _truncate_state,
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
        self.assertEqual(by_key["pm10_daily"].native_unit_of_measurement, "µg/m³")
        for py_file in COMP_DIR.glob("*.py"):
            self.assertNotIn(
                "CONCENTRATION_MICROGRAMS_PER_CUBIC_METER",
                py_file.read_text(encoding="utf-8"),
                f"Deprecated concentration constant used in {py_file.name}",
            )

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
            # Per-species pollen sensors: translated name with the species as placeholder
            self.assertIn("{species}", sensor_tr["pollen_species"]["name"])
            bs_tr = doc["entity"]["binary_sensor"]
            for bdesc in BINARY_SENSOR_DESCRIPTIONS:
                self.assertIn(
                    bdesc.translation_key,
                    bs_tr,
                    f"Missing binary_sensor translation {bdesc.translation_key} in {lang_name}.json",
                )

    def test_no_long_dashes_anywhere_in_repository(self) -> None:
        """Ensure no em-dash or en-dash characters exist anywhere in repository files."""
        binary_suffixes = {".png", ".jpg", ".jpeg", ".webp", ".ico", ".woff2"}
        for p in REPO_ROOT.rglob("*"):
            if not p.is_file() or ".git" in p.parts or "__pycache__" in p.parts:
                continue
            if p.suffix.lower() in binary_suffixes:
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

    def test_bulletin_summary_truncation_fits_ha_255_char_limit(self) -> None:
        long_text = (
            "Domenica il transito di una perturbazione di origine atlantica porta frequenti "
            "annuvolamenti, precipitazioni estese e nevicate sui rilievi montani. "
            "Da lunedi la pressione atmosferica tornera ad aumentare gradualmente favorendo "
            "schiarite via via piu ampie su pianura e costa, con temperature minime in calo "
            "e possibili foschie nelle ore piu fredde della notte e del primo mattino."
        )
        self.assertGreater(len(long_text), MAX_HA_STATE_LEN)

        data = ArpaVenetoData(
            bulletin=BulletinSummary(
                bulletin_code="MV",
                general_evolution=long_text,
            )
        )
        coord, entry = self._make_coordinator(data)
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "bulletin_summary")
        entity = ArpaVenetoSensorEntity(coord, entry, desc)

        val = entity.native_value
        self.assertIsNotNone(val)
        self.assertLessEqual(len(val), MAX_HA_STATE_LEN)
        self.assertTrue(val.endswith("..."))
        # Full untruncated text must stay available in attributes
        self.assertEqual(entity.extra_state_attributes["general_evolution"], long_text)

        # Edge cases for _truncate_state
        self.assertEqual(len(_truncate_state("a" * 300) or ""), MAX_HA_STATE_LEN)
        self.assertEqual(len(_truncate_state("b" * 256) or ""), MAX_HA_STATE_LEN)
        self.assertEqual(_truncate_state("c" * 255), "c" * 255)
        self.assertIsNone(_truncate_state("   "))

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


class TestFrontendCardServing(unittest.IsolatedAsyncioTestCase):
    """Verify built-in Lovelace card registration, version sync, and frontend contracts."""

    async def test_frontend_static_path_and_extra_js_registration_is_idempotent(self) -> None:
        import hashlib

        from custom_components.arpa_veneto_meteo.const import CARD_FILENAME, CARD_URL
        from custom_components.arpa_veneto_meteo.frontend import async_register_frontend

        registered_paths: list[Any] = []

        class _FakeHttp:
            async def async_register_static_paths(self, configs: list[Any]) -> None:
                registered_paths.extend(configs)

        hass = HomeAssistant()
        hass.http = _FakeHttp()  # type: ignore[attr-defined]

        # Must skip safely when frontend component is not loaded (e.g. headless/tests)
        skipped = await async_register_frontend(hass)
        self.assertFalse(skipped)
        self.assertEqual(len(registered_paths), 0)

        hass.config.components.add("frontend")
        first = await async_register_frontend(hass)
        second = await async_register_frontend(hass)
        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(len(registered_paths), 1)
        self.assertEqual(registered_paths[0].url_path, CARD_URL)
        self.assertTrue(registered_paths[0].cache_headers)
        card_file = pathlib.Path(registered_paths[0].path)
        self.assertTrue(card_file.is_file())
        self.assertEqual(card_file.name, CARD_FILENAME)
        expected_digest = hashlib.sha256(card_file.read_bytes()).hexdigest()[:12]
        self.assertEqual(
            getattr(hass, "_extra_js_urls", []),
            [(f"{CARD_URL}?v={expected_digest}", False)],
        )

    def test_lovelace_card_versions_and_design_contracts(self) -> None:
        import shutil
        import subprocess

        from custom_components.arpa_veneto_meteo.const import CARD_FILENAME, CARD_VERSION

        manifest = json.loads((COMP_DIR / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], CARD_VERSION)
        self.assertEqual(manifest["dependencies"], [])
        self.assertIn("frontend", manifest["after_dependencies"])
        self.assertIn("http", manifest["after_dependencies"])

        card_path = COMP_DIR / "frontend" / CARD_FILENAME
        self.assertTrue(card_path.is_file())
        source = card_path.read_text(encoding="utf-8")

        self.assertIn(f'const VERSION = "{CARD_VERSION}"', source)
        self.assertIn("container-type: inline-size", source)
        self.assertIn("overscroll-behavior: contain", source)
        self.assertIn('closedby", "any"', source)
        self.assertIn("closedBy", source)
        self.assertIn('customElements.whenDefined("home-assistant")', source)
        self.assertIn("window.customCards", source)
        self.assertIn("async function loadHaForm()", source)
        self.assertIn("flatten: true", source)
        self.assertIn("filter: { integration: DOMAIN }", source)
        self.assertNotIn("prefers-color-scheme", source)
        self.assertNotIn(":host-context", source)
        self.assertNotIn('role="dialog"', source)
        self.assertNotIn("aria-modal", source)
        self.assertNotIn("__ARPAV_DEMO__", source)

        node_bin = shutil.which("node")
        if node_bin is not None:
            syntax = subprocess.run(
                [node_bin, "--check", str(card_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(syntax.returncode, 0, syntax.stderr)

            behavior = subprocess.run(
                [node_bin, str(REPO_ROOT / "tests" / "test_lovelace_card.mjs")],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(behavior.returncode, 0, behavior.stderr or behavior.stdout)


if __name__ == "__main__":
    unittest.main()
