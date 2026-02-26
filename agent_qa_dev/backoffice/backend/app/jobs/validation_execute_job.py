from __future__ import annotations

import asyncio
import datetime as dt
import json
from collections import defaultdict
from typing import Any, Optional

import aiohttp

from app.adapters.agent_client_adapter import AgentClientAdapter
from app.core.db import SessionLocal
from app.core.enums import EvalStatus, RunStatus
from app.repositories.validation_runs import ValidationRunRepository


def _parse_context_json(raw: str) -> Optional[dict]:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except Exception:
        return None
    if isinstance(payload, dict):
        return payload
    return None


async def execute_validation_run(
    run_id: str,
    base_url: str,
    origin: str,
    referer: str,
    bearer: str,
    cms: str,
    mrs: str,
    default_context: Optional[dict],
    run_default_target_assistant: Optional[str],
    max_parallel: int,
    timeout_ms: int,
):
    db = SessionLocal()
    repo = ValidationRunRepository(db)
    repo.set_status(run_id, RunStatus.RUNNING)
    repo.set_eval_status(run_id, EvalStatus.PENDING)
    db.commit()

    try:
        run_items = repo.list_items(run_id, limit=100000)
        if not run_items:
            repo.set_status(run_id, RunStatus.DONE)
            db.commit()
            return

        grouped_items: dict[int, dict[int, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        for item in run_items:
            room_index = int(item.conversation_room_index or 1)
            repeat_index = int(item.repeat_index or 1)
            grouped_items[room_index][repeat_index].append(
                {
                    "id": item.id,
                    "ordinal": int(item.ordinal or 0),
                    "query_text_snapshot": str(item.query_text_snapshot or ""),
                    "context_json_snapshot": str(item.context_json_snapshot or ""),
                    "target_assistant_snapshot": str(item.target_assistant_snapshot or ""),
                }
            )
        for room_map in grouped_items.values():
            for items in room_map.values():
                items.sort(key=lambda x: int(x.get("ordinal") or 0))

        adapter = AgentClientAdapter(
            base_url,
            bearer,
            cms,
            mrs,
            origin,
            referer,
            max_parallel=max_parallel,
        )
        sem = asyncio.Semaphore(max(1, int(max_parallel or 1)))
        db_lock = asyncio.Lock()
        call_timeout = max(1.0, float(timeout_ms or 1000) / 1000.0)
        timeout = aiohttp.ClientTimeout(total=max(call_timeout + 5.0, 5.0))
        connector = aiohttp.TCPConnector(limit=max(5, int(max_parallel or 1) * 4), ssl=False)

        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            async def _execute_item(item: dict[str, Any]) -> None:
                error = ""
                result: dict[str, Any] = {}
                item_context = _parse_context_json(str(item.get("context_json_snapshot") or "")) or default_context
                default_target = (run_default_target_assistant or "").strip()
                item_target_assistant = default_target or str(item.get("target_assistant_snapshot") or "").strip()
                try:
                    async with sem:
                        result = await asyncio.wait_for(
                            adapter.test_orchestrator_sync(
                                session,
                                str(item.get("query_text_snapshot") or ""),
                                conversation_id=None,
                                context=item_context,
                                target_assistant=item_target_assistant,
                            ),
                            timeout=call_timeout,
                        )
                except asyncio.TimeoutError:
                    error = f"timeout({int(call_timeout * 1000)}ms)"
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"

                if not error and result.get("error"):
                    error = str(result.get("error"))

                conversation_id = str(result.get("conversation_id", "") or "")
                response_text = str(result.get("assistant_message", "") or "")
                response_time_sec = result.get("response_time_sec")
                latency_ms = None
                if isinstance(response_time_sec, (int, float)):
                    latency_ms = int(float(response_time_sec) * 1000)

                raw_json = ""
                try:
                    raw_json = json.dumps(
                        {
                            "assistantMessage": result.get("assistant_message"),
                            "dataUIList": result.get("data_ui_list"),
                            "guideList": result.get("guide_list"),
                            "executionProcesses": result.get("execution_processes", []),
                            "worker": result.get("workers", []),
                            "workerMsMap": result.get("worker_ms_map", {}),
                            "conversationId": result.get("conversation_id", ""),
                            "responseTimeSec": result.get("response_time_sec"),
                            "error": error,
                        },
                        ensure_ascii=False,
                        default=str,
                    )
                except Exception:
                    raw_json = ""

                async with db_lock:
                    repo.update_item_execution(
                        str(item.get("id") or ""),
                        conversation_id=conversation_id,
                        raw_response=response_text,
                        latency_ms=latency_ms,
                        error=error,
                        raw_json=raw_json,
                        executed_at=dt.datetime.utcnow(),
                    )
                    db.commit()

            async def _execute_batch(items: list[dict[str, Any]]) -> None:
                await asyncio.gather(*[_execute_item(item) for item in items])

            for room_index in sorted(grouped_items.keys()):
                room_map = grouped_items[room_index]
                for repeat_index in sorted(room_map.keys()):
                    await _execute_batch(room_map[repeat_index])

        repo.set_status(run_id, RunStatus.DONE)
        db.commit()
    except Exception:
        repo.set_status(run_id, RunStatus.FAILED)
        db.commit()
        raise
    finally:
        db.close()
