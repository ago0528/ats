from fastapi.testclient import TestClient

from app.api.routes import validation_runs as validation_runs_route
from app.core.db import SessionLocal
from app.core.enums import Environment, EvalStatus, RunStatus
from app.main import app
from app.repositories.validation_runs import ValidationRunRepository


def test_validation_runs_flow(monkeypatch):
    client = TestClient(app)
    monkeypatch.setenv("BACKOFFICE_OPENAI_API_KEY", "test-openai-key")

    group_resp = client.post(
        "/api/v1/query-groups",
        json={"groupName": "검증그룹", "description": "desc"},
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
    assert items_resp.json()["items"][0]["targetAssistant"] == "ORCHESTRATOR_ASSISTANT"
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

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    run_item = repo.list_items(run_id, limit=1)[0]
    repo.update_item_execution(
        run_item.id,
        conversation_id="conv-1",
        raw_response="ok",
        latency_ms=100,
        error="",
        raw_json='{"assistantMessage":"결과 A"}',
    )
    repo.set_status(run_id, RunStatus.DONE)
    db.commit()
    db.close()

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


def test_validation_run_evaluate_gate(monkeypatch):
    client = TestClient(app)
    monkeypatch.setenv("BACKOFFICE_OPENAI_API_KEY", "test-openai-key")

    group_resp = client.post(
        "/api/v1/query-groups",
        json={"groupName": "검증그룹-게이트", "description": "desc"},
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
            "environment": "dev",
            "queryIds": [query_id],
        },
    )
    run_id = run_resp.json()["id"]

    pending_eval_resp = client.post(
        f"/api/v1/validation-runs/{run_id}/evaluate",
        json={"openaiModel": "gpt-5.2"},
    )
    assert pending_eval_resp.status_code == 409

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    repo.set_status(run_id, RunStatus.DONE)
    db.commit()
    db.close()

    no_result_eval_resp = client.post(
        f"/api/v1/validation-runs/{run_id}/evaluate",
        json={"openaiModel": "gpt-5.2"},
    )
    assert no_result_eval_resp.status_code == 409


def test_list_validation_runs_with_evaluation_status_filter():
    client = TestClient(app)
    db = SessionLocal()
    repo = ValidationRunRepository(db)

    run_pending = repo.create_run(
        environment=Environment.DEV,
        agent_id="ORCHESTRATOR_WORKER_V3",
        test_model="gpt-5.2",
        eval_model="gpt-5.2",
        repeat_in_conversation=1,
        conversation_room_count=1,
        agent_parallel_calls=1,
        timeout_ms=1000,
    )
    run_running = repo.create_run(
        environment=Environment.DEV,
        agent_id="ORCHESTRATOR_WORKER_V3",
        test_model="gpt-5.2",
        eval_model="gpt-5.2",
        repeat_in_conversation=1,
        conversation_room_count=1,
        agent_parallel_calls=1,
        timeout_ms=1000,
    )
    run_completed = repo.create_run(
        environment=Environment.DEV,
        agent_id="ORCHESTRATOR_WORKER_V3",
        test_model="gpt-5.2",
        eval_model="gpt-5.2",
        repeat_in_conversation=1,
        conversation_room_count=1,
        agent_parallel_calls=1,
        timeout_ms=1000,
    )

    repo.set_status(run_running.id, RunStatus.DONE)
    repo.set_eval_status(run_running.id, EvalStatus.RUNNING)
    repo.set_status(run_completed.id, RunStatus.DONE)
    repo.set_eval_status(run_completed.id, EvalStatus.DONE)
    db.commit()

    done_resp = client.get("/api/v1/validation-runs", params={"environment": "dev", "evaluationStatus": "평가완료"})
    assert done_resp.status_code == 200
    done_items = done_resp.json()["items"]
    done_ids = {item["id"] for item in done_items}
    assert run_completed.id in done_ids
    assert run_running.id not in done_ids
    assert run_pending.id not in done_ids

    running_resp = client.get("/api/v1/validation-runs", params={"environment": "dev", "evaluationStatus": "평가중"})
    assert running_resp.status_code == 200
    running_ids = {item["id"] for item in running_resp.json()["items"]}
    assert run_running.id in running_ids
    assert run_completed.id not in running_ids
    assert run_pending.id not in running_ids

    pending_resp = client.get("/api/v1/validation-runs", params={"environment": "dev", "evaluationStatus": "PENDING"})
    assert pending_resp.status_code == 200
    pending_ids = {item["id"] for item in pending_resp.json()["items"]}
    assert run_pending.id in pending_ids
    assert run_running.id not in pending_ids
    assert run_completed.id not in pending_ids

    db.close()
