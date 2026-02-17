from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import Environment


class ValidationSetting(Base):
    __tablename__ = "validation_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    environment: Mapped[Environment] = mapped_column(Enum(Environment), nullable=False, unique=True, index=True)
    repeat_in_conversation_default: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    conversation_room_count_default: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    agent_parallel_calls_default: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    timeout_ms_default: Mapped[int] = mapped_column(Integer, nullable=False, default=120000)
    test_model_default: Mapped[str] = mapped_column(String(120), nullable=False, default="gpt-5.2")
    eval_model_default: Mapped[str] = mapped_column(String(120), nullable=False, default="gpt-5.2")
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=dt.datetime.utcnow,
        onupdate=dt.datetime.utcnow,
    )
