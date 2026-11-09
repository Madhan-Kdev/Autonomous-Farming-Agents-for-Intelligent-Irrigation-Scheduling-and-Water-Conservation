"""
LangGraph workflow prototype for Phase 2.

Implements a minimal but structurally complete graph:

    START → orchestrator_node → analysis_node → decision_node → END

Purpose
-------
* Verify that LangGraph state passing works correctly.
* Verify that conditional routing can be added.
* Verify that structured outputs flow between nodes.
* Verify error handling at the graph boundary.

This prototype does NOT connect to the Groq LLM or any real agents yet.
Those are implemented in Phase 5–18.  The nodes contain lightweight
placeholder logic that can be replaced incrementally.

Architecture note
-----------------
Each node function receives the current ``OrchestratorGraphState`` dict
and returns a *partial* dict with only the keys it wants to update.
LangGraph merges the returned dict into the existing state automatically.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.orchestrator.state import OrchestratorGraphState

logger = logging.getLogger(__name__)


# ================================================================== #
# Node functions
# ================================================================== #


def orchestrator_node(state: OrchestratorGraphState) -> dict[str, Any]:
    """
    Master Orchestrator node.

    Responsibilities (Phase 2 prototype):
    * Acknowledge the incoming request.
    * Set the ``orchestrator_started`` flag.
    * In later phases: decompose the user objective, plan agent calls,
      and populate the request context.
    """
    logger.info("[Orchestrator] Starting workflow orchestration.")
    return {
        "orchestrator_started": True,
        "errors": [],
        "warnings": [],
    }


def analysis_node(state: OrchestratorGraphState) -> dict[str, Any]:
    """
    Analysis node (placeholder for Weather + Soil + Crop + ET₀ agents).

    In Phase 2 this verifies that the state received from the orchestrator
    is structurally correct before triggering analysis.

    In later phases (Phase 5–8) this node will delegate to:
    * WeatherAgent
    * SoilAgent
    * CropAgent
    * ET0PredictionModule
    """
    logger.info("[Analysis] Running analysis agents (placeholder).")

    if not state.get("orchestrator_started"):
        logger.warning("[Analysis] Orchestrator did not initialise state.")
        return {
            "analysis_completed": False,
            "warnings": ["Orchestrator did not set orchestrator_started flag."],
        }

    return {"analysis_completed": True}


def decision_node(state: OrchestratorGraphState) -> dict[str, Any]:
    """
    Decision node (placeholder for Irrigation Decision + Optimization + Risk agents).

    In Phase 2 this verifies that analysis completed before producing a
    placeholder decision.

    In later phases (Phase 13–17) this node will delegate to:
    * IrrigationDecisionAgent
    * WaterOptimizationAgent
    * RiskAnomalyAgent
    * FarmerAdvisoryAgent
    """
    logger.info("[Decision] Running decision agents (placeholder).")

    if not state.get("analysis_completed"):
        errors = state.get("errors", [])
        errors.append("Decision node reached before analysis was complete.")
        return {
            "decision_completed": False,
            "workflow_complete": False,
            "errors": errors,
        }

    return {
        "decision_completed": True,
        "workflow_complete": True,
    }


# ================================================================== #
# Conditional routing
# ================================================================== #


def _route_after_analysis(state: OrchestratorGraphState) -> str:
    """
    Route to the decision node if analysis succeeded, otherwise end early.

    This demonstrates LangGraph's conditional routing capability which
    will be extended in Phase 18 with full error-recovery logic.
    """
    if state.get("analysis_completed"):
        return "decision"
    logger.warning("[Router] Analysis failed — terminating workflow early.")
    return END


# ================================================================== #
# Graph builder
# ================================================================== #


def build_prototype_graph() -> StateGraph:
    """
    Build and compile the Phase 2 prototype LangGraph workflow.

    Returns
    -------
    CompiledGraph
        A compiled LangGraph graph that can be invoked with
        ``graph.invoke(initial_state)``.
    """
    builder = StateGraph(OrchestratorGraphState)

    # Register nodes.
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("analysis", analysis_node)
    builder.add_node("decision", decision_node)

    # Define edges.
    builder.add_edge(START, "orchestrator")
    builder.add_edge("orchestrator", "analysis")

    # Conditional routing after analysis.
    builder.add_conditional_edges(
        "analysis",
        _route_after_analysis,
        {
            "decision": "decision",
            END: END,
        },
    )
    builder.add_edge("decision", END)

    return builder.compile()


# Module-level compiled graph instance.
# Import as: from app.agents.orchestrator.graph import prototype_graph
prototype_graph = build_prototype_graph()
