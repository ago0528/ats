from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ValidationLogicEvaluation(Base):
    __tablename__ = "validation_logic_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_item_id: Mapped[str] = mapped_column(ForeignKey("validation_run_items.id"), nullable=False, unique=True, index=True)
    eval_items_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result: Mapped[str] = mapped_column(String(20), nullable=False, default="SKIPPED", index=True)
    fail_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evaluated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.utcnow)
