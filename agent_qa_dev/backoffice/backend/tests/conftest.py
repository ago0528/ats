from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault(
    "BACKOFFICE_DB_PATH",
    str(Path(__file__).resolve().parents[1] / "backoffice_test.db"),
)

from app.core.db import Base, _ENGINE, assert_safe_db_reset


@pytest.fixture(autouse=True)
def reset_db():
    assert_safe_db_reset()
    Base.metadata.drop_all(_ENGINE)
    Base.metadata.create_all(_ENGINE)
    yield
