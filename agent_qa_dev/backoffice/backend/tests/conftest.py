from __future__ import annotations

import pytest

from app.core.db import Base, _ENGINE


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(_ENGINE)
    Base.metadata.create_all(_ENGINE)
    yield
