from fastapi.testclient import TestClient

from app.api.routes import generic_runs as generic_routes
from app.core.db import SessionLocal
from app.core.enums import RunStatus
from app.main import app
from app.models.generic_run_row import GenericRunRow
from app.repositories.generic_runs import GenericRunRepository


def test_acceptance_compare_and_rows_flow():
    client = TestClient(app)

    r1 = client.post('/api/v1/generic-runs', data={'environment': 'dev', 'rowsJson': '[{"질의":"q1"}]'})
    run1 = r1.json()['runId']
    r2 = client.post('/api/v1/generic-runs', data={'environment': 'dev', 'rowsJson': '[{"질의":"q1"}]'})
    run2 = r2.json()['runId']
    r3 = client.post('/api/v1/generic-runs', data={'environment': 'pr', 'rowsJson': '[{"질의":"q1"}]'})
    run3 = r3.json()['runId']

    db = SessionLocal()
    repo = GenericRunRepository(db)
    repo.set_status(run1, RunStatus.DONE)
    repo.set_status(run2, RunStatus.DONE)
    repo.set_status(run3, RunStatus.DONE)
    row2 = db.query(GenericRunRow).filter(GenericRunRow.run_id == run2).first()
    row2.logic_result = 'PASS: ok'
    db.commit()
    db.close()

    rows_resp = client.get(f'/api/v1/generic-runs/{run2}/rows')
    assert rows_resp.status_code == 200
    assert len(rows_resp.json()['rows']) == 1

    compare_default = client.get(f'/api/v1/generic-runs/{run2}/compare')
    assert compare_default.status_code == 200
    assert compare_default.json()['baseRunId'] == run1

    compare_cross_env = client.get(f'/api/v1/generic-runs/{run2}/compare', params={'baseRunId': run3})
    assert compare_cross_env.status_code == 400


def test_acceptance_template_and_direct_query_flow(monkeypatch):
    client = TestClient(app)

    template_resp = client.get('/api/v1/generic-runs/template')
    assert template_resp.status_code == 200

    monkeypatch.setattr(
        generic_routes.runner,
        'run',
        lambda job_id, job_coro_factory: generic_routes.runner.jobs.update({job_id: 'DONE'}),
    )

    direct_resp = client.post(
        '/api/v1/generic-runs/direct',
        json={
            'environment': 'dev',
            'query': 'direct accept',
            'llmCriteria': 'criteria',
            'fieldPath': 'assistantMessage',
            'expectedValue': 'ok',
            'bearer': 'b',
            'cms': 'c',
            'mrs': 'm',
        },
    )
    assert direct_resp.status_code == 200
    run_id = direct_resp.json()['runId']
    run_row_id = direct_resp.json()['rowId']
    assert direct_resp.json()['status'] == 'RUNNING'

    rows_resp = client.get(f'/api/v1/generic-runs/{run_id}/rows')
    assert rows_resp.status_code == 200
    rows = rows_resp.json()['rows']
    assert len(rows) == 1
    assert rows[0]['id'] == run_row_id
    assert rows[0]['query'] == 'direct accept'
