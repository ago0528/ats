import asyncio
import json
import time

from app.adapters.agent_client_adapter import AgentClientAdapter
from app.core.db import SessionLocal
from app.core.enums import Environment, RunStatus
from app.jobs.validation_execute_job import execute_validation_run
from app.main import app as _app  # noqa: F401  # Ensure all ORM models are registered.
from app.repositories.validation_runs import ValidationRunRepository


def _create_run_with_items(
    *,
    room_count: int,
    repeat_count: int,
    queries_per_batch: int,
    agent_parallel_calls: int = 3,
):
    db = SessionLocal()
    repo = ValidationRunRepository(db)
    run = repo.create_run(
        environment=Environment.DEV,
        agent_id="ORCHESTRATOR_ASSISTANT",
        test_model="gpt-5.2",
        eval_model="gpt-5.2",
        repeat_in_conversation=repeat_count,
        conversation_room_count=room_count,
        agent_parallel_calls=agent_parallel_calls,
        timeout_ms=5000,
    )
    run_id = str(run.id)

    items = []
    ordinal = 1
    for room in range(1, room_count + 1):
        for repeat in range(1, repeat_count + 1):
            for query_no in range(1, queries_per_batch + 1):
                items.append(
                    {
                        "ordinal": ordinal,
                        "query_text_snapshot": f"q-{room}-{repeat}-{query_no}",
                        "expected_result_snapshot": "expected",
                        "category_snapshot": "Happy path",
                        "applied_criteria_json": "",
                        "logic_field_path_snapshot": "",
                        "logic_expected_value_snapshot": "",
                        "context_json_snapshot": json.dumps(
                            {"room": room, "repeat": repeat, "queryNo": query_no},
                            ensure_ascii=False,
                        ),
                        "target_assistant_snapshot": "",
                        "conversation_room_index": room,
                        "repeat_index": repeat,
                    }
                )
                ordinal += 1
    repo.add_items(run.id, items)
    db.commit()
    db.close()
    return run_id


def _execute_run(run_id: str, *, max_parallel: int = 3):
    asyncio.run(
        execute_validation_run(
            run_id=run_id,
            base_url="https://example.com",
            origin="https://example.com",
            referer="https://example.com",
            bearer="bearer",
            cms="cms",
            mrs="mrs",
            default_context=None,
            run_default_target_assistant=None,
            max_parallel=max_parallel,
            timeout_ms=5000,
        )
    )


def test_execute_validation_run_keeps_query_parallel_limit(monkeypatch):
    run_id = _create_run_with_items(room_count=1, repeat_count=1, queries_per_batch=6)
    state = {
        "active": 0,
        "max_active": 0,
        "conversation_args": [],
    }

    async def fake_orchestrator_sync(
        self, session, query, conversation_id=None, context=None, target_assistant=None
    ):
        state["conversation_args"].append(conversation_id)
        state["active"] += 1
        state["max_active"] = max(state["max_active"], state["active"])
        await asyncio.sleep(0.02)
        state["active"] -= 1
        return {
            "conversation_id": f"conv-{query}",
            "assistant_message": f"ok-{query}",
            "data_ui_list": [],
            "guide_list": [],
            "execution_processes": [],
            "workers": [],
            "worker_ms_map": {},
            "response_time_sec": 0.02,
            "error": "",
        }

    monkeypatch.setattr(AgentClientAdapter, "test_orchestrator_sync", fake_orchestrator_sync)

    _execute_run(run_id, max_parallel=3)

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    run = repo.get_run(run_id)
    run_items = repo.list_items(run_id, limit=100)
    db.close()

    assert state["max_active"] == 3
    assert all(arg is None for arg in state["conversation_args"])
    assert run is not None
    assert run.status == RunStatus.DONE
    assert all((item.error or "") == "" for item in run_items)
    assert all(item.executed_at is not None for item in run_items)


def test_execute_validation_run_processes_room_repeat_batches_sequentially(monkeypatch):
    queries_per_batch = 3
    run_id = _create_run_with_items(room_count=2, repeat_count=2, queries_per_batch=queries_per_batch)
    batch_started_at: dict[tuple[int, int], float] = {}
    batch_finished_at: dict[tuple[int, int], float] = {}
    batch_done_counts: dict[tuple[int, int], int] = {}

    async def fake_orchestrator_sync(
        self, session, query, conversation_id=None, context=None, target_assistant=None
    ):
        _prefix, room_str, repeat_str, _query_str = str(query).split("-")
        batch_key = (int(room_str), int(repeat_str))
        if batch_key not in batch_started_at:
            batch_started_at[batch_key] = time.monotonic()
        await asyncio.sleep(0.015)
        batch_done_counts[batch_key] = batch_done_counts.get(batch_key, 0) + 1
        if batch_done_counts[batch_key] == queries_per_batch:
            batch_finished_at[batch_key] = time.monotonic()
        return {
            "conversation_id": f"conv-{query}",
            "assistant_message": f"ok-{query}",
            "data_ui_list": [],
            "guide_list": [],
            "execution_processes": [],
            "workers": [],
            "worker_ms_map": {},
            "response_time_sec": 0.01,
            "error": "",
        }

    monkeypatch.setattr(AgentClientAdapter, "test_orchestrator_sync", fake_orchestrator_sync)

    _execute_run(run_id, max_parallel=3)

    expected_order = [(1, 1), (1, 2), (2, 1), (2, 2)]
    for batch_key in expected_order:
        assert batch_key in batch_started_at
        assert batch_key in batch_finished_at

    for prev_key, next_key in zip(expected_order, expected_order[1:]):
        assert batch_finished_at[prev_key] <= batch_started_at[next_key]


def test_execute_validation_run_stores_independent_conversation_ids(monkeypatch):
    run_id = _create_run_with_items(room_count=1, repeat_count=1, queries_per_batch=5)

    async def fake_orchestrator_sync(
        self, session, query, conversation_id=None, context=None, target_assistant=None
    ):
        return {
            "conversation_id": f"conv-{query}",
            "assistant_message": "ok",
            "data_ui_list": [],
            "guide_list": [],
            "execution_processes": [],
            "workers": [],
            "worker_ms_map": {},
            "response_time_sec": 0.01,
            "error": "",
        }

    monkeypatch.setattr(AgentClientAdapter, "test_orchestrator_sync", fake_orchestrator_sync)

    _execute_run(run_id, max_parallel=3)

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    run_items = repo.list_items(run_id, limit=100)
    db.close()

    conversation_ids = [str(item.conversation_id or "") for item in run_items]
    assert all(conversation_ids)
    assert len(set(conversation_ids)) == len(run_items)


def test_execute_validation_run_recovers_from_partial_errors(monkeypatch):
    run_id = _create_run_with_items(room_count=1, repeat_count=1, queries_per_batch=5)
    fail_query = "q-1-1-3"

    async def fake_orchestrator_sync(
        self, session, query, conversation_id=None, context=None, target_assistant=None
    ):
        if query == fail_query:
            raise RuntimeError("forced failure")
        return {
            "conversation_id": f"conv-{query}",
            "assistant_message": f"ok-{query}",
            "data_ui_list": [],
            "guide_list": [],
            "execution_processes": [],
            "workers": [],
            "worker_ms_map": {},
            "response_time_sec": 0.01,
            "error": "",
        }

    monkeypatch.setattr(AgentClientAdapter, "test_orchestrator_sync", fake_orchestrator_sync)

    _execute_run(run_id, max_parallel=3)

    db = SessionLocal()
    repo = ValidationRunRepository(db)
    run = repo.get_run(run_id)
    run_items = repo.list_items(run_id, limit=100)
    db.close()

    assert run is not None
    assert run.status == RunStatus.DONE
    failed_item = next(item for item in run_items if item.query_text_snapshot == fail_query)
    success_items = [item for item in run_items if item.query_text_snapshot != fail_query]
    assert "RuntimeError: forced failure" in (failed_item.error or "")
    assert failed_item.executed_at is not None
    assert all((item.error or "") == "" for item in success_items)
    assert all(item.executed_at is not None for item in success_items)
