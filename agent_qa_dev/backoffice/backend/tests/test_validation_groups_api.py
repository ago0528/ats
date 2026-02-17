from fastapi.testclient import TestClient

from app.main import app


def test_validation_query_groups_crud():
    client = TestClient(app)

    create_resp = client.post(
        "/api/v1/query-groups",
        json={
            "groupName": "이동 에이전트",
            "description": "이동 도메인",
            "defaultTargetAssistant": "ORCHESTRATOR_WORKER_V3",
            "llmEvalCriteriaDefault": {"version": 1},
        },
    )
    assert create_resp.status_code == 200
    assert create_resp.json()["defaultTargetAssistant"] == "ORCHESTRATOR_WORKER_V3"
    group_id = create_resp.json()["id"]

    list_resp = client.get("/api/v1/query-groups")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1
    assert list_resp.json()["items"][0]["defaultTargetAssistant"] == "ORCHESTRATOR_WORKER_V3"

    update_resp = client.patch(
        f"/api/v1/query-groups/{group_id}",
        json={"description": "설명 수정", "defaultTargetAssistant": "PLAN_ASSISTANT"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["description"] == "설명 수정"
    assert update_resp.json()["defaultTargetAssistant"] == "PLAN_ASSISTANT"

    delete_resp = client.delete(f"/api/v1/query-groups/{group_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["ok"] is True
