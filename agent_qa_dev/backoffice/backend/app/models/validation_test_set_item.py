from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ValidationTestSetItem(Base):
    __tablename__ = "validation_test_set_items"
    __table_args__ = (
        UniqueConstraint("test_set_id", "query_id", name="uq_validation_test_set_item_test_set_query"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_set_id: Mapped[str] = mapped_column(String(36), ForeignKey("validation_test_sets.id"), nullable=False, index=True)
    query_id: Mapped[str] = mapped_column(String(36), ForeignKey("validation_queries.id"), nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=1)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.utcnow)
