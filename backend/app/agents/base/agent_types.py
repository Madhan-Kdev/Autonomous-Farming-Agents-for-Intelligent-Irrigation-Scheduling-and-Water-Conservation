"""
Agent type constants and registry for the Autonomous Farming Agents system.
"""

from enum import Enum


class AgentType(str, Enum):
    """
    Enumeration of all agents in the system.

    Used to identify agents in execution records, logs, and routing.
    """

    MASTER_ORCHESTRATOR = "MasterOrchestrator"
    FIELD_COORDINATOR = "FieldCoordinator"
    WEATHER = "WeatherAgent"
    SOIL = "SoilAgent"
    CROP = "CropAgent"
    ET0 = "ET0PredictionModule"
    HISTORICAL = "HistoricalAgent"
    IRRIGATION_DECISION = "IrrigationDecisionAgent"
    ZONE_IRRIGATION = "ZoneIrrigationAgent"
    WATER_OPTIMIZATION = "WaterOptimizationAgent"
    RISK = "RiskAnomalyAgent"
    ADVISORY = "FarmerAdvisoryAgent"
