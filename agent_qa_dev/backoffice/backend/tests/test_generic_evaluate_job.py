from fastapi.testclient import TestClient

from app.api.routes import generic_runs as generic_routes
from app.main import app


def test_evaluate_endpoint_enqueues_job(monkeypatch):
    client = TestClient(app)

    create_resp = client.post(
        '/api/v1/generic-runs',
        data={
            'environment': 'dev',
            'rowsJson': '[{"질의":"평가", "LLM 평가기준":"정확도 확인"}]',
        },
    )
    run_id = create_resp.json()['runId']

    def fake_run(job_id, job_coro_factory):
        generic_routes.runner.jobs[job_id] = 'DONE'

    monkeypatch.setattr(generic_routes.runner, 'run', fake_run)

    eval_resp = client.post(
        f'/api/v1/generic-runs/{run_id}/evaluate',
        json={
            'openaiKey': 'k',
            'openaiModel': 'gpt-5.2',
        },
    )
    assert eval_resp.status_code == 200
    assert eval_resp.json()['status'] == 'DONE'
