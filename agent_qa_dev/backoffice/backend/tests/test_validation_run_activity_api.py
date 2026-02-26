from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.core.enums import Environment, EvalStatus, RunStatus
from app.main import app
from app.repositories.validation_runs import ValidationRunRepository


def _create_run(
    repo: ValidationRunRepository,
    *,
    environment: Environment,
    name: str,
):
    return repo.create_run(
        environment=environment,
        name=name,
        agent_id="ORCHESTRATOR_ASSISTANT",
        test_model="gpt-5.2",
        eval_model="gpt-5.2",
        repeat_in_conversation=1,
        conversation_room_count=1,
        agent_parallel_calls=1,
        timeout_ms=1000,
    )


def test_validation_run_activity_flow():
    client = TestClient(app)

    db = SessionLocal()
    repo = ValidationRunRepository(db)

    running_run = _create_run(repo, environment=Environment.DEV, name="실행중 Run")
    repo.set_status(running_run.id, RunStatus.RUNNING)

    evaluating_run = _create_run(repo, environment=Environment.DEV, name="평가중 Run")
    repo.set_status(evaluating_run.id, RunStatus.DONE)
    repo.set_eval_status(evaluating_run.id, EvalStatus.RUNNING)

    done_run = _create_run(repo, environment=Environment.DEV, name="완료 Run")
    repo.set_status(done_run.id, RunStatus.DONE)
    repo.set_eval_status(done_run.id, EvalStatus.DONE)

    other_env_run = _create_run(repo, environment=Environment.ST2, name="타 환경 Run")
    repo.set_status(other_env_run.id, RunStatus.RUNNING)

    db.commit()
    db.close()

    initial_resp = client.get(
        "/api/v1/validation-run-activity",
        params={"environment": "dev", "actorKey": "actor-1"},
    )
    assert initial_resp.status_code == 200
    initial_data = initial_resp.json()
    initial_ids = {item["runId"] for item in initial_data["items"]}
    assert running_run.id in initial_ids
    assert evaluating_run.id in initial_ids
    assert done_run.id not in initial_ids
    assert other_env_run.id not in initial_ids
    assert initial_data["unreadCount"] == 2

    read_one_resp = client.post(
        "/api/v1/validation-run-activity/read",
        json={
            "environment": "dev",
            "actorKey": "actor-1",
            "runIds": [running_run.id],
        },
    )
    assert read_one_resp.status_code == 200
    assert read_one_resp.json()["updatedCount"] == 1

    after_single_read_resp = client.get(
        "/api/v1/validation-run-activity",
        params={"environment": "dev", "actorKey": "actor-1"},
    )
    assert after_single_read_resp.status_code == 200
    after_single_read_data = after_single_read_resp.json()
    by_run_id = {item["runId"]: item for item in after_single_read_data["items"]}
    assert by_run_id[running_run.id]["isRead"] is True
    assert by_run_id[evaluating_run.id]["isRead"] is False
    assert after_single_read_data["unreadCount"] == 1

    read_all_resp = client.post(
        "/api/v1/validation-run-activity/read",
        json={
            "environment": "dev",
            "actorKey": "actor-1",
            "markAll": True,
        },
    )
    assert read_all_resp.status_code == 200
    assert read_all_resp.json()["updatedCount"] == 2

    final_resp = client.get(
        "/api/v1/validation-run-activity",
        params={"environment": "dev", "actorKey": "actor-1"},
    )
    assert final_resp.status_code == 200
    final_data = final_resp.json()
    assert final_data["unreadCount"] == 0
    assert all(item["isRead"] is True for item in final_data["items"])


def test_validation_run_activity_actor_key_and_run_ids_validation():
    client = TestClient(app)

    missing_actor_resp = client.get(
        "/api/v1/validation-run-activity",
        params={"environment": "dev"},
    )
    assert missing_actor_resp.status_code == 400

    missing_actor_read_resp = client.post(
        "/api/v1/validation-run-activity/read",
        json={"environment": "dev", "markAll": True},
    )
    assert missing_actor_read_resp.status_code == 400

    missing_run_ids_resp = client.post(
        "/api/v1/validation-run-activity/read",
        json={"environment": "dev", "actorKey": "actor-1"},
    )
    assert missing_run_ids_resp.status_code == 400
