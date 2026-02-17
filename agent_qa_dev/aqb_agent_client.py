from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

import aiohttp
@dataclass
class AgentResponse:
    conversation_id: str
    connect_time: Optional[datetime]
    chat_time: Optional[datetime]
    response_time_sec: Optional[float]
    assistant_message: str
    data_ui_list: List[Dict[str, Any]]
    guide_list: List[Dict[str, Any]]
    raw_event: Optional[Dict[str, Any]]
    error: str = ""

    @property
    def button_url(self) -> str:
        for ui in self.data_ui_list or []:
            ui_value = (ui or {}).get("uiValue", {}) or {}
            if "buttonUrl" in ui_value:
                return str(ui_value["buttonUrl"])
        return ""

    @property
    def assistant_payload(self) -> Dict[str, Any]:
        """
        평가/로그용으로 'assistantMessage', 'dataUIList', 'guideList' 중심으로 축약한 payload.
        """
        return {
            "assistantMessage": self.assistant_message,
            "dataUIList": self.data_ui_list,
            "guideList": self.guide_list,
        }


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

    def headers(self, for_sse: bool = False) -> Dict[str, str]:
        h = {
            "authorization": f"Bearer {self.bearer_token}",
            "cms-access-token": self.cms_token,
            "mrs-session": self.mrs_session,
            "origin": self.origin,
            "referer": self.referer,
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        if for_sse:
            h["accept"] = "text/event-stream"
        else:
            h["accept"] = "application/json, text/plain, */*"
            h["content-type"] = "application/json"
        return h

    async def send_query(
        self, session: aiohttp.ClientSession, message: str, conversation_id: Optional[str],
        context: Optional[Dict[str, Any]] = None,
        target_assistant: Optional[str] = None
    ) -> Tuple[Optional[str], str]:
        url = f"{self.base_url}/api/v2/ai/orchestrator/query"
        payload = {"conversationId": conversation_id, "userMessage": message}
        if context:
            payload["context"] = context
        if target_assistant:
            payload["targetAssistant"] = target_assistant

        try:
            async with session.post(url, headers=self.headers(), json=payload, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("conversationId"), ""
                return None, f"HTTP {resp.status}: {(await resp.text())[:200]}"
        except asyncio.TimeoutError:
            return None, "timeout(30s)"
        except Exception as e:
            return None, f"{type(e).__name__}: {str(e)[:120]}"

    async def test_orchestrator_sync(
        self,
        session: aiohttp.ClientSession,
        message: str,
        conversation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        target_assistant: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        동기식 테스트 API 호출:
        POST /api/v1/ai/prompt/orchestrator/test

        반환값:
        {
          "conversation_id": str,
          "assistant_message": str,
          "data_ui_list": list,
          "guide_list": list,
          "execution_processes": list[{"messageSummary": str, "workerType": str, "ms": float}],
          "workers": list,
          "worker_ms_map": dict[str, float],  # ex) {"ORCHESTRATOR_WORKER_V3#0": 1446.7}
          "response_time_sec": float,
          "error": str
        }
        """
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

                # 체인 마지막에서 assistantMessage/dataUIList/guideList를 우선 탐색
                assistant_message = ""
                data_ui_list: List[Dict[str, Any]] = []
                guide_list: List[Dict[str, Any]] = []

                execution_processes: List[Dict[str, Any]] = []
                worker_ms_map: Dict[str, float] = {}
                total_ms = 0.0
                worker_type_count: Dict[str, int] = {}

                for w in workers:
                    worker_type = str((w or {}).get("type", "") or "")
                    output = (w or {}).get("output", {}) or {}
                    ms_val = (w or {}).get("ms", 0)
                    try:
                        ms_float = float(ms_val)
                    except Exception:
                        ms_float = 0.0

                    total_ms += ms_float

                    seq = worker_type_count.get(worker_type, 0)
                    worker_type_count[worker_type] = seq + 1
                    worker_key = f"{worker_type}#{seq}"
                    worker_ms_map[worker_key] = ms_float

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

                for w in reversed(workers):
                    output = (w or {}).get("output", {}) or {}
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
        except Exception as e:
            return {
                "conversation_id": "",
                "assistant_message": "",
                "data_ui_list": [],
                "guide_list": [],
                "execution_processes": [],
                "workers": [],
                "worker_ms_map": {},
                "response_time_sec": None,
                "error": f"{type(e).__name__}: {str(e)[:120]}",
            }

    async def subscribe_sse(self, session: aiohttp.ClientSession, conversation_id: str) -> AgentResponse:
        url = f"{self.base_url}/api/v1/ai/orchestrator/chat-room/sse/subscribe"
        params = {"conversationId": conversation_id}

        connect_time: Optional[datetime] = None
        chat_time: Optional[datetime] = None

        buffer = ""
        current_event = None
        last_heartbeat = datetime.now()

        assistant_message = ""
        data_ui_list: List[Dict[str, Any]] = []
        guide_list: List[Dict[str, Any]] = []
        raw_event: Optional[Dict[str, Any]] = None

        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with session.get(url, headers=self.headers(for_sse=True), params=params, timeout=timeout) as resp:
                async for chunk in resp.content.iter_any():
                    buffer += chunk.decode("utf-8", errors="ignore")

                    # heartbeat timeout (30s)
                    if (datetime.now() - last_heartbeat).total_seconds() > 30:
                        return AgentResponse(
                            conversation_id=conversation_id,
                            connect_time=connect_time,
                            chat_time=chat_time,
                            response_time_sec=None,
                            assistant_message=assistant_message,
                            data_ui_list=data_ui_list,
                            guide_list=guide_list,
                            raw_event=raw_event,
                            error="heartbeat timeout(30s)",
                        )

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()

                        if line.startswith("event:"):
                            current_event = line.replace("event:", "").strip()
                            if current_event == "CONNECT":
                                connect_time = datetime.now()
                            elif current_event == "HEARTBEAT":
                                last_heartbeat = datetime.now()

                        elif line.startswith("data:"):
                            data_str = line.replace("data:", "", 1).strip()
                            if current_event != "CHAT":
                                continue
                            if not data_str.startswith("{"):
                                continue
                            try:
                                data = json.loads(data_str)
                            except Exception:
                                continue

                            if data.get("messageType") == "ASSISTANT":
                                chat_time = datetime.now()
                                raw_event = data
                                assistant = data.get("assistant", {}) or {}
                                assistant_message = assistant.get("assistantMessage", "") or ""
                                data_ui_list = assistant.get("dataUIList", []) or []
                                guide_list = assistant.get("guideList", []) or []

                                rt = None
                                if connect_time and chat_time:
                                    rt = (chat_time - connect_time).total_seconds()
                                return AgentResponse(
                                    conversation_id=conversation_id,
                                    connect_time=connect_time,
                                    chat_time=chat_time,
                                    response_time_sec=rt,
                                    assistant_message=assistant_message,
                                    data_ui_list=data_ui_list,
                                    guide_list=guide_list,
                                    raw_event=raw_event,
                                    error="",
                                )

            return AgentResponse(
                conversation_id=conversation_id,
                connect_time=connect_time,
                chat_time=chat_time,
                response_time_sec=None,
                assistant_message=assistant_message,
                data_ui_list=data_ui_list,
                guide_list=guide_list,
                raw_event=raw_event,
                error="sse ended without assistant",
            )

        except asyncio.TimeoutError:
            return AgentResponse(conversation_id, connect_time, chat_time, None, "", [], [], None, "sse timeout(60s)")
        except Exception as e:
            return AgentResponse(conversation_id, connect_time, chat_time, None, "", [], [], None, f"{type(e).__name__}:{str(e)[:120]}")

    async def subscribe_sse_extended(
        self, session: aiohttp.ClientSession, conversation_id: str
    ) -> Dict[str, Any]:
        """
        CHAT + CHAT_EXECUTION_PROCESS 이벤트를 모두 수집하는 확장 SSE 구독.
        범용 테스트 탭에서 사용.

        반환값:
        {
            "conversation_id": str,
            "connect_time": datetime,
            "chat_time": datetime,
            "response_time_sec": float,
            "assistant_message": str,
            "data_ui_list": list,
            "guide_list": list,
            "execution_processes": list,  # CHAT_EXECUTION_PROCESS 이벤트 목록
            "raw_events": list,
            "error": str
        }
        """
        url = f"{self.base_url}/api/v1/ai/orchestrator/chat-room/sse/subscribe"
        params = {"conversationId": conversation_id}

        connect_time: Optional[datetime] = None
        chat_time: Optional[datetime] = None

        buffer = ""
        current_event = None
        last_heartbeat = datetime.now()

        assistant_message = ""
        data_ui_list: List[Dict[str, Any]] = []
        guide_list: List[Dict[str, Any]] = []
        execution_processes: List[Dict[str, Any]] = []
        raw_events: List[Dict[str, Any]] = []

        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with session.get(url, headers=self.headers(for_sse=True), params=params, timeout=timeout) as resp:
                async for chunk in resp.content.iter_any():
                    buffer += chunk.decode("utf-8", errors="ignore")

                    if (datetime.now() - last_heartbeat).total_seconds() > 30:
                        return {
                            "conversation_id": conversation_id,
                            "connect_time": connect_time,
                            "chat_time": chat_time,
                            "response_time_sec": None,
                            "assistant_message": assistant_message,
                            "data_ui_list": data_ui_list,
                            "guide_list": guide_list,
                            "execution_processes": execution_processes,
                            "raw_events": raw_events,
                            "error": "heartbeat timeout(30s)",
                        }

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()

                        if line.startswith("event:"):
                            current_event = line.replace("event:", "").strip()
                            if current_event == "CONNECT":
                                connect_time = datetime.now()
                            elif current_event == "HEARTBEAT":
                                last_heartbeat = datetime.now()

                        elif line.startswith("data:"):
                            data_str = line.replace("data:", "", 1).strip()
                            if not data_str.startswith("{"):
                                continue
                            try:
                                data = json.loads(data_str)
                            except Exception:
                                continue

                            raw_events.append({"event": current_event, "data": data})

                            # CHAT 이벤트 처리
                            if current_event == "CHAT":
                                if data.get("messageType") == "ASSISTANT":
                                    chat_time = datetime.now()
                                    assistant = data.get("assistant", {}) or {}
                                    assistant_message = assistant.get("assistantMessage", "") or ""
                                    data_ui_list = assistant.get("dataUIList", []) or []
                                    guide_list = assistant.get("guideList", []) or []

                                    rt = None
                                    if connect_time and chat_time:
                                        rt = (chat_time - connect_time).total_seconds()
                                    return {
                                        "conversation_id": conversation_id,
                                        "connect_time": connect_time,
                                        "chat_time": chat_time,
                                        "response_time_sec": rt,
                                        "assistant_message": assistant_message,
                                        "data_ui_list": data_ui_list,
                                        "guide_list": guide_list,
                                        "execution_processes": execution_processes,
                                        "raw_events": raw_events,
                                        "error": "",
                                    }

                            # CHAT_EXECUTION_PROCESS 이벤트 처리
                            elif current_event == "CHAT_EXECUTION_PROCESS":
                                execution_processes.append(data)

            return {
                "conversation_id": conversation_id,
                "connect_time": connect_time,
                "chat_time": chat_time,
                "response_time_sec": None,
                "assistant_message": assistant_message,
                "data_ui_list": data_ui_list,
                "guide_list": guide_list,
                "execution_processes": execution_processes,
                "raw_events": raw_events,
                "error": "sse ended without assistant",
            }

        except asyncio.TimeoutError:
            return {
                "conversation_id": conversation_id,
                "connect_time": connect_time,
                "chat_time": chat_time,
                "response_time_sec": None,
                "assistant_message": "",
                "data_ui_list": [],
                "guide_list": [],
                "execution_processes": execution_processes,
                "raw_events": raw_events,
                "error": "sse timeout(60s)",
            }
        except Exception as e:
            return {
                "conversation_id": conversation_id,
                "connect_time": connect_time,
                "chat_time": chat_time,
                "response_time_sec": None,
                "assistant_message": "",
                "data_ui_list": [],
                "guide_list": [],
                "execution_processes": execution_processes,
                "raw_events": raw_events,
                "error": f"{type(e).__name__}:{str(e)[:120]}",
            }

    async def run_n_times(
        self,
        session: aiohttp.ClientSession,
        query: str,
        n_calls: int = 1,
        max_retries: int = 2,
        context: Optional[Dict[str, Any]] = None,
        target_assistant: Optional[str] = None,
        independent_sessions: bool = False,
    ) -> Tuple[List[Optional[AgentResponse]], str]:
        """
        동일 conversationId에서 N번 호출을 수행하며, 실패 시 자동 재시도.
        - n_calls: 호출 횟수 (기본 1회, 일관성 테스트를 위해 2~4회 가능)
        - max_retries: 각 단계별 최대 재시도 횟수 (기본 2회)
        - context: API 호출 시 전달할 context 객체
        - target_assistant: 특정 어시스턴트 지정 (예: RECRUIT_PLAN_ASSISTANT)
        - independent_sessions: True면 매 호출마다 새 채팅방(conversationId=None)으로 실행
        """
        retry_delay = 2.0
        responses: List[Optional[AgentResponse]] = []
        conv_id: Optional[str] = None
        last_err = ""

        for call_idx in range(n_calls):
            resp: Optional[AgentResponse] = None

            for attempt in range(max_retries + 1):
                cid_in = None if independent_sessions else conv_id
                cid, err = await self.send_query(
                    session, query,
                    conversation_id=cid_in,
                    context=context,
                    target_assistant=target_assistant
                )
                if not cid:
                    last_err = f"send_query#{call_idx + 1} failed: {err}"
                    if attempt < max_retries:
                        await asyncio.sleep(retry_delay)
                    continue

                # 첫 호출에서 conversationId 획득
                if conv_id is None and not independent_sessions:
                    conv_id = cid

                resp = await self.subscribe_sse(session, cid)
                if resp.error:
                    last_err = f"sse#{call_idx + 1} failed: {resp.error}"
                    if attempt < max_retries:
                        await asyncio.sleep(retry_delay)
                    continue

                # 성공
                last_err = ""
                break

            responses.append(resp)

            # 첫 호출 실패 시 이후 호출 중단
            if call_idx == 0 and (resp is None or resp.error):
                return responses, last_err

        return responses, last_err

    async def run_double(
        self, session: aiohttp.ClientSession, query: str, max_retries: int = 2,
        context: Optional[Dict[str, Any]] = None,
        target_assistant: Optional[str] = None
    ) -> Tuple[Optional[AgentResponse], Optional[AgentResponse], str]:
        """
        1차/2차 호출을 수행하며, 실패 시 자동 재시도 (run_n_times wrapper).
        """
        responses, err = await self.run_n_times(
            session, query, n_calls=2, max_retries=max_retries,
            context=context, target_assistant=target_assistant
        )
        r1 = responses[0] if len(responses) > 0 else None
        r2 = responses[1] if len(responses) > 1 else None
        return r1, r2, err


# ============================================================
# 4) URL 파싱 (버튼 URL의 condition/columnVisibility 추출)
#    - 평가 점수에 직접 쓰지 않고, "관측치" 및 디버깅 편의용으로만
# ============================================================
def _json_loads_urlencoded(s: str) -> Optional[Any]:
    if not s:
        return None
    cur = s
    for _ in range(3):
        try:
            return json.loads(cur)
        except Exception:
            cur = unquote(cur)
    return None


def parse_button_url(button_url: str) -> Dict[str, Any]:
    if not button_url:
        return {"filter_types": [], "condition": None, "columns": []}

    parsed = urlparse(button_url)
    qs = parse_qs(parsed.query)

    condition_raw = (qs.get("condition", [""])[0] or "")
    columns_raw = (qs.get("columnVisibility", [""])[0] or "")

    condition = _json_loads_urlencoded(condition_raw)
    columns = _json_loads_urlencoded(columns_raw)

    filter_types: List[str] = []
    if isinstance(condition, list):
        for f in condition:
            ft = (f or {}).get("filterType")
            if ft:
                filter_types.append(str(ft))
    filter_types = sorted(set(filter_types))

    if not isinstance(columns, list):
        columns = []
    columns = [str(c) for c in columns]

    return {"filter_types": filter_types, "condition": condition, "columns": columns}
