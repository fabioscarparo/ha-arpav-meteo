"""Weather stations are sorted from the municipality chosen in the first setup step."""

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
from custom_components.arpa_veneto_meteo.api import (  # noqa: E402
    ArpaVenetoApiClient,
    select_station_reference,
)
from custom_components.arpa_veneto_meteo.comuni_coords import COMUNI_COORDS  # noqa: E402
from custom_components.arpa_veneto_meteo.const import (  # noqa: E402
    CONF_COMUNE_ID,
    CONF_STATION_ID,
    CONF_ZONE_ID,
)

# meteo_comuni as served by ARPAV on 2026-11-25 (id, provincia, comune, istat, zonaid)
COMUNI = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "meteo_comuni.json").read_text(encoding="utf-8")
)
BOARA_PISANI = {"id": 2614, "istat": 28012, "zone": 13, "coords": (45.1077, 11.7826)}
ZONE_POINTS = {10: (45.4, 11.9), 13: (45.0, 11.5)}


class TestStationReference(unittest.TestCase):
    def test_municipality_coordinates_win(self) -> None:
        self.assertEqual(select_station_reference(28012, (45.0, 11.5)), BOARA_PISANI["coords"])

    def test_zone_point_when_municipality_is_unknown(self) -> None:
        self.assertEqual(select_station_reference(99999, (45.0, 11.5)), (45.0, 11.5))
        self.assertEqual(select_station_reference(None, (45.0, 11.5)), (45.0, 11.5))

    def test_nothing_known(self) -> None:
        self.assertEqual(select_station_reference(None, None), (None, None))

    def test_every_arpav_municipality_has_coordinates(self) -> None:
        missing = sorted(
            {row["istat"] for row in COMUNI["data"]} - set(COMUNI_COORDS)
        )
        self.assertEqual(missing, [], "run scripts/generate_comuni_coords.py")

    def test_coordinates_are_in_veneto(self) -> None:
        for istat, (lat, lon) in COMUNI_COORDS.items():
            self.assertTrue(44.7 < lat < 46.8 and 10.6 < lon < 13.2, istat)


class TestComuniApi(unittest.TestCase):
    def test_comuni_expose_istat_codes(self) -> None:
        client = ArpaVenetoApiClient(SimpleNamespace())
        with patch.object(client, "_get_json", AsyncMock(return_value=COMUNI)):
            names, zones, istat = asyncio.run(client.async_get_comuni())
        self.assertEqual(names[2614], "Boara Pisani (Padova)")
        self.assertEqual(zones[2614], 13)
        self.assertEqual(istat[2614], 28012)


class TestConfigFlowStationOrder(unittest.TestCase):
    def _flow(self) -> config_flow.ArpaVenetoConfigFlow:
        flow = config_flow.ArpaVenetoConfigFlow()
        # Home Assistant located in Padova: it must not drive the order any more
        flow.hass = SimpleNamespace(config=SimpleNamespace(latitude=45.4064, longitude=11.8768))
        flow.async_show_form = lambda **kwargs: kwargs
        return flow

    def _run_station_step(self, flow: Any) -> tuple[dict[str, Any], AsyncMock]:
        api = config_flow.ArpaVenetoApiClient
        stations = AsyncMock(return_value=[])
        with (
            patch.object(api, "async_get_comuni", AsyncMock(return_value=self._comuni())),
            patch.object(api, "async_get_zones", AsyncMock(return_value=({10: "Padova", 13: "Rovigo"}, ZONE_POINTS))),
            patch.object(api, "async_get_meteo_stations", stations),
        ):
            result = asyncio.run(flow.async_step_station())
        return result, stations

    @staticmethod
    def _comuni() -> tuple[dict[int, str], dict[int, int], dict[int, int]]:
        return (
            {2614: "Boara Pisani (Padova)", 1: "Nowhere (Padova)"},
            {2614: 13, 1: 10},
            {2614: 28012, 1: 99999},
        )

    def test_setup_sorts_from_the_chosen_municipality(self) -> None:
        flow = self._flow()
        flow._comuni, flow._comune_to_zone, flow._comune_istat = self._comuni()
        flow._selected_comune_id = 2614
        _, stations = self._run_station_step(flow)
        stations.assert_awaited_once_with(*BOARA_PISANI["coords"])

    def test_unknown_municipality_falls_back_to_the_zone_point(self) -> None:
        flow = self._flow()
        flow._comuni, flow._comune_to_zone, flow._comune_istat = self._comuni()
        flow._selected_comune_id = 1
        _, stations = self._run_station_step(flow)
        stations.assert_awaited_once_with(*ZONE_POINTS[10])

    def test_reconfigure_loads_the_municipalities_it_needs(self) -> None:
        flow = self._flow()
        flow._reconfigure_entry = SimpleNamespace(data={CONF_COMUNE_ID: 2614, CONF_ZONE_ID: 13, CONF_STATION_ID: 1})
        flow._selected_comune_id = 2614
        _, stations = self._run_station_step(flow)
        stations.assert_awaited_once_with(*BOARA_PISANI["coords"])
        # the zone of the municipality is known again for the zone preselection
        self.assertEqual(flow._comune_to_zone[2614], BOARA_PISANI["zone"])


if __name__ == "__main__":
    unittest.main()
