from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.core.enums import RunStatus
from app.main import app
from app.repositories.validation_runs import ValidationRunRepository


def _create_group_and_query(client: TestClient, *, group_name: str, query_text: str) -> tuple[str, str]:
    group_resp = client.post(
        "/api/v1/query-groups",
        json={"groupName": group_name, "description": "desc", "defaultTargetAssistant": "ORCHESTRATOR_WORKER_V3"},
    )
    assert group_resp.status_code == 200
    group_id = group_resp.json()["id"]

    query_resp = client.post(
        "/api/v1/queries",
        json={
            "queryText": query_text,
            "expectedResult": "ok",
            "category": "Happy path",
            "groupId": group_id,
            "logicFieldPath": "assistantMessage",
            "logicExpectedValue": "ok",
        },
    )
    assert query_resp.status_code == 200
    return group_id, query_resp.json()["id"]


def test_validation_test_set_crud_clone_create_run_and_snapshot():
    client = TestClient(app)

    _group_id, query_id_1 = _create_group_and_query(client, group_name="그룹A", query_text="질의 A")
    _group_id_2, query_id_2 = _create_group_and_query(client, group_name="그룹B", query_text="질의 B")

    create_resp = client.post(
        "/api/v1/validation-test-sets",
        json={
            "name": "테스트세트 A",
            "description": "설명",
            "queryIds": [query_id_1],
            "config": {
                "agentId": "ORCHESTRATOR_WORKER_V3",
                "repeatInConversation": 2,
                "conversationRoomCount": 1,
            },
        },
    )
    assert create_resp.status_code == 200
    test_set_id = create_resp.json()["id"]
    assert create_resp.json()["itemCount"] == 1

    list_resp = client.get("/api/v1/validation-test-sets")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    detail_resp = client.get(f"/api/v1/validation-test-sets/{test_set_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["queryIds"] == [query_id_1]
    assert detail_resp.json()["items"][0]["queryText"] == "질의 A"

    run_resp = client.post(
        f"/api/v1/validation-test-sets/{test_set_id}/runs",
        json={
            "environment": "dev",
            "conversationRoomCount": 2,
        },
    )
    assert run_resp.status_code == 200
    run_id = run_resp.json()["id"]
    assert run_resp.json()["testSetId"] == test_set_id
    assert run_resp.json()["totalItems"] == 4

    run_list_filtered = client.get(f"/api/v1/validation-runs?environment=dev&testSetId={test_set_id}")
    assert run_list_filtered.status_code == 200
    assert run_list_filtered.json()["total"] == 1
    assert run_list_filtered.json()["items"][0]["id"] == run_id

    patch_resp = client.patch(
        f"/api/v1/validation-test-sets/{test_set_id}",
        json={
            "name": "테스트세트 A-수정",
            "queryIds": [query_id_2],
            "config": {"repeatInConversation": 1, "conversationRoomCount": 1},
        },
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["itemCount"] == 1

    old_run_items_resp = client.get(f"/api/v1/validation-runs/{run_id}/items")
    assert old_run_items_resp.status_code == 200
    assert old_run_items_resp.json()["items"][0]["queryText"] == "질의 A"

    clone_resp = client.post(f"/api/v1/validation-test-sets/{test_set_id}/clone", json={})
    assert clone_resp.status_code == 200
    cloned_id = clone_resp.json()["id"]
    assert cloned_id != test_set_id

    cloned_detail_resp = client.get(f"/api/v1/validation-test-sets/{cloned_id}")
    assert cloned_detail_resp.status_code == 200
    assert cloned_detail_resp.json()["queryIds"] == [query_id_2]

    delete_resp = client.delete(f"/api/v1/validation-test-sets/{cloned_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["ok"] is True


def test_validation_run_execute_requires_pending_state(monkeypatch):
    client = TestClient(app)
    _group_id, query_id = _create_group_and_query(client, group_name="그룹C", query_text="질의 C")

    run_resp = client.post(
        "/api/v1/validation-runs",
        json={
            "mode": "REGISTERED",
            "environment": "dev",
            "queryIds": [query_id],
        },
    )
    assert run_resp.status_code == 200
    run_id = run_resp.json()["id"]

    def fake_runner_run(job_id, job_coro_factory):
        from app.api.routes import validation_runs as route

        route.runner.jobs[job_id] = "DONE"

    from app.api.routes import validation_runs as validation_runs_route

    monkeypatch.setattr(validation_runs_route.runner, "run", fake_runner_run)

    execute_ok_resp = client.post(
        f"/api/v1/validation-runs/{run_id}/execute",
        json={"bearer": "b", "cms": "c", "mrs": "m"},
    )
    assert execute_ok_resp.status_code == 200

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    repo.set_status(run_id, RunStatus.DONE)
    db.commit()
    db.close()

    execute_blocked_resp = client.post(
        f"/api/v1/validation-runs/{run_id}/execute",
        json={"bearer": "b", "cms": "c", "mrs": "m"},
    )
    assert execute_blocked_resp.status_code == 409
