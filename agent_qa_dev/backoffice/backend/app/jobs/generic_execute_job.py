from __future__ import annotations

import asyncio
import json
from typing import Optional

import aiohttp

from app.adapters.agent_client_adapter import AgentClientAdapter
from app.core.db import SessionLocal
from app.core.enums import RunStatus
from app.models.generic_run_row import GenericRunRow
from app.repositories.generic_runs import GenericRunRepository


async def execute_generic_run(
    run_id: str,
    base_url: str,
    origin: str,
    referer: str,
    bearer: str,
    cms: str,
    mrs: str,
    context: Optional[dict],
    target_assistant: Optional[str],
    max_parallel: int,
):
    db = SessionLocal()
    repo = GenericRunRepository(db)
    repo.set_status(run_id, RunStatus.RUNNING)
    db.commit()

    try:
        adapter = AgentClientAdapter(
            base_url,
            bearer,
            cms,
            mrs,
            origin,
            referer,
            max_parallel=max_parallel,
        )
        rows = list(
            db.query(GenericRunRow)
            .filter(GenericRunRow.run_id == run_id)
            .order_by(GenericRunRow.ordinal)
            .all()
        )
        timeout = aiohttp.ClientTimeout(total=120)
        connector = aiohttp.TCPConnector(limit=50, ssl=False)

        sem = asyncio.Semaphore(max(1, max_parallel))

        async def _execute_one(row: GenericRunRow, session: aiohttp.ClientSession) -> tuple[GenericRunRow, dict]:
            async with sem:
                result = await adapter.test_orchestrator_sync(
                    session,
                    row.query,
                    context=context,
                    target_assistant=target_assistant,
                )
                payload = {
                    "row_id": row.id,
                    "response_text": "",
                    "response_time_sec": None,
                    "execution_process": "",
                    "error": "",
                    "raw_json": "",
                }

                try:
                    if result.get("error"):
                        payload["error"] = str(result.get("error"))
                    else:
                        payload["response_text"] = str(result.get("assistant_message", ""))
                        rt = result.get("response_time_sec")
                        payload["response_time_sec"] = float(rt) if rt is not None else None
                        execs = result.get("execution_processes", [])
                        payload["execution_process"] = " ".join(
                            f"[{x.get('messageSummary', '')} ({float(x.get('ms', 0)):.1f}ms)]"
                            for x in execs
                            if x.get("messageSummary")
                        )
                        payload["raw_json"] = json.dumps(
                            {
                                "assistantMessage": result.get("assistant_message"),
                                "dataUIList": result.get("data_ui_list"),
                                "guideList": result.get("guide_list"),
                                "execution_processes": result.get("execution_processes", []),
                                "worker": result.get("workers", []),
                                "workerMsMap": result.get("worker_ms_map", {}),
                                "conversation_id": result.get("conversation_id"),
                                "response_time_sec": result.get("response_time_sec"),
                                "error": result.get("error", ""),
                            },
                            ensure_ascii=False,
                            default=str,
                        )
                except Exception as e:
                    payload["error"] = f"parsing_error: {e}"

                return row, payload

        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            tasks = [asyncio.create_task(_execute_one(row, session)) for row in rows]
            completed = [await t for t in asyncio.as_completed(tasks)]

        for row, payload in completed:
            row.response_text = payload["response_text"]
            row.response_time_sec = payload["response_time_sec"]
            row.execution_process = payload["execution_process"]
            row.error = payload["error"]
            row.raw_json = payload["raw_json"]

        db.commit()
        repo.set_status(run_id, RunStatus.DONE)
        db.commit()
    except Exception:
        repo.set_status(run_id, RunStatus.FAILED)
        db.commit()
        raise
    finally:
        db.close()
