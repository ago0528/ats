from fastapi.testclient import TestClient

from app.main import app


def test_append_single_row_to_run():
    client = TestClient(app)
    create_resp = client.post(
        '/api/v1/generic-runs',
        data={
            'environment': 'dev',
            'rowsJson': '[{"질의":"기존 질의"}]',
        },
    )
    run_id = create_resp.json()['runId']

    row_resp = client.post(
        f'/api/v1/generic-runs/{run_id}/rows',
        json={
            'query': '추가 질의',
            'llmCriteria': '기준',
            'fieldPath': 'assistantMessage',
            'expectedValue': 'ok',
        },
    )
    assert row_resp.status_code == 200
    payload = row_resp.json()
    assert payload['status'] == 'PENDING'
    row_id = payload['rowId']

    rows_resp = client.get(f'/api/v1/generic-runs/{run_id}/rows')
    rows = rows_resp.json()['rows']
    assert len(rows) == 2
    assert rows[1]['id'] == row_id
    assert rows[1]['query'] == '추가 질의'
    assert rows[1]['llmCriteria'] == '기준'

