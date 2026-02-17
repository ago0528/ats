from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.routes import prompts as prompts_route
from app.core.db import SessionLocal
from app.main import app
from app.models.prompt_audit_log import PromptAuditLog


def test_prompts_api_with_audit(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        prompts_route.PromptApiAdapter,
        'workers',
        staticmethod(lambda: [{'workerType': 'W1', 'description': 'd1'}]),
    )
    monkeypatch.setattr(
        prompts_route.PromptApiAdapter,
        'get_prompt',
        lambda self, worker_type: SimpleNamespace(before='before', after='after'),
    )
    monkeypatch.setattr(
        prompts_route.PromptApiAdapter,
        'update_prompt',
        lambda self, worker_type, prompt: SimpleNamespace(before='old', after=prompt),
    )
    monkeypatch.setattr(
        prompts_route.PromptApiAdapter,
        'reset_prompt',
        lambda self, worker_type: SimpleNamespace(before='old', after='default'),
    )

    workers = client.get('/api/v1/prompts/workers')
    assert workers.status_code == 200
    assert workers.json()['workers'][0]['workerType'] == 'W1'

    get_resp = client.get('/api/v1/prompts/dev/W1')
    assert get_resp.status_code == 200
    assert get_resp.json()['after'] == 'after'

    update_resp = client.put('/api/v1/prompts/dev/W1', json={'prompt': 'new prompt'})
    assert update_resp.status_code == 200
    assert update_resp.json()['after'] == 'new prompt'

    reset_resp = client.put('/api/v1/prompts/dev/W1/reset', json={})
    assert reset_resp.status_code == 200
    assert reset_resp.json()['after'] == 'default'

    db = SessionLocal()
    logs = db.query(PromptAuditLog).all()
    assert len(logs) == 3
    actions = sorted([x.action for x in logs])
    assert actions == ['GET', 'RESET', 'UPDATE']
    db.close()
