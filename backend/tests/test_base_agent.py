"""
Tests for the BaseAgent abstraction.

Tests:
- Concrete subclass executes _run correctly.
- Execution record is appended to state after execute().
- Agent that raises AgentError records FAILED status without crashing.
- Agent that raises unexpected exception records FAILED status safely.
- Duration is recorded in milliseconds.
- Agent name is set in the execution record.
- Multiple agents can be chained through the same state.
"""

from __future__ import annotations

import pytest

from app.agents.base.base_agent import BaseAgent
from app.core.exceptions import AgentError
from app.schemas.agent_state import AgentState, AgentStatus


# ------------------------------------------------------------------ #
# Concrete test agents
# ------------------------------------------------------------------ #


class _SuccessAgent(BaseAgent):
    """Agent that writes a marker to state.llm_scratch and returns."""

    name = "SuccessAgent"

    def _run(self, state: AgentState) -> AgentState:
        state.llm_scratch["success_agent_ran"] = True
        return state


class _AgentErrorAgent(BaseAgent):
    """Agent that raises an AgentError."""

    name = "AgentErrorAgent"

    def _run(self, state: AgentState) -> AgentState:
        raise AgentError("Test agent error.")


class _UnexpectedErrorAgent(BaseAgent):
    """Agent that raises an unexpected (non-AgentError) exception."""

    name = "UnexpectedErrorAgent"

    def _run(self, state: AgentState) -> AgentState:
        raise RuntimeError("Unexpected runtime error.")


class _SecondAgent(BaseAgent):
    """Second agent used to test chaining."""

    name = "SecondAgent"

    def _run(self, state: AgentState) -> AgentState:
        state.llm_scratch["second_agent_ran"] = True
        return state


# ------------------------------------------------------------------ #
# Tests
# ------------------------------------------------------------------ #


def test_successful_agent_runs():
    """A successful agent must set its marker in state."""
    state = AgentState()
    agent = _SuccessAgent()
    result = agent.execute(state)
    assert result.llm_scratch.get("success_agent_ran") is True


def test_successful_agent_records_completed():
    """A successful agent must append a COMPLETED execution record."""
    state = AgentState()
    agent = _SuccessAgent()
    result = agent.execute(state)
    assert len(result.agent_executions) == 1
    record = result.agent_executions[0]
    assert record.status == AgentStatus.COMPLETED
    assert record.agent_name == "SuccessAgent"


def test_successful_agent_records_duration():
    """Execution record must have a non-negative duration in milliseconds."""
    state = AgentState()
    agent = _SuccessAgent()
    result = agent.execute(state)
    record = result.agent_executions[0]
    assert record.duration_ms is not None
    assert record.duration_ms >= 0


def test_successful_agent_records_timestamps():
    """Execution record must have both started_at and completed_at."""
    state = AgentState()
    agent = _SuccessAgent()
    result = agent.execute(state)
    record = result.agent_executions[0]
    assert record.started_at is not None
    assert record.completed_at is not None
    assert record.completed_at >= record.started_at


def test_agent_error_does_not_crash_workflow():
    """AgentError must be caught — state is returned with FAILED record."""
    state = AgentState()
    agent = _AgentErrorAgent()
    result = agent.execute(state)  # Must NOT raise.
    assert result is not None


def test_agent_error_records_failed_status():
    """AgentError must produce a FAILED execution record."""
    state = AgentState()
    agent = _AgentErrorAgent()
    result = agent.execute(state)
    record = result.agent_executions[0]
    assert record.status == AgentStatus.FAILED
    assert record.agent_name == "AgentErrorAgent"


def test_agent_error_appends_to_errors_list():
    """AgentError must append a message to state.errors."""
    state = AgentState()
    agent = _AgentErrorAgent()
    result = agent.execute(state)
    assert len(result.errors) == 1
    assert "AgentErrorAgent" in result.errors[0]


def test_unexpected_error_does_not_crash_workflow():
    """Unexpected exceptions must be caught — workflow continues."""
    state = AgentState()
    agent = _UnexpectedErrorAgent()
    result = agent.execute(state)  # Must NOT raise.
    assert result is not None


def test_unexpected_error_records_failed_status():
    """Unexpected exceptions must produce a FAILED execution record."""
    state = AgentState()
    agent = _UnexpectedErrorAgent()
    result = agent.execute(state)
    record = result.agent_executions[0]
    assert record.status == AgentStatus.FAILED


def test_unexpected_error_appends_to_errors_list():
    """Unexpected exceptions must append to state.errors."""
    state = AgentState()
    agent = _UnexpectedErrorAgent()
    result = agent.execute(state)
    assert len(result.errors) > 0


def test_agents_can_be_chained():
    """Two agents executed in sequence must both record execution."""
    state = AgentState()
    a1 = _SuccessAgent()
    a2 = _SecondAgent()
    state = a1.execute(state)
    state = a2.execute(state)
    assert len(state.agent_executions) == 2
    assert state.llm_scratch.get("success_agent_ran") is True
    assert state.llm_scratch.get("second_agent_ran") is True


def test_failed_agent_does_not_block_next_agent():
    """A failing agent must not prevent subsequent agents from running."""
    state = AgentState()
    failing = _AgentErrorAgent()
    success = _SuccessAgent()
    state = failing.execute(state)
    state = success.execute(state)
    # Both must have execution records.
    names = [r.agent_name for r in state.agent_executions]
    assert "AgentErrorAgent" in names
    assert "SuccessAgent" in names
    assert state.llm_scratch.get("success_agent_ran") is True


def test_agent_repr():
    """Agent repr must include the class name."""
    agent = _SuccessAgent()
    r = repr(agent)
    assert "_SuccessAgent" in r

