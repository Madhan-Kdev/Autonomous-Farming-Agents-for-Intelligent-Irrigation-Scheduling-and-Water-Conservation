"""
Multi-Agent Orchestration Workflow Graph.

Full production-grade LangGraph workflow connecting all specialized domain agents:
1. WeatherAgent (Meteorological data acquisition & safety)
2. SoilAgent (Soil moisture profile & FAO-56 balance)
3. CropAgent (Phenology, growth stages, Kc curves)
4. ET0PredictionModule (FAO-56 reference + ML regressor forecast)
5. HistoricalAgent (30d rainfall & irrigation auditing)
6. IrrigationDecisionAgent (Multi-criteria rules decision)
7. ZoneIrrigationAgent (Multi-zone precision scheduling)
8. WaterOptimizationAgent (Conservation, baseline, Liters saved)
9. RiskAnomalyAgent (Hazards & telemetry anomaly diagnostics)
10. FarmerAdvisoryAgent (Explainable AI & farmer guidance)

Execution Topology:
  START
    ↓
  weather_node
    ↓
  soil_node
    ↓
  crop_node
    ↓
  et0_node
    ↓
  historical_node
    ↓
  decision_node
    ↓
  zone_planning_node
    ↓
  optimization_node
    ↓
  risk_node
    ↓
  advisory_node
    ↓
  END

Safety & Error Containment:
- Nodes run via BaseAgent.execute(state) to contain exceptions and log telemetry.
- State is preserved and updated monotonically without loss.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.advisory.advisory_agent import FarmerAdvisoryAgent
from app.agents.crop.crop_agent import CropAgent
from app.agents.et0.et0_agent import ET0PredictionModule
from app.agents.historical.historical_agent import HistoricalAgent
from app.agents.irrigation.irrigation_decision_agent import IrrigationDecisionAgent
from app.agents.irrigation.zone_irrigation_agent import ZoneIrrigationAgent
from app.agents.risk.risk_agent import RiskAnomalyAgent
from app.agents.soil.soil_agent import SoilAgent
from app.agents.water_optimization.water_optimization_agent import WaterOptimizationAgent
from app.agents.weather.weather_agent import WeatherAgent
from app.schemas.agent_state import AgentState

logger = logging.getLogger(__name__)


def create_agent_workflow(db: Session) -> Any:
    """
    Construct and compile the full multi-agent LangGraph workflow.

    Parameters
    ----------
    db : Session
        Active SQLAlchemy database session passed to agents.

    Returns
    -------
    CompiledGraph
        Compiled workflow executable via `.invoke(state)` where state is an `AgentState`.
    """

    # Instantiate agents
    weather_agent = WeatherAgent(db=db)
    soil_agent = SoilAgent(db=db)
    crop_agent = CropAgent(db=db)
    et0_agent = ET0PredictionModule(db=db)
    historical_agent = HistoricalAgent(db=db)
    decision_agent = IrrigationDecisionAgent(db=db)
    zone_agent = ZoneIrrigationAgent(db=db)
    optimization_agent = WaterOptimizationAgent(db=db)
    risk_agent = RiskAnomalyAgent(db=db)
    advisory_agent = FarmerAdvisoryAgent(db=db)

    # ------------------------------------------------------------------ #
    # Node Callbacks
    # ------------------------------------------------------------------ #

    def run_weather(state: AgentState) -> AgentState:
        state.workflow_step = "WEATHER_ANALYSIS"
        return weather_agent.execute(state)

    def run_soil(state: AgentState) -> AgentState:
        state.workflow_step = "SOIL_ANALYSIS"
        return soil_agent.execute(state)

    def run_crop(state: AgentState) -> AgentState:
        state.workflow_step = "CROP_ANALYSIS"
        return crop_agent.execute(state)

    def run_et0(state: AgentState) -> AgentState:
        state.workflow_step = "ET0_PREDICTION"
        return et0_agent.execute(state)

    def run_historical(state: AgentState) -> AgentState:
        state.workflow_step = "HISTORICAL_AUDIT"
        return historical_agent.execute(state)

    def run_decision(state: AgentState) -> AgentState:
        state.workflow_step = "IRRIGATION_DECISION"
        return decision_agent.execute(state)

    def run_zone_planning(state: AgentState) -> AgentState:
        state.workflow_step = "ZONE_PLANNING"
        return zone_agent.execute(state)

    def run_optimization(state: AgentState) -> AgentState:
        state.workflow_step = "WATER_OPTIMIZATION"
        return optimization_agent.execute(state)

    def run_risk(state: AgentState) -> AgentState:
        state.workflow_step = "RISK_DIAGNOSTICS"
        return risk_agent.execute(state)

    def run_advisory(state: AgentState) -> AgentState:
        state.workflow_step = "FARMER_ADVISORY"
        state = advisory_agent.execute(state)
        state.is_complete = True
        state.workflow_step = "COMPLETED"
        return state

    # ------------------------------------------------------------------ #
    # Graph Construction
    # ------------------------------------------------------------------ #

    graph = StateGraph(AgentState)

    graph.add_node("weather", run_weather)
    graph.add_node("soil", run_soil)
    graph.add_node("crop", run_crop)
    graph.add_node("et0", run_et0)
    graph.add_node("historical", run_historical)
    graph.add_node("decision", run_decision)
    graph.add_node("zone_planning", run_zone_planning)
    graph.add_node("optimization", run_optimization)
    graph.add_node("risk", run_risk)
    graph.add_node("advisory", run_advisory)

    # Edges (Linear sequential pipeline with error-containment)
    graph.add_edge(START, "weather")
    graph.add_edge("weather", "soil")
    graph.add_edge("soil", "crop")
    graph.add_edge("crop", "et0")
    graph.add_edge("et0", "historical")
    graph.add_edge("historical", "decision")
    graph.add_edge("decision", "zone_planning")
    graph.add_edge("zone_planning", "optimization")
    graph.add_edge("optimization", "risk")
    graph.add_edge("risk", "advisory")
    graph.add_edge("advisory", END)

    return graph.compile()

