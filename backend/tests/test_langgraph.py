"""
Tests for the LangGraph prototype workflow.

Tests:
- Graph builds and compiles without error.
- Successful invocation produces correct state flags.
- orchestrator_node sets orchestrator_started=True.
- analysis_node sets analysis_completed=True.
- decision_node sets decision_completed and workflow_complete=True.
- Conditional routing works: analysis failure routes to END.
- Errors list is initialised as empty by orchestrator.
- Graph can be invoked multiple times (stateless between calls).
"""

from __future__ import annotations

import pytest


def test_graph_builds_without_error():
    """build_prototype_graph must return a compiled graph without raising."""
    from app.agents.orchestrator.graph import build_prototype_graph
    graph = build_prototype_graph()
    assert graph is not None


def test_prototype_graph_is_importable():
    """Module-level prototype_graph must be importable."""
    from app.agents.orchestrator.graph import prototype_graph
    assert prototype_graph is not None


def test_full_workflow_completes_successfully():
    """Invoking the graph with an empty initial state must complete the workflow."""
    from app.agents.orchestrator.graph import prototype_graph
    result = prototype_graph.invoke({})
    assert result.get("workflow_complete") is True


def test_orchestrator_node_sets_flag():
    """orchestrator_started must be True after a successful invocation."""
    from app.agents.orchestrator.graph import prototype_graph
    result = prototype_graph.invoke({})
    assert result.get("orchestrator_started") is True


def test_analysis_node_sets_flag():
    """analysis_completed must be True after a successful invocation."""
    from app.agents.orchestrator.graph import prototype_graph
    result = prototype_graph.invoke({})
    assert result.get("analysis_completed") is True


def test_decision_node_sets_flag():
    """decision_completed must be True after a successful invocation."""
    from app.agents.orchestrator.graph import prototype_graph
    result = prototype_graph.invoke({})
    assert result.get("decision_completed") is True


def test_errors_is_list():
    """errors must be a list in the result state."""
    from app.agents.orchestrator.graph import prototype_graph
    result = prototype_graph.invoke({})
    assert isinstance(result.get("errors"), list)


def test_errors_empty_on_success():
    """errors must be empty after a fully successful workflow."""
    from app.agents.orchestrator.graph import prototype_graph
    result = prototype_graph.invoke({})
    assert result.get("errors") == []


def test_graph_stateless_between_invocations():
    """Two separate invocations must produce independent results."""
    from app.agents.orchestrator.graph import prototype_graph
    r1 = prototype_graph.invoke({})
    r2 = prototype_graph.invoke({})
    # Both must succeed independently.
    assert r1.get("workflow_complete") is True
    assert r2.get("workflow_complete") is True


def test_orchestrator_graph_state_is_importable():
    """OrchestratorGraphState TypedDict must be importable."""
    from app.agents.orchestrator.state import OrchestratorGraphState
    assert OrchestratorGraphState is not None


def test_conditional_routing_skips_decision_when_analysis_fails():
    """
    If analysis_completed is False, the conditional router must route to END
    and decision_completed must remain unset/False.
    """
    from app.agents.orchestrator.graph import (
        OrchestratorGraphState,
        _route_after_analysis,
    )
    from langgraph.graph import END

    state: OrchestratorGraphState = {
        "orchestrator_started": True,
        "analysis_completed": False,
        "errors": [],
        "warnings": [],
    }
    route = _route_after_analysis(state)
    assert route == END

