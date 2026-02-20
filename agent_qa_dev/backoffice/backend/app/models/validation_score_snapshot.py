from __future__ import annotations

import datetime as dt
import uuid
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ValidationScoreSnapshot(Base):
    __tablename__ = "validation_score_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("validation_runs.id"), nullable=False, index=True)
    test_set_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("validation_test_sets.id"), nullable=True, index=True)
    query_group_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("validation_query_groups.id"), nullable=True, index=True)
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    executed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    logic_pass_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    logic_pass_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    llm_done_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_metric_averages_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    llm_total_score_avg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evaluated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.utcnow, index=True)

