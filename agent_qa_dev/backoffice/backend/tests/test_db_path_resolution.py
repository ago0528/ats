from __future__ import annotations

from pathlib import Path

from app.core import db as db_core


def test_resolve_db_path_uses_backend_root_for_relative_path() -> None:
    resolved = db_core._resolve_db_path("./backoffice_test.db")
    expected = str((Path(__file__).resolve().parents[1] / "backoffice_test.db").resolve())
    assert resolved == expected


def test_resolve_db_path_keeps_absolute_path() -> None:
    absolute = str((Path(__file__).resolve().parents[1] / "tmp" / "custom.db").resolve())
    resolved = db_core._resolve_db_path(absolute)
    assert resolved == absolute


def test_resolve_db_path_keeps_query_string() -> None:
    resolved = db_core._resolve_db_path("sqlite:///./backoffice_test.db?mode=ro")
    expected_base = str((Path(__file__).resolve().parents[1] / "backoffice_test.db").resolve())
    assert resolved == f"{expected_base}?mode=ro"


def test_resolve_db_path_accepts_memory_db() -> None:
    assert db_core._resolve_db_path(":memory:") == ":memory:"
    assert db_core._to_sqlite_engine_url(":memory:") == "sqlite:///:memory:"
