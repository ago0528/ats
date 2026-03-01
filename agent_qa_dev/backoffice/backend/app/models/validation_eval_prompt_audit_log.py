from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ValidationEvalPromptAuditLog(Base):
    __tablename__ = "validation_eval_prompt_audit_logs"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    prompt_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    before_version_label: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    after_version_label: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    before_len: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    after_len: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actor: Mapped[str] = mapped_column(Text, nullable=False, default="system")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.utcnow)
