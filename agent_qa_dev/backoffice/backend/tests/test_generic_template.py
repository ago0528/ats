from fastapi.testclient import TestClient

from app.main import app


def test_generic_template_download():
    client = TestClient(app)
    resp = client.get('/api/v1/generic-runs/template')
    assert resp.status_code == 200
    assert resp.headers['content-type'].startswith('text/csv')
    content_disposition = resp.headers.get('content-disposition', '')
    assert 'generic_template.csv' in content_disposition
    body = resp.content.decode('utf-8')
    assert '질의' in body
    assert 'LLM 평가기준' in body
    assert '검증 필드' in body
    assert '기대값' in body

