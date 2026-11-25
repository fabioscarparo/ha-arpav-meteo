"""Tests for the options flow: optional station catalogs and how their failures are reported."""

from __future__ import annotations

import asyncio
import json
import pathlib
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from tests.ha_stubs import install_stubs_if_needed

install_stubs_if_needed()

from custom_components.arpa_veneto_meteo import config_flow  # noqa: E402
from custom_components.arpa_veneto_meteo.const import (  # noqa: E402
    CONF_STATION_LAT,
    CONF_STATION_LON,
)
from custom_components.arpa_veneto_meteo.models import GeoStation  # noqa: E402

COMP_DIR = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "arpa_veneto_meteo"


def _station(station_id: str, name: str) -> GeoStation:
    return GeoStation(station_id=station_id, name=name, province="Padova", distance_km=5.0)


def _aerodrome() -> SimpleNamespace:
    return SimpleNamespace(icao="LIPU", label="LIPU - Padova (20.7 km)")


class TestOptionsFlowCatalogs(unittest.TestCase):
    """The options form loads six optional catalogs; failures must be visible, not silent."""

    def _run(
        self,
        metar_result: Any,
        arpav_error: Exception | None = None,
        station_coords: tuple[float | None, float | None] = (45.21, 11.83),
    ) -> tuple[dict[str, Any], AsyncMock]:
        handler = config_flow.ArpaVenetoOptionsFlowHandler()
        handler.hass = SimpleNamespace(config=SimpleNamespace(latitude=45.4064, longitude=11.8768))
        handler.config_entry = SimpleNamespace(
            data={CONF_STATION_LAT: station_coords[0], CONF_STATION_LON: station_coords[1]},
            options={},
        )
        handler.async_show_form = lambda **kwargs: kwargs

        stations = AsyncMock(return_value=[_station("1", "Mandria")])
        if arpav_error is not None:
            stations.side_effect = arpav_error
        metar_fetch = AsyncMock()
        if isinstance(metar_result, BaseException):
            metar_fetch.side_effect = metar_result
        else:
            metar_fetch.return_value = metar_result

        api = config_flow.ArpaVenetoApiClient
        with (
            patch.object(api, "async_get_air_quality_stations", stations),
            patch.object(api, "async_get_hydro_stations", stations),
            patch.object(api, "async_get_pollen_stations", stations),
            patch.object(config_flow.metar, "async_fetch_stations", metar_fetch),
        ):
            result = asyncio.run(handler.async_step_init())
        return result, metar_fetch

    def test_all_catalogs_loaded_shows_no_error(self) -> None:
        result, _ = self._run([_aerodrome()])
        self.assertEqual(result["errors"], {})
        self.assertIsNone(result["description_placeholders"])

    def test_cancelled_catalog_propagates(self) -> None:
        with self.assertRaises(asyncio.CancelledError):
            self._run(asyncio.CancelledError())

    def test_failed_metar_catalog_is_reported_and_logged(self) -> None:
        with self.assertLogs(config_flow._LOGGER, level="WARNING") as logs:
            result, _ = self._run(TimeoutError())
        self.assertEqual(result["errors"], {"base": "catalog_unavailable"})
        self.assertEqual(result["description_placeholders"], {"sources": "NOAA aviationweather.gov"})
        self.assertIn("METAR aerodromes from NOAA aviationweather.gov: TimeoutError", logs.output[0])

    def test_each_failed_source_is_named_once(self) -> None:
        with self.assertLogs(config_flow._LOGGER, level="WARNING") as logs:
            result, _ = self._run(OSError("network unreachable"), arpav_error=OSError("refused"))
        self.assertEqual(
            result["description_placeholders"], {"sources": "ARPAV, NOAA aviationweather.gov"}
        )
        # Five ARPAV catalogs and the METAR one, each with its own reason in the log
        self.assertEqual(len(logs.output), 6)
        self.assertIn("refused", logs.output[0])

    def test_station_without_coordinates_uses_home_location_for_metar(self) -> None:
        _, metar_fetch = self._run([_aerodrome()], station_coords=(None, None))
        args = metar_fetch.await_args.args
        self.assertEqual((args[1], args[2]), (45.4064, 11.8768))

    def test_error_message_is_translated_with_its_placeholder(self) -> None:
        for name in ("strings.json", "translations/en.json", "translations/it.json"):
            doc = json.loads((COMP_DIR / name).read_text(encoding="utf-8"))
            self.assertIn("{sources}", doc["options"]["error"]["catalog_unavailable"], name)


if __name__ == "__main__":
    unittest.main()
