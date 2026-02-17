from fastapi.testclient import TestClient

from app.main import app


def test_create_run_with_rows_json():
    client = TestClient(app)
    resp = client.post(
        '/api/v1/generic-runs',
        data={
            'environment': 'dev',
            'rowsJson': '[{"질의":"테스트"}]',
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'PENDING'
    run_id = data['runId']
    rows_resp = client.get(f'/api/v1/generic-runs/{run_id}/rows')
    assert rows_resp.status_code == 200
    rows = rows_resp.json()['rows']
    assert len(rows) == 1
    assert rows[0]['queryId'] == 'Q-1'
    assert rows[0]['query'] == '테스트'
