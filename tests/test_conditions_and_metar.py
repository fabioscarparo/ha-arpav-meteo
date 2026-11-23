"""Unit tests for the weather condition classifier and METAR parser."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from tests.ha_stubs import install_stubs_if_needed

install_stubs_if_needed()

from custom_components.arpa_veneto_meteo.conditions import async_classify_condition  # noqa: E402
from custom_components.arpa_veneto_meteo.const import (  # noqa: E402
    ARPAV_TZ,
    CONF_DAY_CONDITION_RADIATION_OR_FORECAST,
    CONF_NIGHT_CONDITION_BRIGHTNESS_OR_FORECAST,
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
)
from custom_components.arpa_veneto_meteo.metar import (  # noqa: E402
    is_observation_current,
    metar_condition,
    parse_observation,
)
from custom_components.arpa_veneto_meteo.models import (  # noqa: E402
    ForecastEntry,
    SkyBrightnessReading,
)


class TestMetarParser(unittest.TestCase):
    """Tests for NOAA METAR parsing and condition mapping."""

    def test_parse_observation_and_condition(self) -> None:
        now = datetime.now(UTC)
        report = {
            "icaoId": "LIPZ",
            "reportTime": now.isoformat().replace("+00:00", "Z"),
            "temp": 12.0,
            "dewp": 10.0,
            "altim": 1018.2,
            "visib": "6+",
            "wspd": 10,
            "wgst": 20,
            "wdir": 180,
            "clouds": [{"cover": "FEW"}, {"cover": "BKN"}],
            "rawOb": "METAR LIPZ ... BKN030",
        }
        obs = parse_observation(report)
        self.assertTrue(is_observation_current(obs, now))
        self.assertEqual(obs.cloud_coverage, 75)
        self.assertEqual(obs.values["pressure"], 1018.2)
        self.assertAlmostEqual(obs.values["visibility"], 9.66, places=2)
        self.assertEqual(obs.values["wind_bearing"], 180)
        self.assertEqual(obs.values["wind_bearing_cardinal"], "S")
        self.assertEqual(metar_condition(obs, is_day=True), "cloudy")

        # Staleness check (> 90 min)
        self.assertFalse(is_observation_current(obs, now + timedelta(minutes=95)))

    def test_metar_present_weather_precedence(self) -> None:
        obs_ts = parse_observation({"icaoId": "LIPZ", "wxString": "+TSRA", "clouds": []})
        self.assertEqual(metar_condition(obs_ts, is_day=True), "lightning-rainy")

        obs_cavok = parse_observation({"icaoId": "LIPZ", "clouds": [], "rawOb": "LIPZ CAVOK"})
        self.assertEqual(obs_cavok.cloud_coverage, 0)
        self.assertEqual(metar_condition(obs_cavok, is_day=False), "clear-night")


class TestConditionClassifier(unittest.IsolatedAsyncioTestCase):
    """Tests for sky condition inference rules and fallbacks."""

    async def test_precipitation_rules_including_fixed_pouring_threshold(self) -> None:
        dt = datetime(2026, 11, 23, 12, 0, tzinfo=ARPAV_TZ)

        # Heavy rain: 1.0 mm in 5 min -> 12.0 mm/h >= 10 mm/h => pouring!
        cond, prov = await async_classify_condition(
            latitude=45.4,
            longitude=11.9,
            dt=dt,
            sensors={"temperature": 12.0, "precipitation_5m": 1.0, "precipitation_intensity": 12.0},
            sources={},
            forecasts=[],
            zone_name="Padova",
        )
        self.assertEqual(cond, "pouring")
        self.assertEqual(prov.rule, RULE_PRECIPITATION)

        # Freezing precipitation => snowy
        cond_snow, _ = await async_classify_condition(
            latitude=45.4,
            longitude=11.9,
            dt=dt,
            sensors={"temperature": -0.5, "precipitation_5m": 0.4, "precipitation_intensity": 4.8},
            sources={},
            forecasts=[],
            zone_name="Arabba",
        )
        self.assertEqual(cond_snow, "snowy")

        # Near-freezing => snowy-rainy
        cond_mix, _ = await async_classify_condition(
            latitude=45.4,
            longitude=11.9,
            dt=dt,
            sensors={"temperature": 1.5, "precipitation_5m": 0.2, "precipitation_intensity": 2.4},
            sources={},
            forecasts=[],
            zone_name="Belluno",
        )
        self.assertEqual(cond_mix, "snowy-rainy")

    async def test_fog_and_wind_overrides(self) -> None:
        dt = datetime(2026, 11, 23, 12, 0, tzinfo=ARPAV_TZ)
        cond_fog, prov_fog = await async_classify_condition(
            latitude=45.4,
            longitude=11.9,
            dt=dt,
            sensors={"visibility": 0.6, "wind_speed": 40.0},
            sources={},
            forecasts=[],
            zone_name="Padova",
        )
        self.assertEqual(cond_fog, "fog")
        self.assertEqual(prov_fog.rule, RULE_VISIBILITY)

        cond_wind, prov_wind = await async_classify_condition(
            latitude=45.4,
            longitude=11.9,
            dt=dt,
            sensors={"visibility": 20.0, "wind_speed": 42.0},
            sources={},
            forecasts=[],
            zone_name="Padova",
        )
        self.assertEqual(cond_wind, "windy")
        self.assertEqual(prov_wind.rule, RULE_WIND)

    async def test_daytime_radiation_and_low_sun_fallback(self) -> None:
        dt = datetime(2026, 6, 21, 12, 0, tzinfo=ARPAV_TZ)
        fc = [
            ForecastEntry(
                dt=dt,
                forecast_type="twice_daily",
                is_daytime=True,
                condition="partlycloudy",
            )
        ]

        # High sun (60 deg), high GHI -> sunny from solar radiation
        with patch(
            "custom_components.arpa_veneto_meteo.conditions._sun_is_day_and_elevation",
            return_value=(True, 60.0),
        ):
            cond, prov = await async_classify_condition(
                latitude=45.4,
                longitude=11.9,
                dt=dt,
                sensors={"solar_radiation": 800.0},
                sources={},
                forecasts=fc,
                zone_name="Padova",
                day_strategy=CONF_DAY_CONDITION_RADIATION_OR_FORECAST,
            )
            self.assertEqual(cond, "sunny")
            self.assertEqual(prov.rule, RULE_SOLAR_RADIATION)

        # Very low sun (2 deg) -> radiation ignored, falls back to METAR if available
        obs_metar = parse_observation({"icaoId": "LIPZ", "clouds": [], "rawOb": "CAVOK"})
        with patch(
            "custom_components.arpa_veneto_meteo.conditions._sun_is_day_and_elevation",
            return_value=(True, 2.0),
        ):
            cond2, prov2 = await async_classify_condition(
                latitude=45.4,
                longitude=11.9,
                dt=dt,
                sensors={"solar_radiation": 5.0},
                sources={},
                forecasts=fc,
                zone_name="Padova",
                day_strategy=CONF_DAY_CONDITION_RADIATION_OR_FORECAST,
                metar_obs=obs_metar,
            )
            self.assertEqual(cond2, "sunny")
            self.assertEqual(prov2.source, SOURCE_METAR)
            self.assertEqual(prov2.rule, RULE_CLOUD_COVER)

    async def test_nighttime_brightness_and_forecast_fallback(self) -> None:
        dt = datetime(2026, 11, 23, 22, 0, tzinfo=ARPAV_TZ)
        fc = [
            ForecastEntry(
                dt=dt,
                forecast_type="twice_daily",
                is_daytime=False,
                condition="sunny",
            )
        ]

        async def _bright() -> SkyBrightnessReading:
            return SkyBrightnessReading(value=21.2, station_name="Ekar")

        with (
            patch(
                "custom_components.arpa_veneto_meteo.conditions._sun_is_day_and_elevation",
                return_value=(False, -30.0),
            ),
            patch(
                "custom_components.arpa_veneto_meteo.conditions.moon_illumination",
                return_value=5.0,
            ),
        ):
            cond, prov = await async_classify_condition(
                latitude=45.4,
                longitude=11.9,
                dt=dt,
                sensors={},
                sources={},
                forecasts=fc,
                zone_name="Padova",
                night_strategy=CONF_NIGHT_CONDITION_BRIGHTNESS_OR_FORECAST,
                fetch_brightness=_bright,
            )
            self.assertEqual(cond, "clear-night")
            self.assertEqual(prov.source, SOURCE_BRIGHTNESS)
            self.assertEqual(prov.rule, RULE_SKY_BRIGHTNESS)

        async def _no_bright() -> None:
            return None

        with patch(
            "custom_components.arpa_veneto_meteo.conditions._sun_is_day_and_elevation",
            return_value=(False, -30.0),
        ):
            cond_fb, prov_fb = await async_classify_condition(
                latitude=45.4,
                longitude=11.9,
                dt=dt,
                sensors={},
                sources={},
                forecasts=fc,
                zone_name="Padova",
                night_strategy=CONF_NIGHT_CONDITION_BRIGHTNESS_OR_FORECAST,
                fetch_brightness=_no_bright,
            )
            # Forecast "sunny" at night is mapped to "clear-night"
            self.assertEqual(cond_fb, "clear-night")
            self.assertEqual(prov_fb.source, SOURCE_FORECAST)
            self.assertEqual(prov_fb.rule, RULE_FORECAST)


if __name__ == "__main__":
    unittest.main()
