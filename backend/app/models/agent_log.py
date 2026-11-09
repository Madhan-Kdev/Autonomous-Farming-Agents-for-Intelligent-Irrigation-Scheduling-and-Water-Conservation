"""
AgentExecutionLog model.

Persists every agent execution into the database so that:
* Execution history is queryable across sessions.
* The HistoricalAgent can analyse agent performance over time.
* Debugging and audit trails are available without log files.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.engine import Base
from app.models.base import TimestampMixin


class AgentExecutionLog(Base, TimestampMixin):
    """
    Persistent log of a single agent execution within a workflow run.

    Attributes
    ----------
    id : int
        Primary key.
    run_id : str
        UUID of the AgentState workflow run. Groups all agents from one
        invocation together.
    farm_id : int | None
        FK → farms.id. Null for system-level runs.
    agent_name : str
        Agent that executed (matches AgentType enum value).
    status : str
        "PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED".
    started_at : datetime | None
        UTC timestamp when execution began.
    completed_at : datetime | None
        UTC timestamp when execution ended.
    duration_ms : float | None
        Execution duration in milliseconds.
    error_message : str | None
        Error message if status is FAILED.
    input_summary : str | None
        Brief summary of the input state (not full state to save space).
    output_summary : str | None
        Brief summary of the output produced.
    """

    __tablename__ = "agent_execution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    farm_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("farms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[float | None] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)
    input_summary: Mapped[str | None] = mapped_column(Text)
    output_summary: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:
        return (
            f"<AgentExecutionLog id={self.id} agent={self.agent_name!r} "
            f"status={self.status!r} run_id={self.run_id!r}>"
        )
