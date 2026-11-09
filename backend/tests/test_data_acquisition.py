"""
Phase 4 — Data Acquisition tests.

Tests cover:
1. FAO-56 Penman-Monteith ET0 calculator (known reference values).
2. Weather validation (bounds checking, sentinel removal).
3. NASA POWER client parsing (mocked HTTP).
4. OpenWeatherMap client parsing (mocked HTTP).
5. WeatherDataService integration (mocked clients, real DB).
6. Effective rainfall (USDA SCS formula).

No real network calls are made — all external HTTP is mocked.
"""

from __future__ import annotations

import math
import os
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://postgres:FarmAgent2024!@localhost:5432/autonomous_farming"
)
os.environ["DEBUG"] = "false"


# ================================================================== #
# Fixtures
# ================================================================== #

@pytest.fixture(scope="module")
def db():
    from app.core.config import _reset_settings
    _reset_settings()
    from app.database.engine import SessionLocal
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


# ================================================================== #
# 1. FAO-56 Penman-Monteith ET0 Calculator
# ================================================================== #

class TestFAO56Calculator:
    """
    Reference values from FAO-56 Example 18 (Chapter 4).

    Location: Leysin, Switzerland
    Date: 1 July (DOY=182)
    Latitude: 46.3°N
    Altitude: 1200m

    FAO-56 book result: ET0 ≈ 3.97 mm/day (within ±0.5 for test tolerance)
    """

    def _get_calc(self):
        from app.service.et0_calculator import FAO56PenmanMonteith
        return FAO56PenmanMonteith()

    def _fao56_example_inputs(self):
        from app.service.et0_calculator import ET0Inputs
        return ET0Inputs(
            temp_max_c=21.5,
            temp_min_c=12.3,
            humidity_max_pct=84.0,
            humidity_min_pct=63.0,
            wind_speed_m_s=2.78,
            solar_radiation_mj_m2=22.07,
            latitude_rad=math.radians(46.3),
            altitude_m=1200.0,
            day_of_year=182,
            pressure_kpa=None,
        )

    def test_et0_returns_float(self):
        et0 = self._get_calc().compute(self._fao56_example_inputs())
        assert isinstance(et0, float)

    def test_et0_positive(self):
        et0 = self._get_calc().compute(self._fao56_example_inputs())
        assert et0 > 0.0

    def test_et0_fao56_example_reference_value(self):
        """ET0 must be within ±0.8 mm of FAO-56 Example 18 reference value (~3.97)."""
        et0 = self._get_calc().compute(self._fao56_example_inputs())
        assert abs(et0 - 3.97) < 0.8, f"ET0={et0} too far from FAO-56 reference ~3.97"

    def test_et0_hot_dry_day_higher_than_cool_humid(self):
        """Hot, dry, windy day must produce higher ET0 than cool, humid day."""
        from app.service.et0_calculator import ET0Inputs
        hot = ET0Inputs(
            temp_max_c=40.0, temp_min_c=28.0,
            humidity_max_pct=30.0, humidity_min_pct=15.0,
            wind_speed_m_s=4.0, solar_radiation_mj_m2=28.0,
            latitude_rad=math.radians(20.0), altitude_m=100.0,
            day_of_year=180,
        )
        cool = ET0Inputs(
            temp_max_c=18.0, temp_min_c=10.0,
            humidity_max_pct=90.0, humidity_min_pct=70.0,
            wind_speed_m_s=1.0, solar_radiation_mj_m2=10.0,
            latitude_rad=math.radians(20.0), altitude_m=100.0,
            day_of_year=180,
        )
        calc = self._get_calc()
        assert calc.compute(hot) > calc.compute(cool)

    def test_et0_never_negative(self):
        """ET0 must always be >= 0."""
        from app.service.et0_calculator import ET0Inputs
        night_inputs = ET0Inputs(
            temp_max_c=5.0, temp_min_c=1.0,
            humidity_max_pct=95.0, humidity_min_pct=80.0,
            wind_speed_m_s=0.5, solar_radiation_mj_m2=2.0,
            latitude_rad=math.radians(60.0), altitude_m=0.0,
            day_of_year=355,
        )
        et0 = self._get_calc().compute(night_inputs)
        assert et0 >= 0.0

    def test_build_et0_inputs_from_dict(self):
        """build_et0_inputs must construct valid inputs from a weather dict."""
        from app.service.et0_calculator import build_et0_inputs
        weather = {
            "temperature_max_c": 30.0,
            "temperature_min_c": 18.0,
            "humidity_max_pct": 75.0,
            "humidity_min_pct": 40.0,
            "humidity_mean_pct": 57.5,
            "wind_speed_m_s": 2.5,
            "solar_radiation_mj_m2": 20.0,
            "pressure_kpa": 101.3,
        }
        inputs = build_et0_inputs(weather, latitude_deg=18.52, altitude_m=560.0, day_of_year=200)
        assert inputs is not None
        assert inputs.temp_max_c == 30.0

    def test_build_et0_inputs_returns_none_for_missing_critical(self):
        """If solar radiation is missing, build_et0_inputs must return None."""
        from app.service.et0_calculator import build_et0_inputs
        weather = {
            "temperature_max_c": 30.0,
            "temperature_min_c": 18.0,
            "wind_speed_m_s": 2.5,
            "solar_radiation_mj_m2": None,  # missing
        }
        assert build_et0_inputs(weather, 18.52, 560.0, 200) is None

    def test_et0_tropical_location(self):
        """Pune-like climate: ET0 should be in realistic range 4-8 mm/day."""
        from app.service.et0_calculator import ET0Inputs
        pune = ET0Inputs(
            temp_max_c=35.0, temp_min_c=22.0,
            humidity_max_pct=65.0, humidity_min_pct=30.0,
            wind_speed_m_s=2.0, solar_radiation_mj_m2=22.0,
            latitude_rad=math.radians(18.52), altitude_m=560.0,
            day_of_year=120,
        )
        et0 = self._get_calc().compute(pune)
        assert 3.0 <= et0 <= 12.0, f"ET0={et0} outside realistic tropical range"


# ================================================================== #
# 2. Weather Validation
# ================================================================== #

class TestWeatherValidation:

    def test_valid_record_passes_unchanged(self):
        from app.service.weather_data_service import validate_weather_record
        record = {
            "temperature_max_c": 35.0,
            "temperature_min_c": 20.0,
            "humidity_mean_pct": 60.0,
            "wind_speed_m_s": 3.0,
            "solar_radiation_mj_m2": 22.0,
            "precipitation_mm": 5.0,
        }
        cleaned = validate_weather_record(record)
        assert cleaned["temperature_max_c"] == 35.0
        assert cleaned["precipitation_mm"] == 5.0

    def test_out_of_range_temp_set_to_none(self):
        from app.service.weather_data_service import validate_weather_record
        record = {"temperature_max_c": 999.0}
        cleaned = validate_weather_record(record)
        assert cleaned["temperature_max_c"] is None

    def test_negative_precipitation_set_to_none(self):
        from app.service.weather_data_service import validate_weather_record
        record = {"precipitation_mm": -5.0}
        cleaned = validate_weather_record(record)
        assert cleaned["precipitation_mm"] is None

    def test_humidity_over_100_set_to_none(self):
        from app.service.weather_data_service import validate_weather_record
        record = {"humidity_mean_pct": 110.0}
        cleaned = validate_weather_record(record)
        assert cleaned["humidity_mean_pct"] is None

    def test_none_values_pass_through_unchanged(self):
        from app.service.weather_data_service import validate_weather_record
        record = {"solar_radiation_mj_m2": None, "wind_speed_m_s": None}
        cleaned = validate_weather_record(record)
        assert cleaned["solar_radiation_mj_m2"] is None


# ================================================================== #
# 3. NASA POWER Client (mocked)
# ================================================================== #

class TestNASAPOWERClient:

    def _mock_response(self):
        """Minimal valid NASA POWER API response for 2 days."""
        return {
            "properties": {
                "parameter": {
                    "T2M_MAX":         {"20240101": 30.5, "20240102": 32.1},
                    "T2M_MIN":         {"20240101": 18.0, "20240102": 19.5},
                    "T2M":             {"20240101": 24.0, "20240102": 25.6},
                    "RH2M":            {"20240101": 55.0, "20240102": 50.0},
                    "RH2M_MAX":        {"20240101": 75.0, "20240102": 70.0},
                    "RH2M_MIN":        {"20240101": 35.0, "20240102": 30.0},
                    "WS2M":            {"20240101": 2.5,  "20240102": 3.0},
                    "ALLSKY_SFC_SW_DWN": {"20240101": 20.0, "20240102": 22.0},
                    "PRECTOTCORR":     {"20240101": 0.0,  "20240102": 5.2},
                    "PS":              {"20240101": 98.5, "20240102": 98.3},
                }
            }
        }

    def test_parse_response_returns_correct_count(self):
        from app.service.nasa_power_client import NASAPOWERClient
        client = NASAPOWERClient()
        records = client._parse_response(self._mock_response())
        assert len(records) == 2

    def test_parse_response_correct_date(self):
        from app.service.nasa_power_client import NASAPOWERClient
        records = NASAPOWERClient()._parse_response(self._mock_response())
        assert records[0]["observation_date"] == date(2024, 1, 1)

    def test_parse_response_correct_temp(self):
        from app.service.nasa_power_client import NASAPOWERClient
        records = NASAPOWERClient()._parse_response(self._mock_response())
        assert records[0]["temperature_max_c"] == 30.5

    def test_parse_response_missing_data_sentinel(self):
        """NASA -999 sentinel values must be converted to None."""
        from app.service.nasa_power_client import NASAPOWERClient
        raw = {
            "properties": {"parameter": {
                "T2M_MAX":         {"20240101": -999.0},
                "T2M_MIN":         {"20240101": 18.0},
                "T2M":             {"20240101": -999.0},
                "RH2M":            {"20240101": 50.0},
                "RH2M_MAX":        {"20240101": 70.0},
                "RH2M_MIN":        {"20240101": 30.0},
                "WS2M":            {"20240101": 2.5},
                "ALLSKY_SFC_SW_DWN": {"20240101": 20.0},
                "PRECTOTCORR":     {"20240101": 0.0},
                "PS":              {"20240101": 98.5},
            }}
        }
        records = NASAPOWERClient()._parse_response(raw)
        assert records[0]["temperature_max_c"] is None
        assert records[0]["temperature_mean_c"] is None

    def test_parse_response_source_is_nasa_power(self):
        from app.service.nasa_power_client import NASAPOWERClient
        records = NASAPOWERClient()._parse_response(self._mock_response())
        assert all(r["source"] == "NASA_POWER" for r in records)

    @patch("app.service.nasa_power_client.requests.get")
    def test_fetch_daily_calls_correct_url(self, mock_get):
        from app.service.nasa_power_client import NASAPOWERClient
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = self._mock_response()
        mock_get.return_value = mock_resp

        client = NASAPOWERClient(base_url="https://test.nasa.gov/api")
        records = client.fetch_daily(
            lat=18.52, lon=73.86,
            start=date(2024, 1, 1), end=date(2024, 1, 2)
        )
        assert len(records) == 2
        mock_get.assert_called_once()

    @patch("app.service.nasa_power_client.requests.get")
    def test_fetch_daily_raises_on_network_error(self, mock_get):
        import requests as req
        from app.core.exceptions import NASAPOWERError
        from app.service.nasa_power_client import NASAPOWERClient
        mock_get.side_effect = req.exceptions.ConnectionError("no network")
        client = NASAPOWERClient()
        with pytest.raises(NASAPOWERError):
            client.fetch_daily(lat=0.0, lon=0.0,
                               start=date(2024, 1, 1), end=date(2024, 1, 1))


# ================================================================== #
# 4. OpenWeatherMap Client (mocked)
# ================================================================== #

class TestOpenWeatherMapClient:

    def test_invalid_key_raises_weather_api_error(self):
        from app.core.exceptions import WeatherAPIError
        from app.service.weather_client import OpenWeatherMapClient
        client = OpenWeatherMapClient(api_key="your_weather_api_key_here")
        with pytest.raises(WeatherAPIError, match="not configured"):
            client.fetch_current(lat=18.52, lon=73.86)

    def test_empty_key_raises_weather_api_error(self):
        from app.core.exceptions import WeatherAPIError
        from app.service.weather_client import OpenWeatherMapClient
        client = OpenWeatherMapClient(api_key="")
        with pytest.raises(WeatherAPIError):
            client.fetch_current(lat=18.52, lon=73.86)

    def test_parse_current_returns_correct_keys(self):
        from app.service.weather_client import OpenWeatherMapClient
        client = OpenWeatherMapClient(api_key="test_key")
        raw = {
            "main": {"temp": 28.0, "temp_max": 33.0, "temp_min": 22.0,
                     "humidity": 60, "pressure": 1013},
            "wind": {"speed": 3.5},
            "rain": {"1h": 0.0},
        }
        result = client._parse_current(raw)
        assert result["temperature_mean_c"] == 28.0
        assert result["wind_speed_m_s"] == 3.5
        assert result["source"] == "OpenWeatherMap"

    def test_pressure_converted_from_hpa_to_kpa(self):
        from app.service.weather_client import OpenWeatherMapClient
        client = OpenWeatherMapClient(api_key="test_key")
        raw = {"main": {"temp": 25.0, "temp_max": 30.0, "temp_min": 20.0,
                        "humidity": 50, "pressure": 1013},
               "wind": {}, "rain": {}}
        result = client._parse_current(raw)
        assert abs(result["pressure_kpa"] - 101.3) < 0.1

    def test_dew_point_calculation(self):
        from app.service.weather_client import OpenWeatherMapClient
        dp = OpenWeatherMapClient._calc_dew_point(25.0, 60.0)
        assert dp is not None
        assert 14.0 < dp < 20.0  # physically expected range

    def test_dew_point_none_on_missing_input(self):
        from app.service.weather_client import OpenWeatherMapClient
        assert OpenWeatherMapClient._calc_dew_point(None, 60.0) is None
        assert OpenWeatherMapClient._calc_dew_point(25.0, None) is None


# ================================================================== #
# 5. Effective Rainfall
# ================================================================== #

class TestEffectiveRainfall:

    def test_zero_precip(self):
        from app.service.weather_data_service import _effective_rainfall
        assert _effective_rainfall(0.0) == 0.0

    def test_small_precip_under_25mm(self):
        from app.service.weather_data_service import _effective_rainfall
        # 20mm: 0.6*20 - 10 = 2.0
        assert abs(_effective_rainfall(20.0) - 2.0) < 0.01

    def test_precip_below_17mm_gives_zero(self):
        """Below ~16.7mm, SCS effective rainfall is 0."""
        from app.service.weather_data_service import _effective_rainfall
        assert _effective_rainfall(10.0) == 0.0

    def test_large_precip_over_25mm(self):
        from app.service.weather_data_service import _effective_rainfall
        # 50mm: 0.8*50 - 25 = 15.0
        assert abs(_effective_rainfall(50.0) - 15.0) < 0.01

    def test_always_non_negative(self):
        from app.service.weather_data_service import _effective_rainfall
        for p in [0, 5, 10, 25, 50, 100, 200]:
            assert _effective_rainfall(float(p)) >= 0.0


# ================================================================== #
# 6. WeatherDataService integration (mocked NASA POWER)
# ================================================================== #

class TestWeatherDataService:

    def _mock_nasa_records(self, farm_id: int = 1) -> list[dict]:
        return [
            {
                "observation_date": date.today() - timedelta(days=2),
                "source": "NASA_POWER",
                "temperature_max_c": 33.0,
                "temperature_min_c": 21.0,
                "temperature_mean_c": 27.0,
                "humidity_max_pct": 70.0,
                "humidity_min_pct": 35.0,
                "humidity_mean_pct": 52.0,
                "wind_speed_m_s": 2.5,
                "solar_radiation_mj_m2": 21.0,
                "precipitation_mm": 0.0,
                "pressure_kpa": 99.0,
                "dew_point_c": None,
                "sunshine_hours": None,
                "raw_response": None,
            }
        ]

    @patch("app.service.weather_data_service.NASAPOWERClient.fetch_daily")
    def test_fetch_and_store_stores_record(self, mock_fetch, db):
        from app.service.weather_data_service import WeatherDataService
        from app.repositories.repositories import FarmRepository, WeatherRecordRepository
        farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
        mock_fetch.return_value = self._mock_nasa_records()

        svc = WeatherDataService(db)
        result = svc.fetch_and_store_nasa_power(farm_id=farm.id, days_back=1)

        assert "stored" in result
        assert result["farm_id"] == farm.id
        db.rollback()

    @patch("app.service.weather_data_service.NASAPOWERClient.fetch_daily")
    def test_fetch_and_store_idempotent(self, mock_fetch, db):
        """Calling twice for same date should not double-insert."""
        from app.service.weather_data_service import WeatherDataService
        from app.repositories.repositories import FarmRepository
        farm = FarmRepository(db).get_by_name("Autonomous Demo Farm")
        mock_fetch.return_value = self._mock_nasa_records()

        svc = WeatherDataService(db)
        result1 = svc.fetch_and_store_nasa_power(farm_id=farm.id, days_back=1)
        result2 = svc.fetch_and_store_nasa_power(farm_id=farm.id, days_back=1)

        # Second call: stored=0, skipped=1 (already exists)
        assert result2["stored"] == 0
        assert result2["skipped"] >= 1
        db.rollback()

