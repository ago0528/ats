import asyncio
import datetime as dt

from fastapi.testclient import TestClient

from app.api.routes import validation_agents as validation_agents_route
from app.core.db import SessionLocal
from app.main import app
from app.repositories.validation_runs import ValidationRunRepository


def _make_sync_runner(monkeypatch):
    def fake_runner_run(job_id, job_coro_factory):
        validation_agents_route.runner.jobs[job_id] = "RUNNING"
        asyncio.run(job_coro_factory())
        validation_agents_route.runner.jobs[job_id] = "DONE"

    monkeypatch.setattr(validation_agents_route.runner, "run", fake_runner_run)


def _seed_test_set_with_run(client: TestClient) -> tuple[str, str]:
    group_resp = client.post("/api/v1/query-groups", json={"groupName": "에이전트 그룹", "description": "desc"})
    group_id = group_resp.json()["id"]

    query_resp = client.post(
        "/api/v1/queries",
        json={
            "queryText": "에이전트 질의",
            "expectedResult": "에이전트 결과",
            "category": "Happy path",
            "groupId": group_id,
        },
    )
    query_id = query_resp.json()["id"]

    test_set_resp = client.post(
        "/api/v1/validation-test-sets",
        json={"name": "에이전트 테스트세트", "queryIds": [query_id]},
    )
    test_set_id = test_set_resp.json()["id"]

    run_resp = client.post(
        f"/api/v1/validation-test-sets/{test_set_id}/runs",
        json={"environment": "dev"},
    )
    run_id = run_resp.json()["id"]

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    item = repo.list_items(run_id, limit=1)[0]
    repo.update_item_execution(
        item.id,
        conversation_id="conv-agent-1",
        raw_response="",
        latency_ms=1000,
        error="timeout",
        raw_json='{"assistantMessage":"에러"}',
        executed_at=dt.datetime.utcnow(),
    )
    db.commit()
    db.close()

    return test_set_id, run_id


def test_validation_agents_query_generator_and_report(monkeypatch):
    _make_sync_runner(monkeypatch)
    client = TestClient(app)
    test_set_id, run_id = _seed_test_set_with_run(client)

    query_job_resp = client.post(
        "/api/v1/validation-agents/query-generator",
        json={"testSetId": test_set_id, "limit": 3},
    )
    assert query_job_resp.status_code == 200
    query_job_id = query_job_resp.json()["jobId"]
    assert query_job_resp.json()["status"] == "DONE"

    query_job_detail = client.get(f"/api/v1/validation-agents/jobs/{query_job_id}")
    assert query_job_detail.status_code == 200
    assert query_job_detail.json()["status"] == "DONE"
    assert query_job_detail.json()["result"]["testSetId"] == test_set_id

    report_job_resp = client.post(
        "/api/v1/validation-agents/report-writer",
        json={"testSetId": test_set_id, "runId": run_id},
    )
    assert report_job_resp.status_code == 200
    report_job_id = report_job_resp.json()["jobId"]
    assert report_job_resp.json()["status"] == "DONE"

    report_job_detail = client.get(f"/api/v1/validation-agents/jobs/{report_job_id}")
    assert report_job_detail.status_code == 200
    assert report_job_detail.json()["status"] == "DONE"
    assert report_job_detail.json()["result"]["testSetId"] == test_set_id
    assert "summary" in report_job_detail.json()["result"]
