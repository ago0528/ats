from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.routes import prompts as prompts_route
from app.core.db import SessionLocal
from app.core.enums import Environment
from app.main import app
from app.models.prompt_audit_log import PromptAuditLog
from app.models.prompt_snapshot import PromptSnapshot


def _new_client():
    return TestClient(app)


def _mock_workers(monkeypatch):
    monkeypatch.setattr(
        prompts_route.PromptApiAdapter,
        "workers",
        staticmethod(lambda: [{"workerType": "W1", "description": "d1"}]),
    )


def _load_snapshot(db, environment: Environment = Environment.DEV, worker_type: str = "W1"):
    return (
        db.query(PromptSnapshot)
        .filter(PromptSnapshot.environment == environment, PromptSnapshot.worker_type == worker_type)
        .one_or_none()
    )


def test_prompts_workers_list(monkeypatch):
    _mock_workers(monkeypatch)
    client = _new_client()

    workers = client.get("/api/v1/prompts/workers")

    assert workers.status_code == 200
    assert workers.json()["workers"][0]["workerType"] == "W1"


def test_get_prompt_creates_snapshot_with_empty_previous(monkeypatch):
    _mock_workers(monkeypatch)
    monkeypatch.setattr(
        prompts_route.PromptApiAdapter,
        "get_prompt",
        lambda self, worker_type: SimpleNamespace(before="legacy-before", after="ats-current"),
    )
    client = _new_client()

    response = client.get("/api/v1/prompts/dev/W1")

    assert response.status_code == 200
    assert response.json()["before"] == "legacy-before"
    assert response.json()["after"] == "ats-current"
    assert response.json()["currentPrompt"] == "ats-current"
    assert response.json()["previousPrompt"] == ""

    db = SessionLocal()
    try:
        snapshot = _load_snapshot(db)
        assert snapshot is not None
        assert snapshot.current_prompt == "ats-current"
        assert snapshot.previous_prompt == ""

        logs = db.query(PromptAuditLog).all()
        assert len(logs) == 1
        assert logs[0].action == "GET"
    finally:
        db.close()


def test_get_prompt_rotates_previous_when_ats_value_changes(monkeypatch):
    _mock_workers(monkeypatch)
    responses = iter(
        [
            SimpleNamespace(before="legacy", after="ats-v1"),
            SimpleNamespace(before="legacy", after="ats-v2"),
        ]
    )
    monkeypatch.setattr(
        prompts_route.PromptApiAdapter,
        "get_prompt",
        lambda self, worker_type: next(responses),
    )
    client = _new_client()

    first = client.get("/api/v1/prompts/dev/W1")
    second = client.get("/api/v1/prompts/dev/W1")

    assert first.status_code == 200
    assert first.json()["currentPrompt"] == "ats-v1"
    assert first.json()["previousPrompt"] == ""

    assert second.status_code == 200
    assert second.json()["currentPrompt"] == "ats-v2"
    assert second.json()["previousPrompt"] == "ats-v1"

    db = SessionLocal()
    try:
        snapshot = _load_snapshot(db)
        assert snapshot is not None
        assert snapshot.current_prompt == "ats-v2"
        assert snapshot.previous_prompt == "ats-v1"
    finally:
        db.close()


def test_update_prompt_returns_current_from_ats_and_previous_from_snapshot(monkeypatch):
    _mock_workers(monkeypatch)
    monkeypatch.setattr(
        prompts_route.PromptApiAdapter,
        "get_prompt",
        lambda self, worker_type: SimpleNamespace(before="legacy", after="ats-current-1"),
    )
    monkeypatch.setattr(
        prompts_route.PromptApiAdapter,
        "update_prompt",
        lambda self, worker_type, prompt: SimpleNamespace(before="ats-current-1", after=prompt),
    )
    client = _new_client()

    seed = client.get("/api/v1/prompts/dev/W1")
    update = client.put("/api/v1/prompts/dev/W1", json={"prompt": "ats-current-2"})

    assert seed.status_code == 200
    assert update.status_code == 200
    assert update.json()["before"] == "ats-current-1"
    assert update.json()["after"] == "ats-current-2"
    assert update.json()["currentPrompt"] == "ats-current-2"
    assert update.json()["previousPrompt"] == "ats-current-1"

    db = SessionLocal()
    try:
        snapshot = _load_snapshot(db)
        assert snapshot is not None
        assert snapshot.current_prompt == "ats-current-2"
        assert snapshot.previous_prompt == "ats-current-1"
    finally:
        db.close()


def test_reset_prompt_returns_current_from_ats_and_previous_from_snapshot(monkeypatch):
    _mock_workers(monkeypatch)
    monkeypatch.setattr(
        prompts_route.PromptApiAdapter,
        "reset_prompt",
        lambda self, worker_type: SimpleNamespace(before="ats-current-x", after="default"),
    )
    client = _new_client()

    reset = client.put("/api/v1/prompts/dev/W1/reset", json={})

    assert reset.status_code == 200
    assert reset.json()["before"] == "ats-current-x"
    assert reset.json()["after"] == "default"
    assert reset.json()["currentPrompt"] == "default"
    assert reset.json()["previousPrompt"] == "ats-current-x"

    db = SessionLocal()
    try:
        snapshot = _load_snapshot(db)
        assert snapshot is not None
        assert snapshot.current_prompt == "default"
        assert snapshot.previous_prompt == "ats-current-x"
    finally:
        db.close()


def test_get_prompt_returns_empty_snapshot_when_ats_call_fails_without_cache(monkeypatch):
    _mock_workers(monkeypatch)

    def _raise_error(self, worker_type):
        raise RuntimeError("ATS unavailable")

    monkeypatch.setattr(prompts_route.PromptApiAdapter, "get_prompt", _raise_error)
    client = _new_client()

    response = client.get("/api/v1/prompts/dev/W1")

    assert response.status_code == 200
    assert response.json()["before"] == ""
    assert response.json()["after"] == ""
    assert response.json()["currentPrompt"] == ""
    assert response.json()["previousPrompt"] == ""

    db = SessionLocal()
    try:
        assert db.query(PromptSnapshot).count() == 0
        assert db.query(PromptAuditLog).count() == 0
    finally:
        db.close()


def test_get_prompt_returns_cached_snapshot_when_ats_call_fails(monkeypatch):
    _mock_workers(monkeypatch)

    db = SessionLocal()
    try:
        db.add(
            PromptSnapshot(
                environment=Environment.DEV,
                worker_type="W1",
                current_prompt="cached-current",
                previous_prompt="cached-previous",
                actor="seed",
            )
        )
        db.commit()
    finally:
        db.close()

    def _raise_error(self, worker_type):
        raise RuntimeError("ATS unavailable")

    monkeypatch.setattr(prompts_route.PromptApiAdapter, "get_prompt", _raise_error)
    client = _new_client()

    response = client.get("/api/v1/prompts/dev/W1")

    assert response.status_code == 200
    assert response.json()["before"] == "cached-previous"
    assert response.json()["after"] == "cached-current"
    assert response.json()["currentPrompt"] == "cached-current"
    assert response.json()["previousPrompt"] == "cached-previous"


def test_get_prompt_returns_200_when_snapshot_persistence_fails(monkeypatch):
    _mock_workers(monkeypatch)
    monkeypatch.setattr(
        prompts_route.PromptApiAdapter,
        "get_prompt",
        lambda self, worker_type: SimpleNamespace(before="legacy-before", after="ats-current"),
    )

    def _raise_db_error(*args, **kwargs):
        raise RuntimeError("db fail")

    monkeypatch.setattr(prompts_route, "_add_audit_log", _raise_db_error)
    client = _new_client()

    response = client.get("/api/v1/prompts/dev/W1")

    assert response.status_code == 200
    assert response.json()["before"] == "legacy-before"
    assert response.json()["after"] == "ats-current"
    assert response.json()["currentPrompt"] == "ats-current"
    assert response.json()["previousPrompt"] == ""

    db = SessionLocal()
    try:
        assert db.query(PromptSnapshot).count() == 0
        assert db.query(PromptAuditLog).count() == 0
    finally:
        db.close()
