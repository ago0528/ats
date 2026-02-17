from __future__ import annotations

import datetime as dt
import uuid
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ValidationLlmEvaluation(Base):
    __tablename__ = "validation_llm_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_item_id: Mapped[str] = mapped_column(ForeignKey("validation_run_items.id"), nullable=False, unique=True, index=True)
    eval_model: Mapped[str] = mapped_column(String(120), nullable=False, default="gpt-5.2")
    metric_scores_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    total_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    llm_comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="PENDING", index=True)
    evaluated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.utcnow)
