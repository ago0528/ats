from fastapi.testclient import TestClient

from app.api.routes import validation_runs as validation_runs_route
from app.main import app


def test_validation_runs_flow(monkeypatch):
    client = TestClient(app)
    monkeypatch.setenv("BACKOFFICE_OPENAI_API_KEY", "test-openai-key")

    group_resp = client.post(
        "/api/v1/query-groups",
        json={"groupName": "검증그룹", "description": "desc", "defaultTargetAssistant": "ORCHESTRATOR_WORKER_V3"},
    )
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
        json={
            "mode": "REGISTERED",
            "environment": "dev",
            "queryIds": [query_id],
            "repeatInConversation": 2,
            "conversationRoomCount": 2,
        },
    )
    assert run_resp.status_code == 200
    run_id = run_resp.json()["id"]
    assert run_resp.json()["totalItems"] == 4

    items_resp = client.get(f"/api/v1/validation-runs/{run_id}/items")
    assert items_resp.status_code == 200
    assert items_resp.json()["items"][0]["targetAssistant"] == "ORCHESTRATOR_WORKER_V3"
    item_id = items_resp.json()["items"][0]["id"]

    def fake_runner_run(job_id, job_coro_factory):
        validation_runs_route.runner.jobs[job_id] = "DONE"

    monkeypatch.setattr(validation_runs_route.runner, "run", fake_runner_run)

    exec_resp = client.post(
        f"/api/v1/validation-runs/{run_id}/execute",
        json={"bearer": "b", "cms": "c", "mrs": "m"},
    )
    assert exec_resp.status_code == 200
    assert exec_resp.json()["status"] == "DONE"

    eval_resp = client.post(
        f"/api/v1/validation-runs/{run_id}/evaluate",
        json={"openaiModel": "gpt-5.2"},
    )
    assert eval_resp.status_code == 200
    assert eval_resp.json()["status"] == "DONE"

    rerun_resp = client.post(f"/api/v1/validation-runs/{run_id}/rerun")
    assert rerun_resp.status_code == 200
    assert rerun_resp.json()["baseRunId"] == run_id

    save_resp = client.post(
        f"/api/v1/validation-runs/{run_id}/items/{item_id}/save-query",
        json={"groupId": group_id, "category": "Happy path"},
    )
    assert save_resp.status_code == 200
    assert save_resp.json()["queryId"]

    compare_resp = client.get(f"/api/v1/validation-runs/{run_id}/compare")
    assert compare_resp.status_code == 200
    assert "changedRows" in compare_resp.json()

    export_resp = client.get(f"/api/v1/validation-runs/{run_id}/export.xlsx")
    assert export_resp.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in export_resp.headers["content-type"]
    assert ".xlsx" in export_resp.headers.get("content-disposition", "")

    missing_export_resp = client.get("/api/v1/validation-runs/not-found/export.xlsx")
    assert missing_export_resp.status_code == 404
