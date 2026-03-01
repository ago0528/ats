from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ValidationEvalPromptConfig(Base):
    __tablename__ = "validation_eval_prompt_configs"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    prompt_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    current_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    previous_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    current_version_label: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    previous_version_label: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    updated_by: Mapped[str] = mapped_column(Text, nullable=False, default="system")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=dt.datetime.utcnow,
        onupdate=dt.datetime.utcnow,
    )
