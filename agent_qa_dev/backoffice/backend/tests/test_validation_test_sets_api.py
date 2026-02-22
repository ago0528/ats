from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.core.enums import RunStatus
from app.main import app
from app.repositories.validation_queries import ValidationQueryRepository
from app.repositories.validation_query_groups import ValidationQueryGroupRepository
from app.repositories.validation_runs import ValidationRunRepository


def _create_group_and_query(
    client: TestClient,
    *,
    group_name: str,
    query_text: str,
    category: str = "Happy path",
) -> tuple[str, str]:
    group_resp = client.post(
        "/api/v1/query-groups",
        json={"groupName": group_name, "description": "desc"},
    )
    assert group_resp.status_code == 200
    group_id = group_resp.json()["id"]

    query_resp = client.post(
        "/api/v1/queries",
        json={
            "queryText": query_text,
            "expectedResult": "ok",
            "category": category,
            "groupId": group_id,
            "logicFieldPath": "assistantMessage",
            "logicExpectedValue": "ok",
        },
    )
    assert query_resp.status_code == 200
    return group_id, query_resp.json()["id"]


def _bulk_create_queries(*, group_name: str, query_prefix: str, count: int) -> tuple[str, list[str]]:
    db = SessionLocal()
    try:
        group_repo = ValidationQueryGroupRepository(db)
        query_repo = ValidationQueryRepository(db)
        group = group_repo.create(group_name=group_name, description="bulk group")
        rows = [
            {
                "query_text": f"{query_prefix} {index}",
                "expected_result": "",
                "category": "Happy path",
                "group_id": group.id,
                "llm_eval_criteria": "",
                "logic_field_path": "",
                "logic_expected_value": "",
                "context_json": "",
                "target_assistant": "",
            }
            for index in range(count)
        ]
        query_ids = query_repo.bulk_create(rows, created_by="tester")
        db.commit()
        return group.id, query_ids
    finally:
        db.close()


def test_validation_test_set_crud_clone_create_run_and_snapshot():
    client = TestClient(app)

    _group_id, query_id_1 = _create_group_and_query(client, group_name="그룹A", query_text="질의 A")
    _group_id_2, query_id_2 = _create_group_and_query(client, group_name="그룹B", query_text="질의 B")

    create_resp = client.post(
        "/api/v1/validation-test-sets",
        json={
            "name": "테스트 세트 A",
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
            "name": "테스트 세트 A-수정",
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


def test_validation_test_set_create_with_filtered_query_selection():
    client = TestClient(app)
    group_a_id, query_id_1 = _create_group_and_query(client, group_name="필터그룹A", query_text="필터 대상 A", category="Happy path")
    _group_a_id_2, _query_id_2 = _create_group_and_query(client, group_name="필터그룹A-2", query_text="필터 대상 B", category="Edge case")
    _group_b_id, _query_id_3 = _create_group_and_query(client, group_name="필터그룹B", query_text="비대상 C", category="Happy path")

    create_resp = client.post(
        "/api/v1/validation-test-sets",
        json={
            "name": "필터 선택 테스트 세트",
            "querySelection": {
                "mode": "filtered",
                "filter": {
                    "q": "필터 대상",
                    "category": ["Happy path"],
                    "groupId": [group_a_id],
                },
            },
        },
    )
    assert create_resp.status_code == 200
    test_set_id = create_resp.json()["id"]
    assert create_resp.json()["itemCount"] == 1

    detail_resp = client.get(f"/api/v1/validation-test-sets/{test_set_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["queryIds"] == [query_id_1]


def test_validation_test_set_append_queries_deduplicates_and_excludes():
    client = TestClient(app)
    group_id, query_id_1 = _create_group_and_query(client, group_name="추가그룹", query_text="추가 대상 1")
    _group_id_2, query_id_2 = _create_group_and_query(client, group_name="추가그룹-2", query_text="추가 대상 2")
    _group_id_3, query_id_3 = _create_group_and_query(client, group_name="추가그룹-3", query_text="추가 대상 3")

    create_resp = client.post(
        "/api/v1/validation-test-sets",
        json={"name": "추가 테스트 세트", "queryIds": [query_id_1]},
    )
    assert create_resp.status_code == 200
    test_set_id = create_resp.json()["id"]

    append_resp = client.post(
        f"/api/v1/validation-test-sets/{test_set_id}/append-queries",
        json={
            "querySelection": {
                "mode": "ids",
                "queryIds": [query_id_1, query_id_2, query_id_3],
                "excludedQueryIds": [query_id_3],
            },
        },
    )
    assert append_resp.status_code == 200
    assert append_resp.json()["requestedCount"] == 2
    assert append_resp.json()["addedCount"] == 1
    assert append_resp.json()["skippedCount"] == 1
    assert append_resp.json()["itemCount"] == 2

    append_filtered_resp = client.post(
        f"/api/v1/validation-test-sets/{test_set_id}/append-queries",
        json={
            "querySelection": {
                "mode": "filtered",
                "filter": {
                    "q": "추가 대상",
                    "groupId": [group_id],
                },
                "excludedQueryIds": [query_id_1],
            },
        },
    )
    assert append_filtered_resp.status_code == 400

    detail_resp = client.get(f"/api/v1/validation-test-sets/{test_set_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["queryIds"] == [query_id_1, query_id_2]


def test_validation_test_set_filtered_selection_limit():
    client = TestClient(app)
    group_id, _ = _bulk_create_queries(group_name="대량필터그룹", query_prefix="대량 질의", count=5001)

    create_resp = client.post(
        "/api/v1/validation-test-sets",
        json={
            "name": "대량 선택 제한 테스트",
            "querySelection": {
                "mode": "filtered",
                "filter": {
                    "groupId": [group_id],
                },
            },
        },
    )
    assert create_resp.status_code == 400
    assert "Selected queries exceed limit (5000)" in create_resp.json().get("detail", "")
