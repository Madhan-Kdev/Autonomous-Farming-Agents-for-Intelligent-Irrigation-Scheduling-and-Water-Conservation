"""
LangGraph state definition for the orchestrator workflow prototype.

In Phase 2 we define a minimal TypedDict-based graph state that mirrors
the sections of ``AgentState``.  In Phase 18 (Master Orchestrator), this
will be replaced by the full production workflow.

LangGraph requires its state to be a TypedDict (or Pydantic model).
We use ``AgentState`` (Pydantic) converted to a dict at the graph boundary
so that LangGraph can apply the ``Annotated`` reducers.
"""

from __future__ import annotations

from typing import Annotated, Any

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class OrchestratorGraphState(TypedDict, total=False):
    """
    Minimal LangGraph graph state for the Phase 2 prototype.

    Each key corresponds to a section populated by one agent node.
    The ``messages`` field uses LangGraph's built-in ``add_messages``
    reducer to accumulate conversation history.

    In Phase 18 this will be replaced by the full ``AgentState``-backed
    graph with conditional routing for every specialized agent.
    """

    # Conversation / reasoning messages (LangGraph pattern).
    messages: Annotated[list[Any], add_messages]

    # Simple status flags set by prototype nodes.
    orchestrator_started: bool
    analysis_completed: bool
    decision_completed: bool
    workflow_complete: bool

    # Errors accumulated during execution.
    errors: list[str]
    warnings: list[str]
