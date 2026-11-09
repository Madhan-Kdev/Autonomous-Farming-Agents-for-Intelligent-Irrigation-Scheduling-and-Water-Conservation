"""
Risk and Anomaly Detection Engine.

Detects agricultural, meteorological, hydraulic, and sensor hazards across
farm intelligence streams without LLM hallucinations.

Rules:
1. Frost Risk: Ambient temperature <= 2.0°C.
2. Heatwave Risk: Ambient temperature >= 38.0°C.
3. Rain Conflict: Irrigation scheduled despite imminent rain >= 5.0 mm.
4. High Wind Hazard: Wind speed >= 8.0 m/s causing spray drift / evaporation.
5. Soil Saturation / Waterlogging: Soil moisture >= Field Capacity or is_over_wet is True.
6. Severe Drought / Crop Desiccation: Available Water Content < 20% or soil stress index >= 0.70.
7. Sensor Anomaly: Soil moisture < 0% or > 100%, or theta < theta_WP / theta > saturation.
8. Hydraulic Overload: Recommended irrigation depth exceeds zone hydraulic capacity.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.agent_state import RiskItem, RiskSeverity


@dataclass
class RiskEvaluationResult:
    """Consolidated risk assessment outcome."""

    risks: list[RiskItem] = field(default_factory=list)
    overall_risk_level: RiskSeverity = RiskSeverity.INFO
    recommendation_safe: bool = True
    risk_summary: str = ""


_SEVERITY_WEIGHTS = {
    RiskSeverity.CRITICAL: 4,
    RiskSeverity.HIGH: 3,
    RiskSeverity.MEDIUM: 2,
    RiskSeverity.LOW: 1,
    RiskSeverity.INFO: 0,
}


def evaluate_system_risks(
    *,
    temperature_c: float | None = None,
    wind_speed_ms: float | None = None,
    rainfall_mm: float | None = None,
    forecast_rain_7d_mm: float | None = None,
    soil_moisture_pct: float | None = None,
    field_capacity_pct: float | None = None,
    wilting_point_pct: float | None = None,
    available_water_pct: float | None = None,
    soil_stress_index: float | None = None,
    is_over_wet: bool = False,
    is_over_dry: bool = False,
    irrigation_required: bool = False,
    recommended_volume_mm: float | None = None,
    max_irrigation_capacity_mm: float | None = None,
) -> RiskEvaluationResult:
    """
    Evaluate system telemetry and planned operations for agro-climatic and hydraulic risks.

    Parameters
    ----------
    temperature_c : float, optional
        Ambient air temperature (°C).
    wind_speed_ms : float, optional
        Sustained wind speed (m/s).
    rainfall_mm : float, optional
        Current rainfall (mm).
    forecast_rain_7d_mm : float, optional
        Forecast precipitation (mm).
    soil_moisture_pct : float, optional
        Volumetric or percentage soil moisture.
    field_capacity_pct : float, optional
        Field capacity threshold (%).
    wilting_point_pct : float, optional
        Permanent wilting point (%).
    available_water_pct : float, optional
        Available water percentage of TAW.
    soil_stress_index : float, optional
        Soil moisture stress index (0.0 to 1.0).
    is_over_wet : bool
        Whether root-zone is over-saturated.
    is_over_dry : bool
        Whether root-zone is severely dry.
    irrigation_required : bool
        Whether irrigation is planned/recommended.
    recommended_volume_mm : float, optional
        Proposed application depth (mm).
    max_irrigation_capacity_mm : float, optional
        Zone hydraulic absorption ceiling (mm).

    Returns
    -------
    RiskEvaluationResult
    """
    risks: list[RiskItem] = []

    # ------------------------------------------------------------------ #
    # 1. Weather Hazards
    # ------------------------------------------------------------------ #

    # Frost Hazard
    if temperature_c is not None and temperature_c <= 2.0:
        risks.append(
            RiskItem(
                risk_type="FROST_RISK",
                severity=RiskSeverity.HIGH if temperature_c > 0.0 else RiskSeverity.CRITICAL,
                description=f"Frost event danger: Ambient temperature is {temperature_c:.1f}°C.",
                evidence=[
                    f"Temperature {temperature_c:.1f}°C <= 2.0°C frost danger threshold.",
                    "Freezing surface moisture damages plant tissue and causes root freezing.",
                ],
                mitigation="Suspend nighttime/sprinkler irrigation unless active frost protection cycling is configured.",
            )
        )

    # Heatwave & Extreme Evaporative Demand
    if temperature_c is not None and temperature_c >= 38.0:
        risks.append(
            RiskItem(
                risk_type="HEATWAVE_RISK",
                severity=RiskSeverity.HIGH,
                description=f"Extreme heatwave danger: Ambient temperature is {temperature_c:.1f}°C.",
                evidence=[
                    f"Temperature {temperature_c:.1f}°C >= 38.0°C thermal stress threshold.",
                    "Elevated vapor pressure deficit causes acute stomatal closure and wilting.",
                ],
                mitigation="Apply pulse irrigation during early morning or evening to minimize midday evaporative loss.",
            )
        )

    # High Wind / Drift Hazard
    if wind_speed_ms is not None and wind_speed_ms >= 8.0:
        sev = RiskSeverity.CRITICAL if wind_speed_ms >= 12.0 else RiskSeverity.HIGH
        risks.append(
            RiskItem(
                risk_type="HIGH_WIND_HAZARD",
                severity=sev,
                description=f"High wind condition: Wind velocity is {wind_speed_ms:.1f} m/s.",
                evidence=[
                    f"Wind speed {wind_speed_ms:.1f} m/s >= 8.0 m/s distribution threshold.",
                    "Causes acute droplet drift, non-uniform distribution, and high kinetic evaporation.",
                ],
                mitigation="Postpone overhead sprinkler irrigation until wind speed drops below 6.0 m/s; use drip emitters if available.",
            )
        )

    # ------------------------------------------------------------------ #
    # 2. Decision & Weather Conflict Hazards
    # ------------------------------------------------------------------ #

    # Rain Conflict: Scheduled irrigation when rain is imminent
    imminent_rain = (rainfall_mm or 0.0) + (forecast_rain_7d_mm or 0.0)
    if irrigation_required and (rainfall_mm is not None and rainfall_mm >= 5.0 or imminent_rain >= 10.0):
        risks.append(
            RiskItem(
                risk_type="RAIN_CONFLICT",
                severity=RiskSeverity.HIGH,
                description="Irrigation scheduled during significant precipitation.",
                evidence=[
                    f"Current rain: {rainfall_mm or 0.0:.1f} mm, Upcoming rain: {imminent_rain:.1f} mm.",
                    "Irrigating immediately before or during rainfall causes runoff and nutrient leaching.",
                ],
                mitigation="Postpone irrigation event; re-evaluate effective rainfall depth.",
            )
        )

    # ------------------------------------------------------------------ #
    # 3. Soil Moisture & Agronomic Hazards
    # ------------------------------------------------------------------ #

    # Waterlogging / Saturated Soil
    if is_over_wet or (
        soil_moisture_pct is not None
        and field_capacity_pct is not None
        and soil_moisture_pct > (field_capacity_pct * 1.15)
    ):
        risks.append(
            RiskItem(
                risk_type="WATERLOGGING_RISK",
                severity=RiskSeverity.HIGH if irrigation_required else RiskSeverity.MEDIUM,
                description="Root zone waterlogging and soil saturation detected.",
                evidence=[
                    f"Soil moisture {soil_moisture_pct if soil_moisture_pct is not None else 'N/A'}% exceeds field capacity saturation limits.",
                    "Anaerobic root conditions inhibit nutrient uptake and foster fungal pathogens.",
                ],
                mitigation="Halt all irrigation inputs; ensure field drainage channels are clear.",
            )
        )

    # Severe Drought / Desiccation
    stress_val = soil_stress_index if soil_stress_index is not None else 0.0
    aw_val = available_water_pct if available_water_pct is not None else 50.0
    if is_over_dry or stress_val >= 0.70 or aw_val < 20.0:
        sev = RiskSeverity.CRITICAL if (stress_val >= 0.85 or aw_val < 10.0) else RiskSeverity.HIGH
        risks.append(
            RiskItem(
                risk_type="DROUGHT_STRESS_RISK",
                severity=sev,
                description="Severe crop water deficit and moisture depletion.",
                evidence=[
                    f"Soil stress index: {stress_val:.2f}, Available water: {aw_val:.1f}%.",
                    "Root-zone water depletion has crossed critical threshold into permanent wilting danger.",
                ],
                mitigation="Trigger high-priority replenishment irrigation immediately.",
            )
        )

    # ------------------------------------------------------------------ #
    # 4. Sensor Telemetry Anomalies
    # ------------------------------------------------------------------ #

    if soil_moisture_pct is not None:
        if soil_moisture_pct < 0.0 or soil_moisture_pct > 100.0:
            risks.append(
                RiskItem(
                    risk_type="SENSOR_ANOMALY",
                    severity=RiskSeverity.HIGH,
                    description=f"Physical sensor out-of-range: Moisture reading {soil_moisture_pct:.1f}%.",
                    evidence=[
                        f"Soil moisture {soil_moisture_pct:.1f}% is outside physical boundary [0.0%, 100.0%].",
                        "Indicates probe disconnection, calibration drift, or telemetry electrical fault.",
                    ],
                    mitigation="Flag sensor for inspection and default to soil water balance simulation.",
                )
            )
        elif (
            wilting_point_pct is not None
            and field_capacity_pct is not None
            and wilting_point_pct >= field_capacity_pct
        ):
            risks.append(
                RiskItem(
                    risk_type="SENSOR_ANOMALY",
                    severity=RiskSeverity.MEDIUM,
                    description="Inconsistent soil hydraulic calibration: Wilting point >= Field capacity.",
                    evidence=[
                        f"Wilting point ({wilting_point_pct:.1f}%) >= Field capacity ({field_capacity_pct:.1f}%).",
                    ],
                    mitigation="Review and correct soil texture and hydraulic parameters.",
                )
            )

    # ------------------------------------------------------------------ #
    # 5. Hydraulic & Operational Hazards
    # ------------------------------------------------------------------ #

    if irrigation_required and recommended_volume_mm is not None and recommended_volume_mm > 0.0:
        capacity_ceiling = max_irrigation_capacity_mm or 45.0
        if recommended_volume_mm > capacity_ceiling:
            risks.append(
                RiskItem(
                    risk_type="HYDRAULIC_OVERLOAD",
                    severity=RiskSeverity.HIGH,
                    description=f"Recommended volume {recommended_volume_mm:.1f} mm exceeds zone intake ceiling ({capacity_ceiling:.1f} mm).",
                    evidence=[
                        f"Recommended depth {recommended_volume_mm:.1f} mm > Capacity ceiling {capacity_ceiling:.1f} mm.",
                        "Application rate exceeds soil infiltration capacity, triggering surface runoff and erosion.",
                    ],
                    mitigation=f"Split irrigation event into multiple cycle-and-soak pulses (max {capacity_ceiling:.1f} mm each).",
                )
            )

    # ------------------------------------------------------------------ #
    # Synthesis & Aggregation
    # ------------------------------------------------------------------ #

    if not risks:
        return RiskEvaluationResult(
            risks=[],
            overall_risk_level=RiskSeverity.INFO,
            recommendation_safe=True,
            risk_summary="All agro-climatic, soil moisture, and hydraulic telemetry are within nominal safe operating parameters.",
        )

    # Determine highest severity
    highest_severity = RiskSeverity.INFO
    highest_weight = 0
    for r in risks:
        w = _SEVERITY_WEIGHTS.get(r.severity, 0)
        if w > highest_weight:
            highest_weight = w
            highest_severity = r.severity

    # Recommendation safety
    recommendation_safe = highest_severity not in (RiskSeverity.CRITICAL, RiskSeverity.HIGH)

    summary_items = [f"[{r.severity.value}] {r.risk_type}: {r.description}" for r in risks]
    summary = f"Detected {len(risks)} system risk(s). Highest severity: {highest_severity.value}. " + " ".join(summary_items)

    return RiskEvaluationResult(
        risks=risks,
        overall_risk_level=highest_severity,
        recommendation_safe=recommendation_safe,
        risk_summary=summary,
    )

