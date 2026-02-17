from __future__ import annotations

"""
bulktest_agent_v3.py
- 목적: 서비스 에이전트를 대상으로 "하이브리드 멀티턴" bulktest 수행
  * 기본은 Single-turn
  * 단, 응답 dataUIList 안에 "사용자 입력이 필요한 UI(formType)"가 있을 때만 autopilot이 다음 userMessage를 생성하여 이어감
  * LINK(buttonUrl) 기반 이동은 절대 수행하지 않음 (클릭/이동 금지)

- MAX_USER_TURNS: '질의 3번' 기준 (초기 질의 1 + autopilot 최대 2회)
- transcript를 A/B 두 번 재현하여 Judge(LLM 평가 프롬프트) 단계에 전달 가능

필수 환경변수(.env 권장):
  ATS_BASE_URL, ATS_ORIGIN, ATS_REFERER  (또는 env preset 사용)
  ATS_BEARER_TOKEN, ATS_CMS_TOKEN, ATS_MRS_SESSION

이 파일은 Streamlit/CLI 어디서든 import해서 쓰는 용도입니다.
"""

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from dotenv import load_dotenv

# -----------------------------
# Env presets (필요시 확장)
# -----------------------------
ENV_PRESETS: Dict[str, Dict[str, str]] = {
    "PR": {
        "base_url": "https://api-llm.ats.kr-pr-midasin.com",
        "origin": "https://pr-jobda02-cms.recruiter.co.kr",
        "referer": "https://pr-jobda02-cms.recruiter.co.kr/",
    },
    "ST": {
        "base_url": "https://api-llm.ats.kr-st-midasin.com",
        "origin": "https://st-jobda02-cms.recruiter.co.kr",
        "referer": "https://st-jobda02-cms.recruiter.co.kr/",
    },
    "DV": {
        "base_url": "https://api-llm.ats.kr-dv-midasin.com",
        "origin": "https://dv-jobda02-cms.recruiter.co.kr",
        "referer": "https://dv-jobda02-cms.recruiter.co.kr/",
    },
    "QA": {
        "base_url": "https://api-llm.ats.kr-st2-midasin.com",
        "origin": "https://st-jobda02-cms.recruiter.co.kr",
        "referer": "https://st-jobda02-cms.recruiter.co.kr/",
    },
}

# -----------------------------
# Autopilot: 사용자 입력이 필요한 UI form types
#  - LINK는 절대 실행하지 않음
#  - 실제 서비스에서 더 다양한 타입이 있을 수 있어 확장 가능
# -----------------------------
ACTIONABLE_FORM_TYPES = {
    "SELECT",
    "INPUT",
    "TEXT",
    "TEXT_INPUT",
    "DATE",
    "DATETIME",
    "DATE_RANGE",
    "NUMBER",
    "RADIO",
    "CHECKBOX",
    "MULTI_SELECT",
    "MULTISELECT",
}

# MAX Turns: "질의 3번까지만" = userMessage 총 3회(초기 1 + 추가 2)
DEFAULT_MAX_USER_TURNS = 3


@dataclass
class AssistantSnapshot:
    chat_id: Optional[int]
    created: Optional[str]
    assistant_message: str
    data_ui_list: List[Dict[str, Any]]
    guide_list: List[Dict[str, Any]]
    raw_event: Dict[str, Any]


@dataclass
class Turn:
    user_message: str
    assistant: Optional[AssistantSnapshot]
    error: str = ""


@dataclass
class RunResult:
    conversation_id: str
    status: str  # COMPLETED | NEEDS_USER | ABORTED
    user_turns: int
    started_at: str
    ended_at: str
    turns: List[Turn]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _extract_actionable_ui(data_ui_list: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    dataUIList 중에서 "사용자 입력을 요구하는" 첫 UI 블록을 반환.
    - formType in ACTIONABLE_FORM_TYPES
    - LINK는 제외
    """
    for ui in data_ui_list or []:
        ui_value = (ui or {}).get("uiValue") or {}
        form_type = str(ui_value.get("formType") or "").upper()
        if not form_type:
            continue
        if form_type == "LINK":
            continue
        if form_type in ACTIONABLE_FORM_TYPES:
            return ui
    return None


def _has_actionable_input(data_ui_list: List[Dict[str, Any]]) -> bool:
    return _extract_actionable_ui(data_ui_list) is not None


def autopilot_next_user_message(
    assistant_message: str,
    data_ui_list: List[Dict[str, Any]],
    prefer_keywords: Optional[List[str]] = None,
) -> Tuple[Optional[str], str]:
    """
    '선택/입력 UI'가 있을 때만 다음 userMessage를 자동 생성.
    - prefer_keywords: optionName에 포함되면 우선 선택 (예: ['즉시', '실행', '발송'])
    - LINK 이동은 수행하지 않음: LINK만 있는 경우 None 반환
    반환: (next_message or None, debug_reason)
    """
    prefer_keywords = [k.strip() for k in (prefer_keywords or []) if k and k.strip()]

    ui = _extract_actionable_ui(data_ui_list)
    if not ui:
        return None, "no actionable UI (or only LINK)"

    ui_value = (ui or {}).get("uiValue") or {}
    form_type = str(ui_value.get("formType") or "").upper()

    # 1) SELECT 류
    if form_type in {"SELECT", "MULTI_SELECT", "MULTISELECT"}:
        opts = ui_value.get("selectOptionList") or []
        if not opts:
            return None, "SELECT but empty option list"

        # prefer keyword match in optionName
        best = None
        if prefer_keywords:
            scored = []
            for opt in opts:
                name = str(opt.get("optionName") or "")
                score = sum(1 for k in prefer_keywords if k in name)
                scored.append((score, name, opt))
            scored.sort(key=lambda x: (-x[0], x[1]))
            best = scored[0][2]
        else:
            best = opts[0]

        # 가장 안전: optionName 그대로 user가 입력한 것처럼 보냄
        option_name = str(best.get("optionName") or "").strip()
        option_value = str(best.get("optionValue") or "").strip()

        if option_name:
            return option_name, f"SELECT choose optionName='{option_name}'"
        if option_value:
            return option_value, f"SELECT fallback optionValue='{option_value}'"
        return None, "SELECT option had no name/value"

    # 2) TEXT/INPUT 류 (서비스 구현이 다양하니 보수적으로 기본값)
    if form_type in {"INPUT", "TEXT", "TEXT_INPUT"}:
        placeholder = str(ui_value.get("placeholder") or "").strip()

        # 문맥 기반 기본값
        if "기간" in assistant_message or "기간" in placeholder:
            return "최근 1년", "TEXT default '최근 1년' (period-like)"
        if "날짜" in assistant_message or "날짜" in placeholder:
            return datetime.now().strftime("%Y-%m-%d"), "TEXT default today (date-like)"
        if any(x in assistant_message for x in ["공고", "채용", "플랜", "전형"]):
            return "전체", "TEXT default '전체' (scope-like)"

        return "확인", "TEXT default '확인'"

    # 3) DATE 류
    if form_type in {"DATE", "DATETIME", "DATE_RANGE"}:
        if form_type == "DATE_RANGE":
            return "최근 1년", "DATE_RANGE default '최근 1년'"
        return datetime.now().strftime("%Y-%m-%d"), f"{form_type} default today"

    # 4) NUMBER
    if form_type == "NUMBER":
        return "1", "NUMBER default 1"

    # 5) RADIO/CHECKBOX (구조가 서비스마다 달라 기본값만)
    if form_type in {"RADIO", "CHECKBOX"}:
        return "1", f"{form_type} default 1"

    return None, f"unhandled formType={form_type}"


class ServiceAgentClient:
    """ATS Orchestrator 기반 서비스 에이전트 호출 클라이언트"""

    def __init__(
        self,
        base_url: str,
        bearer_token: str,
        cms_token: str,
        mrs_session: str,
        origin: str,
        referer: str,
    ):
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token.strip()
        self.cms_token = cms_token.strip()
        self.mrs_session = mrs_session.strip()
        self.origin = origin.strip()
        self.referer = referer.strip()

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
        self,
        session: aiohttp.ClientSession,
        user_message: str,
        conversation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        target_assistant: Optional[str] = None,
    ) -> Tuple[Optional[str], str]:
        url = f"{self.base_url}/api/v2/ai/orchestrator/query"
        payload: Dict[str, Any] = {"conversationId": conversation_id, "userMessage": user_message}
        if context:
            payload["context"] = context
        if target_assistant:
            payload["targetAssistant"] = target_assistant

        try:
            async with session.post(url, headers=self.headers(), json=payload, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("conversationId"), ""
                return None, f"HTTP {resp.status}: {(await resp.text())[:300]}"
        except asyncio.TimeoutError:
            return None, "timeout(30s)"
        except Exception as e:
            return None, f"{type(e).__name__}: {str(e)[:200]}"

    async def subscribe_sse(self, session: aiohttp.ClientSession, conversation_id: str) -> AssistantSnapshot:
        url = f"{self.base_url}/api/v1/ai/orchestrator/chat-room/sse/subscribe"
        params = {"conversationId": conversation_id}

        buffer = ""
        current_event = None
        last_heartbeat = datetime.now()

        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with session.get(url, headers=self.headers(for_sse=True), params=params, timeout=timeout) as resp:
                async for chunk in resp.content.iter_any():
                    buffer += chunk.decode("utf-8", errors="ignore")

                    if (datetime.now() - last_heartbeat).total_seconds() > 30:
                        raise TimeoutError("heartbeat timeout(30s)")

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()

                        if line.startswith("event:"):
                            current_event = line.replace("event:", "").strip()
                            if current_event == "HEARTBEAT":
                                last_heartbeat = datetime.now()

                        elif line.startswith("data:"):
                            if current_event != "CHAT":
                                continue
                            data_str = line.replace("data:", "", 1).strip()
                            if not data_str.startswith("{"):
                                continue
                            try:
                                data = json.loads(data_str)
                            except Exception:
                                continue

                            if data.get("messageType") == "ASSISTANT":
                                assistant = data.get("assistant", {}) or {}
                                return AssistantSnapshot(
                                    chat_id=data.get("chatId"),
                                    created=data.get("createdDateTime"),
                                    assistant_message=assistant.get("assistantMessage", "") or "",
                                    data_ui_list=assistant.get("dataUIList", []) or [],
                                    guide_list=assistant.get("guideList", []) or [],
                                    raw_event=data,
                                )

            return AssistantSnapshot(
                chat_id=None,
                created=None,
                assistant_message="",
                data_ui_list=[],
                guide_list=[],
                raw_event={"error": "sse ended without assistant"},
            )
        except Exception as e:
            return AssistantSnapshot(
                chat_id=None,
                created=None,
                assistant_message="",
                data_ui_list=[],
                guide_list=[],
                raw_event={"error": f"{type(e).__name__}: {str(e)[:200]}"},
            )

    async def run_hybrid_multiturn(
        self,
        session: aiohttp.ClientSession,
        initial_user_message: str,
        context: Optional[Dict[str, Any]] = None,
        target_assistant: Optional[str] = None,
        max_user_turns: int = DEFAULT_MAX_USER_TURNS,
        prefer_keywords: Optional[List[str]] = None,
    ) -> RunResult:
        started = _now_iso()
        turns: List[Turn] = []
        conv_id: Optional[str] = None

        user_turn_count = 0
        next_user_message = initial_user_message

        while True:
            user_turn_count += 1
            if user_turn_count > max_user_turns:
                return RunResult(
                    conversation_id=conv_id or "",
                    status="ABORTED",
                    user_turns=user_turn_count - 1,
                    started_at=started,
                    ended_at=_now_iso(),
                    turns=turns,
                )

            new_conv_id, err = await self.send_query(
                session,
                user_message=next_user_message,
                conversation_id=conv_id,
                context=context,
                target_assistant=target_assistant,
            )
            if not new_conv_id:
                turns.append(Turn(user_message=next_user_message, assistant=None, error=f"send_query failed: {err}"))
                return RunResult(
                    conversation_id=conv_id or "",
                    status="ABORTED",
                    user_turns=user_turn_count,
                    started_at=started,
                    ended_at=_now_iso(),
                    turns=turns,
                )

            conv_id = new_conv_id

            snap = await self.subscribe_sse(session, conv_id)
            turns.append(Turn(user_message=next_user_message, assistant=snap, error=""))

            if "error" in (snap.raw_event or {}):
                return RunResult(
                    conversation_id=conv_id,
                    status="ABORTED",
                    user_turns=user_turn_count,
                    started_at=started,
                    ended_at=_now_iso(),
                    turns=turns,
                )

            if _has_actionable_input(snap.data_ui_list):
                msg, _reason = autopilot_next_user_message(
                    assistant_message=snap.assistant_message,
                    data_ui_list=snap.data_ui_list,
                    prefer_keywords=prefer_keywords,
                )
                if not msg:
                    return RunResult(
                        conversation_id=conv_id,
                        status="NEEDS_USER",
                        user_turns=user_turn_count,
                        started_at=started,
                        ended_at=_now_iso(),
                        turns=turns,
                    )
                next_user_message = msg
                continue

            # actionable UI가 없으면 자동 진행 종료
            msg_text = (snap.assistant_message or "").strip()
            looks_like_question = ("?" in msg_text) or any(x in msg_text for x in ["선택", "입력", "알려", "정해", "어느", "어떤"])
            status = "NEEDS_USER" if looks_like_question else "COMPLETED"

            return RunResult(
                conversation_id=conv_id,
                status=status,
                user_turns=user_turn_count,
                started_at=started,
                ended_at=_now_iso(),
                turns=turns,
            )


def run_result_to_transcript_json(run: RunResult) -> str:
    def turn_to_dict(t: Turn) -> Dict[str, Any]:
        d: Dict[str, Any] = {"user_message": t.user_message, "error": t.error}
        if t.assistant is None:
            d["assistant"] = None
        else:
            a = t.assistant
            d["assistant"] = {
                "chatId": a.chat_id,
                "createdDateTime": a.created,
                "assistantMessage": a.assistant_message,
                "dataUIList": a.data_ui_list,
                "guideList": a.guide_list,
                "raw": a.raw_event,
            }
        return d

    payload = {
        "conversationId": run.conversation_id,
        "status": run.status,
        "user_turns": run.user_turns,
        "started_at": run.started_at,
        "ended_at": run.ended_at,
        "turns": [turn_to_dict(t) for t in run.turns],
    }
    return json.dumps(payload, ensure_ascii=False)


# -----------------------------
# CLI quick test
# -----------------------------
async def _cli_main():
    load_dotenv()

    p = argparse.ArgumentParser()
    p.add_argument("--env", choices=["DV", "QA", "ST", "PR"], default="PR")
    p.add_argument("--message", required=True)
    p.add_argument("--target-assistant", default="")
    p.add_argument("--context-json", default="")
    p.add_argument("--max-user-turns", type=int, default=DEFAULT_MAX_USER_TURNS)
    p.add_argument("--prefer", default="즉시,실행,발송")
    args = p.parse_args()

    preset = ENV_PRESETS[args.env]
    base_url = os.getenv("ATS_BASE_URL") or preset.get("base_url", "")
    origin = os.getenv("ATS_ORIGIN") or preset.get("origin", "")
    referer = os.getenv("ATS_REFERER") or preset.get("referer", "")

    bearer = os.getenv("ATS_BEARER_TOKEN", "").strip()
    cms = os.getenv("ATS_CMS_TOKEN", "").strip()
    mrs = os.getenv("ATS_MRS_SESSION", "").strip()
    if not (base_url and origin and referer and bearer and cms and mrs):
        raise SystemExit("Missing env vars. Need ATS_* and base/origin/referer.")

    context = None
    if args.context_json.strip():
        context = json.loads(args.context_json)

    prefer = [x.strip() for x in args.prefer.split(",") if x.strip()]

    client = ServiceAgentClient(
        base_url=base_url,
        bearer_token=bearer,
        cms_token=cms,
        mrs_session=mrs,
        origin=origin,
        referer=referer,
    )

    connector = aiohttp.TCPConnector(limit=5, ssl=False)
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        run = await client.run_hybrid_multiturn(
            session=session,
            initial_user_message=args.message,
            context=context,
            target_assistant=(args.target_assistant or None),
            max_user_turns=args.max_user_turns,
            prefer_keywords=prefer,
        )

    print(run_result_to_transcript_json(run))


if __name__ == "__main__":
    asyncio.run(_cli_main())
