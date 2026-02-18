from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_RESET_FLAG_ENV = "BACKOFFICE_ALLOW_DB_RESET"
_SAFE_TEST_DB_SUFFIX = "_test"
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _split_sqlite_path_and_query(db_path: str) -> tuple[str, str]:
    path, separator, query = db_path.partition("?")
    if not separator:
        return path, ""
    return path, query


def _normalize_sqlite_path(db_path: str) -> str:
    normalized = db_path.removeprefix("sqlite:///")
    path_only, _query = _split_sqlite_path_and_query(normalized)
    return path_only


def _resolve_db_path(raw_db_path: str | None) -> str:
    configured_path = (raw_db_path or "").strip()
    if not configured_path:
        configured_path = str(_BACKEND_ROOT / "backoffice.db")

    normalized = configured_path.removeprefix("sqlite:///")
    sqlite_path, query = _split_sqlite_path_and_query(normalized)
    if sqlite_path == ":memory:":
        return ":memory:"

    candidate = Path(sqlite_path).expanduser()
    if not candidate.is_absolute():
        candidate = (_BACKEND_ROOT / candidate).resolve()
    else:
        candidate = candidate.resolve()

    resolved_path = str(candidate)
    if query:
        return f"{resolved_path}?{query}"
    return resolved_path


def _to_sqlite_engine_url(db_path: str) -> str:
    if db_path == ":memory:":
        return "sqlite:///:memory:"
    return f"sqlite:///{db_path}"


_DB_PATH = _resolve_db_path(os.getenv("BACKOFFICE_DB_PATH"))
_ENGINE = create_engine(_to_sqlite_engine_url(_DB_PATH), future=True)
SessionLocal = sessionmaker(bind=_ENGINE, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db_path() -> str:
    return _DB_PATH


def is_test_db_path(db_path: str) -> bool:
    normalized = _normalize_sqlite_path(db_path)
    if normalized == ":memory:":
        return True
    return Path(normalized).stem.endswith(_SAFE_TEST_DB_SUFFIX)


def assert_safe_db_reset() -> None:
    current_db_path = get_db_path()
    if not is_test_db_path(current_db_path):
        raise RuntimeError(
            "DB reset blocked: BACKOFFICE_DB_PATH must point to a *_test DB "
            f"(current: {current_db_path})."
        )
    if os.getenv(_RESET_FLAG_ENV) != "1":
        raise RuntimeError(
            "DB reset blocked: set BACKOFFICE_ALLOW_DB_RESET=1 to allow destructive reset in test DB."
        )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
