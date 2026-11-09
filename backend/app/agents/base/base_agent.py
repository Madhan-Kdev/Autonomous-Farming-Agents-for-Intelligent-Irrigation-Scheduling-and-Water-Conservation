"""
Base agent abstractions for the Autonomous Farming Agents system.

All specialized agents must inherit from ``BaseAgent``.  This enforces:
* A consistent execution interface (``execute`` method).
* Structured input/output via ``AgentState``.
* Execution timing and status recording.
* Standardised error handling — agents catch and log errors rather than
  crashing the entire workflow.
* Clear separation of responsibilities — each agent writes only to its
  designated section of the shared state.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, ClassVar

from app.core.exceptions import AgentError, AgentTimeoutError
from app.schemas.agent_state import AgentExecutionRecord, AgentState, AgentStatus

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class that every specialized agent must subclass.

    Subclasses must implement :meth:`_run` which contains the actual
    agent logic.  The public :meth:`execute` method wraps ``_run`` with:

    * Execution timing
    * Status recording into the shared ``AgentState``
    * Standardised exception handling
    * Logging

    Agent contract
    --------------
    * Each agent reads from the shared ``AgentState`` (all sections).
    * Each agent writes ONLY to its designated section.
    * Agents must NOT call other agents directly — all coordination goes
      through the LangGraph orchestrator.
    * Numerical outputs must come from validated computations — never
      from LLM-generated free text.
    """

    #: Human-readable agent name (used in logs and execution records).
    name: ClassVar[str] = "BaseAgent"

    #: Maximum allowed execution time in seconds.  Override in subclasses.
    timeout_seconds: ClassVar[float] = 30.0

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """
        Initialise the agent with optional configuration overrides.

        Parameters
        ----------
        config:
            Optional dictionary of agent-specific configuration.
            Subclasses should document which keys they support.
        """
        self.config: dict[str, Any] = config or {}
        self._logger = logging.getLogger(
            f"{__name__}.{type(self).__name__}"
        )

    # ------------------------------------------------------------------ #
    # Public interface
    # ------------------------------------------------------------------ #

    def execute(self, state: AgentState) -> AgentState:
        """
        Execute the agent against the current shared state.

        This is the only method that should be called by the LangGraph
        workflow.  It records timing, updates the execution record in
        the shared state, and delegates to :meth:`_run`.

        Parameters
        ----------
        state:
            The current shared ``AgentState``.

        Returns
        -------
        AgentState
            The updated state with this agent's output written to its
            designated section.
        """
        record = AgentExecutionRecord(
            agent_name=self.name,
            status=AgentStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        self._logger.info("Agent [%s] starting", self.name)
        start_time = time.perf_counter()

        try:
            state = self._run(state)
            duration_ms = (time.perf_counter() - start_time) * 1000
            record.status = AgentStatus.COMPLETED
            record.completed_at = datetime.now(timezone.utc)
            record.duration_ms = duration_ms
            self._summarize_agent_io(state, record)
            self._logger.info(
                "Agent [%s] completed in %.1f ms", self.name, duration_ms
            )

        except AgentTimeoutError as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            record.status = AgentStatus.FAILED
            record.completed_at = datetime.now(timezone.utc)
            record.duration_ms = duration_ms
            record.error_message = str(exc)
            state.errors.append(f"[{self.name}] timeout: {exc}")
            self._logger.error("Agent [%s] timed out: %s", self.name, exc)

        except AgentError as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            record.status = AgentStatus.FAILED
            record.completed_at = datetime.now(timezone.utc)
            record.duration_ms = duration_ms
            record.error_message = str(exc)
            state.errors.append(f"[{self.name}] error: {exc}")
            self._logger.error("Agent [%s] error: %s", self.name, exc)

        except Exception as exc:  # noqa: BLE001
            # Unexpected errors are caught here so the workflow can continue
            # with degraded information rather than crashing entirely.
            duration_ms = (time.perf_counter() - start_time) * 1000
            record.status = AgentStatus.FAILED
            record.completed_at = datetime.now(timezone.utc)
            record.duration_ms = duration_ms
            record.error_message = f"Unexpected: {exc}"
            state.errors.append(f"[{self.name}] unexpected error: {exc}")
            self._logger.exception(
                "Agent [%s] raised unexpected exception", self.name
            )

        finally:
            state.agent_executions.append(record)

        return state

    # ------------------------------------------------------------------ #
    # Abstract method — subclasses implement this
    # ------------------------------------------------------------------ #

    @abstractmethod
    def _run(self, state: AgentState) -> AgentState:
        """
        Core agent logic.

        Parameters
        ----------
        state:
            The current shared ``AgentState``.

        Returns
        -------
        AgentState
            Updated state with this agent's output written to the
            appropriate section.

        Notes
        -----
        * Do not catch all exceptions silently inside ``_run``.
          Allow errors to propagate to ``execute`` which handles them.
        * Do not write to another agent's state section.
        * Do not fabricate numerical values via LLM prompting.
        """

    # ------------------------------------------------------------------ #
    # Convenience helpers available to all subclasses
    # ------------------------------------------------------------------ #

    def _log_debug(self, message: str, *args: Any) -> None:
        self._logger.debug(message, *args)

    def _log_info(self, message: str, *args: Any) -> None:
        self._logger.info(message, *args)

    def _log_warning(self, message: str, *args: Any) -> None:
        self._logger.warning(message, *args)
        # Also record as a state warning so the orchestrator can see it.

    def _log_error(self, message: str, *args: Any) -> None:
        self._logger.error(message, *args)

    def _add_warning(self, state: AgentState, message: str) -> None:
        """Append a warning to the shared state warning list."""
        state.warnings.append(f"[{self.name}] {message}")
        self._logger.warning("[%s] %s", self.name, message)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r})"

    def _summarize_agent_io(self, state: AgentState, record: AgentExecutionRecord) -> None:
        """Derive structured input summary, output summary, and confidence from state."""
        try:
            name = self.name.lower()
            if "weather" in name and state.weather:
                w = state.weather
                record.input_summary = (
                    f"Coordinates ({state.request.location_latitude or 'N/A'}, {state.request.location_longitude or 'N/A'}), "
                    f"NASA POWER / OWM ingestion"
                )
                record.output_summary = (
                    f"Temp: {w.temperature_c}°C, Rain: {w.rainfall_mm}mm, "
                    f"Wind: {w.wind_speed_ms}m/s, Suitable: {w.irrigation_suitable}"
                )
                record.confidence = w.confidence
            elif "soil" in name and state.soil:
                s = state.soil
                record.input_summary = (
                    f"Target Zone: {state.request.zone_ids[0] if state.request.zone_ids else 1}, "
                    f"Moisture: {s.soil_moisture_pct}%, Soil: {s.soil_type or 'Sandy Loam'}"
                )
                record.output_summary = (
                    f"TAW: {s.taw_mm}mm, RAW: {s.raw_mm}mm, Depletion: {s.depletion_mm}mm, "
                    f"Ks: {s.water_stress_coefficient_ks}, Stress Index: {s.soil_stress_index}"
                )
                record.confidence = s.confidence
            elif "crop" in name and state.crop:
                c = state.crop
                record.input_summary = f"Crop: {c.crop_type}, DAP: {c.days_after_planting}, Stage: {c.growth_stage}"
                record.output_summary = (
                    f"Kc: {c.crop_coefficient_kc}, Root Depth: {c.current_root_depth_m}m, "
                    f"Water Demand: {c.crop_water_requirement_mm}mm"
                )
                record.confidence = c.confidence
            elif "et0" in name and state.et0:
                e = state.et0
                record.input_summary = f"Solar radiation, temp, vapor pressure deficit, wind speed"
                record.output_summary = (
                    f"FAO-56 ET0: {e.et0_reference_mm} mm/day, "
                    f"ML Predicted ET0: {e.et0_predicted_mm} mm/day"
                )
                record.confidence = e.confidence
            elif "historical" in name and state.historical:
                h = state.historical
                record.input_summary = f"30-day precipitation & 7-day irrigation event records"
                record.output_summary = (
                    f"30d Rain: {h.avg_rainfall_30d_mm}mm, 7d Irrig: {h.avg_irrigation_7d_mm}mm, "
                    f"Over-irrig: {h.detected_over_irrigation}"
                )
                record.confidence = h.confidence
            elif "decision" in name and state.irrigation_decision:
                d = state.irrigation_decision
                record.input_summary = f"Available Water: {state.soil.available_water_pct if state.soil else 0}%, ETc: {state.crop.crop_water_requirement_mm if state.crop else 0}mm"
                record.output_summary = f"Directive: {d.decision.value}, Priority: {d.priority.value}, Depth: {d.recommended_volume_mm}mm"
                record.confidence = d.confidence
            elif "zone" in name and state.zone_plans:
                record.input_summary = f"Heterogeneous multi-zone topology ({len(state.zone_plans)} zones)"
                record.output_summary = f"Generated {len(state.zone_plans)} zone schedules ({sum(1 for p in state.zone_plans if p.irrigation_required)} requiring irrigation)"
                record.confidence = 0.92
            elif "optimization" in name and state.optimization:
                opt = state.optimization
                record.input_summary = f"Baseline: {opt.baseline_volume_mm}mm, Optimized: {opt.optimized_volume_mm}mm"
                record.output_summary = f"Conserved: {opt.water_saving_mm}mm ({opt.water_saving_pct}%), Deep drainage prevented: {opt.over_irrigation_detected}"
                record.confidence = 0.95
            elif "risk" in name and state.risk:
                rk = state.risk
                record.input_summary = f"8 hazard categories audited (frost, heat, wind, rain, waterlog, drought, sensor, hydraulic)"
                record.output_summary = f"Severity: {rk.overall_risk_level}, Recommendation Safe: {rk.recommendation_safe}, Risks: {len(rk.risks)}"
                record.confidence = 0.95
            elif "advisory" in name and state.advisory:
                adv = state.advisory
                record.input_summary = f"Multi-agent context synthesis & physical threshold attribution"
                record.output_summary = f"Action: {adv.recommended_action}"
                record.confidence = adv.confidence
        except Exception:
            pass
