from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.models.validation_eval_prompt_audit_log import ValidationEvalPromptAuditLog
from app.models.validation_eval_prompt_config import ValidationEvalPromptConfig
from app.repositories.validation_eval_prompt_configs import ValidationEvalPromptConfigRepository


def _new_client():
    return TestClient(app)


def test_get_eval_prompt_bootstraps_default_config():
    client = _new_client()

    response = client.get("/api/v1/prompts/evaluation/scoring")

    assert response.status_code == 200
    body = response.json()
    assert body["promptKey"] == "validation_scoring"
    assert body["currentVersionLabel"] == "validation-scoring-default.v1"
    assert body["currentPrompt"]

    db = SessionLocal()
    try:
        entity = db.query(ValidationEvalPromptConfig).one_or_none()
        assert entity is not None
        assert entity.prompt_key == "validation_scoring"
        logs = db.query(ValidationEvalPromptAuditLog).all()
        assert len(logs) == 1
        assert logs[0].action == "INIT"
    finally:
        db.close()


def test_patch_eval_prompt_updates_current_and_rotates_previous():
    client = _new_client()
    seed = client.get("/api/v1/prompts/evaluation/scoring")
    assert seed.status_code == 200

    patch = client.patch(
        "/api/v1/prompts/evaluation/scoring",
        json={
            "prompt": "new scoring prompt",
            "versionLabel": "v3.0.0",
        },
    )

    assert patch.status_code == 200
    body = patch.json()
    assert body["currentPrompt"] == "new scoring prompt"
    assert body["currentVersionLabel"] == "v3.0.0"
    assert body["previousVersionLabel"] == "validation-scoring-default.v1"

    db = SessionLocal()
    try:
        entity = db.query(ValidationEvalPromptConfig).one_or_none()
        assert entity is not None
        assert entity.current_prompt == "new scoring prompt"
        assert entity.previous_prompt
        logs = db.query(ValidationEvalPromptAuditLog).all()
        assert [log.action for log in logs] == ["INIT", "UPDATE"]
    finally:
        db.close()


def test_patch_eval_prompt_rejects_invalid_version_label():
    client = _new_client()

    response = client.patch(
        "/api/v1/prompts/evaluation/scoring",
        json={
            "prompt": "abc",
            "versionLabel": "-invalid",
        },
    )

    assert response.status_code == 400


def test_revert_previous_requires_previous_prompt():
    client = _new_client()
    seed = client.get("/api/v1/prompts/evaluation/scoring")
    assert seed.status_code == 200

    response = client.post(
        "/api/v1/prompts/evaluation/scoring/revert-previous",
        json={"versionLabel": "v3.0.1"},
    )

    assert response.status_code == 400
    assert "no previous prompt" in response.json()["detail"]


def test_revert_previous_swaps_current_and_previous():
    client = _new_client()
    client.get("/api/v1/prompts/evaluation/scoring")
    client.patch(
        "/api/v1/prompts/evaluation/scoring",
        json={
            "prompt": "prompt-v2",
            "versionLabel": "v2.0.0",
        },
    )

    response = client.post(
        "/api/v1/prompts/evaluation/scoring/revert-previous",
        json={"versionLabel": "v3.0.0"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["currentVersionLabel"] == "v3.0.0"
    assert body["previousVersionLabel"] == "v2.0.0"


def test_reset_default_sets_default_prompt_and_version_label():
    client = _new_client()
    client.get("/api/v1/prompts/evaluation/scoring")
    client.patch(
        "/api/v1/prompts/evaluation/scoring",
        json={
            "prompt": "prompt-custom",
            "versionLabel": "v4.0.0",
        },
    )

    response = client.post(
        "/api/v1/prompts/evaluation/scoring/reset-default",
        json={"versionLabel": "v4.0.1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["currentVersionLabel"] == "v4.0.1"
    assert body["previousVersionLabel"] == "v4.0.0"

    db = SessionLocal()
    try:
        entity = db.query(ValidationEvalPromptConfig).one_or_none()
        assert entity is not None
        assert entity.current_version_label == "v4.0.1"
        expected_default = ValidationEvalPromptConfigRepository.load_default_prompt()
        assert entity.current_prompt == expected_default
    finally:
        db.close()
