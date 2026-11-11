"""
FAO-56 Penman-Monteith Reference Evapotranspiration Calculator.

Implements the complete FAO-56 ET0 calculation as described in:

    Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998).
    Crop evapotranspiration — Guidelines for computing crop water
    requirements. FAO Irrigation and Drainage Paper 56.
    Food and Agriculture Organization of the United Nations, Rome.

All equations reference section/equation numbers from FAO-56.

Units
-----
Input temperatures : °C
Input humidity     : %
Input wind speed   : m/s at 2m height
Input radiation    : MJ/m²/day
Input pressure     : kPa
Output ET0         : mm/day

CRITICAL CONSTRAINT (from project spec):
    All numerical ET0 values come ONLY from this validated analytical
    implementation.  LLM outputs are NEVER used for any numeric computation.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

from app.core.exceptions import ET0CalculationError

logger = logging.getLogger(__name__)


# ================================================================== #
# Data class for validated inputs
# ================================================================== #

@dataclass
class ET0Inputs:
    """
    Validated inputs required for FAO-56 Penman-Monteith ET0.

    All values must be provided in SI units as specified by FAO-56.
    Missing critical inputs raise ``ET0CalculationError``.

    Attributes
    ----------
    temp_max_c : float
        Maximum daily air temperature at 2m (°C).
    temp_min_c : float
        Minimum daily air temperature at 2m (°C).
    humidity_max_pct : float
        Maximum relative humidity at 2m (%).
    humidity_min_pct : float
        Minimum relative humidity at 2m (%).
    wind_speed_m_s : float
        Mean daily wind speed at 2m height (m/s).
    solar_radiation_mj_m2 : float
        Incoming solar (shortwave) radiation (MJ/m²/day).
    latitude_rad : float
        Site latitude in radians. Used to compute extraterrestrial radiation.
    altitude_m : float
        Site elevation above sea level (m). Used to compute pressure.
    day_of_year : int
        Julian day of year (1–365/366).
    pressure_kpa : float | None
        Atmospheric pressure (kPa). If None, estimated from altitude_m.
    humidity_mean_pct : float | None
        Mean relative humidity. Used as fallback if max/min unavailable.
    """

    temp_max_c: float
    temp_min_c: float
    humidity_max_pct: float
    humidity_min_pct: float
    wind_speed_m_s: float
    solar_radiation_mj_m2: float
    latitude_rad: float
    altitude_m: float
    day_of_year: int
    pressure_kpa: float | None = None
    humidity_mean_pct: float | None = None


# ================================================================== #
# Calculator
# ================================================================== #

class FAO56PenmanMonteith:
    """
    FAO-56 Penman-Monteith ET0 calculator.

    All equation numbers refer to Allen et al. (1998) FAO-56.

    Example
    -------
    ::

        calc = FAO56PenmanMonteith()
        et0 = calc.compute(inputs)   # returns float (mm/day)
    """

    def compute(self, inputs: ET0Inputs) -> float:
        """
        Compute ET0 using the full FAO-56 Penman-Monteith equation.

        Parameters
        ----------
        inputs : ET0Inputs
            Validated weather inputs.

        Returns
        -------
        float
            Reference evapotranspiration ET0 in mm/day.
            Always >= 0 (clipped at zero — ET0 cannot be negative).

        Raises
        ------
        ET0CalculationError
            If any critical input is NaN/infinite after computation.
        """
        try:
            et0 = self._compute_internal(inputs)
        except (ZeroDivisionError, ValueError, OverflowError) as exc:
            raise ET0CalculationError(
                f"FAO-56 ET0 computation failed: {exc}"
            ) from exc

        if not math.isfinite(et0):
            raise ET0CalculationError(
                f"FAO-56 ET0 result is non-finite: {et0}"
            )

        et0 = max(0.0, et0)
        logger.debug("FAO-56 PM ET0 = %.3f mm/day", et0)
        return round(et0, 3)

    def _compute_internal(self, i: ET0Inputs) -> float:
        """Internal computation — all FAO-56 equations."""

        # ── Step 1: Mean temperature (Eq. 9) ────────────────────────
        T_mean = (i.temp_max_c + i.temp_min_c) / 2.0

        # ── Step 2: Atmospheric pressure (Eq. 7) ────────────────────
        # If measured pressure available, use it. Otherwise estimate.
        P = i.pressure_kpa if i.pressure_kpa else self._atm_pressure(i.altitude_m)

        # ── Step 3: Psychrometric constant γ (Eq. 8) ────────────────
        gamma = self._psychrometric_constant(P)

        # ── Step 4: Saturation vapour pressure (Eq. 11, 12) ─────────
        e_sat_max = self._sat_vapour_pressure(i.temp_max_c)
        e_sat_min = self._sat_vapour_pressure(i.temp_min_c)
        e_s = (e_sat_max + e_sat_min) / 2.0   # Eq. 12

        # ── Step 5: Actual vapour pressure (Eq. 17) ─────────────────
        if (i.humidity_max_pct is not None and i.humidity_min_pct is not None
                and i.humidity_max_pct > 0 and i.humidity_min_pct > 0):
            e_a = (
                (e_sat_min * i.humidity_max_pct / 100.0)
                + (e_sat_max * i.humidity_min_pct / 100.0)
            ) / 2.0
        elif i.humidity_mean_pct:
            # Fallback: Eq. 19
            e_a = (i.humidity_mean_pct / 100.0) * e_s
        else:
            # Approximate from dew point ≈ T_min (Eq. 48)
            e_a = self._sat_vapour_pressure(i.temp_min_c)

        # Clip: actual vapour pressure cannot exceed saturation.
        e_a = min(e_a, e_s)

        # Vapour pressure deficit
        vpd = e_s - e_a

        # ── Step 6: Slope of saturation vapour pressure curve (Eq. 13)
        Delta = self._slope_saturation(T_mean)

        # ── Step 7: Extraterrestrial radiation Ra (Eq. 21) ───────────
        Ra = self._extraterrestrial_radiation(i.latitude_rad, i.day_of_year)

        # ── Step 8: Clear-sky solar radiation Rso (Eq. 37) ──────────
        Rso = (0.75 + 2e-5 * i.altitude_m) * Ra

        # ── Step 9: Net shortwave radiation Rns (Eq. 38) ────────────
        alpha = 0.23   # grass reference albedo
        Rns = (1.0 - alpha) * i.solar_radiation_mj_m2

        # ── Step 10: Net longwave radiation Rnl (Eq. 39) ────────────
        Rnl = self._net_longwave(
            i.temp_max_c, i.temp_min_c, e_a,
            i.solar_radiation_mj_m2, Rso
        )

        # ── Step 11: Net radiation Rn (Eq. 40) ──────────────────────
        Rn = Rns - Rnl

        # ── Step 12: Soil heat flux G ────────────────────────────────
        # For daily time step, G ≈ 0 (FAO-56 Eq. 42)
        G = 0.0

        # ── Step 13: FAO-56 PM equation (Eq. 6) ─────────────────────
        #
        #         0.408 Δ (Rn − G) + γ [900/(T+273)] u2 (es − ea)
        # ET0 = ─────────────────────────────────────────────────────
        #                    Δ + γ (1 + 0.34 u2)
        #
        numerator = (
            0.408 * Delta * (Rn - G)
            + gamma * (900.0 / (T_mean + 273.0)) * i.wind_speed_m_s * vpd
        )
        denominator = Delta + gamma * (1.0 + 0.34 * i.wind_speed_m_s)
        return numerator / denominator

    def compute_derivation(self, inputs: ET0Inputs) -> dict[str, Any]:
        """
        Compute ET0 with the complete 13-step thermodynamic FAO-56 derivation.

        Returns all physical components, aerodynamic and radiation terms,
        and intermediate equation steps for scientific inspection.
        """
        i = inputs
        # Step 1: Mean temperature (Eq. 9)
        T_mean = (i.temp_max_c + i.temp_min_c) / 2.0

        # Step 2: Atmospheric pressure (Eq. 7)
        P = i.pressure_kpa if i.pressure_kpa else self._atm_pressure(i.altitude_m)

        # Step 3: Psychrometric constant (Eq. 8)
        gamma = self._psychrometric_constant(P)

        # Step 4: Saturation vapour pressure (Eq. 11, 12)
        e_sat_max = self._sat_vapour_pressure(i.temp_max_c)
        e_sat_min = self._sat_vapour_pressure(i.temp_min_c)
        e_s = (e_sat_max + e_sat_min) / 2.0

        # Step 5: Actual vapour pressure (Eq. 17)
        if (i.humidity_max_pct is not None and i.humidity_min_pct is not None
                and i.humidity_max_pct > 0 and i.humidity_min_pct > 0):
            e_a = (
                (e_sat_min * i.humidity_max_pct / 100.0)
                + (e_sat_max * i.humidity_min_pct / 100.0)
            ) / 2.0
        elif i.humidity_mean_pct:
            e_a = (i.humidity_mean_pct / 100.0) * e_s
        else:
            e_a = self._sat_vapour_pressure(i.temp_min_c)
        e_a = min(e_a, e_s)
        vpd = max(0.0, e_s - e_a)

        # Step 6: Slope of saturation curve Delta (Eq. 13)
        Delta = self._slope_saturation(T_mean)

        # Step 7: Extraterrestrial radiation Ra (Eq. 21)
        Ra = self._extraterrestrial_radiation(i.latitude_rad, i.day_of_year)

        # Step 8: Clear-sky solar radiation Rso (Eq. 37)
        Rso = (0.75 + 2e-5 * i.altitude_m) * Ra

        # Step 9: Net shortwave radiation Rns (Eq. 38)
        alpha = 0.23
        Rns = (1.0 - alpha) * i.solar_radiation_mj_m2

        # Step 10: Net longwave radiation Rnl (Eq. 39)
        Rnl = self._net_longwave(
            i.temp_max_c, i.temp_min_c, e_a,
            i.solar_radiation_mj_m2, Rso
        )

        # Step 11: Net radiation Rn (Eq. 40)
        Rn = Rns - Rnl

        # Step 12: Soil heat flux G (Eq. 42)
        G = 0.0

        # Step 13: FAO-56 Penman-Monteith combination (Eq. 6)
        denominator = Delta + gamma * (1.0 + 0.34 * i.wind_speed_m_s)
        rad_num = 0.408 * Delta * (Rn - G)
        aero_num = gamma * (900.0 / (T_mean + 273.0)) * i.wind_speed_m_s * vpd

        rad_term = max(0.0, rad_num / denominator) if denominator > 0 else 0.0
        aero_term = max(0.0, aero_num / denominator) if denominator > 0 else 0.0
        et0 = max(0.0, rad_term + aero_term)

        total_term = rad_term + aero_term
        rad_pct = round((rad_term / total_term) * 100, 1) if total_term > 0 else 50.0
        aero_pct = round((aero_term / total_term) * 100, 1) if total_term > 0 else 50.0

        steps = [
            {
                "step_number": 1,
                "title": "Mean Daily Air Temperature",
                "fao_equation": "Eq. 9: T_mean = (T_max + T_min) / 2",
                "formula_latex": r"T_{\text{mean}} = \frac{T_{\text{max}} + T_{\text{min}}}{2}",
                "result_value": round(T_mean, 2),
                "result_unit": "°C",
                "scientific_note": "Averaging maximum and minimum daily shelter air temperatures.",
            },
            {
                "step_number": 2,
                "title": "Atmospheric Pressure",
                "fao_equation": "Eq. 7: P = 101.3 * ((293 - 0.0065 z) / 293)^5.26",
                "formula_latex": r"P = 101.3 \left(\frac{293 - 0.0065 z}{293}\right)^{5.26}",
                "result_value": round(P, 2),
                "result_unit": "kPa",
                "scientific_note": f"Standard barometric pressure estimated at altitude {i.altitude_m} m.",
            },
            {
                "step_number": 3,
                "title": "Psychrometric Constant",
                "fao_equation": "Eq. 8: gamma = 0.000665 * P",
                "formula_latex": r"\gamma = \frac{c_p P}{\varepsilon \lambda} \approx 0.000665 P",
                "result_value": round(gamma, 4),
                "result_unit": "kPa/°C",
                "scientific_note": "Ratio of specific heat of moist air to latent heat of vaporization.",
            },
            {
                "step_number": 4,
                "title": "Saturation Vapour Pressure",
                "fao_equation": "Eq. 11, 12: e_s = (e°(T_max) + e°(T_min)) / 2",
                "formula_latex": r"e_s = \frac{e^\circ(T_{\text{max}}) + e^\circ(T_{\text{min}})}{2}",
                "result_value": round(e_s, 3),
                "result_unit": "kPa",
                "scientific_note": "Mean saturation vapour pressure derived via Tetens formulation.",
            },
            {
                "step_number": 5,
                "title": "Actual Vapour Pressure & Deficit",
                "fao_equation": "Eq. 17, VPD = e_s - e_a",
                "formula_latex": r"\text{VPD} = e_s - e_a",
                "result_value": round(vpd, 3),
                "result_unit": "kPa",
                "scientific_note": f"Drying power of air. e_a = {round(e_a, 3)} kPa, VPD = {round(vpd, 3)} kPa.",
            },
            {
                "step_number": 6,
                "title": "Slope of Saturation Vapour Curve",
                "fao_equation": "Eq. 13: Delta = 4098 * e°(T) / (T + 237.3)^2",
                "formula_latex": r"\Delta = \frac{4098 [0.6108 \exp(\frac{17.27 T}{T+237.3})]}{(T + 237.3)^2}",
                "result_value": round(Delta, 4),
                "result_unit": "kPa/°C",
                "scientific_note": "Rate of increase of saturation vapour pressure with temperature.",
            },
            {
                "step_number": 7,
                "title": "Extraterrestrial Solar Radiation",
                "fao_equation": "Eq. 21: R_a from solar constant, latitude, & declination",
                "formula_latex": r"R_a = \frac{24(60)}{\pi} G_{sc} d_r [\omega_s \sin\varphi \sin\delta + \cos\varphi \cos\delta \sin\omega_s]",
                "result_value": round(Ra, 2),
                "result_unit": "MJ/m²/day",
                "scientific_note": f"Solar radiation received at top of earth atmosphere on Julian day {i.day_of_year}.",
            },
            {
                "step_number": 8,
                "title": "Clear-Sky Solar Radiation",
                "fao_equation": "Eq. 37: R_so = (0.75 + 2e-5 * z) * R_a",
                "formula_latex": r"R_{so} = (0.75 + 2\times 10^{-5} z) R_a",
                "result_value": round(Rso, 2),
                "result_unit": "MJ/m²/day",
                "scientific_note": "Expected solar radiation without cloud attenuation.",
            },
            {
                "step_number": 9,
                "title": "Net Shortwave Radiation",
                "fao_equation": "Eq. 38: R_ns = (1 - alpha) * R_s",
                "formula_latex": r"R_{ns} = (1 - \alpha) R_s \quad (\alpha = 0.23)",
                "result_value": round(Rns, 2),
                "result_unit": "MJ/m²/day",
                "scientific_note": "Shortwave radiation absorbed by hypothetical reference grass crop.",
            },
            {
                "step_number": 10,
                "title": "Net Longwave Radiation",
                "fao_equation": "Eq. 39: R_nl via Stefan-Boltzmann & cloudiness ratio",
                "formula_latex": r"R_{nl} = \sigma \left[\frac{T_{\text{max,K}}^4 + T_{\text{min,K}}^4}{2}\right] (0.34 - 0.14\sqrt{e_a}) (1.35 \frac{R_s}{R_{so}} - 0.35)",
                "result_value": round(Rnl, 2),
                "result_unit": "MJ/m²/day",
                "scientific_note": "Thermal infrared heat energy emitted back into outer space.",
            },
            {
                "step_number": 11,
                "title": "Net Radiation at Surface",
                "fao_equation": "Eq. 40: R_n = R_ns - R_nl",
                "formula_latex": r"R_n = R_{ns} - R_{nl}",
                "result_value": round(Rn, 2),
                "result_unit": "MJ/m²/day",
                "scientific_note": "Total available radiant energy balance at the crop canopy.",
            },
            {
                "step_number": 12,
                "title": "Soil Heat Flux",
                "fao_equation": "Eq. 42: G ≈ 0 (daily time step)",
                "formula_latex": r"G \approx 0 \quad \text{(for 24h daily periods)}",
                "result_value": 0.0,
                "result_unit": "MJ/m²/day",
                "scientific_note": "Daily soil heat flux is negligible as daytime intake equals nighttime release.",
            },
            {
                "step_number": 13,
                "title": "FAO-56 Penman-Monteith ET0",
                "fao_equation": "Eq. 6: Combination of Radiation and Aerodynamic Terms",
                "formula_latex": r"ET_0 = \frac{0.408 \Delta (R_n - G) + \gamma \frac{900}{T+273} u_2 (e_s - e_a)}{\Delta + \gamma(1 + 0.34 u_2)}",
                "result_value": round(et0, 3),
                "result_unit": "mm/day",
                "scientific_note": f"Radiation term: {round(rad_term, 2)} mm ({rad_pct}%), Aerodynamic term: {round(aero_term, 2)} mm ({aero_pct}%).",
            },
        ]

        return {
            "et0_mm": round(et0, 3),
            "radiation_term_mm": round(rad_term, 3),
            "aerodynamic_term_mm": round(aero_term, 3),
            "radiation_share_pct": rad_pct,
            "aerodynamic_share_pct": aero_pct,
            "t_mean_c": round(T_mean, 2),
            "pressure_kpa": round(P, 2),
            "gamma_kpa_c": round(gamma, 4),
            "es_kpa": round(e_s, 3),
            "ea_kpa": round(e_a, 3),
            "vpd_kpa": round(vpd, 3),
            "delta_kpa_c": round(Delta, 4),
            "ra_mj_m2": round(Ra, 2),
            "rso_mj_m2": round(Rso, 2),
            "rns_mj_m2": round(Rns, 2),
            "rnl_mj_m2": round(Rnl, 2),
            "rn_mj_m2": round(Rn, 2),
            "wind_speed_m_s": round(inputs.wind_speed_m_s, 2),
            "solar_radiation_mj_m2": round(inputs.solar_radiation_mj_m2, 2),
            "steps": steps,
        }

    # ------------------------------------------------------------------ #
    # Sub-computations
    # ------------------------------------------------------------------ #

    @staticmethod
    def _atm_pressure(altitude_m: float) -> float:
        """Atmospheric pressure at altitude (Eq. 7). Returns kPa."""
        return 101.3 * ((293.0 - 0.0065 * altitude_m) / 293.0) ** 5.26

    @staticmethod
    def _psychrometric_constant(pressure_kpa: float) -> float:
        """Psychrometric constant γ (Eq. 8). Returns kPa/°C."""
        return 0.000665 * pressure_kpa

    @staticmethod
    def _sat_vapour_pressure(temp_c: float) -> float:
        """Saturation vapour pressure (Eq. 11). Returns kPa."""
        return 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))

    @staticmethod
    def _slope_saturation(temp_mean_c: float) -> float:
        """Slope of saturation vapour pressure curve Δ (Eq. 13). Returns kPa/°C."""
        return (
            4098.0
            * (0.6108 * math.exp((17.27 * temp_mean_c) / (temp_mean_c + 237.3)))
            / (temp_mean_c + 237.3) ** 2
        )

    @staticmethod
    def _extraterrestrial_radiation(lat_rad: float, doy: int) -> float:
        """
        Extraterrestrial radiation Ra (Eq. 21). Returns MJ/m²/day.

        Parameters
        ----------
        lat_rad : float
            Latitude in radians.
        doy : int
            Day of year (1–365).
        """
        dr = 1.0 + 0.033 * math.cos(2.0 * math.pi / 365.0 * doy)  # Eq. 23
        delta = 0.409 * math.sin(2.0 * math.pi / 365.0 * doy - 1.39)  # Eq. 24
        omega_s = math.acos(-math.tan(lat_rad) * math.tan(delta))  # Eq. 25
        Gsc = 0.082   # solar constant (MJ/m²/min)
        Ra = (
            24.0 * 60.0 / math.pi
            * Gsc * dr
            * (
                omega_s * math.sin(lat_rad) * math.sin(delta)
                + math.cos(lat_rad) * math.cos(delta) * math.sin(omega_s)
            )
        )  # Eq. 21
        return max(0.0, Ra)

    @staticmethod
    def _net_longwave(
        t_max: float, t_min: float, e_a: float, Rs: float, Rso: float
    ) -> float:
        """
        Net outgoing longwave radiation Rnl (Eq. 39). Returns MJ/m²/day.
        """
        sigma = 4.903e-9   # Stefan-Boltzmann constant (MJ/K⁴/m²/day)
        t_max_k = t_max + 273.16
        t_min_k = t_min + 273.16
        rs_rso = min(Rs / Rso, 1.0) if Rso > 0 else 0.5
        return (
            sigma
            * ((t_max_k ** 4 + t_min_k ** 4) / 2.0)
            * (0.34 - 0.14 * math.sqrt(max(e_a, 0.0)))
            * (1.35 * rs_rso - 0.35)
        )


# ================================================================== #
# Convenience helper: build ET0Inputs from a weather record dict
# ================================================================== #

def build_et0_inputs(
    weather: dict[str, Any],
    latitude_deg: float,
    altitude_m: float,
    day_of_year: int,
) -> ET0Inputs | None:
    """
    Build ``ET0Inputs`` from a weather record dictionary.

    Returns ``None`` if critical fields are missing (so callers can decide
    whether to skip computation rather than raising immediately).

    Critical fields required: temp_max_c, temp_min_c, wind_speed_m_s,
    solar_radiation_mj_m2 (at minimum).
    """
    critical = [
        weather.get("temperature_max_c"),
        weather.get("temperature_min_c"),
        weather.get("wind_speed_m_s"),
        weather.get("solar_radiation_mj_m2"),
    ]
    if any(v is None for v in critical):
        missing = [
            k for k, v in zip(
                ["temp_max_c", "temp_min_c", "wind_speed_m_s", "solar_radiation_mj_m2"],
                critical,
            )
            if v is None
        ]
        logger.warning("ET0 skipped — missing critical fields: %s", missing)
        return None

    rh_max = weather.get("humidity_max_pct")
    rh_min = weather.get("humidity_min_pct")
    rh_mean = weather.get("humidity_mean_pct")

    # Fallback: if only mean RH is available, use it for both max/min
    if rh_max is None and rh_min is None and rh_mean is not None:
        rh_max = rh_mean + 5.0
        rh_min = max(rh_mean - 5.0, 0.0)

    return ET0Inputs(
        temp_max_c=float(weather["temperature_max_c"]),
        temp_min_c=float(weather["temperature_min_c"]),
        humidity_max_pct=float(rh_max) if rh_max is not None else 70.0,
        humidity_min_pct=float(rh_min) if rh_min is not None else 30.0,
        humidity_mean_pct=float(rh_mean) if rh_mean is not None else None,
        wind_speed_m_s=float(weather["wind_speed_m_s"]),
        solar_radiation_mj_m2=float(weather["solar_radiation_mj_m2"]),
        latitude_rad=math.radians(latitude_deg),
        altitude_m=altitude_m,
        day_of_year=day_of_year,
        pressure_kpa=weather.get("pressure_kpa"),
    )

