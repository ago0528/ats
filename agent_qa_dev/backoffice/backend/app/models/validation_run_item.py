from __future__ import annotations

import datetime as dt
import uuid
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ValidationRunItem(Base):
    __tablename__ = "validation_run_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("validation_runs.id"), nullable=False, index=True)
    query_id: Mapped[Optional[str]] = mapped_column(ForeignKey("validation_queries.id"), nullable=True, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    query_text_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    expected_result_snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category_snapshot: Mapped[str] = mapped_column(String(40), nullable=False, default="Happy path")
    applied_criteria_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    logic_field_path_snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="")
    logic_expected_value_snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="")
    context_json_snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="")
    target_assistant_snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="")
    conversation_room_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    repeat_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    conversation_id: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    raw_response: Mapped[str] = mapped_column(Text, nullable=False, default="")
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    executed_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, nullable=True)
