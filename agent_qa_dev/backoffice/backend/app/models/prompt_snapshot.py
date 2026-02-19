from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, Enum, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import Environment


class PromptSnapshot(Base):
    __tablename__ = "prompt_snapshots"
    __table_args__ = (
        UniqueConstraint("environment", "worker_type", name="uq_prompt_snapshots_environment_worker_type"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    environment: Mapped[Environment] = mapped_column(Enum(Environment), nullable=False)
    worker_type: Mapped[str] = mapped_column(Text, nullable=False)
    current_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    previous_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    actor: Mapped[str] = mapped_column(Text, nullable=False, default="system")
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=dt.datetime.utcnow,
        onupdate=dt.datetime.utcnow,
    )
