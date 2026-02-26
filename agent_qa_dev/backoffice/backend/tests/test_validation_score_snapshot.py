import asyncio
import datetime as dt

from fastapi.testclient import TestClient

from app.adapters.openai_judge_adapter import OpenAIJudgeAdapter
from app.core.db import SessionLocal
from app.jobs.validation_evaluate_job import evaluate_validation_run
from app.main import app
from app.models.validation_score_snapshot import ValidationScoreSnapshot
from app.repositories.validation_runs import ValidationRunRepository


def test_validation_score_snapshot_created_after_evaluation(monkeypatch):
    client = TestClient(app)

    group_resp = client.post("/api/v1/query-groups", json={"groupName": "스냅샷 그룹", "description": "desc"})
    group_id = group_resp.json()["id"]

    query_resp = client.post(
        "/api/v1/queries",
        json={
            "queryText": "질의 score",
            "expectedResult": "결과 score",
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

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    item = repo.list_items(run_id)[0]
    repo.update_item_execution(
        item.id,
        conversation_id="conv-score-1",
        raw_response="ok",
        latency_ms=800,
        error="",
        raw_json='{"assistantMessage":"결과 score"}',
        executed_at=dt.datetime.utcnow(),
    )
    db.commit()
    db.close()

    async def _fake_judge(self, session, api_key, model, prompt, **kwargs):
        return (
            {
                "intent": 4.0,
                "accuracy": 4.0,
                "consistency": None,
                "latencySingle": 5.0,
                "latencyMulti": None,
                "stability": 5.0,
                "reasoning": "ok",
            },
            {},
            "",
        )

    monkeypatch.setattr(OpenAIJudgeAdapter, "judge", _fake_judge)
    asyncio.run(
        evaluate_validation_run(
            run_id,
            openai_key="test-key",
            openai_model="gpt-5.2",
            max_chars=5000,
            max_parallel=1,
        )
    )

    db = SessionLocal()
    snapshots = list(db.query(ValidationScoreSnapshot).filter(ValidationScoreSnapshot.run_id == run_id).all())
    db.close()
    assert snapshots
    overall = [row for row in snapshots if row.query_group_id is None][0]
    assert overall.total_items == 1
    assert overall.logic_pass_items == 1
    assert overall.llm_done_items == 1
