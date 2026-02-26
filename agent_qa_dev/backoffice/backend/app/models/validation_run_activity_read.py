from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ValidationRunActivityRead(Base):
    __tablename__ = "validation_run_activity_reads"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "actor_key",
            name="uq_validation_run_activity_reads_run_actor",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("validation_runs.id"),
        nullable=False,
        index=True,
    )
    actor_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=dt.datetime.utcnow,
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=dt.datetime.utcnow,
        onupdate=dt.datetime.utcnow,
    )
