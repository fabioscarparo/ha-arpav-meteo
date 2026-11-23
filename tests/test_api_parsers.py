"""Unit tests for all pure ARPA Veneto API parsers."""

from __future__ import annotations

import base64
import unittest
from datetime import UTC, datetime, timedelta

from tests.ha_stubs import install_stubs_if_needed

install_stubs_if_needed()

from custom_components.arpa_veneto_meteo.api import (  # noqa: E402
    compute_dew_point,
    degrees_to_cardinal,
    haversine_km,
    map_symbol_to_condition,
    parse_air_quality_latest,
    parse_air_quality_stations,
    parse_avalanche_xml,
    parse_brightness_reading,
    parse_bulletin_text,
    parse_forecast_symbols,
    parse_hydro_reading,
    parse_hydro_stations,
    parse_pollen_index,
    parse_pollen_report,
    parse_radar_base_frame,
    parse_station_observations,
    parse_ultime24ore,
    select_bulletin_code_for_zone,
)
from custom_components.arpa_veneto_meteo.const import (  # noqa: E402
    AQ_PARAM_OZONE,
    AQ_PARAM_PM10,
    AQ_PARAM_PM25,
    ARPAV_TZ,
)


class TestStationObservationsParser(unittest.TestCase):
    """Tests for `meteo_meteogrammi_tabella` parsing and precipitation windows."""

    def test_empty_station_payload_does_not_crash(self) -> None:
        obs = parse_station_observations(300000202, {"data": []})
        self.assertEqual(obs.station_id, 300000202)
        self.assertEqual(obs.values, {})
        self.assertIsNone(obs.observed_at)

    def test_multi_sensor_parsing_and_units(self) -> None:
        payload = {
            "data": [
                {
                    "nome_stazione": "Asiago - aeroporto",
                    "tipo": "TARIA2M",
                    "valore": "4.1",
                    "unitnm": "°C",
                    "dataora": "2026-11-23T10:20:00",
                },
                {
                    "nome_stazione": "Asiago - aeroporto",
                    "tipo": "TARIA2M",
                    "valore": "1.2",
                    "unitnm": "°C",
                    "dataora": "2026-11-23T06:00:00",
                },
                {
                    "nome_stazione": "Asiago - aeroporto",
                    "tipo": "UMID2M",
                    "valore": "79",
                    "unitnm": "%",
                    "dataora": "2026-11-23T10:20:00",
                },
                {
                    "nome_stazione": "Asiago - aeroporto",
                    "tipo": "PRESS",
                    "valore": "1015.4",
                    "unitnm": "hPa",
                    "dataora": "2026-11-23T10:00:00",
                },
                {
                    "nome_stazione": "Asiago - aeroporto",
                    "tipo": "VISIB",
                    "valore": "75000",
                    "unitnm": "m",
                    "dataora": "2026-11-23T10:20:00",
                },
                {
                    "nome_stazione": "Asiago - aeroporto",
                    "tipo": "VVENTO10M",
                    "valore": "2.5",
                    "unitnm": "m/s",
                    "dataora": "2026-11-23T10:20:00",
                },
                {
                    "nome_stazione": "Asiago - aeroporto",
                    "tipo": "DVENTO10M",
                    "valore": "360",
                    "unitnm": "gradi",
                    "dataora": "2026-11-23T10:20:00",
                },
                {
                    "nome_stazione": "Asiago - aeroporto",
                    "tipo": "RADSOL",
                    "valore": "0.720",
                    "unitnm": "MJ/m2",
                    "dataora": "2026-11-23T10:10:00",
                },
                {
                    "nome_stazione": "Asiago - aeroporto",
                    "tipo": "NIVOM",
                    "valore": "13",
                    "unitnm": "cm",
                    "dataora": "2026-11-23T10:00:00",
                },
                {
                    "nome_stazione": "Asiago - aeroporto",
                    "tipo": "BFOGL",
                    "valore": "25",
                    "unitnm": "% T",
                    "dataora": "2026-11-23T10:15:00",
                },
            ]
        }
        obs = parse_station_observations(300000252, payload)
        self.assertEqual(obs.values["temperature"], 4.1)
        self.assertEqual(obs.values["humidity"], 79)
        self.assertEqual(obs.values["pressure"], 1015.4)
        self.assertEqual(obs.values["visibility"], 75.0)
        self.assertEqual(obs.values["wind_speed"], 9.0)
        self.assertEqual(obs.values["wind_bearing"], 0)
        self.assertEqual(obs.values["wind_bearing_cardinal"], "N")
        self.assertAlmostEqual(obs.values["solar_radiation"], 200.0, places=1)
        self.assertAlmostEqual(obs.values["uv_index"], 1.7, places=1)
        self.assertEqual(obs.values["snow_depth"], 13.0)
        self.assertEqual(obs.values["leaf_wetness"], 25.0)
        self.assertIsNotNone(obs.values["dew_point"])
        self.assertEqual(obs.measured_temp_date, "2026-11-23")
        self.assertEqual(obs.measured_temp_min, 1.2)
        self.assertEqual(obs.measured_temp_max, 4.1)

    def test_radsol_uppercase_wm2_and_visib_km(self) -> None:
        payload = {
            "data": [
                {
                    "nome_stazione": "Adria",
                    "tipo": "RADSOL",
                    "valore": "500",
                    "unitnm": "W/m2",
                    "dataora": "2026-07-15T12:00:00",
                },
                {
                    "nome_stazione": "Adria",
                    "tipo": "VISIB",
                    "valore": "66.20",
                    "unitnm": "Km",
                    "dataora": "2026-07-15T12:00:00",
                },
            ]
        }
        obs = parse_station_observations(1, payload)
        self.assertEqual(obs.values["solar_radiation"], 500.0)
        self.assertEqual(obs.values["uv_index"], 1.2)
        self.assertEqual(obs.values["visibility"], 66.2)

    def test_precipitation_rolling_windows_and_today(self) -> None:
        # Reference time: 2026-11-23 10:00:00+01:00 (09:00 UTC)
        now = datetime(2026, 11, 23, 9, 0, 0, tzinfo=UTC)
        payload = {
            "data": [
                {"tipo": "PREC", "valore": "1.0", "dataora": "2026-11-23T10:00:00"},
                {"tipo": "PREC", "valore": "0.5", "dataora": "2026-11-23T09:30:00"},
                {"tipo": "PREC", "valore": "2.0", "dataora": "2026-11-23T08:00:00"},
                {"tipo": "PREC", "valore": "3.0", "dataora": "2026-11-23T05:00:00"},
                {"tipo": "PREC", "valore": "4.0", "dataora": "2026-11-22T23:00:00"},
                {"tipo": "PREC", "valore": "10.0", "dataora": "2026-11-22T09:00:00"},  # > 24h ago
            ]
        }
        obs = parse_station_observations(10, payload, now=now)
        self.assertEqual(obs.values["precipitation_5m"], 1.0)
        self.assertEqual(obs.values["precipitation_intensity"], 12.0)
        self.assertEqual(obs.values["precipitation_1h"], 1.5)
        self.assertEqual(obs.values["precipitation_3h"], 3.5)
        self.assertEqual(obs.values["precipitation_6h"], 6.5)
        self.assertEqual(obs.values["precipitation_12h"], 10.5)
        self.assertEqual(obs.values["precipitation_24h"], 10.5)
        self.assertEqual(obs.values["precipitation_today"], 6.5)


class TestUltime24OreAndForecastParsers(unittest.TestCase):
    """Tests for 24h summary, IT/EN forecasts, and textual bulletins."""

    def test_parse_ultime24ore(self) -> None:
        payload = {
            "data": [
                {
                    "codseqst": 300000158,
                    "nome_stazione": "Arabba",
                    "dataora_aggiornamento": "2026-11-23T10:20:00",
                    "ultima_temp_aria": -1.0,
                    "temp_aria_min": -3.6,
                    "temp_aria_max": -0.2,
                    "precipitazione": 0.0,
                    "velo_vento_max": 1.9,
                    "velo_vento_raffica": 5.8,
                    "altezza_neve": 13.0,
                    "humidex": None,
                    "windchill": -1.9,
                }
            ]
        }
        parsed = parse_ultime24ore(payload)
        self.assertIn(300000158, parsed)
        s = parsed[300000158]
        self.assertEqual(s.temp_min, -3.6)
        self.assertEqual(s.temp_max, -0.2)
        self.assertEqual(s.wind_speed_max_kmh, 6.8)
        self.assertEqual(s.wind_gust_kmh, 20.9)
        self.assertEqual(s.snow_depth_cm, 13.0)
        self.assertEqual(s.windchill, -1.9)

    def test_forecast_symbols_it_and_en(self) -> None:
        it_payload = {
            "data": [
                {
                    "dataemissione": "2026-11-22T13:00:00",
                    "aggiornamento": "2026-11-23T09:00:00",
                    "zonaid": 10,
                    "zona": "Padova e pianura centrale",
                    "scadenza": "2026-11-23",
                    "intervallo": "notte/mattina",
                    "simbolo": "a1N.png",
                    "testo": "Sereno",
                    "temperatura": "5/7",
                    "prob precipitazioni": "10%",
                    "attendibilita": "Buona",
                    "precipitazioni": "Assenti",
                    "quota neve": "",
                },
                {
                    "scadenza": "2026-11-23",
                    "intervallo": "pom/sera",
                    "simbolo": "b7.png",
                    "testo": "Molto nuvoloso",
                    "temperatura": "12/14",
                    "prob precipitazioni": "90%",
                    "quota neve": "Oltre i 1200/1400 m",
                },
                {
                    "scadenza": "2026-11-24",
                    "intervallo": "",
                    "simbolo": "d3.png",
                    "testo": "Nevicate",
                    "temperatura": "",
                    "temperatura 2000m": "-5",
                    "prob precipitazioni": "80%",
                },
            ]
        }
        entries = parse_forecast_symbols(it_payload)
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0].forecast_type, "twice_daily")
        self.assertFalse(entries[0].is_daytime)
        self.assertEqual(entries[0].condition, "clear-night")
        self.assertEqual(entries[0].temp_min, 5.0)
        self.assertEqual(entries[0].temp_max, 7.0)
        self.assertEqual(entries[0].precipitation_probability, 10)
        self.assertEqual(entries[1].condition, "pouring")
        self.assertTrue(entries[1].is_daytime)
        self.assertEqual(entries[1].snow_line, "Oltre i 1200/1400 m")
        self.assertEqual(entries[2].forecast_type, "daily")
        self.assertEqual(entries[2].condition, "snowy")
        self.assertEqual(entries[2].temp_max, -5.0)

    def test_symbol_mapping_clear_night_before_sunny(self) -> None:
        self.assertEqual(map_symbol_to_condition("a1N.png"), "clear-night")
        self.assertEqual(map_symbol_to_condition("a1.png"), "sunny")
        self.assertEqual(map_symbol_to_condition("c4.png"), "lightning-rainy")
        self.assertEqual(map_symbol_to_condition("e3.png"), "snowy-rainy")
        self.assertEqual(map_symbol_to_condition("f2.png"), "fog")

    def test_bulletin_text_and_alerts(self) -> None:
        payload = {
            "data": [
                {
                    "bollettino": "MV",
                    "dataemissione": "2026-11-22T13:00:00",
                    "aggiornamento": "2026-11-23T09:00:00",
                    "giorno": 0,
                    "scadenza": "2026-11-22",
                    "evoluzionegenerale": "Perturbazione atlantica.",
                    "avviso": "<b>Temporali forti</b> in pianura.",
                    "fenomeniparticolari": "",
                    "previsione": "<b>Previsione: </b>Piogge diffuse&nbsp;ovunque.",
                    "attendibilita": "Buona",
                }
            ]
        }
        b = parse_bulletin_text("MV", payload)
        self.assertIsNotNone(b)
        assert b is not None
        self.assertTrue(b.has_alert)
        self.assertEqual(b.alert, "Temporali forti in pianura.")
        self.assertEqual(b.days[0].forecast_text, "Previsione: Piogge diffuse ovunque.")
        self.assertEqual(select_bulletin_code_for_zone(1), "DM")
        self.assertEqual(select_bulletin_code_for_zone(10), "MV")


class TestAirHydroAvalanchePollenRadarParsers(unittest.TestCase):
    """Tests for air quality, hydrology, avalanche XML, pollen, radar, and brightness."""

    def test_air_quality_flag_and_excluded_codseq_filter(self) -> None:
        payload = {
            "data": [
                # Invalid FLAG < 9 (newer timestamp, must be ignored!)
                {
                    "CODSEQ": 500003783,
                    "COD_PARAMETRO": 25,
                    "FLAG": 3,
                    "MEDIA": 999.0,
                    "DATA": "2026-11-23T10:00:00",
                    "DATA_ORA": "202611231000",
                    "STAZIONE": "PD Granze",
                },
                # Excluded duplicate sensor CODSEQ 500014236 (must be ignored!)
                {
                    "CODSEQ": 500014236,
                    "COD_PARAMETRO": 25,
                    "FLAG": 9,
                    "MEDIA": 777.0,
                    "DATA": "2026-11-23T09:00:00",
                    "DATA_ORA": "202611230900",
                    "STAZIONE": "PD Granze",
                },
                # Valid record
                {
                    "CODSEQ": 500003783,
                    "COD_PARAMETRO": 25,
                    "FLAG": 9,
                    "MEDIA": 25.8,
                    "DATA": "2026-11-23T08:00:00",
                    "DATA_ORA": "202611230800",
                    "STAZIONE": "PD Granze",
                },
                # Different parameter (O3)
                {
                    "CODSEQ": 500009999,
                    "COD_PARAMETRO": 7,
                    "FLAG": 9,
                    "MEDIA": 42.1,
                    "DATA": "2026-11-23T09:00:00",
                    "DATA_ORA": "202611230900",
                    "STAZIONE": "PD Mandria",
                },
            ]
        }
        pm10 = parse_air_quality_latest(payload, AQ_PARAM_PM10)
        self.assertIsNotNone(pm10)
        assert pm10 is not None
        self.assertEqual(pm10["MEDIA"], 25.8)

        o3 = parse_air_quality_latest(payload, AQ_PARAM_OZONE)
        self.assertIsNotNone(o3)
        assert o3 is not None
        self.assertEqual(o3["MEDIA"], 42.1)

        pm25 = parse_air_quality_latest(payload, AQ_PARAM_PM25)
        self.assertIsNone(pm25)

    def test_air_quality_stations_distance_sorting(self) -> None:
        payload = {
            "data": [
                {
                    "codseqst": 1,
                    "name": "Far Station",
                    "prov": "BL",
                    "latitudine": 46.5,
                    "longitudine": 12.2,
                    "attiva": "s",
                    "pm10": "a",
                },
                {
                    "codseqst": 2,
                    "name": "Near Station",
                    "prov": "PD",
                    "latitudine": 45.4,
                    "longitudine": 11.9,
                    "attiva": "s",
                    "pm10": "a",
                },
                {
                    "codseqst": 3,
                    "name": "Inactive",
                    "prov": "PD",
                    "latitudine": 45.4,
                    "longitudine": 11.9,
                    "attiva": "n",
                },
            ]
        }
        sts = parse_air_quality_stations(payload, ref_lat=45.41, ref_lon=11.88)
        self.assertEqual(len(sts), 2)
        self.assertEqual(sts[0].station_id, "2")
        self.assertIn("km", sts[0].label())

    def test_hydro_stations_and_reading(self) -> None:
        liv = {
            "data": [
                {
                    "codseqst": 300004440,
                    "nome_stazione": "A7P - Malcontenta",
                    "provincia": "VENEZIA",
                    "latitudine": 45.44,
                    "longitudine": 12.20,
                    "livello": 3.12,
                    "trend": "+",
                    "dataora": "2026-11-23T10:00:00",
                }
            ]
        }
        tab = {
            "data": [
                {
                    "nome_stazione": "A7P - Malcontenta",
                    "tipo": "PORT",
                    "valore": "9.83",
                    "unitnm": "m3/s",
                    "dataora": "2026-11-23T10:00:00",
                }
            ]
        }
        sts = parse_hydro_stations(liv, 45.4, 12.0)
        self.assertEqual(len(sts), 1)
        reading = parse_hydro_reading(300004440, liv, tab)
        self.assertIsNotNone(reading)
        assert reading is not None
        self.assertEqual(reading.level_m, 3.12)
        self.assertEqual(reading.trend, "+")
        self.assertEqual(reading.discharge_m3s, 9.83)

    def test_avalanche_xml_inactive_and_active(self) -> None:
        inactive_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <previsioni>
          <data_emissione date="17/11/2026 alle 12:00" />
          <bollettino>
            <situazione>Assenza di manto nevoso continuo.</situazione>
            <scadenza data="17 novembre">
              <area nome="DOLOMITI"><pericolo></pericolo></area>
              <area nome="PREALPI"><pericolo></pericolo></area>
            </scadenza>
          </bollettino>
        </previsioni>"""
        b0 = parse_avalanche_xml(inactive_xml)
        self.assertFalse(b0.is_active)
        self.assertEqual(b0.areas["DOLOMITI"].danger_level, "not_issued")

        active_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <previsioni>
          <data_emissione date="15/02/2026 alle 16:00" />
          <bollettino>
            <situazione>Manto nevoso instabile in quota.</situazione>
            <scadenza data="16 febbraio">
              <area nome="DOLOMITI">
                <pericolo>3 - Marcato</pericolo>
                <neve_fresca>20-30 cm</neve_fresca>
              </area>
              <area nome="PREALPI">
                <pericolo>2 - Moderato</pericolo>
              </area>
            </scadenza>
          </bollettino>
        </previsioni>"""
        b1 = parse_avalanche_xml(active_xml)
        self.assertTrue(b1.is_active)
        self.assertEqual(b1.areas["DOLOMITI"].danger_level, "3_considerable")
        self.assertEqual(b1.areas["DOLOMITI"].fresh_snow, "20-30 cm")
        self.assertEqual(b1.areas["PREALPI"].danger_level, "2_moderate")

    def test_pollen_index_and_report(self) -> None:
        idx = {
            "data": [
                {
                    "codice_stazione": "PD01",
                    "nome_stazione": "Padova",
                    "provincia": "PD",
                    "latitudine": 45.40,
                    "longitudine": 11.88,
                    "file_dati": "pollini-PD01-2026-45.json",
                }
            ]
        }
        sts = parse_pollen_index(idx, 45.4, 11.9)
        self.assertEqual(sts[0].station_id, "PD01")

        report_payload = {
            "data": [
                {
                    "codice_stazione": "PD01",
                    "nome_stazione": "Padova",
                    "provincia": "PD",
                    "periodo": "dal 09/11/2026 al 15/11/2026",
                    "numboll": 45,
                    "anno": 2026,
                    "commento": "Spore di Alternaria basse.",
                    "grafici": [
                        {
                            "codice_specie": "505",
                            "nome_specie": "Poaceae (Graminae)",
                            "giudizio": "Assente",
                            "previsione": "Assente",
                            "misure": [{"dataora": "2026-11-15T00:00:00", "valore": "0"}],
                        },
                        {
                            "codice_specie": "548",
                            "nome_specie": "Alternaria",
                            "giudizio": "Bassa",
                            "previsione": "Media",
                            "misure": [{"dataora": "2026-11-15T00:00:00", "valore": "3"}],
                        },
                    ],
                }
            ]
        }
        rep = parse_pollen_report(report_payload)
        self.assertIsNotNone(rep)
        assert rep is not None
        self.assertEqual(rep.max_risk_level, "low")
        self.assertEqual(rep.max_forecast_level, "moderate")
        self.assertEqual(len(rep.species), 2)
        self.assertEqual(rep.species[1].slug, "alternaria")
        self.assertEqual(rep.species[1].latest_value, 3.0)

    def test_radar_base_frame(self) -> None:
        fake_jpg = b"\xff\xd8\xff\xe0TESTJPEG"
        payload = {
            "data": [
                {
                    "radar": "teolo",
                    "date": "2026-11-23T08:00:00",
                    "image": base64.b64encode(b"OLD").decode(),
                },
                {
                    "radar": "teolo",
                    "date": "2026-11-23T08:20:00",
                    "image": base64.b64encode(fake_jpg).decode(),
                },
                {
                    "radar": "concordia",
                    "date": "2026-11-23T08:30:00",
                    "image": base64.b64encode(b"CONCO").decode(),
                },
            ]
        }
        frame = parse_radar_base_frame("teolo", payload)
        self.assertIsNotNone(frame)
        assert frame is not None
        self.assertEqual(frame.image_bytes, fake_jpg)
        self.assertEqual(frame.content_type, "image/jpeg")

    def test_brightness_reading_freshness_and_zero_rejection(self) -> None:
        now = datetime(2026, 11, 23, 22, 0, 0, tzinfo=ARPAV_TZ)
        fresh = {
            "data": [
                {"dataora": "2026-11-23T21:00:00", "valore": "20.8", "nome_stazione": "Ekar"}
            ]
        }
        r = parse_brightness_reading(fresh, now=now)
        self.assertIsNotNone(r)
        assert r is not None
        self.assertEqual(r.value, 20.8)

        stale = {
            "data": [
                {"dataora": "2026-11-23T12:00:00", "valore": "20.8", "nome_stazione": "Ekar"}
            ]
        }
        self.assertIsNone(parse_brightness_reading(stale, now=now))

        zero = {
            "data": [{"dataora": "2026-11-23T21:30:00", "valore": "0.0", "nome_stazione": "Ekar"}]
        }
        self.assertIsNone(parse_brightness_reading(zero, now=now))

    def test_math_helpers(self) -> None:
        self.assertAlmostEqual(haversine_km(45.4064, 11.8768, 45.4408, 12.3155), 34.4, delta=0.5)
        self.assertEqual(degrees_to_cardinal(0), "N")
        self.assertEqual(degrees_to_cardinal(360), "N")
        self.assertEqual(degrees_to_cardinal(90), "E")
        self.assertEqual(degrees_to_cardinal(225), "SW")
        dp = compute_dew_point(20.0, 50.0)
        self.assertIsNotNone(dp)
        assert dp is not None
        self.assertAlmostEqual(dp, 9.3, delta=0.2)
        _ = timedelta


if __name__ == "__main__":
    unittest.main()
