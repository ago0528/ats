from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, Enum, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import Environment


class PromptAuditLog(Base):
    __tablename__ = "prompt_audit_logs"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    environment: Mapped[Environment] = mapped_column(Enum(Environment), nullable=False)
    worker_type: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    before_len: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    after_len: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actor: Mapped[str] = mapped_column(Text, nullable=False, default="system")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.utcnow)
