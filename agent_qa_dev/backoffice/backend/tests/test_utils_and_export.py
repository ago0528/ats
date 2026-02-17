from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.core.enums import Environment

from app.main import app


def test_parse_curl_api():
    client = TestClient(app)
    payload = {'curlText': "curl -H 'authorization: Bearer x' -H 'cms-access-token: y' -H 'mrs-session: z'"}
    resp = client.post('/api/v1/utils/parse-curl', json=payload)
    assert resp.status_code == 200
    assert resp.json()['authorization'] == 'Bearer x'


def test_curl_status_api():
    client = TestClient(app)
    payload = {'bearer': 'Bearer abc', 'cms': 'cms-token', 'mrs': 'mrs-session'}
    mock_response = MagicMock()
    mock_response.status_code = 200
    with patch("app.api.routes.utils.httpx.put", return_value=mock_response):
        resp = client.post('/api/v1/utils/curl-status', json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body['allValid'] is True
    assert body['checks'][0]['field'] == 'bearer'
    assert body['checks'][0]['valid'] is True
    assert body['checks'][1]['valid'] is True
    assert body['checks'][2]['valid'] is True


def test_curl_status_api_uses_selected_environment():
    client = TestClient(app)
    payload = {'environment': Environment.ST.value, 'bearer': 'Bearer abc', 'cms': 'cms-token', 'mrs': 'mrs-session'}
    mock_response = MagicMock()
    mock_response.status_code = 200
    with patch("app.api.routes.utils.httpx.put", return_value=mock_response) as put_mock:
        resp = client.post('/api/v1/utils/curl-status', json=payload)

    assert resp.status_code == 200
    requested_url = str(put_mock.call_args.args[0])
    assert 'api-llm.ats.kr-st-midasin.com/api/v1/ai/prompt' in requested_url


def test_export_xlsx_headers():
    client = TestClient(app)
    create_resp = client.post(
        '/api/v1/generic-runs',
        data={
            'environment': 'dev',
            'rowsJson': '[{"질의":"다운로드 테스트"}]',
        },
    )
    run_id = create_resp.json()['runId']
    export_resp = client.get(f'/api/v1/generic-runs/{run_id}/export.xlsx')
    assert export_resp.status_code == 200
    assert 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in export_resp.headers['content-type']
    assert '.xlsx' in export_resp.headers.get('content-disposition', '')
