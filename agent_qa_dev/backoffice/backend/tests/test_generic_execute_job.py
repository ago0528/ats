import json

from fastapi.testclient import TestClient

from app.api.routes import generic_runs as generic_routes
from app.core.db import SessionLocal
from app.main import app
from app.repositories.generic_runs import GenericRunRepository


def test_execute_endpoint_enqueues_job_without_persisting_secrets(monkeypatch):
    client = TestClient(app)

    create_resp = client.post(
        '/api/v1/generic-runs',
        data={
            'environment': 'dev',
            'rowsJson': '[{"질의":"실행"}]',
        },
    )
    run_id = create_resp.json()['runId']

    def fake_run(job_id, job_coro_factory):
        generic_routes.runner.jobs[job_id] = 'DONE'

    monkeypatch.setattr(generic_routes.runner, 'run', fake_run)

    exec_resp = client.post(
        f'/api/v1/generic-runs/{run_id}/execute',
        json={
            'bearer': 'secret-bearer',
            'cms': 'secret-cms',
            'mrs': 'secret-mrs',
        },
    )
    assert exec_resp.status_code == 200
    assert exec_resp.json()['status'] == 'DONE'

    db = SessionLocal()
    repo = GenericRunRepository(db)
    run = repo.get_run(run_id)
    options = json.loads(run.options_json)
    dumped = json.dumps(options)
    assert 'secret-bearer' not in dumped
    assert 'secret-cms' not in dumped
    assert 'secret-mrs' not in dumped
    db.close()
