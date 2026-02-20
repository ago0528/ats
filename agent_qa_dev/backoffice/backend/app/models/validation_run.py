from __future__ import annotations

import datetime as dt
import uuid
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import Environment, EvalStatus, RunStatus


class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="REGISTERED")
    environment: Mapped[Environment] = mapped_column(Enum(Environment), nullable=False, index=True)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), nullable=False, default=RunStatus.PENDING, index=True)
    base_run_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("validation_runs.id"), nullable=True)
    test_set_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("validation_test_sets.id"), nullable=True, index=True)
    agent_id: Mapped[str] = mapped_column(String(120), nullable=False, default="ORCHESTRATOR_WORKER_V3")
    test_model: Mapped[str] = mapped_column(String(120), nullable=False, default="gpt-5.2")
    eval_model: Mapped[str] = mapped_column(String(120), nullable=False, default="gpt-5.2")
    repeat_in_conversation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    conversation_room_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    agent_parallel_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=120000)
    options_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.utcnow)
    started_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, nullable=True)
    eval_status: Mapped[EvalStatus] = mapped_column(Enum(EvalStatus), nullable=False, default=EvalStatus.PENDING, index=True)
    eval_started_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, nullable=True)
    eval_finished_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, nullable=True)
