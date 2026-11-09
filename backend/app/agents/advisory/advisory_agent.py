"""
Farmer Advisory / Explainable AI (XAI) Agent.

Responsibilities
----------------
1. Ingest multidimensional agent outputs:
   - Weather: temperature, wind, rainfall, suitability.
   - Soil: moisture %, field capacity, stress index, wet/dry status.
   - Crop: growth stage, Kc, water requirement (ETc).
   - ET₀: FAO-56 reference and ML predicted values.
   - Historical: 30d rainfall and irrigation patterns.
   - Decision: irrigation decision, priority, recommended volume and timing.
   - Optimization: water savings (mm, %), over-irrigation averted.
   - Risk: detected hazards, safety status, mitigations.
2. Formulate interpretable, transparent agronomic rationale for farmers.
3. Populate `state.advisory` (`AdvisoryContext`):
   - `irrigation_required: bool`
   - `recommended_action: str`
   - `recommended_time: str | None`
   - `recommended_volume_mm: float | None`
   - `target_zones: list[int]`
   - `weather_influence: str`
   - `soil_influence: str`
   - `crop_influence: str`
   - `et0_influence: str`
   - `rainfall_influence: str`
   - `risk_summary: str`
   - `water_conservation_summary: str`
   - `full_explanation: str`
   - `confidence: float`
4. Log `AgentExecutionRecord` containing execution timing and status.

ARCHITECTURAL CONSTRAINTS:
- Writes ONLY to `state.advisory`.
- All factual and numerical data originate strictly from validated agent outputs.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base.agent_types import AgentType
from app.agents.base.base_agent import BaseAgent
from app.schemas.agent_state import AdvisoryContext, AgentState
from app.service.advisory_engine import generate_farmer_advisory

logger = logging.getLogger(__name__)


class FarmerAdvisoryAgent(BaseAgent):
    """
    Farmer Advisory / Explainable AI Agent.

    Synthesizes domain intelligence into clear, actionable, and explainable
    agronomic advisories for human farmers and farm operators.

    Writes to
    ---------
    * ``state.advisory`` — AdvisoryContext
    """

    name = AgentType.ADVISORY.value
    timeout_seconds = 30.0

    def __init__(
        self,
        db: Session | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(config)
        self._db = db

    def _run(self, state: AgentState) -> AgentState:
        """
        Synthesize explainable advisory and populate state.advisory.

        Parameters
        ----------
        state : AgentState
            The shared agent state.

        Returns
        -------
        AgentState
            Updated state with state.advisory populated.
        """
        self._log_info("FarmerAdvisoryAgent synthesizing explainable advisory")

        target_zones = []
        if state.request and state.request.zone_ids:
            target_zones = state.request.zone_ids
        elif state.irrigation_decision and state.irrigation_decision.affected_zones:
            target_zones = state.irrigation_decision.affected_zones

        advisory: AdvisoryContext = generate_farmer_advisory(
            decision_ctx=state.irrigation_decision,
            weather_ctx=state.weather,
            soil_ctx=state.soil,
            crop_ctx=state.crop,
            et0_ctx=state.et0,
            historical_ctx=state.historical,
            risk_ctx=state.risk,
            optimization_ctx=state.optimization,
            target_zones=target_zones,
        )

        state.advisory = advisory
        self._log_info(
            "FarmerAdvisoryAgent completed: action='%s', target_zones=%s, confidence=%.2f",
            advisory.recommended_action[:50],
            advisory.target_zones,
            advisory.confidence,
        )
        return state

