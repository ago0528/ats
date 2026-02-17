from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class GenericRunRow(Base):
    __tablename__ = "generic_run_rows"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("generic_runs.id"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    query_id: Mapped[str] = mapped_column(Text, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    llm_criteria: Mapped[str] = mapped_column(Text, nullable=False, default="")
    field_path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    expected_value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    response_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    response_time_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    execution_process: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    logic_result: Mapped[str] = mapped_column(Text, nullable=False, default="")
    llm_eval_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    llm_eval_status: Mapped[str] = mapped_column(Text, nullable=False, default="")
