"""
Schemas package for the Autonomous Farming Agents backend.
"""

from app.schemas.agent_state import (
    AdvisoryContext,
    AgentExecutionRecord,
    AgentState,
    AgentStatus,
    CropContext,
    ET0Context,
    HistoricalContext,
    IrrigationDecision,
    IrrigationDecisionContext,
    IrrigationPriority,
    OptimizationContext,
    RequestContext,
    RiskContext,
    RiskItem,
    RiskSeverity,
    SoilContext,
    WeatherContext,
    ZoneIrrigationPlan,
)
from app.schemas.common import APIResponse, ErrorResponse, PaginatedResponse

__all__ = [
    # Common
    "APIResponse",
    "ErrorResponse",
    "PaginatedResponse",
    # Agent State
    "AgentState",
    "RequestContext",
    "WeatherContext",
    "SoilContext",
    "CropContext",
    "ET0Context",
    "HistoricalContext",
    "ZoneIrrigationPlan",
    "IrrigationDecisionContext",
    "OptimizationContext",
    "RiskContext",
    "RiskItem",
    "AdvisoryContext",
    "AgentExecutionRecord",
    # Enums
    "IrrigationDecision",
    "IrrigationPriority",
    "RiskSeverity",
    "AgentStatus",
]
