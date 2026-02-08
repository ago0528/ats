
"""
지원자 관리 에이전트 검증 백오피스 (Streamlit)
- 목적:
  1) CSV(질의/기대필터)를 업로드해서 지원자 관리 에이전트를 1차/2차(동일 세션)로 호출
  2) "지원자 관리 에이전트 평가 프롬프트" 프레임워크에 맞춰 ChatGPT(OpenAI API)로 자동 평가(JSON)
  3) 결과를 표로 확인하고 Excel로 다운로드
  4) 필요 시 'URL Agent(이동/버튼URL)' 벌크 테스트도 같은 화면에서 실행

실행:
  streamlit run backoffice_app.py

.env (이 파일과 같은 폴더 권장):
  # ATS(채용솔루션) 토큰
  ATS_BEARER_TOKEN=...
  ATS_CMS_TOKEN=...
  ATS_MRS_SESSION=...

  # OpenAI (ChatGPT 평가)
  OPENAI_API_KEY=...
  OPENAI_MODEL=gpt-5.2

주의:
- 토큰/키는 절대 깃에 커밋하지 마세요.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

import aiohttp
import pandas as pd
import streamlit as st


# ============================================================
# 0) 유틸: .env 로드 (python-dotenv 없이도 동작)
# ============================================================
_DOTENV_LINE = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$')

def load_dotenv(dotenv_path: str) -> Dict[str, str]:
    """
    아주 심플한 .env 로더.
    - KEY=VALUE
    - # 주석 지원
    - VALUE의 따옴표(" or ') 제거
    - 이미 환경변수에 있는 값은 덮어쓰지 않음
    """
    loaded: Dict[str, str] = {}
    if not dotenv_path:
        return loaded
    if not os.path.exists(dotenv_path):
        return loaded

    with open(dotenv_path, "r", encoding="utf-8") as f:
        for raw in f.readlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            m = _DOTENV_LINE.match(line)
            if not m:
                continue
            k, v = m.group(1), m.group(2)
            v = v.strip()
            # strip quotes
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            if k not in os.environ:
                os.environ[k] = v
            loaded[k] = v
    return loaded


# ============================================================
# 1) 환경 프리셋 (DV/QA/ST/PR)
#    - DV/QA는 조직마다 달라질 수 있어 입력 필드로 override 가능
# ============================================================
ENV_PRESETS: Dict[str, Dict[str, str]] = {
    "PR": {
        "base_url": "https://api-llm.ats.kr-pr-midasin.com",
        "origin": "https://pr-jobda02-cms.recruiter.co.kr",
        "referer": "https://pr-jobda02-cms.recruiter.co.kr/",
    },
    "ST": {
        "base_url": "https://api-llm.ats.kr-st2-midasin.com",
        "origin": "https://st-jobda02-cms.recruiter.co.kr",
        "referer": "https://st-jobda02-cms.recruiter.co.kr/",
    },
    "DV": {"base_url": "", "origin": "", "referer": ""},
    "QA": {"base_url": "", "origin": "", "referer": ""},
}


# ============================================================
# 2) 평가 프롬프트 (기본값)
#    - 같은 폴더에 '지원자 관리 에이전트 평가 프롬프트_260202.md'가 있으면 자동 로드
# ============================================================
DEFAULT_EVAL_PROMPT_MD = """
# 지원자 관리 에이전트 평가 프롬프트

## 역할

당신은 채용솔루션의 '지원자 관리 에이전트'의 응답 품질을 평가하는 QA 전문가입니다.
사용자의 질의와 에이전트의 1차/2차 응답을 비교 분석하여 정확성과 일관성을 평가합니다.

---

## 평가 입력

```
질의 ID: {query_id}
질의 내용: {query}
기대 필터/열: {expected_filters}
1차 응답: {response_1}
2차 응답: {response_2}
```

---

## 평가 기준

### 1. 열/필터 정확성 (Filter Accuracy)

Response에서 추론 가능한 정보를 바탕으로 기대한 열/필터가 사용되었는지 판단합니다.

**추론 가능한 정보:**

- `assistantMessage` 내 언급된 조건 (예: "최근 1년 기준" → 기간 필터)
- `dataUIList.uiValue.columnName` (예: "채용분야", "TOEIC 평균" → 사용된 열)
- `dataUIList.uiValue.rowValue` (예: 실제 출력된 데이터 구조)
- 기타 Response에 포함된 모든 정보

**점수 기준 (0~5점):**

| 점수 | 기준                                                               |
| ---- | ------------------------------------------------------------------ |
| 5    | 기대 필터/열이 모두 정확하게 사용됨                                |
| 4    | 기대 필터/열 사용 + 기대하지 않은 추가 필터 존재 (유의사항에 기록) |
| 3    | 기대 필터/열 일부만 사용됨 (주요 필터는 포함)                      |
| 2    | 기대 필터/열과 유사하지만 다른 필터 사용                           |
| 1    | 기대 필터/열 대부분 누락                                           |
| 0    | 기대 필터/열과 완전히 무관한 결과 또는 응답 실패                   |

**기간 필터 특별 규칙:**

| 상황                                                          | 처리 방식                      |
| ------------------------------------------------------------- | ------------------------------ |
| 질의에 기간 미명시 + 응답에서 "1년/최근 1년/365일" 사용       | 정상 (Default 기간, 감점 없음) |
| 질의에 기간 미명시 + 응답에서 다른 기간 사용 (예: 3개월)      | 유의사항 기록 (4점)            |
| 질의에 "최근 3개월" 명시 + 응답에서 "최근 3개월" 사용         | 정상 (5점)                     |
| 질의에 "최근 3개월" 명시 + 응답에서 "1년" 또는 다른 기간 사용 | 감점 대상 (2~3점)              |

---

### 2. 답변 일관성 (Response Consistency)

1차 응답과 2차 응답이 의미적으로 동일한 결과를 반환했는지 판단합니다.

**비교 항목:**

- 핵심 수치 (지원자 수, 평균 점수, 비율 등)
- 순위/정렬 결과 (Top N 순서)
- 데이터 구조 (테이블 행/열 내용)

**점수 기준 (0~5점):**

| 점수 | 기준                                                             |
| ---- | ---------------------------------------------------------------- |
| 5    | 핵심 데이터(수치, 순위) 완전 일치                                |
| 4    | 핵심 데이터 일치 + 표현/포맷 차이 (테이블 컬럼 수, 문장 표현 등) |
| 3    | 핵심 데이터 대부분 일치, 일부 수치 미세 차이 (반올림, 소수점 등) |
| 2    | 핵심 데이터 일부만 일치, 순위나 주요 수치 불일치                 |
| 1    | 핵심 데이터 대부분 불일치                                        |
| 0    | 완전히 다른 결과 또는 1차/2차 중 응답 실패                       |

**판단 원칙:**

- 표현만 다르고 의미하는 바가 같으면 "일치"로 판단 (예: "152명입니다" vs "총 152명이에요")
- 숫자 포맷 차이는 감점하지 않음 (예: "990점" vs "990.0점")
- 테이블 컬럼 수나 순서 차이는 경미한 차이로 처리 (4점)

---

## 평가 출력 형식

```json
{
  "query_id": "{질의 ID}",
  "filter_accuracy": {
    "score": {0-5},
    "expected": ["{기대 필터/열 목록}"],
    "detected": ["{Response에서 감지된 필터/열 목록}"],
    "note": "{추가 필터 사용, 누락된 필터, 기간 필터 관련 사항 등}"
  },
  "consistency": {
    "score": {0-5},
    "matched": ["{일치하는 항목 목록}"],
    "diff": ["{차이나는 항목 목록}"],
    "note": "{표현 차이, 포맷 차이 등 유의사항}"
  },
  "total_score": {(filter_accuracy.score + consistency.score) / 2},
  "remarks": "{종합 의견 및 특이사항}"
}
```

---

## 평가 예시

### 입력

```
질의 ID: T-22
질의 내용: 채용분야별로 토익 평균이랑 학점 평균을 표로 보여주고 토익 평균 높은 순 Top 5로 정렬해줘
기대 필터/열: 지원분야 + 외국어시험 + 학점
1차 응답: {sample_1}
2차 응답: {sample_2}
```

### 출력

```json
{
  "query_id": "T-22",
  "filter_accuracy": {
    "score": 3,
    "expected": ["지원분야", "외국어시험", "학점"],
    "detected": ["지원분야", "외국어시험", "기간(최근 1년)"],
    "note": "학점 필터 미사용. 기간 필터는 Default(최근 1년) 사용으로 감점 없음."
  },
  "consistency": {
    "score": 4,
    "matched": [
      "1위 채용분야(경력-2-ㄹㅇㄴㅋㄴㅇㄹ)",
      "평균 점수(990점)",
      "Top 5 순위"
    ],
    "diff": ["테이블 컬럼 수 차이(5개 vs 3개)", "채용분야명 오타 차이"],
    "note": "핵심 데이터 일치, 출력 포맷과 상세 컬럼만 상이"
  },
  "total_score": 3.5,
  "remarks": "1차 답변이 더 상세한 테이블(최소/최대 컬럼 포함) 제공. 핵심 결과는 동일하나 학점 필터가 적용되지 않아 filter_accuracy 3점 처리."
}
```

---

## 주의사항

1. Response 구조는 샘플 외에도 다양한 형태로 제공될 수 있습니다. `assistantMessage`, `dataUIList`, `guideList` 등 모든 필드를 종합적으로 분석하세요.

2. 의미 기반 집합 필터(SKY, 인서울, 지거국, 이공계 등)는 정확한 범위 정의가 어려울 수 있으므로, 합리적인 범위 내에서 사용되었다면 정상으로 판단합니다.

3. 에이전트가 추가 질문을 던지거나 가이드를 제공한 경우(`guideList`), 이는 평가에서 감점 요소가 아닙니다.

4. 1차/2차 응답 시간 차이는 평가 지표에 포함하지 않습니다. (참고용)

5. 평가 결과는 최종적으로 CSV/엑셀로 저장될 예정이므로, JSON 형식을 정확히 준수하세요.

6. **기간 필터 판단 시**: "1년", "최근 1년", "365일"은 시스템 Default 기간이므로, 질의에 기간이 명시되지 않은 경우 이 값들이 사용되어도 감점하지 않습니다. 단, 질의에서 특정 기간(예: "최근 3개월", "작년 하반기")을 명시했는데 에이전트가 다른 기간을 사용했다면 이는 감점 대상입니다.

"""


def read_prompt_template(script_dir: str) -> str:
    """
    1) ./지원자 관리 에이전트 평가 프롬프트_260202.md 있으면 그걸 사용
    2) 없으면 DEFAULT_EVAL_PROMPT_MD 사용
    """
    cand = os.path.join(script_dir, "지원자 관리 에이전트 평가 프롬프트_260202.md")
    if os.path.exists(cand):
        try:
            with open(cand, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    return DEFAULT_EVAL_PROMPT_MD


def safe_fill_template(template: str, mapping: Dict[str, str]) -> str:
    """
    str.format()은 JSON 예시의 { } 때문에 깨질 수 있어, 안전하게 치환.
    """
    out = template
    for k, v in mapping.items():
        out = out.replace("{" + k + "}", v)
    return out


# ============================================================
# 3) ATS 에이전트 호출 (지원자 관리)
# ============================================================
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
        self, session: aiohttp.ClientSession, message: str, conversation_id: Optional[str]
    ) -> Tuple[Optional[str], str]:
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
            return None, f"{type(e).__name__}: {str(e)[:120]}"

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

    async def run_double(
        self, session: aiohttp.ClientSession, query: str
    ) -> Tuple[Optional[AgentResponse], Optional[AgentResponse], str]:
        # 1차
        conv_id, err = await self.send_query(session, query, conversation_id=None)
        if not conv_id:
            return None, None, f"send_query#1 failed: {err}"

        r1 = await self.subscribe_sse(session, conv_id)
        if r1.error:
            return r1, None, f"sse#1 failed: {r1.error}"

        # 2차 (동일 conversationId)
        conv_id2, err2 = await self.send_query(session, query, conversation_id=conv_id)
        if not conv_id2:
            return r1, None, f"send_query#2 failed: {err2}"

        r2 = await self.subscribe_sse(session, conv_id2)
        if r2.error:
            return r1, r2, f"sse#2 failed: {r2.error}"

        return r1, r2, ""


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

def make_arrow_safe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Streamlit(st.dataframe)에서 pyarrow 변환 실패를 막기 위한 정리:
    - ''(빈문자) -> NA
    - 숫자 컬럼(시간/점수) -> to_numeric(errors='coerce')
    - 텍스트 컬럼은 string dtype으로 고정
    """
    if df is None or df.empty:
        return df

    df = df.copy()

    # 1) 빈 문자열을 결측으로
    df.replace({"": pd.NA}, inplace=True)

    # 2) 시간/점수 계열 컬럼은 숫자로 강제 변환 (안되면 NA)
    numeric_candidates = []
    for c in df.columns:
        if "(초)" in c:
            numeric_candidates.append(c)
        if c.endswith("_score") or c.endswith("score"):
            numeric_candidates.append(c)

    for c in set(numeric_candidates):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # 3) 사람이 쓰는 결과 텍스트 컬럼은 string으로 고정
    text_cols = ["열/필터 일치 여부", "답변 일관성", "차이 유형", "특이사항", "에러"]
    for c in text_cols:
        if c in df.columns:
            df[c] = df[c].astype("string")

    return df

# ============================================================
# 5) OpenAI Judge (ChatGPT) - 평가 프롬프트 기반 JSON 출력
#    - 룰북/정규식으로 "판정"하지 않고, 프롬프트에 정의된 기준대로 LLM이 JSON을 생성
# ============================================================
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def extract_openai_output_text(resp_json: Dict[str, Any]) -> str:
    """
    Responses API 응답에서 텍스트를 최대한 안전하게 추출.
    - SDK의 output_text와 달리 raw JSON에서는 output 배열을 파싱해야 할 수 있음.
    """
    if isinstance(resp_json, dict) and isinstance(resp_json.get("output_text"), str):
        return resp_json["output_text"]

    out = resp_json.get("output", [])
    texts: List[str] = []
    if isinstance(out, list):
        for item in out:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "message":
                content = item.get("content", [])
                if isinstance(content, list):
                    for c in content:
                        if not isinstance(c, dict):
                            continue
                        ctype = c.get("type")
                        if ctype in ("output_text", "text"):
                            t = c.get("text")
                            if isinstance(t, str):
                                texts.append(t)
            # 일부 응답은 output에 바로 text가 올 수도 있어 방어적으로 처리
            if isinstance(item.get("text"), str):
                texts.append(item["text"])
    return "\n".join(texts).strip()


def coerce_int_0_100(x: Any) -> int:
    try:
        v = int(float(x))
    except Exception:
        return 0
    return max(0, min(100, v))


def robust_json_loads(s: str) -> Optional[Dict[str, Any]]:
    """
    1) 그대로 json.loads
    2) 실패 시: 첫 '{'부터 마지막 '}'까지 잘라서 재시도
    """
    if not s:
        return None
    s = s.strip()
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            obj = json.loads(s[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    return None


async def openai_judge_once(
    session: aiohttp.ClientSession,
    api_key: str,
    model: str,
    prompt_text: str,
    timeout_sec: int = 90,
) -> Tuple[Optional[Dict[str, Any]], str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # JSON mode on Responses API: text.format.type = "json_object"
    # (JSON 문자열이 컨텍스트에 포함되어야 한다는 조건도 있으므로 system에 JSON 명시)
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": "You are a QA evaluator. Output MUST be a valid JSON object and nothing else. JSON only.",
            },
            {"role": "user", "content": prompt_text},
        ],
        "text": {"format": {"type": "json_object"}},
        "temperature": 0,
    }

    try:
        async with session.post(OPENAI_RESPONSES_URL, headers=headers, json=payload, timeout=timeout_sec) as resp:
            text = await resp.text()
            if resp.status != 200:
                return None, f"OpenAI HTTP {resp.status}: {text[:250]}"
            data = json.loads(text)
            out_text = extract_openai_output_text(data)
            parsed = robust_json_loads(out_text)
            if parsed is None:
                return None, f"OpenAI output is not JSON. raw={out_text[:200]}"
            return parsed, ""
    except asyncio.TimeoutError:
        return None, f"OpenAI timeout({timeout_sec}s)"
    except Exception as e:
        return None, f"OpenAI error: {type(e).__name__}: {str(e)[:200]}"


async def openai_judge_with_retry(
    session: aiohttp.ClientSession,
    api_key: str,
    model: str,
    prompt_text: str,
    max_retries: int = 2,
) -> Tuple[Optional[Dict[str, Any]], str]:
    wait = 2.0
    last_err = ""
    for attempt in range(max_retries + 1):
        result, err = await openai_judge_once(session, api_key, model, prompt_text)
        if result is not None and not err:
            return result, ""
        last_err = err or "unknown"
        # 간단 백오프 (429/5xx가 많아서)
        await asyncio.sleep(wait)
        wait *= 2
    return None, last_err


def postprocess_eval_json(obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    - score 필드 정수화/클램프
    - total_score 재계산(안전)
    - 누락 키 방어적으로 채움
    """
    out = obj.copy()

    fa = out.get("filter_accuracy") if isinstance(out.get("filter_accuracy"), dict) else {}
    con = out.get("consistency") if isinstance(out.get("consistency"), dict) else {}

    fa_score = coerce_int_0_100(fa.get("score"))
    con_score = coerce_int_0_100(con.get("score"))

    fa["score"] = fa_score
    con["score"] = con_score

    # 리스트 기본값
    fa["expected"] = fa.get("expected") if isinstance(fa.get("expected"), list) else []
    fa["detected"] = fa.get("detected") if isinstance(fa.get("detected"), list) else []
    fa["note"] = str(fa.get("note") or "")

    con["matched"] = con.get("matched") if isinstance(con.get("matched"), list) else []
    con["diff"] = con.get("diff") if isinstance(con.get("diff"), list) else []
    con["note"] = str(con.get("note") or "")

    out["filter_accuracy"] = fa
    out["consistency"] = con

    out["total_score"] = (fa_score * 0.5) + (con_score * 0.5)
    out["remarks"] = str(out.get("remarks") or "")

    return out


def derive_csv_fields_from_eval(eval_json: Dict[str, Any]) -> Dict[str, str]:
    """
    CSV 템플릿 컬럼(열/필터 일치 여부, 답변 일관성, 차이 유형, 특이사항)을
    LLM 평가 결과(JSON)에서 도출.
    """
    fa = eval_json.get("filter_accuracy", {}) or {}
    con = eval_json.get("consistency", {}) or {}

    fa_score = int(fa.get("score", 0))
    con_score = int(con.get("score", 0))

    # 기준: 프롬프트 정의 그대로(80 이상은 기대필터 사용 + 추가필터)
    filter_pass = "PASS" if fa_score >= 4 else "FAIL"
    consistency = "일치" if con_score >= 4 else "차이 발생"

    # 차이 유형 (검증 규칙 문서의 분류를 LLM 평가 결과로 매핑)
    diff_type = ""
    if fa_score < 80:
        diff_type = "열/필터 변경"
    else:
        if con_score < 80:
            diff_type = "통계값만 변경"
        elif con_score < 100:
            diff_type = "표현만 변경"
        else:
            diff_type = ""

    note_parts = []
    fa_note = str(fa.get("note") or "").strip()
    con_note = str(con.get("note") or "").strip()
    remarks = str(eval_json.get("remarks") or "").strip()

    for s in [fa_note, con_note, remarks]:
        if s and s not in note_parts:
            note_parts.append(s)

    return {
        "열/필터 일치 여부": filter_pass,
        "답변 일관성": consistency,
        "차이 유형": diff_type,
        "특이사항": " / ".join(note_parts),
    }


# ============================================================
# 6) 비동기 러너 (Streamlit에서 안전하게 실행)
# ============================================================
def run_async(coro):
    """
    Streamlit 내부에서 asyncio.run()이 충돌하는 경우가 있어,
    새 이벤트 루프를 만들어 run_until_complete로 실행.
    (기존 URL Agent 툴이 쓰던 방식과 동일)
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ============================================================
# 7) Applicant bulktest (호출) + Judge (평가)
# ============================================================
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def get_col(df: pd.DataFrame, name: str) -> Optional[str]:
    for c in df.columns:
        if c.strip() == name:
            return c
    return None


def is_blank(x: Any) -> bool:
    if x is None:
        return True
    s = str(x)
    return not s.strip() or s.strip().lower() == "nan"


def truncate_text(s: str, max_chars: int) -> str:
    if not s:
        return ""
    s = str(s)
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + f"\n...(truncated, {len(s)} chars total)"


def build_surrogate_response_payload(row: pd.Series, prefix: str) -> Optional[Dict[str, Any]]:
    """
    기존 CSV에 raw(assistant payload)가 없을 때를 대비한 fallback.
    - {prefix} 답변 / {prefix} buttonUrl 로 최소한의 Response 구조를 복원한다.
    - 프롬프트 평가 기준은 'Response에서 추론 가능한 정보'이므로,
      최소한 assistantMessage + buttonUrl만 있어도 LLM이 일정 수준 판정 가능.
    """
    msg = str(row.get(f"{prefix} 답변", "") or "").strip()
    btn = str(row.get(f"{prefix} buttonUrl", "") or "").strip()

    if not msg and not btn:
        return None

    data_ui_list = []
    if btn:
        data_ui_list = [
            {
                "uiDescription": "지원자 관리(추정)",
                "uiValue": {
                    "formType": "LINK",
                    "buttonUrl": btn,
                },
            }
        ]

    return {
        "assistantMessage": msg,
        "dataUIList": data_ui_list,
        "guideList": [],
    }


async def run_applicant_calls_async(
    df: pd.DataFrame,
    client: ApplicantAgentClient,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    only_missing: bool = True,
    limit_rows: Optional[int] = None,
) -> pd.DataFrame:
    """
    CSV df를 받아, 지원자 에이전트를 1차/2차로 호출해 df에 컬럼을 채움.
    (이 단계에서는 '평가'를 하지 않음)
    """
    df = df.copy()

    id_col = get_col(df, "ID") or "ID"
    query_col = get_col(df, "질의") or "질의"

    # 출력 컬럼 확보
    for c in ["1차 답변", "1차 답변 시간(초)", "2차 답변", "2차 답변 시간(초)", "1차 raw", "2차 raw",
              "1차 buttonUrl", "2차 buttonUrl", "1차 detected_filterTypes", "2차 detected_filterTypes"]:
        if c not in df.columns:
            df[c] = ""

    # 대상 row 인덱스 구성
    target_idxs: List[int] = []
    for i, r in df.iterrows():
        if limit_rows is not None and len(target_idxs) >= limit_rows:
            break
        if only_missing:
            if (not is_blank(r.get("1차 답변"))) and (not is_blank(r.get("2차 답변"))):
                continue
        target_idxs.append(i)

    total = len(target_idxs)
    if total == 0:
        return df

    connector = aiohttp.TCPConnector(limit=50, ssl=False)
    timeout = aiohttp.ClientTimeout(total=120)

    done = 0
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = []

        async def _run_one(idx: int):
            async with client.semaphore:
                query = str(df.loc[idx, query_col])
                r1, r2, err = await client.run_double(session, query)

                out = {
                    "idx": idx,
                    "err": err,
                    "r1": r1,
                    "r2": r2,
                }
                return out

        for idx in target_idxs:
            tasks.append(asyncio.create_task(_run_one(idx)))

        for fut in asyncio.as_completed(tasks):
            res = await fut
            idx = res["idx"]
            err = res["err"]
            r1: Optional[AgentResponse] = res["r1"]
            r2: Optional[AgentResponse] = res["r2"]

            if r1:
                df.at[idx, "1차 답변"] = r1.assistant_message
                df.at[idx, "1차 답변 시간(초)"] = round(r1.response_time_sec, 2) if r1.response_time_sec is not None else ""
                df.at[idx, "1차 raw"] = json.dumps(r1.assistant_payload, ensure_ascii=False)
                df.at[idx, "1차 buttonUrl"] = r1.button_url
                p1 = parse_button_url(r1.button_url)
                df.at[idx, "1차 detected_filterTypes"] = ",".join(p1["filter_types"])
            if r2:
                df.at[idx, "2차 답변"] = r2.assistant_message
                df.at[idx, "2차 답변 시간(초)"] = round(r2.response_time_sec, 2) if r2.response_time_sec is not None else ""
                df.at[idx, "2차 raw"] = json.dumps(r2.assistant_payload, ensure_ascii=False)
                df.at[idx, "2차 buttonUrl"] = r2.button_url
                p2 = parse_button_url(r2.button_url)
                df.at[idx, "2차 detected_filterTypes"] = ",".join(p2["filter_types"])

            if err:
                # 특이사항 칼럼이 있으면 에러를 남기되, 평가 단계에서 제외할 수 있음
                if "특이사항" not in df.columns:
                    df["특이사항"] = ""
                df.at[idx, "특이사항"] = str(err)

            done += 1
            if progress_cb:
                progress_cb(done, total, f"[{df.loc[idx, id_col]}] calls done (err={bool(err)})")

    return df


async def run_openai_judge_async(
    df: pd.DataFrame,
    prompt_template: str,
    api_key: str,
    model: str,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    only_missing: bool = True,
    limit_rows: Optional[int] = None,
    max_chars_per_response: int = 15000,
    max_parallel: int = 3,
) -> pd.DataFrame:
    """
    df에 있는 1차/2차 raw를 바탕으로 OpenAI 평가를 수행하고, 결과 컬럼을 채움.
    """
    df = df.copy()
    df = normalize_columns(df)

    id_col = get_col(df, "ID") or "ID"
    query_col = get_col(df, "질의") or "질의"
    expected_col = get_col(df, "기대 필터/열") or "기대 필터/열"

    # 평가 결과 컬럼 확보
    out_cols = [
        "llm_eval_json",
        "filter_accuracy_score",
        "filter_accuracy_expected",
        "filter_accuracy_detected",
        "filter_accuracy_note",
        "consistency_score",
        "consistency_matched",
        "consistency_diff",
        "consistency_note",
        "total_score",
        "remarks",
    ]
    for c in out_cols:
        if c not in df.columns:
            df[c] = ""

    # 템플릿 컬럼들(있으면 채움)
    for c in ["열/필터 일치 여부", "답변 일관성", "차이 유형", "특이사항"]:
        if c not in df.columns:
            df[c] = ""

    # 대상 row 인덱스 구성
    target_idxs: List[int] = []
    for i, r in df.iterrows():
        if limit_rows is not None and len(target_idxs) >= limit_rows:
            break

        # 평가 입력 준비: raw가 없으면 assistantMessage/buttonUrl에서 surrogate 구성
        if is_blank(r.get("1차 raw")):
            surrogate1 = build_surrogate_response_payload(r, "1차")
            if surrogate1 is not None:
                df.at[i, "1차 raw"] = json.dumps(surrogate1, ensure_ascii=False)

        if is_blank(r.get("2차 raw")):
            surrogate2 = build_surrogate_response_payload(r, "2차")
            if surrogate2 is not None:
                df.at[i, "2차 raw"] = json.dumps(surrogate2, ensure_ascii=False)

        if is_blank(r.get("1차 raw")) or is_blank(r.get("2차 raw")):
            continue  # 호출 결과가 없으면 평가 불가

        if only_missing and (not is_blank(r.get("llm_eval_json"))):
            continue

        # 기존 에러가 있으면 스킵(원하면 UI에서 override 가능하게 만들 수 있음)
        if isinstance(r.get("특이사항"), str) and "send_query" in r.get("특이사항"):
            continue

        target_idxs.append(i)

    total = len(target_idxs)
    if total == 0:
        return df

    sem = asyncio.Semaphore(max_parallel)

    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:

        async def _judge_one(idx: int) -> Dict[str, Any]:
            async with sem:
                qid = str(df.loc[idx, id_col])
                query = str(df.loc[idx, query_col])
                expected = str(df.loc[idx, expected_col])

                r1_raw = truncate_text(str(df.loc[idx, "1차 raw"]), max_chars_per_response)
                r2_raw = truncate_text(str(df.loc[idx, "2차 raw"]), max_chars_per_response)

                prompt_text = safe_fill_template(
                    prompt_template,
                    {
                        "query_id": qid,
                        "query": query,
                        "expected_filters": expected,
                        "response_1": r1_raw,
                        "response_2": r2_raw,
                    },
                )

                eval_obj, err = await openai_judge_with_retry(session, api_key, model, prompt_text)
                return {"idx": idx, "qid": qid, "eval": eval_obj, "err": err}

        tasks = [asyncio.create_task(_judge_one(idx)) for idx in target_idxs]

        done = 0
        for fut in asyncio.as_completed(tasks):
            res = await fut
            idx = res["idx"]
            qid = res["qid"]
            err = res["err"]
            eval_obj = res["eval"]

            if eval_obj is None:
                df.at[idx, "특이사항"] = f"LLM 평가 실패: {err}"
            else:
                eval_obj = postprocess_eval_json(eval_obj)
                df.at[idx, "llm_eval_json"] = json.dumps(eval_obj, ensure_ascii=False)
                df.at[idx, "filter_accuracy_score"] = eval_obj["filter_accuracy"]["score"]
                df.at[idx, "filter_accuracy_expected"] = ",".join(eval_obj["filter_accuracy"]["expected"])
                df.at[idx, "filter_accuracy_detected"] = ",".join(eval_obj["filter_accuracy"]["detected"])
                df.at[idx, "filter_accuracy_note"] = eval_obj["filter_accuracy"]["note"]

                df.at[idx, "consistency_score"] = eval_obj["consistency"]["score"]
                df.at[idx, "consistency_matched"] = ",".join(eval_obj["consistency"]["matched"])
                df.at[idx, "consistency_diff"] = ",".join(eval_obj["consistency"]["diff"])
                df.at[idx, "consistency_note"] = eval_obj["consistency"]["note"]

                df.at[idx, "total_score"] = eval_obj["total_score"]
                df.at[idx, "remarks"] = eval_obj["remarks"]

                # CSV 템플릿 컬럼 채움
                derived = derive_csv_fields_from_eval(eval_obj)
                for k, v in derived.items():
                    if k in df.columns:
                        df.at[idx, k] = v

            done += 1
            if progress_cb:
                progress_cb(done, total, f"[{qid}] judge done (err={bool(err)})")

    return df


def dataframe_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "results") -> bytes:
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return bio.getvalue()


# ============================================================
# 8) URL Agent 벌크테스트 (간단 버전)
#    - 기존 URL Agent 코드를 "백오피스 탭"으로 옮긴 축약판
# ============================================================
class UrlAgentTester:
    def __init__(self, base_url: str, bearer_token: str, cms_token: str, mrs_session: str, origin: str, referer: str, max_parallel: int = 1):
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token.strip()
        self.cms_token = cms_token.strip()
        self.mrs_session = mrs_session.strip()
        self.origin = origin.strip()
        self.referer = referer.strip()
        self.semaphore = asyncio.Semaphore(max_parallel)

    def get_headers(self, for_sse: bool = False) -> dict:
        headers = {
            "authorization": f"Bearer {self.bearer_token}",
            "cms-access-token": self.cms_token,
            "mrs-session": self.mrs_session,
            "origin": self.origin,
            "referer": self.referer,
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        if for_sse:
            headers["accept"] = "text/event-stream"
        else:
            headers["accept"] = "application/json, text/plain, */*"
            headers["content-type"] = "application/json"
        return headers

    async def send_query(self, session: aiohttp.ClientSession, message: str) -> tuple[Optional[str], str]:
        url = f"{self.base_url}/api/v2/ai/orchestrator/query"
        payload = {"conversationId": None, "userMessage": message}
        try:
            async with session.post(url, headers=self.get_headers(), json=payload, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("conversationId"), ""
                else:
                    error_text = await response.text()
                    return None, f"HTTP {response.status}: {error_text[:200]}"
        except asyncio.TimeoutError:
            return None, "timeout(30s)"
        except Exception as e:
            return None, f"{type(e).__name__}: {str(e)[:120]}"

    async def subscribe_sse_get_buttonurl(self, session: aiohttp.ClientSession, conversation_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/ai/orchestrator/chat-room/sse/subscribe"
        params = {"conversationId": conversation_id}

        connect_time: Optional[datetime] = None
        chat_time: Optional[datetime] = None
        button_url: str = ""
        error_msg: str = ""

        buffer = ""
        current_event = None
        last_heartbeat = datetime.now()

        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with session.get(url, headers=self.get_headers(for_sse=True), params=params, timeout=timeout) as response:
                async for chunk in response.content.iter_any():
                    buffer += chunk.decode("utf-8", errors="ignore")

                    if (datetime.now() - last_heartbeat).total_seconds() > 30:
                        error_msg = "heartbeat timeout(30s)"
                        break

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
                            if current_event == "CHAT" and data_str.startswith("{"):
                                try:
                                    data = json.loads(data_str)
                                except Exception:
                                    continue
                                if data.get("messageType") == "ASSISTANT":
                                    chat_time = datetime.now()
                                    assistant = data.get("assistant", {}) or {}
                                    for ui in assistant.get("dataUIList", []) or []:
                                        ui_value = (ui or {}).get("uiValue", {}) or {}
                                        if "buttonUrl" in ui_value:
                                            button_url = str(ui_value["buttonUrl"])
                                            break
                                    rt = "-"
                                    if connect_time and chat_time:
                                        rt = f"{(chat_time - connect_time).total_seconds():.2f}"
                                    return {
                                        "응답시간(초)": rt,
                                        "실제URL": button_url or "-",
                                        "실패사유": "" if button_url else "URL 미반환",
                                    }
        except asyncio.TimeoutError:
            error_msg = "sse timeout(60s)"
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)[:80]}"

        return {"응답시간(초)": "-", "실제URL": "-", "실패사유": error_msg or "알 수 없는 오류"}

    async def run_one(self, session: aiohttp.ClientSession, row: Dict[str, str]) -> Dict[str, Any]:
        async with self.semaphore:
            qid = row.get("ID", "")
            query = row.get("질의", "")
            expected_url = row.get("기대URL", "")

            conv_id, err = await self.send_query(session, query)
            if not conv_id:
                return {
                    "ID": qid,
                    "질의": query,
                    "기대URL": expected_url,
                    "성공여부": "FAIL",
                    "실패사유": err,
                    "실제URL": "-",
                    "응답시간(초)": "-",
                }

            r = await self.subscribe_sse_get_buttonurl(session, conv_id)
            actual = r.get("실제URL", "-")
            success = "PASS"
            fail_reason = ""
            if expected_url:
                # 단순 포함/정규식 둘 다 지원 (정규식: /.../ 형태)
                if expected_url.startswith("/") and expected_url.endswith("/") and len(expected_url) > 2:
                    pat = expected_url[1:-1]
                    try:
                        if not re.search(pat, actual):
                            success = "FAIL"
                            fail_reason = "정규식 불일치"
                    except re.error:
                        success = "FAIL"
                        fail_reason = "정규식 오류"
                else:
                    if expected_url not in actual:
                        success = "FAIL"
                        fail_reason = "URL 불일치"
            if r.get("실패사유"):
                success = "FAIL"
                fail_reason = r.get("실패사유")

            return {
                "ID": qid,
                "질의": query,
                "기대URL": expected_url,
                "성공여부": success,
                "실패사유": fail_reason,
                "실제URL": actual,
                "응답시간(초)": r.get("응답시간(초)", "-"),
            }


async def run_url_tests_async(
    rows: List[Dict[str, str]],
    tester: UrlAgentTester,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> pd.DataFrame:
    connector = aiohttp.TCPConnector(limit=50, ssl=False)
    timeout = aiohttp.ClientTimeout(total=120)
    results: List[Dict[str, Any]] = []

    total = len(rows)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [asyncio.create_task(tester.run_one(session, r)) for r in rows]
        done = 0
        for fut in asyncio.as_completed(tasks):
            res = await fut
            results.append(res)
            done += 1
            if progress_cb:
                progress_cb(done, total, f"[{res.get('ID')}] url test done ({res.get('성공여부')})")
    return pd.DataFrame(results)


# ============================================================
# 9) Streamlit UI
# ============================================================
def main():
    st.set_page_config(page_title="지원자 관리 에이전트 검증 백오피스", page_icon="🧪", layout="wide")

    script_dir = os.path.dirname(os.path.abspath(__file__))

    # .env 자동 로드
    loaded_env = load_dotenv(os.path.join(script_dir, ".env"))

    st.title("🧪 지원자 관리·이동 에이전트 검증 백오피스")

    with st.sidebar:
        st.header("설정")
        st.caption("토큰/키는 .env 또는 아래 입력으로 주입하세요. (커밋 금지)")

        # ENV 선택
        env = st.selectbox("환경 (DV/QA/ST/PR)", ["PR", "ST", "QA", "DV"], index=0)
        preset = ENV_PRESETS.get(env, {})

        base_url = st.text_input("ATS base_url", value=preset.get("base_url", ""), placeholder="https://api-llm....")
        origin = st.text_input("origin", value=preset.get("origin", ""), placeholder="https://...cms...")
        referer = st.text_input("referer", value=preset.get("referer", ""), placeholder="https://.../")

        st.divider()
        st.subheader("ATS 토큰")
        bearer = st.text_input("ATS_BEARER_TOKEN", value=os.getenv("ATS_BEARER_TOKEN", ""), type="password")
        cms = st.text_input("ATS_CMS_TOKEN", value=os.getenv("ATS_CMS_TOKEN", ""), type="password")
        mrs = st.text_input("ATS_MRS_SESSION", value=os.getenv("ATS_MRS_SESSION", ""), type="password")

        st.divider()
        st.subheader("OpenAI (ChatGPT 평가)")
        openai_key = st.text_input("OPENAI_API_KEY", value=os.getenv("OPENAI_API_KEY", ""), type="password")
        openai_model = st.text_input("OPENAI_MODEL", value=os.getenv("OPENAI_MODEL", "gpt-5.2"))
        judge_parallel = st.slider("LLM 병렬수", min_value=1, max_value=10, value=3, step=1)
        max_chars = st.slider("응답 최대 길이(평가 입력)", min_value=2000, max_value=30000, value=15000, step=1000)

        st.divider()
        st.subheader("실행 옵션")
        agent_parallel = st.slider("ATS 호출 병렬수", min_value=1, max_value=10, value=3, step=1)
        only_missing = st.checkbox("이미 채워진 row는 스킵", value=True)
        limit_rows = st.number_input("상위 N개만 실행 (0=전체)", min_value=0, value=0, step=1)
        limit_rows = None if int(limit_rows) == 0 else int(limit_rows)

        st.caption("✅ .env 로드됨" if loaded_env else "⚠️ .env 미로드(없거나 비어있음)")

    tab1, tab2 = st.tabs(["지원자 에이전트 검증", "URL Agent (이동) 테스트"])

    # --------------------------------------------
    # Tab 1: Applicant Agent
    # --------------------------------------------
    with tab1:
        st.subheader("1) CSV 업로드")
        uploaded = st.file_uploader("지원자 관리 질의 CSV", type=["csv"])

        # 프롬프트 템플릿 로드 + 편집
        st.subheader("2) 평가 프롬프트")
        prompt_default = read_prompt_template(script_dir)
        prompt_text = st.text_area("평가 프롬프트(수정 가능)", value=prompt_default, height=320)

        if uploaded is None:
            st.info("CSV를 업로드하면 실행할 수 있어요.")
            return

        try:
            df_in = pd.read_csv(uploaded, encoding="utf-8")
        except Exception:
            df_in = pd.read_csv(uploaded, encoding="utf-8-sig")
        df_in = normalize_columns(df_in)

        st.write("미리보기", df_in.head(10))

        # 실행 버튼
        colA, colB, colC = st.columns(3)
        run_calls = colA.button("① ATS 호출만 실행")
        run_judge = colB.button("② LLM 평가만 실행")
        run_all = colC.button("③ 전체 실행(호출+평가)")

        progress = st.progress(0)
        log_area = st.empty()

        def progress_cb(done: int, total: int, msg: str):
            if total > 0:
                progress.progress(min(1.0, done / total))
            log_area.write(msg)

        # 상태 df는 session_state에 보관
        if "applicant_df" not in st.session_state:
            st.session_state["applicant_df"] = df_in

        # 버튼을 누르면 session_state를 기준으로 실행
        if run_calls or run_all:
            if not (base_url and origin and referer and bearer and cms and mrs):
                st.error("ATS 설정(base_url/origin/referer)과 토큰 3종을 입력하세요.")
            else:
                client = ApplicantAgentClient(
                    base_url=base_url,
                    bearer_token=bearer,
                    cms_token=cms,
                    mrs_session=mrs,
                    origin=origin,
                    referer=referer,
                    max_parallel=agent_parallel,
                )
                st.session_state["applicant_df"] = run_async(
                    run_applicant_calls_async(
                        st.session_state["applicant_df"],
                        client,
                        progress_cb=progress_cb,
                        only_missing=only_missing,
                        limit_rows=limit_rows,
                    )
                )
                st.success("ATS 호출 완료")

        if run_judge or run_all:
            if not openai_key:
                st.error("OPENAI_API_KEY를 입력하세요.")
            else:
                st.session_state["applicant_df"] = run_async(
                    run_openai_judge_async(
                        st.session_state["applicant_df"],
                        prompt_template=prompt_text,
                        api_key=openai_key,
                        model=openai_model,
                        progress_cb=progress_cb,
                        only_missing=only_missing,
                        limit_rows=limit_rows,
                        max_chars_per_response=max_chars,
                        max_parallel=judge_parallel,
                    )
                )
                st.success("LLM 평가 완료")

        df_out = st.session_state["applicant_df"]

        st.subheader("3) 결과 요약")
        # 기본 요약
        total_rows = len(df_out)
        err_rows = df_out["특이사항"].astype(str).str.contains("fail|timeout|HTTP|LLM 평가 실패", case=False, na=False).sum() if "특이사항" in df_out.columns else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("총 Row", total_rows)
        c2.metric("에러/특이", int(err_rows))
        if "total_score" in df_out.columns:
            try:
                avg_total = float(pd.to_numeric(df_out["total_score"], errors="coerce").dropna().mean())
            except Exception:
                avg_total = 0.0
            c3.metric("평균 total_score", f"{avg_total:.1f}")

        st.subheader("4) 결과 테이블")
        st.dataframe(make_arrow_safe(df_out), use_container_width=True, height=420)


        st.subheader("5) 다운로드")
        xlsx_bytes = dataframe_to_excel_bytes(df_out, sheet_name="applicant_results")
        st.download_button(
            "📥 결과 Excel 다운로드",
            data=xlsx_bytes,
            file_name=f"applicant_agent_results_{env}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # --------------------------------------------
    # Tab 2: URL Agent
    # --------------------------------------------
    with tab2:
        st.subheader("URL Agent 테스트 입력")
        st.caption("CSV 컬럼 예시: ID, 질의, 기대URL (기대URL은 부분문자열 또는 /정규식/ 형태 지원)")
        up2 = st.file_uploader("URL 테스트 CSV", type=["csv"], key="urlcsv")

        if up2 is None:
            st.info("URL 테스트용 CSV를 업로드하세요.")
            return

        try:
            df2 = pd.read_csv(up2, encoding="utf-8")
        except Exception:
            df2 = pd.read_csv(up2, encoding="utf-8-sig")
        df2 = normalize_columns(df2)

        st.write("미리보기", df2.head(10))

        if not (base_url and origin and referer and bearer and cms and mrs):
            st.warning("좌측 설정에서 ATS 환경/토큰을 입력하세요.")
        else:
            tester = UrlAgentTester(
                base_url=base_url,
                bearer_token=bearer,
                cms_token=cms,
                mrs_session=mrs,
                origin=origin,
                referer=referer,
                max_parallel=agent_parallel,
            )

            rows = []
            for _, r in df2.iterrows():
                rows.append(
                    {
                        "ID": str(r.get("ID", "")),
                        "질의": str(r.get("질의", "")),
                        "기대URL": str(r.get("기대URL", "")),
                    }
                )

            run_url = st.button("URL 테스트 실행")
            progress2 = st.progress(0)
            log2 = st.empty()

            def progress_cb2(done: int, total: int, msg: str):
                if total > 0:
                    progress2.progress(min(1.0, done / total))
                log2.write(msg)

            if run_url:
                df_url_out = run_async(run_url_tests_async(rows, tester, progress_cb=progress_cb2))
                st.session_state["url_df"] = df_url_out
                st.success("URL 테스트 완료")

            if "url_df" in st.session_state:
                df_url_out = st.session_state["url_df"]
                st.dataframe(df_url_out, use_container_width=True, height=420)

                xlsx_bytes = dataframe_to_excel_bytes(df_url_out, sheet_name="url_results")
                st.download_button(
                    "📥 URL 결과 Excel 다운로드",
                    data=xlsx_bytes,
                    file_name=f"url_agent_results_{env}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )


if __name__ == "__main__":
    main()
