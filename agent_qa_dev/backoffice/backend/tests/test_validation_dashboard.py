import datetime as dt

from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.repositories.validation_runs import ValidationRunRepository


def test_validation_group_dashboard():
    client = TestClient(app)

    group_resp = client.post("/api/v1/query-groups", json={"groupName": "대시보드 그룹", "description": "desc"})
    group_id = group_resp.json()["id"]

    query_resp = client.post(
        "/api/v1/queries",
        json={
            "queryText": "질의 A",
            "expectedResult": "결과 A",
            "category": "Happy path",
            "groupId": group_id,
            "logicFieldPath": "assistantMessage",
            "logicExpectedValue": "결과",
        },
    )
    query_id = query_resp.json()["id"]

    run_resp = client.post(
        "/api/v1/validation-runs",
        json={"mode": "REGISTERED", "environment": "dev", "queryIds": [query_id]},
    )
    run_id = run_resp.json()["id"]

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    item = repo.list_items(run_id)[0]
    repo.update_item_execution(
        item.id,
        conversation_id="conv-1",
        raw_response="ok",
        latency_ms=1000,
        error="",
        raw_json='{"assistantMessage":"결과 A"}',
        executed_at=dt.datetime.utcnow(),
    )
    repo.upsert_logic_eval(item.id, eval_items={"k": "v"}, result="PASS", fail_reason="")
    repo.upsert_llm_eval(
        item.id,
        eval_model="gpt-5.2",
        metric_scores={"accuracy": 4.0, "completeness": 5.0},
        total_score=4.5,
        llm_comment="ok",
        status="DONE",
    )
    db.commit()
    db.close()

    dashboard_resp = client.get(f"/api/v1/validation-dashboard/groups/{group_id}")
    assert dashboard_resp.status_code == 200
    body = dashboard_resp.json()
    assert body["groupId"] == group_id
    assert body["totalItems"] == 1
    assert body["logicPassRate"] == 100.0


def test_validation_test_set_dashboard():
    client = TestClient(app)

    group_resp = client.post("/api/v1/query-groups", json={"groupName": "대시보드 테스트세트 그룹", "description": "desc"})
    group_id = group_resp.json()["id"]

    query_resp = client.post(
        "/api/v1/queries",
        json={
            "queryText": "질의 TS",
            "expectedResult": "결과 TS",
            "category": "Happy path",
            "groupId": group_id,
            "logicFieldPath": "assistantMessage",
            "logicExpectedValue": "결과",
        },
    )
    query_id = query_resp.json()["id"]

    test_set_resp = client.post(
        "/api/v1/validation-test-sets",
        json={"name": "대시보드 테스트세트", "queryIds": [query_id]},
    )
    test_set_id = test_set_resp.json()["id"]

    run_resp = client.post(
        f"/api/v1/validation-test-sets/{test_set_id}/runs",
        json={"environment": "dev"},
    )
    run_id = run_resp.json()["id"]

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    item = repo.list_items(run_id)[0]
    repo.update_item_execution(
        item.id,
        conversation_id="conv-ts-1",
        raw_response="ok",
        latency_ms=900,
        error="",
        raw_json='{"assistantMessage":"결과 TS"}',
        executed_at=dt.datetime.utcnow(),
    )
    repo.upsert_logic_eval(item.id, eval_items={"k": "v"}, result="PASS", fail_reason="")
    repo.upsert_llm_eval(
        item.id,
        eval_model="gpt-5.2",
        metric_scores={"accuracy": 5.0},
        total_score=5.0,
        llm_comment="ok",
        status="DONE",
    )
    db.commit()
    db.close()

    dashboard_resp = client.get(f"/api/v1/validation-dashboard/test-sets/{test_set_id}")
    assert dashboard_resp.status_code == 200
    body = dashboard_resp.json()
    assert body["testSetId"] == test_set_id
    assert body["runCount"] == 1
    assert body["totalItems"] == 1
    assert body["logicPassRate"] == 100.0
