"""
지원자 관리 에이전트 Bulktest (Light v1)
- 목적: CSV(질의/기대필터)를 읽어서 1차/2차(동일 세션) 응답을 수집하고,
        최소한의 규칙 기반으로 결과 컬럼을 채워 Excel로 저장.

실행 예시 (CLI):
  python bulktest_applicant_agent_light.py --env PR --input "/mnt/data/지원자 관리 질의_260202.csv" --output "./out.xlsx" --max-parallel 3

토큰 설정 (우선순위: CLI > 환경변수 > 파일 내):
  - 파일 내: DEFAULT_ATS_BEARER_TOKEN, DEFAULT_ATS_CMS_TOKEN, DEFAULT_ATS_MRS_SESSION 변수에 값 지정
  - 환경변수: ATS_BEARER_TOKEN, ATS_CMS_TOKEN, ATS_MRS_SESSION
  - CLI: --bearer-token, --cms-token, --mrs-session

주의:
- env별 base_url/origin/referer는 조직 설정에 따라 다를 수 있습니다.
  PR/ST는 기본값 제공, DV/QA는 필요 시 --base-url/--origin/--referer로 덮어쓰세요.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

import aiohttp
import pandas as pd


# -----------------------------
# 1) 환경 설정 (DV/QA/ST/PR)
# -----------------------------
ENV_PRESETS: Dict[str, Dict[str, str]] = {
    # ✅ PR/ST는 참고용 파일에 있던 값을 기본 제공
    "PR": {
        "base_url": "https://api-llm.ats.kr-pr-midasin.com",
        "origin": "https://pr-jobda02-cms.recruiter.co.kr",
        "referer": "https://pr-jobda02-cms.recruiter.co.kr/",
    },
    "ST": {
        "base_url": "https://api-llm.ats.kr-st2-midasin.com",
        # ⛳️ 아래 2개는 조직 설정에 맞게 바꿀 가능성이 큼 (필요시 CLI로 override)
        "origin": "https://st-jobda02-cms.recruiter.co.kr",
        "referer": "https://st-jobda02-cms.recruiter.co.kr/",
    },
    # ⛳️ DV/QA는 조직마다 URL이 달라질 수 있어 기본값을 비워둠 (CLI override 권장)
    "DV": {"base_url": "", "origin": "", "referer": ""},
    "QA": {"base_url": "", "origin": "", "referer": ""},
}

# -----------------------------
# 1-2) 토큰 기본값 (파일 내 정의, CLI/환경변수보다 우선순위 낮음)
# -----------------------------
DEFAULT_ATS_BEARER_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJqdGkiOiI3YjcyN2UzNy1iZDkxLTQyYjctYjgzZi05MWIxZWU2NmRlMzciLCJpYXQiOjE3NzAwNDE2MjYsImlzcyI6IlJldGVudGlvbiIsImV4cCI6MTc3MDA0ODgyNiwiU0VSVklDRV9OQU1FIjoiTVJTIiwiQ09NUEFOWV9OQU1FIjoiam9iZGEwMiIsIlNQQUNFX0lEIjoiMjEwIiwiSk9CREFfREVWX0FETUlOX0RPTUFJTiI6InByLWpvYmRhMDIuY21zLnBocy1wcm9ncmFtbWVydGVzdC5jb20iLCJBQ0NfRE9NQUlOIjoicHItam9iZGEwMi5hY2NhLmFpIiwiSk9CREFfREVWX0RPTUFJTiI6InByLWpvYmRhMDIucGhzLXByb2dyYW1tZXJ0ZXN0LmNvbSIsIlRPS0VOX1RZUEUiOiJNRU1CRVIiLCJURU5BTlRfSUQiOiIzMzI1NDMiLCJNRU1CRVJfSUQiOjE2NjYxLCJBQ0NfQURNSU5fRE9NQUlOIjoicHItam9iZGEwMi1jbXMuYWNjYS5yZWNydWl0ZXIuY28ua3IiLCJFTUFJTCI6ImFnbzA1MjhAamFpbndvbi5jb20ifQ.zVM0arzfZdV9lvGa7qY6PD_f1Xc5QJkDD9I2CO-Oavc"
DEFAULT_ATS_CMS_TOKEN = "eyJhbGciOiJSUzI1NiJ9.eyJhdWQiOiJtcnNfYXBpIiwic3ViIjoiYWdvMDUyOCIsInNwYWNlU24iOjIxMCwiY29tcGFueVNuIjozMzI1NDMsImlkIjoiYWdvMDUyOCIsInVzZXJfbmFtZSI6ImFnbzA1MjgiLCJhY2NBdXRoVG9rZW4iOiJleUpoYkdjaU9pSklVekkxTmlKOS5leUp6ZFdJaU9pSk5RVTVCUjBWU0lpd2lZWFZrSWpvaU1USTFJaXdpVkVWT1FVNVVYMU5PSWpvME5EVXNJbk53WVdObFUyNGlPakVzSW1selZYTmxVM0JoWTJVaU9tWmhiSE5sTENKemNHRmpaVkp2YkdWTWFYTjBJanBiZXlKemNHRmpaVk51SWpveExDSnliMnhsSWpvaVRVRk9RVWRGVWlKOVhTd2lhV0YwSWpveE56Y3dNREF5TmpreUxDSmxlSEFpT2pFM056QXdNalF5T1RKOS5GanR6ZzZoZGJXQnhWMGkzR1FZUzlrdHVKdkZna2RyX0p1aTZyR1RIeUtvIiwiaXNTbXNDb25maXJtIjpmYWxzZSwiaXNFbWFpbENvbmZpcm0iOmZhbHNlLCJqb2JkYURldlNlc3Npb25JZCI6ImY3YTE4NmY4LWQ0ZGMtNGJhNi1hNTEzLTFhODc5MmU0NTJjNCIsImF1dGhvcml0aWVzIjpbIlJPTEVfVVNFUiJdLCJleHAiOjE3NzA2MDc0OTJ9.TsG9G68YUnj6XmasXrGyxwtoN1nvBRrDHRQMZ4UWecsO1FYWLuYCtRR4vWGI7wrvqD2BFkdjMRWQpg2r89TzXfVHpV3_62xlRNC167w2mLXoll6Mluxg0vUB4dDMtVbLSpFC3nHdkLp_xG2NrwefrrinDbTfVttfLMcYrWAnwf3_wsvQx6CtCHv4sAQdMIlmGKQyhWJMYekADFKkgcfBGW-5hLV27aaYE0-OfZUXwglBdNPa1MnazVH0s4diGB_7JuMM3U4qMNhEW9j-Wv1WalXRiYvSANaZOnjpsfqyiq5dJ0LwA4YBdlI3YsoEdPc2NvSiF5O1si-0iQasy7rb5A"
DEFAULT_ATS_MRS_SESSION = "ZmI0MTNhMDMtMzU0Ny00NTFiLWI1ZmUtYTU3OTA3N2FiMzNj"


# -----------------------------
# 2) 룰북 (초기 버전)
#    - expected(한글) -> condition.filterType 기대값
#    - 여기부터 "바이브코딩"으로 계속 확장하는 영역
# -----------------------------
RULEBOOK: Dict[str, Dict[str, Any]] = {
    # Track1 예시 몇 개만 선반영 (나머지는 실행하면서 발견된 filterType으로 채워넣는 방식 추천)
    "지원서 제출 여부": {"any_filter_types": ["RESUME_SUBMIT"]},
    "열람 여부": {"any_filter_types": ["RESUME_READ", "RESUME_OPEN", "RESUME_VIEW"]},  # 후보군
    "지원 경로": {"any_filter_types": ["APPLY_PATH", "APPLY_ROUTE", "APPLY_SOURCE"]},  # 후보군
    "국적": {"any_filter_types": ["NATIONALITY"]},
    "병역": {"any_filter_types": ["MILITARY"]},
    "장애": {"any_filter_types": ["DISABILITY"]},
    "보훈": {"any_filter_types": ["VETERAN"]},
    "최종학력": {"any_filter_types": ["EDUCATION_LEVEL"]},
    "학점": {"any_filter_types": ["GPA"]},
    "외국어 시험": {"any_filter_types": ["LANG_TEST", "FOREIGN_LANGUAGE_TEST"]},
    "자격증": {"any_filter_types": ["CERTIFICATE"]},
    # 기간은 특별 규칙 때문에 별도로 다룸
}


# -----------------------------
# 3) SSE 응답 구조
# -----------------------------
@dataclass
class AgentResponse:
    conversation_id: str
    connect_time: Optional[datetime]
    chat_time: Optional[datetime]
    response_time_sec: Optional[float]
    assistant_message: str
    data_ui_list: List[Dict[str, Any]]
    raw_event: Optional[Dict[str, Any]]
    error: str = ""

    @property
    def button_url(self) -> str:
        for ui in self.data_ui_list or []:
            ui_value = (ui or {}).get("uiValue", {}) or {}
            if "buttonUrl" in ui_value:
                return ui_value["buttonUrl"]
        return ""


# -----------------------------
# 4) 유틸: URL에 들어있는 condition/columnVisibility 파싱
# -----------------------------
def _json_loads_urlencoded(s: str) -> Optional[Any]:
    """URL-encoded JSON을 최대 3회 unquote 해보며 파싱."""
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
    """
    /agent/integrated-grid/applicant?...&condition=[...]&columnVisibility=[...]
    를 파싱해서 filterType/columns를 추출
    """
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


# -----------------------------
# 5) 유틸: 핵심 수치 추출 (일관성 비교용)
# -----------------------------
_NUM_WITH_UNIT = re.compile(r"(?P<num>\d[\d,]*)(?:\.\d+)?\s*(?P<unit>명|개|점|%)")

def extract_key_metrics(text: str) -> List[Tuple[str, str]]:
    """
    '21,950명', '990점', '10%' 같은 핵심 수치를 뽑는다.
    반환: [(num_str, unit), ...]  (num_str는 콤마 포함)
    """
    if not text:
        return []
    metrics = []
    for m in _NUM_WITH_UNIT.finditer(text):
        num = m.group("num")
        unit = m.group("unit")
        metrics.append((num, unit))
    return metrics


def normalize_num(num_str: str) -> Optional[float]:
    if not num_str:
        return None
    try:
        return float(num_str.replace(",", ""))
    except Exception:
        return None


def pick_primary_metric(metrics: List[Tuple[str, str]]) -> Optional[Tuple[float, str]]:
    """
    우선순위:
    1) '명' 또는 '개'  (카운트 질의가 많아서)
    2) 그 외 첫 번째
    """
    if not metrics:
        return None
    for num, unit in metrics:
        if unit in ("명", "개"):
            v = normalize_num(num)
            if v is not None:
                return (v, unit)
    num, unit = metrics[0]
    v = normalize_num(num)
    if v is None:
        return None
    return (v, unit)


# -----------------------------
# 6) 유틸: 질의에 "특정 기간"이 명시됐는지 (기간 필터 감점 규칙용)
# -----------------------------
_PERIOD_EXPLICIT = re.compile(
    r"(3개월|6개월|1개월|2개월|지난\s?달|이번\s?달|작년|지난해|올해|상반기|하반기|분기|Q[1-4]|20\d{2})"
)

def query_has_explicit_period(query: str) -> bool:
    if not query:
        return False
    return bool(_PERIOD_EXPLICIT.search(query))


# -----------------------------
# 7) 룰 기반 평가 (Light)
# -----------------------------
def split_expected(expected_str: str) -> List[str]:
    """'A + B + C' 형태를 분해"""
    if not isinstance(expected_str, str):
        return []
    parts = [p.strip() for p in expected_str.split("+")]
    return [p for p in parts if p]


def rule_match_expected_token(expected_token: str, detected_filter_types: List[str], assistant_message: str) -> Tuple[bool, str]:
    """
    expected_token 하나가 충족되는지 판단.
    - RULEBOOK에 있으면 filterType 기반 체크
    - 없으면 fallback: assistantMessage에 expected_token이 포함되는지(아주 약한 휴리스틱)
    """
    rb = RULEBOOK.get(expected_token)
    if rb and rb.get("any_filter_types"):
        for ft in rb["any_filter_types"]:
            if ft in detected_filter_types:
                return True, f"filterType={ft}"
        return False, f"missing any of {rb['any_filter_types']}"
    # fallback
    if expected_token and expected_token in (assistant_message or ""):
        return True, "fallback:assistantMessage"
    return False, "unmapped"


def score_filter_accuracy(query: str, expected_filters: List[str], detected_filter_types: List[str]) -> Tuple[int, str]:
    """
    매우 가벼운 스코어링:
    - expected 전부 충족: 기본 100
    - expected 충족 + 추가필터 존재: 80
    - 일부만: 60
    - 대부분 누락: 20
    - 완전 무관: 0

    기간(RESUME_PERIOD)은:
    - query에 특정 기간이 없으면 추가되어도 감점하지 않음.
    """
    if not expected_filters:
        return 100, "expected empty"

    # 각 expected token별 매치 결과
    # (assistantMessage는 별도에서 넣고 싶다면 함수 시그니처를 확장하면 됨)
    # 여기서는 filterType 기준으로만 최대한 판단
    matched = 0
    notes = []
    for tok in expected_filters:
        ok, why = rule_match_expected_token(tok, detected_filter_types, assistant_message="")
        if ok:
            matched += 1
        else:
            notes.append(f"{tok}:{why}")

    if matched == 0:
        return 0, "no expected matched; " + "; ".join(notes)

    if matched < len(expected_filters):
        # 절반 이상 매치면 60, 아니면 20
        ratio = matched / max(len(expected_filters), 1)
        return (60 if ratio >= 0.5 else 20), "partial; " + "; ".join(notes)

    # 여기부터 expected는 모두 매치
    # 추가 필터 체크
    extra = [ft for ft in detected_filter_types if ft not in flatten_expected_filtertypes(expected_filters)]
    extra_wo_period = [ft for ft in extra if ft != "RESUME_PERIOD"]

    if extra_wo_period:
        return 80, f"extra filters: {extra_wo_period}"
    # RESUME_PERIOD만 추가된 경우
    if "RESUME_PERIOD" in extra and not query_has_explicit_period(query):
        return 100, "period auto-added (ignored)"
    if "RESUME_PERIOD" in extra and query_has_explicit_period(query):
        # 특정 기간 명시인데 period가 있는 건 오히려 정상. 다만 begin/end 검증은 여기선 생략.
        return 100, "period present (explicit in query)"
    return 100, "exact match"


def flatten_expected_filtertypes(expected_filters: List[str]) -> List[str]:
    """expected token들이 RULEBOOK에서 매핑되는 filterType 후보를 모두 펼침"""
    fts: List[str] = []
    for tok in expected_filters:
        rb = RULEBOOK.get(tok)
        if rb and rb.get("any_filter_types"):
            fts.extend(rb["any_filter_types"])
    return sorted(set(fts))


def score_consistency(msg1: str, msg2: str) -> Tuple[int, str]:
    """
    가벼운 일관성 점수:
    - 핵심 '명/개/점/%' 수치(1개) 동일: 100
    - 수치 못 뽑았지만 문장 길이/키워드 유사: 80
    - 다름: 20
    """
    m1 = pick_primary_metric(extract_key_metrics(msg1))
    m2 = pick_primary_metric(extract_key_metrics(msg2))

    if m1 and m2:
        if m1 == m2:
            return 100, f"primary metric match {m1}"
        else:
            return 20, f"primary metric diff {m1} vs {m2}"

    # metric 추출 실패 시 fallback
    if (msg1 or "").strip() and (msg2 or "").strip():
        # 아주 러프하게 '제출/미제출/평균/Top' 같은 키워드 비교
        kw = ["제출", "미제출", "평균", "Top", "상위", "하위", "명", "개", "점"]
        overlap = sum(1 for k in kw if k in msg1 and k in msg2)
        return (80 if overlap >= 2 else 40), f"metric missing; keyword overlap={overlap}"

    return 0, "empty message"


def classify_diff(
    detected1: List[str], detected2: List[str],
    msg1: str, msg2: str
) -> str:
    if set(detected1) != set(detected2):
        return "열/필터 변경"

    m1 = pick_primary_metric(extract_key_metrics(msg1))
    m2 = pick_primary_metric(extract_key_metrics(msg2))
    if m1 and m2 and m1 != m2:
        return "통계값만 변경"

    if (msg1 or "").strip() != (msg2 or "").strip():
        return "표현만 변경"

    return ""


# -----------------------------
# 8) API Client
# -----------------------------
class ApplicantAgentClient:
    def __init__(self, base_url: str, bearer_token: str, cms_token: str, mrs_session: str,
                 origin: str, referer: str, max_parallel: int = 3):
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token.strip()
        self.cms_token = cms_token.strip()
        self.mrs_session = mrs_session.strip()
        self.origin = origin
        self.referer = referer
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

    async def send_query(self, session: aiohttp.ClientSession, message: str, conversation_id: Optional[str]) -> Tuple[Optional[str], str]:
        url = f"{self.base_url}/api/v2/ai/orchestrator/query"
        payload = {"conversationId": conversation_id, "userMessage": message}
        try:
            async with session.post(url, headers=self.headers(), json=payload, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("conversationId"), ""
                return None, f"HTTP {resp.status}: {(await resp.text())[:200]}"
        except asyncio.TimeoutError:
            return None, "timeout(30s)"
        except Exception as e:
            return None, f"{type(e).__name__}: {str(e)[:80]}"

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

                                # ✅ 여기서는 "첫 ASSISTANT"를 받으면 종료 (필요시 '마지막'으로 바꿔도 됨)
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
                raw_event=raw_event,
                error="sse ended without assistant",
            )

        except asyncio.TimeoutError:
            return AgentResponse(conversation_id, connect_time, chat_time, None, "", [], None, "sse timeout(60s)")
        except Exception as e:
            return AgentResponse(conversation_id, connect_time, chat_time, None, "", [], None, f"{type(e).__name__}:{str(e)[:80]}")

    async def run_double(self, session: aiohttp.ClientSession, query: str) -> Tuple[Optional[AgentResponse], Optional[AgentResponse], str]:
        """
        동일 세션 2회 질의:
          1) conversationId=None로 1차 query
          2) SSE로 1차 응답 수신
          3) 같은 conversationId로 2차 query
          4) SSE로 2차 응답 수신
        """
        # 1차
        conv_id, err = await self.send_query(session, query, conversation_id=None)
        if not conv_id:
            return None, None, f"send_query#1 failed: {err}"

        r1 = await self.subscribe_sse(session, conv_id)
        if r1.error:
            # 그래도 2차는 시도해볼지 선택 가능. 여기선 중단.
            return r1, None, f"sse#1 failed: {r1.error}"

        # 2차
        conv_id2, err2 = await self.send_query(session, query, conversation_id=conv_id)
        if not conv_id2:
            return r1, None, f"send_query#2 failed: {err2}"

        r2 = await self.subscribe_sse(session, conv_id2)
        if r2.error:
            return r1, r2, f"sse#2 failed: {r2.error}"

        return r1, r2, ""

    async def run_row(self, session: aiohttp.ClientSession, row: pd.Series) -> Dict[str, Any]:
        async with self.semaphore:
            query_id = str(row.get("ID", "")).strip()
            query = str(row.get("질의", "")).strip()
            expected_raw = str(row.get("기대 필터/열", "")).strip()
            expected_tokens = split_expected(expected_raw)

            started = time.time()
            r1, r2, err = await self.run_double(session, query)
            elapsed = time.time() - started

            # 기본 결과
            out: Dict[str, Any] = {
                "ID": query_id,
                "질의": query,
                "기대 필터/열": expected_raw,
                "실행소요(초)": round(elapsed, 2),
                "에러": err,
            }

            # 1차/2차 응답 채움
            if r1:
                out["1차 답변"] = r1.assistant_message
                out["1차 답변 시간(초)"] = round(r1.response_time_sec, 2) if r1.response_time_sec is not None else ""
                out["1차 buttonUrl"] = r1.button_url
                p1 = parse_button_url(r1.button_url)
                out["1차 detected_filterTypes"] = ",".join(p1["filter_types"])
                out["1차 detected_columns"] = ",".join(p1["columns"])
            else:
                out["1차 답변"] = ""
                out["1차 답변 시간(초)"] = ""
                out["1차 buttonUrl"] = ""
                out["1차 detected_filterTypes"] = ""
                out["1차 detected_columns"] = ""

            if r2:
                out["2차 답변"] = r2.assistant_message
                out["2차 답변 시간(초)"] = round(r2.response_time_sec, 2) if r2.response_time_sec is not None else ""
                out["2차 buttonUrl"] = r2.button_url
                p2 = parse_button_url(r2.button_url)
                out["2차 detected_filterTypes"] = ",".join(p2["filter_types"])
                out["2차 detected_columns"] = ",".join(p2["columns"])
            else:
                out["2차 답변"] = ""
                out["2차 답변 시간(초)"] = ""
                out["2차 buttonUrl"] = ""
                out["2차 detected_filterTypes"] = ""
                out["2차 detected_columns"] = ""

            # 간단 평가 (에러 없을 때만)
            if (not err) and r1 and r2:
                d1 = parse_button_url(r1.button_url)["filter_types"]
                d2 = parse_button_url(r2.button_url)["filter_types"]

                fa_score, fa_note = score_filter_accuracy(query, expected_tokens, d1)
                con_score, con_note = score_consistency(r1.assistant_message, r2.assistant_message)

                out["열/필터 점수"] = fa_score
                out["열/필터 노트"] = fa_note
                out["답변 일관성 점수"] = con_score
                out["답변 일관성 노트"] = con_note

                out["열/필터 일치 여부"] = "Pass" if fa_score >= 80 else "Fail"
                out["답변 일관성"] = "일치" if con_score >= 80 else "차이 발생"
                out["차이 유형"] = classify_diff(d1, d2, r1.assistant_message, r2.assistant_message)

                # 특이사항: period 자동 포함 등
                if "RESUME_PERIOD" in d1 and not query_has_explicit_period(query):
                    out["특이사항"] = "기간 필터(최근 1년)가 자동 포함됨(규칙상 감점 없음)"
                else:
                    out["특이사항"] = ""
            else:
                out["열/필터 일치 여부"] = ""
                out["답변 일관성"] = ""
                out["차이 유형"] = ""
                out["특이사항"] = err or ""

            return out


# -----------------------------
# 9) 엔트리포인트
# -----------------------------
async def run_bulktest(args: argparse.Namespace) -> pd.DataFrame:
    # CSV 로드 & 컬럼 정리
    df = pd.read_csv(args.input, encoding="utf-8")
    df.columns = [c.strip() for c in df.columns]

    # 토큰 확보: CLI > 환경변수 > 파일 내 기본값
    bearer = (args.bearer_token or os.getenv("ATS_BEARER_TOKEN") or DEFAULT_ATS_BEARER_TOKEN or "").strip()
    cms = (args.cms_token or os.getenv("ATS_CMS_TOKEN") or DEFAULT_ATS_CMS_TOKEN or "").strip()
    mrs = (args.mrs_session or os.getenv("ATS_MRS_SESSION") or DEFAULT_ATS_MRS_SESSION or "").strip()

    if not bearer or not cms or not mrs:
        raise RuntimeError("토큰이 없습니다. --bearer-token/--cms-token/--mrs-session, 환경변수 ATS_*, 또는 파일 내 DEFAULT_ATS_* 를 설정하세요.")

    preset = ENV_PRESETS.get(args.env.upper())
    if not preset:
        raise RuntimeError(f"지원하지 않는 env={args.env}. (DV/QA/ST/PR)")

    base_url = (args.base_url or preset.get("base_url", "")).strip()
    origin = (args.origin or preset.get("origin", "")).strip()
    referer = (args.referer or preset.get("referer", "")).strip()

    if not base_url or not origin or not referer:
        raise RuntimeError(
            f"env={args.env} 설정이 불완전합니다.\n"
            f"- base_url='{base_url}'\n- origin='{origin}'\n- referer='{referer}'\n"
            f"DV/QA는 보통 CLI로 override가 필요합니다."
        )

    client = ApplicantAgentClient(
        base_url=base_url,
        bearer_token=bearer,
        cms_token=cms,
        mrs_session=mrs,
        origin=origin,
        referer=referer,
        max_parallel=args.max_parallel,
    )

    connector = aiohttp.TCPConnector(limit=20, ssl=False)
    timeout = aiohttp.ClientTimeout(total=120)

    results: List[Dict[str, Any]] = []
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = []
        for _, row in df.iterrows():
            # 이미 1차 답변이 채워져 있으면 스킵(원하면 옵션화 가능)
            if isinstance(row.get("1차 답변"), str) and row.get("1차 답변").strip():
                continue
            tasks.append(asyncio.create_task(client.run_row(session, row)))

        # 병렬 실행
        for coro in asyncio.as_completed(tasks):
            res = await coro
            results.append(res)
            if args.verbose:
                print(f"[{res.get('ID')}] done - err={res.get('에러')}")

    # 결과를 원본 DF에 merge
    out_df = df.copy()

    res_df = pd.DataFrame(results)
    if not res_df.empty:
        out_df = out_df.merge(res_df, on=["ID", "질의", "기대 필터/열"], how="left", suffixes=("", "_new"))

        # 기존 컬럼(템플릿)에 채워넣기: 1차/2차 답변/시간, Pass/Fail 등
        # 템플릿 컬럼명이 조금씩 달라도 strip 해둔 상태라 매칭 가능
        for col in ["1차 답변", "1차 답변 시간(초)", "2차 답변", "2차 답변 시간(초)", "열/필터 일치 여부", "답변 일관성", "차이 유형", "특이사항"]:
            if col in out_df.columns and (col + "_new") in out_df.columns:
                # new 값이 있으면 덮어쓰기
                out_df[col] = out_df[col].where(out_df[col].notna() & (out_df[col].astype(str).str.strip() != ""), out_df[col + "_new"])

        # 중복 컬럼 정리
        drop_cols = [c for c in out_df.columns if c.endswith("_new")]
        out_df.drop(columns=drop_cols, inplace=True, errors="ignore")

    return out_df


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--env", required=True, choices=["DV", "QA", "ST", "PR"])
    p.add_argument("--input", required=True, help="입력 CSV 경로")
    p.add_argument("--output", required=True, help="출력 Excel(.xlsx) 경로")
    p.add_argument("--max-parallel", type=int, default=3)
    p.add_argument("--base-url", default="", help="env preset override")
    p.add_argument("--origin", default="", help="env preset override")
    p.add_argument("--referer", default="", help="env preset override")

    # 토큰은 env var 또는 옵션으로
    p.add_argument("--bearer-token", default="")
    p.add_argument("--cms-token", default="")
    p.add_argument("--mrs-session", default="")

    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    out_df = asyncio.run(run_bulktest(args))

    # Excel 저장
    out_df.to_excel(args.output, index=False)
    print(f"Saved: {args.output}  (rows={len(out_df)})")

    # --- (선택) 룰북 후보 자동 추출: expected(한글 토큰) -> 관측된 filterType 상위 N개
    # 초기엔 "에이전트가 보통 맞다"는 가정 하에 후보를 빠르게 수집하는 용도입니다.
    try:
        from collections import Counter, defaultdict
        suggestions = defaultdict(Counter)

        if "1차 detected_filterTypes" in out_df.columns and "기대 필터/열" in out_df.columns:
            for _, r in out_df.iterrows():
                exp_raw = str(r.get("기대 필터/열", "")).strip()
                if not exp_raw:
                    continue
                exp_tokens = [t.strip() for t in exp_raw.split("+") if t.strip()]
                detected = str(r.get("1차 detected_filterTypes", "")).strip()
                fts = [x.strip() for x in detected.split(",") if x.strip()]
                if not fts:
                    continue
                for tok in exp_tokens:
                    for ft in fts:
                        suggestions[tok][ft] += 1

        sug_out = {}
        for tok, counter in suggestions.items():
            sug_out[tok] = [{"filterType": ft, "count": c} for ft, c in counter.most_common(8)]

        if sug_out:
            out_json = re.sub(r"\.xlsx?$", "", args.output) + "_rule_suggestions.json"
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(sug_out, f, ensure_ascii=False, indent=2)
            print(f"Rule suggestions saved: {out_json}")
    except Exception as e:
        print(f"[warn] rule suggestion dump failed: {type(e).__name__}: {str(e)[:80]}")



if __name__ == "__main__":
    main()
