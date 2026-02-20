from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import aiohttp


class ApplicantAgentClient:
    def __init__(
        self,
        base_url: str,
        bearer_token: str,
        cms_token: str,
        mrs_session: str,
        origin: str,
        referer: str,
        max_parallel: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token.strip()
        self.cms_token = cms_token.strip()
        self.mrs_session = mrs_session.strip()
        self.origin = origin.strip()
        self.referer = referer.strip()
        self.semaphore = asyncio.Semaphore(max_parallel)

    def headers(self) -> Dict[str, str]:
        return {
            "authorization": f"Bearer {self.bearer_token}",
            "cms-access-token": self.cms_token,
            "mrs-session": self.mrs_session,
            "origin": self.origin,
            "referer": self.referer,
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

    async def test_orchestrator_sync(
        self,
        session: aiohttp.ClientSession,
        message: str,
        conversation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        target_assistant: Optional[str] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/ai/prompt/orchestrator/test"
        payload: Dict[str, Any] = {
            "conversationId": conversation_id or "",
            "userMessage": message,
            "context": context or {},
        }
        if target_assistant:
            payload["targetAssistant"] = target_assistant

        try:
            timeout = aiohttp.ClientTimeout(total=120)
            async with session.post(url, headers=self.headers(), json=payload, timeout=timeout) as resp:
                if resp.status != 200:
                    return {
                        "conversation_id": "",
                        "assistant_message": "",
                        "data_ui_list": [],
                        "guide_list": [],
                        "execution_processes": [],
                        "workers": [],
                        "worker_ms_map": {},
                        "response_time_sec": None,
                        "error": f"HTTP {resp.status}: {(await resp.text())[:200]}",
                    }

                data = await resp.json()
                workers = data.get("worker", []) or []
                conversation_id_out = str(data.get("conversationId", "") or "")

                assistant_message = ""
                data_ui_list: list[Dict[str, Any]] = []
                guide_list: list[Dict[str, Any]] = []
                execution_processes: list[Dict[str, Any]] = []
                worker_ms_map: Dict[str, float] = {}
                total_ms = 0.0
                worker_type_count: Dict[str, int] = {}

                for worker in workers:
                    worker_type = str((worker or {}).get("type", "") or "")
                    output = (worker or {}).get("output", {}) or {}
                    ms_val = (worker or {}).get("ms", 0)
                    try:
                        ms_float = float(ms_val)
                    except Exception:
                        ms_float = 0.0

                    total_ms += ms_float
                    seq = worker_type_count.get(worker_type, 0)
                    worker_type_count[worker_type] = seq + 1
                    worker_ms_map[f"{worker_type}#{seq}"] = ms_float

                    summary = worker_type
                    sub_worker = output.get("subWorker") if isinstance(output, dict) else None
                    if sub_worker:
                        summary = f"{worker_type} -> {sub_worker}"
                    execution_processes.append(
                        {
                            "messageSummary": summary,
                            "workerType": worker_type,
                            "ms": ms_float,
                            "index": len(execution_processes),
                        }
                    )

                for worker in reversed(workers):
                    output = (worker or {}).get("output", {}) or {}
                    if not isinstance(output, dict):
                        continue
                    msg = output.get("assistantMessage")
                    if msg:
                        assistant_message = str(msg)
                        data_ui_list = output.get("dataUIList", []) or []
                        guide_list = output.get("guideList", []) or []
                        break

                return {
                    "conversation_id": conversation_id_out,
                    "assistant_message": assistant_message,
                    "data_ui_list": data_ui_list,
                    "guide_list": guide_list,
                    "execution_processes": execution_processes,
                    "workers": workers,
                    "worker_ms_map": worker_ms_map,
                    "response_time_sec": round(total_ms / 1000.0, 4),
                    "error": "",
                }
        except asyncio.TimeoutError:
            return {
                "conversation_id": "",
                "assistant_message": "",
                "data_ui_list": [],
                "guide_list": [],
                "execution_processes": [],
                "workers": [],
                "worker_ms_map": {},
                "response_time_sec": None,
                "error": "timeout(120s)",
            }
        except Exception as exc:
            return {
                "conversation_id": "",
                "assistant_message": "",
                "data_ui_list": [],
                "guide_list": [],
                "execution_processes": [],
                "workers": [],
                "worker_ms_map": {},
                "response_time_sec": None,
                "error": f"{type(exc).__name__}: {str(exc)[:120]}",
            }

