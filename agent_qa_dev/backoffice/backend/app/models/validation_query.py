from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ValidationQuery(Base):
    __tablename__ = "validation_queries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    expected_result: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="Happy path", index=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("validation_query_groups.id"), nullable=False, index=True)
    llm_eval_criteria_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    logic_field_path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    logic_expected_value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    context_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    target_assistant: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(120), nullable=False, default="unknown")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=dt.datetime.utcnow,
        onupdate=dt.datetime.utcnow,
    )
