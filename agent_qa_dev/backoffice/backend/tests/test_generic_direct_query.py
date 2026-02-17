from fastapi.testclient import TestClient

from app.api.routes import generic_runs as generic_routes
from app.core.db import SessionLocal
from app.repositories.generic_runs import GenericRunRepository
from app.main import app


def test_direct_run_creates_row_and_enqueues_execute(monkeypatch):
    client = TestClient(app)

    captured = {}
    def fake_runner_run(job_id, job_coro_factory):
        captured["job_id"] = job_id
        generic_routes.runner.jobs[job_id] = "RUNNING"

    monkeypatch.setattr(generic_routes.runner, 'run', fake_runner_run)

    resp = client.post(
        '/api/v1/generic-runs/direct',
        json={
            'environment': 'dev',
            'query': '테스트 질의',
            'llmCriteria': '정확도 확인',
            'fieldPath': 'assistantMessage',
            'expectedValue': 'ok',
            'contextJson': '{"foo": "bar"}',
            'targetAssistant': 'agent-01',
            'maxParallel': 2,
            'maxChars': 15000,
            'openaiModel': 'gpt-5.2',
            'bearer': 'bearer-token',
            'cms': 'cms-token',
            'mrs': 'mrs-token',
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'RUNNING'
    run_id = data['runId']
    row_id = data['rowId']
    assert data['executeJobId'] == captured['job_id']

    db = SessionLocal()
    repo = GenericRunRepository(db)
    run = repo.get_run(run_id)
    assert run is not None
    assert 'bearer-token' not in run.options_json
    assert 'cms-token' not in run.options_json
    assert 'mrs-token' not in run.options_json

    rows = repo.list_rows(run_id)
    assert len(rows) == 1
    row = rows[0]
    assert row.id == row_id
    assert row.query == '테스트 질의'
    assert row.llm_criteria == '정확도 확인'
    assert row.field_path == 'assistantMessage'
    assert row.expected_value == 'ok'
    db.close()
