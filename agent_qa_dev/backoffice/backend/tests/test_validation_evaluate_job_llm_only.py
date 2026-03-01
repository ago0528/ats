import asyncio
import datetime as dt
import json

from fastapi.testclient import TestClient

from app.adapters.openai_judge_adapter import OpenAIJudgeAdapter
from app.core.db import SessionLocal
from app.jobs.validation_evaluate_job import evaluate_validation_run
from app.main import app
from app.repositories.validation_eval_prompt_configs import ValidationEvalPromptConfigRepository
from app.repositories.validation_runs import ValidationRunRepository


def _prepare_run(*, repeat_in_conversation: int = 1) -> tuple[str, list[str]]:
    client = TestClient(app)

    group_resp = client.post("/api/v1/query-groups", json={"groupName": f"그룹-{repeat_in_conversation}", "description": "desc"})
    group_id = group_resp.json()["id"]

    query_resp = client.post(
        "/api/v1/queries",
        json={
            "queryText": "질의 llm only",
            "expectedResult": "결과 llm only",
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
            "repeatInConversation": repeat_in_conversation,
            "conversationRoomCount": 1,
        },
    )
    run_id = run_resp.json()["id"]

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    items = repo.list_items(run_id, limit=100)
    for index, item in enumerate(items):
        repo.update_item_execution(
            item.id,
            conversation_id=f"conv-{index}",
            raw_response="ok",
            latency_ms=1200 + index,
            error="",
            raw_json='{"assistantMessage":"결과"}',
            executed_at=dt.datetime.utcnow(),
        )
    db.commit()
    item_ids = [row.id for row in items]
    db.close()
    return run_id, item_ids


def test_evaluate_job_keeps_llm_scores_without_stability_fallback(monkeypatch):
    run_id, item_ids = _prepare_run(repeat_in_conversation=1)

    async def _fake_judge(self, session, api_key, model, prompt, **kwargs):
        return (
            {
                "intent": 4.0,
                "accuracy": 3.0,
                "consistency": None,
                "latencySingle": 5.0,
                "latencyMulti": None,
                "stability": None,
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
            item_ids=item_ids,
        )
    )

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    llm_map = repo.get_llm_eval_map(item_ids)
    llm = llm_map[item_ids[0]]
    metric_scores = json.loads(llm.metric_scores_json)

    assert metric_scores.get("stability") is None
    assert llm.total_score is None
    assert llm.prompt_version
    db.close()


def test_evaluate_job_persists_openai_usage_and_latency(monkeypatch):
    run_id, item_ids = _prepare_run(repeat_in_conversation=1)

    async def _fake_judge(self, session, api_key, model, prompt, **kwargs):
        await asyncio.sleep(0.01)
        return (
            {
                "intent": 5.0,
                "accuracy": 4.0,
                "consistency": None,
                "latencySingle": 4.0,
                "latencyMulti": None,
                "stability": 5.0,
                "reasoning": "ok",
            },
            {"input_tokens": 123, "output_tokens": 45},
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
            item_ids=item_ids,
        )
    )

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    llm_map = repo.get_llm_eval_map(item_ids)
    llm = llm_map[item_ids[0]]

    assert llm.input_tokens == 123
    assert llm.output_tokens == 45
    assert isinstance(llm.llm_latency_ms, int)
    assert llm.llm_latency_ms >= 0
    db.close()


def test_evaluate_job_does_not_sync_consistency_between_items(monkeypatch):
    run_id, item_ids = _prepare_run(repeat_in_conversation=2)
    db = SessionLocal()
    prompt_repo = ValidationEvalPromptConfigRepository(db)
    prompt_repo.update_scoring_prompt(
        prompt="custom scoring prompt v9",
        version_label="v9.0.0",
        actor="tester",
    )
    db.commit()
    db.close()

    responses = iter(
        [
            {
                "intent": 4.0,
                "accuracy": 4.0,
                "consistency": 1.0,
                "latencySingle": 4.0,
                "latencyMulti": None,
                "stability": 5.0,
                "reasoning": "first",
            },
            {
                "intent": 4.0,
                "accuracy": 4.0,
                "consistency": 5.0,
                "latencySingle": 4.0,
                "latencyMulti": None,
                "stability": 5.0,
                "reasoning": "second",
            },
        ]
    )

    async def _fake_judge(self, session, api_key, model, prompt, **kwargs):
        return (next(responses), {}, "")

    monkeypatch.setattr(OpenAIJudgeAdapter, "judge", _fake_judge)

    asyncio.run(
        evaluate_validation_run(
            run_id,
            openai_key="test-key",
            openai_model="gpt-5.2",
            max_chars=5000,
            max_parallel=1,
            item_ids=item_ids,
        )
    )

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    llm_map = repo.get_llm_eval_map(item_ids)
    values = [json.loads(llm_map[item_id].metric_scores_json).get("consistency") for item_id in item_ids]
    prompt_versions = [str(llm_map[item_id].prompt_version or "") for item_id in item_ids]

    assert values == [1.0, 5.0]
    assert set(prompt_versions) == {"v9.0.0"}
    db.close()
