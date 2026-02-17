from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_DB_PATH = os.getenv("BACKOFFICE_DB_PATH", str(Path(__file__).resolve().parents[2] / "backoffice.db"))
_ENGINE = create_engine(f"sqlite:///{_DB_PATH}", future=True)
SessionLocal = sessionmaker(bind=_ENGINE, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
