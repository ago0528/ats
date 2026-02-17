from fastapi.testclient import TestClient

from app.main import app


def test_healthz_ok():
    client = TestClient(app)
    resp = client.get('/healthz')
    assert resp.status_code == 200
    assert resp.json() == {'ok': True}


def test_version_api_exists():
    client = TestClient(app)
    resp = client.get('/api/v1/version')
    assert resp.status_code == 200
    payload = resp.json()
    assert 'version' in payload
    assert isinstance(payload['version'], str)
