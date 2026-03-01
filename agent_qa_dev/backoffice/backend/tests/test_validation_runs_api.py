import datetime as dt

from fastapi.testclient import TestClient

from app.api.routes import validation_runs as validation_runs_route
from app.core.db import SessionLocal
from app.core.enums import Environment, EvalStatus, RunStatus
from app.main import app
from app.repositories.validation_queries import ValidationQueryRepository
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
    item_id = items_resp.json()["items"][0]["id"]

    def fake_runner_run(job_id, job_coro_factory, **kwargs):
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


def test_run_item_inherits_latency_class_from_query_criteria():
    client = TestClient(app)

    group_resp = client.post(
        "/api/v1/query-groups",
        json={"groupName": "검증그룹-latency-snapshot", "description": "desc"},
    )
    group_id = group_resp.json()["id"]

    db = SessionLocal()
    query_repo = ValidationQueryRepository(db)
    query = query_repo.create(
        query_text="질의 latency snapshot",
        expected_result="결과",
        category="Happy path",
        group_id=group_id,
        llm_eval_meta={"meta": {"latencyClass": "MULTI"}},
        created_by="tester",
    )
    db.commit()
    query_id = query.id
    db.close()

    run_resp = client.post(
        "/api/v1/validation-runs",
        json={
            "environment": "dev",
            "queryIds": [query_id],
        },
    )
    assert run_resp.status_code == 200
    run_id = run_resp.json()["id"]

    items_resp = client.get(f"/api/v1/validation-runs/{run_id}/items")
    assert items_resp.status_code == 200
    items = items_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["latencyClass"] == "MULTI"


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


def test_evaluate_route_resets_eval_status_when_runner_schedule_fails(monkeypatch):
    client = TestClient(app)
    monkeypatch.setenv("BACKOFFICE_OPENAI_API_KEY", "test-openai-key")

    group_resp = client.post(
        "/api/v1/query-groups",
        json={"groupName": "검증그룹-스케줄오류", "description": "desc"},
    )
    group_id = group_resp.json()["id"]

    query_resp = client.post(
        "/api/v1/queries",
        json={
            "queryText": "질의 schedule fail",
            "expectedResult": "결과",
            "category": "Happy path",
            "groupId": group_id,
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

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    item = repo.list_items(run_id, limit=1)[0]
    repo.update_item_execution(
        item.id,
        conversation_id="conv-1",
        raw_response="ok",
        latency_ms=120,
        error="",
        raw_json='{"assistantMessage":"ok"}',
    )
    repo.set_status(run_id, RunStatus.DONE)
    db.commit()
    db.close()

    def _raise_on_run(job_id, job_coro_factory, **kwargs):
        raise RuntimeError("schedule failed")

    monkeypatch.setattr(validation_runs_route.runner, "run", _raise_on_run)

    resp = client.post(
        f"/api/v1/validation-runs/{run_id}/evaluate",
        json={"openaiModel": "gpt-5.2"},
    )
    assert resp.status_code == 500
    assert "Failed to schedule evaluation job" in str(resp.json().get("detail", ""))

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    run = repo.get_run(run_id)
    assert run is not None
    assert run.eval_status == EvalStatus.PENDING
    db.close()


def test_list_validation_runs_with_evaluation_status_filter(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(validation_runs_route.runner, "has_active_job", lambda job_key: True)
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


def test_execute_run_with_item_ids_resets_target_items(monkeypatch):
    client = TestClient(app)

    group_resp = client.post(
        "/api/v1/query-groups",
        json={"groupName": "검증그룹-부분실행", "description": "desc"},
    )
    group_id = group_resp.json()["id"]

    query_resp = client.post(
        "/api/v1/queries",
        json={
            "queryText": "질의 부분 실행",
            "expectedResult": "결과",
            "category": "Happy path",
            "groupId": group_id,
        },
    )
    query_id = query_resp.json()["id"]

    run_resp = client.post(
        "/api/v1/validation-runs",
        json={
            "environment": "dev",
            "queryIds": [query_id],
            "repeatInConversation": 2,
            "conversationRoomCount": 1,
        },
    )
    run_id = run_resp.json()["id"]

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    run_items = repo.list_items(run_id, limit=100)
    target_item = run_items[0]
    other_item = run_items[1]
    target_item_id = target_item.id
    other_item_id = other_item.id
    for row in run_items:
        repo.update_item_execution(
            row.id,
            conversation_id=f"conv-{row.id}",
            raw_response="ok",
            latency_ms=120,
            error="",
            raw_json='{"assistantMessage":"ok"}',
        )
        repo.upsert_logic_eval(
            row.id,
            eval_items={"fieldPath": "assistantMessage", "expectedValue": "ok"},
            result="PASS",
            fail_reason="",
        )
        repo.upsert_llm_eval(
            row.id,
            eval_model="gpt-5.2",
            metric_scores={"intent": 5, "accuracy": 5, "consistency": 5, "stability": 5},
            total_score=5.0,
            llm_comment="ok",
            status="DONE",
        )
    repo.set_status(run_id, RunStatus.DONE)
    repo.set_eval_status(run_id, EvalStatus.DONE)
    db.commit()
    db.close()

    def fake_runner_run(job_id, job_coro_factory, **kwargs):
        validation_runs_route.runner.jobs[job_id] = "DONE"

    monkeypatch.setattr(validation_runs_route.runner, "run", fake_runner_run)

    exec_resp = client.post(
        f"/api/v1/validation-runs/{run_id}/execute",
        json={
            "bearer": "b",
            "cms": "c",
            "mrs": "m",
            "itemIds": [target_item_id],
        },
    )
    assert exec_resp.status_code == 200

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    refreshed_target = repo.get_item(target_item_id)
    refreshed_other = repo.get_item(other_item_id)
    assert refreshed_target is not None
    assert refreshed_target.executed_at is None
    assert refreshed_target.raw_response == ""
    assert refreshed_target.error == ""
    assert refreshed_other is not None
    assert refreshed_other.raw_response == "ok"
    assert target_item_id not in repo.get_logic_eval_map([target_item_id])
    assert target_item_id not in repo.get_llm_eval_map([target_item_id])
    refreshed_run = repo.get_run(run_id)
    assert refreshed_run is not None
    assert refreshed_run.eval_status == EvalStatus.PENDING
    db.close()


def test_execute_run_with_item_ids_recovers_stale_running_run(monkeypatch):
    client = TestClient(app)

    group_resp = client.post(
        "/api/v1/query-groups",
        json={"groupName": "검증그룹-실행고착", "description": "desc"},
    )
    group_id = group_resp.json()["id"]

    query_resp = client.post(
        "/api/v1/queries",
        json={
            "queryText": "질의 실행 고착",
            "expectedResult": "결과",
            "category": "Happy path",
            "groupId": group_id,
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

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    run = repo.get_run(run_id)
    assert run is not None
    repo.set_status(run_id, RunStatus.RUNNING)
    run.started_at = dt.datetime.utcnow() - dt.timedelta(minutes=30)
    db.commit()
    target_item_id = repo.list_items(run_id, limit=1)[0].id
    db.close()

    def fake_runner_run(job_id, job_coro_factory, **kwargs):
        validation_runs_route.runner.jobs[job_id] = "DONE"

    monkeypatch.setattr(validation_runs_route.runner, "run", fake_runner_run)

    exec_resp = client.post(
        f"/api/v1/validation-runs/{run_id}/execute",
        json={
            "bearer": "b",
            "cms": "c",
            "mrs": "m",
            "itemIds": [target_item_id],
        },
    )
    assert exec_resp.status_code == 200


def test_get_validation_run_reconciles_stale_running_status():
    client = TestClient(app)

    group_resp = client.post(
        "/api/v1/query-groups",
        json={"groupName": "검증그룹-고착조회", "description": "desc"},
    )
    group_id = group_resp.json()["id"]

    query_resp = client.post(
        "/api/v1/queries",
        json={
            "queryText": "질의 고착 조회",
            "expectedResult": "결과",
            "category": "Happy path",
            "groupId": group_id,
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

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    run = repo.get_run(run_id)
    assert run is not None
    repo.set_status(run_id, RunStatus.RUNNING)
    run.started_at = dt.datetime.utcnow() - dt.timedelta(minutes=30)
    db.commit()
    db.close()

    get_resp = client.get(f"/api/v1/validation-runs/{run_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "FAILED"


def test_cancel_evaluate_run_requires_running_state():
    client = TestClient(app)

    group_resp = client.post(
        "/api/v1/query-groups",
        json={"groupName": "검증그룹-평가중단가드", "description": "desc"},
    )
    group_id = group_resp.json()["id"]

    query_resp = client.post(
        "/api/v1/queries",
        json={
            "queryText": "질의 평가중단 가드",
            "expectedResult": "결과",
            "category": "Happy path",
            "groupId": group_id,
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

    cancel_resp = client.post(f"/api/v1/validation-runs/{run_id}/evaluate/cancel")
    assert cancel_resp.status_code == 409
    assert cancel_resp.json()["detail"] == "Evaluation is not running"


def test_cancel_evaluate_run_requests_cancel_when_active_job(monkeypatch):
    client = TestClient(app)

    group_resp = client.post(
        "/api/v1/query-groups",
        json={"groupName": "검증그룹-평가중단활성", "description": "desc"},
    )
    group_id = group_resp.json()["id"]

    query_resp = client.post(
        "/api/v1/queries",
        json={
            "queryText": "질의 평가중단 활성",
            "expectedResult": "결과",
            "category": "Happy path",
            "groupId": group_id,
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

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    repo.set_status(run_id, RunStatus.DONE)
    repo.set_eval_status(run_id, EvalStatus.RUNNING)
    db.commit()
    db.close()

    monkeypatch.setattr(validation_runs_route.runner, "has_active_job", lambda job_key: True)
    monkeypatch.setattr(validation_runs_route.runner, "cancel_by_key", lambda job_key: True)

    cancel_resp = client.post(f"/api/v1/validation-runs/{run_id}/evaluate/cancel")
    assert cancel_resp.status_code == 200
    payload = cancel_resp.json()
    assert payload["ok"] is True
    assert payload["action"] == "CANCEL_REQUESTED"
    assert payload["evalStatus"] == "RUNNING"
    assert payload["evalCancelRequested"] is True

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    run = repo.get_run(run_id)
    assert run is not None
    assert bool(run.eval_cancel_requested) is True
    assert run.eval_cancel_requested_at is not None
    db.close()


def test_cancel_evaluate_run_recovers_stale_running_state(monkeypatch):
    client = TestClient(app)

    group_resp = client.post(
        "/api/v1/query-groups",
        json={"groupName": "검증그룹-평가중단고착", "description": "desc"},
    )
    group_id = group_resp.json()["id"]

    query_resp = client.post(
        "/api/v1/queries",
        json={
            "queryText": "질의 평가중단 고착",
            "expectedResult": "결과",
            "category": "Happy path",
            "groupId": group_id,
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

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    repo.set_status(run_id, RunStatus.DONE)
    repo.set_eval_status(run_id, EvalStatus.RUNNING)
    db.commit()
    db.close()

    monkeypatch.setattr(validation_runs_route.runner, "has_active_job", lambda job_key: False)

    cancel_resp = client.post(f"/api/v1/validation-runs/{run_id}/evaluate/cancel")
    assert cancel_resp.status_code == 200
    payload = cancel_resp.json()
    assert payload["ok"] is True
    assert payload["action"] == "RECOVERED_STALE"
    assert payload["evalStatus"] == "PENDING"
    assert payload["evalCancelRequested"] is False


def test_get_validation_run_reconciles_stale_running_evaluation(monkeypatch):
    client = TestClient(app)

    group_resp = client.post(
        "/api/v1/query-groups",
        json={"groupName": "검증그룹-평가고착조회", "description": "desc"},
    )
    group_id = group_resp.json()["id"]

    query_resp = client.post(
        "/api/v1/queries",
        json={
            "queryText": "질의 평가 고착 조회",
            "expectedResult": "결과",
            "category": "Happy path",
            "groupId": group_id,
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

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    repo.set_status(run_id, RunStatus.DONE)
    repo.set_eval_status(run_id, EvalStatus.RUNNING)
    db.commit()
    db.close()

    monkeypatch.setattr(validation_runs_route.runner, "has_active_job", lambda job_key: False)

    get_resp = client.get(f"/api/v1/validation-runs/{run_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["evalStatus"] == "PENDING"


def test_evaluate_run_with_item_ids_scope_validation():
    client = TestClient(app)

    group_resp = client.post(
        "/api/v1/query-groups",
        json={"groupName": "검증그룹-부분평가", "description": "desc"},
    )
    group_id = group_resp.json()["id"]

    query_resp = client.post(
        "/api/v1/queries",
        json={
            "queryText": "질의 부분 평가",
            "expectedResult": "결과",
            "category": "Happy path",
            "groupId": group_id,
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

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    repo.set_status(run_id, RunStatus.DONE)
    db.commit()
    target_item = repo.list_items(run_id, limit=1)[0]
    db.close()

    invalid_item_resp = client.post(
        f"/api/v1/validation-runs/{run_id}/evaluate",
        json={"openaiModel": "gpt-5.2", "itemIds": ["not-found-item-id"]},
    )
    assert invalid_item_resp.status_code == 400

    no_result_resp = client.post(
        f"/api/v1/validation-runs/{run_id}/evaluate",
        json={"openaiModel": "gpt-5.2", "itemIds": [target_item.id]},
    )
    assert no_result_resp.status_code == 409

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    repo.update_item_execution(
        target_item.id,
        conversation_id="conv-target",
        raw_response="ok",
        latency_ms=100,
        error="",
        raw_json='{"assistantMessage":"ok"}',
    )
    repo.update_item_snapshots(target_item.id, expected_result_snapshot="")
    db.commit()
    db.close()

    missing_expected_resp = client.post(
        f"/api/v1/validation-runs/{run_id}/evaluate",
        json={"openaiModel": "gpt-5.2", "itemIds": [target_item.id]},
    )
    assert missing_expected_resp.status_code == 409
    detail = missing_expected_resp.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("code") == "expected_result_missing"


def test_update_run_item_latency_class_snapshot():
    client = TestClient(app)

    group_resp = client.post(
        "/api/v1/query-groups",
        json={"groupName": "검증그룹-응답속도타입", "description": "desc"},
    )
    group_id = group_resp.json()["id"]

    query_resp = client.post(
        "/api/v1/queries",
        json={
            "queryText": "질의 속도 타입 수정",
            "expectedResult": "결과",
            "category": "Happy path",
            "groupId": group_id,
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

    items_resp = client.get(f"/api/v1/validation-runs/{run_id}/items")
    assert items_resp.status_code == 200
    item = items_resp.json()["items"][0]
    item_id = item["id"]

    update_single_resp = client.patch(
        f"/api/v1/validation-runs/{run_id}/items/{item_id}",
        json={"latencyClass": "SINGLE"},
    )
    assert update_single_resp.status_code == 200
    assert update_single_resp.json()["latencyClass"] == "SINGLE"

    updated_items_resp = client.get(f"/api/v1/validation-runs/{run_id}/items")
    assert updated_items_resp.status_code == 200
    assert updated_items_resp.json()["items"][0]["latencyClass"] == "SINGLE"

    update_unclassified_resp = client.patch(
        f"/api/v1/validation-runs/{run_id}/items/{item_id}",
        json={"latencyClass": "UNCLASSIFIED"},
    )
    assert update_unclassified_resp.status_code == 200
    assert update_unclassified_resp.json()["latencyClass"] == "UNCLASSIFIED"

    invalid_resp = client.patch(
        f"/api/v1/validation-runs/{run_id}/items/{item_id}",
        json={"latencyClass": "FAST"},
    )
    assert invalid_resp.status_code == 400


def test_validation_run_create_rejects_removed_ad_hoc_logic_fields():
    client = TestClient(app)

    resp = client.post(
        "/api/v1/validation-runs",
        json={
            "environment": "dev",
            "adHocQuery": {
                "queryText": "단일 질의",
                "logicFieldPath": "assistantMessage",
            },
        },
    )
    assert resp.status_code == 422
