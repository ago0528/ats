
"""
채용 에이전트 검증 백오피스 / 업데이트일자: 260205
- 목적:
  1) CSV(질의/기대필터)를 업로드해서 지원자 관리 에이전트를 1차/2차(동일 세션)로 호출
  2) "지원자 관리 에이전트 평가 프롬프트" 프레임워크에 맞춰 ChatGPT(OpenAI API)로 자동 평가(JSON)
  3) 결과를 표로 확인하고 Excel로 다운로드
  4) 필요 시 'URL Agent(이동/버튼URL)' 벌크 테스트도 같은 화면에서 실행

실행:
  streamlit run backoffice_app_v3.1.0.py

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
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

import aiohttp
import pandas as pd
import streamlit as st

# 상위 폴더(ax)의 모듈을 import하기 위해 경로 추가
_AX_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _AX_DIR not in sys.path:
    sys.path.insert(0, _AX_DIR)

from curl_parsing import parse_curl_headers
from prompt_api import (
    AxPromptApiClient,
    WORKER_TYPES,
    WORKER_DESCRIPTIONS,
    safe_len,
)




# ============================================================
# Arrow-safe DataFrame (Streamlit st.dataframe용)
# - pyarrow가 dtype 추론 중 빈 문자열('')을 숫자로 변환하려다 터지는 케이스 방지
# ============================================================
_NUMERIC_COLUMNS_HINT = {
    "1차 답변 시간(초)", "2차 답변 시간(초)", "응답 시간(초)",
    "안정성 점수", "정확도 점수", "일관성 점수", "총점",
    "입력 토큰 수", "출력 토큰 수", "캐시 토큰 수", "추론 토큰 수", "전체 토큰 수",
    "LLM 비용(USD)",
}

def make_arrow_safe(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()

    for c in df2.columns:
        # 숫자 컬럼 힌트가 있으면 강제 numeric
        if c in _NUMERIC_COLUMNS_HINT:
            df2[c] = pd.to_numeric(df2[c], errors="coerce")
            continue

        # object 컬럼 중, 숫자/문자 혼합으로 보이는 것은 문자열로 통일
        if df2[c].dtype == "object":
            # 빈 문자열/None 섞여있으면 Arrow가 종종 numeric으로 오해 → string으로 고정
            try:
                df2[c] = df2[c].astype("string")
            except Exception:
                df2[c] = df2[c].astype(str)

    return df2


# ============================================================
# OpenAI usage 파싱 & 비용 계산
# ============================================================
def extract_usage_fields(resp_json: Dict[str, Any]) -> Dict[str, int]:
    usage = (resp_json or {}).get("usage") or {}
    if not isinstance(usage, dict):
        usage = {}

    input_tokens = usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0
    output_tokens = usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0
    total_tokens = usage.get("total_tokens", 0) or 0

    # cached tokens는 docs에서 prompt_tokens_details.cached_tokens 로 안내됨
    itd = usage.get("input_tokens_details", usage.get("prompt_tokens_details", {})) or {}
    if not isinstance(itd, dict):
        itd = {}
    cached_tokens = itd.get("cached_tokens", 0) or 0

    otd = usage.get("output_tokens_details", usage.get("completion_tokens_details", {})) or {}
    if not isinstance(otd, dict):
        otd = {}
    reasoning_tokens = otd.get("reasoning_tokens", 0) or 0

    def _to_int(x: Any) -> int:
        try:
            return int(x)
        except Exception:
            try:
                return int(float(x))
            except Exception:
                return 0

    return {
        "input_tokens": _to_int(input_tokens),
        "output_tokens": _to_int(output_tokens),
        "cached_tokens": _to_int(cached_tokens),
        "reasoning_tokens": _to_int(reasoning_tokens),
        "total_tokens": _to_int(total_tokens),
    }


def estimate_cost_usd(
    usage: Dict[str, int],
    price_input_per_1m: float,
    price_output_per_1m: float,
    price_cached_input_per_1m: float,
) -> float:
    if not usage:
        return 0.0
    inp = float(usage.get("input_tokens", 0) or 0)
    out = float(usage.get("output_tokens", 0) or 0)
    cached = float(usage.get("cached_tokens", 0) or 0)
    uncached = max(0.0, inp - cached)

    cost = 0.0
    if price_input_per_1m > 0:
        cost += (uncached / 1_000_000.0) * float(price_input_per_1m)
    if price_cached_input_per_1m > 0:
        cost += (cached / 1_000_000.0) * float(price_cached_input_per_1m)
    if price_output_per_1m > 0:
        cost += (out / 1_000_000.0) * float(price_output_per_1m)
    return float(cost)


def build_applicant_csv_template() -> bytes:
    # 최소 입력 컬럼 + 자주 쓰는 결과 컬럼을 포함한 템플릿
    cols = [
        "ID", "질의", "기대 필터/열",
        "1차 답변", "1차 답변 시간(초)", "1차 답변 raw", "1차 buttonUrl", "1차 감지된 필터",
        "2차 답변", "2차 답변 시간(초)", "2차 답변 raw", "2차 buttonUrl", "2차 감지된 필터",
        "열/필터 일치 여부", "답변 일관성", "차이 유형", "특이사항",
        "LLM 모델", "입력 토큰 수", "출력 토큰 수", "캐시 토큰 수", "추론 토큰 수", "전체 토큰 수", "LLM 비용(USD)",
        "LLM 평가 원본(JSON)",
        "안정성 점수", "1차 응답 상태", "2차 응답 상태", "안정성 비고",
        "정확도 점수", "기대 필터", "감지된 필터", "정확도 비고",
        "일관성 점수", "일치 항목", "불일치 항목", "일관성 비고",
        "총점", "종합 코멘트",
    ]
    df = pd.DataFrame([{c: "" for c in cols}])
    b = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    return b


def resolve_field_path(data: Any, path: str) -> Any:
    """JSON 필드 경로 탐색.

    예시:
      - ``"assistantMessage"`` → 최상위 키
      - ``"dataUIList[0].uiValue.buttonUrl"`` → 배열 인덱스 + 중첩 딕셔너리
    경로 실패 시 ``None`` 반환.
    """
    if data is None or not path:
        return None

    # "aaa[0].bbb.ccc" → ["aaa", "[0]", "bbb", "ccc"]
    tokens: List[str] = []
    for part in path.split("."):
        # "dataUIList[0]" → "dataUIList", "[0]"
        while "[" in part:
            before, rest = part.split("[", 1)
            if before:
                tokens.append(before)
            idx_str, part = rest.split("]", 1)
            tokens.append(f"[{idx_str}]")
            if part.startswith("."):
                part = part[1:]
        if part:
            tokens.append(part)

    cur = data
    for tok in tokens:
        if tok.startswith("[") and tok.endswith("]"):
            # 배열 인덱스
            try:
                idx = int(tok[1:-1])
                cur = cur[idx]
            except (IndexError, TypeError, ValueError, KeyError):
                return None
        else:
            if isinstance(cur, dict):
                cur = cur.get(tok)
            else:
                return None
        if cur is None:
            return None
    return cur


def run_logic_check(raw_json_str: str, field_path: str, expected_value: str) -> str:
    """로직 평가 실행.

    ``raw_json_str`` 을 JSON 파싱 → ``resolve_field_path`` 로 값 추출 →
    ``expected_value in actual_str`` 포함 여부 체크.
    결과: ``"PASS: ..."`` 또는 ``"FAIL: ..."`` 문자열.
    """
    if not field_path or not expected_value:
        return ""
    try:
        data = json.loads(raw_json_str)
    except (json.JSONDecodeError, TypeError):
        return f"FAIL: raw JSON 파싱 실패"

    actual = resolve_field_path(data, field_path)
    if actual is None:
        return f"FAIL: 필드 '{field_path}' 를 찾을 수 없음"

    actual_str = str(actual)
    if expected_value in actual_str:
        return f"PASS: '{expected_value}' 포함 확인 (실제값: {actual_str[:200]})"
    else:
        return f"FAIL: '{expected_value}' 미포함 (실제값: {actual_str[:200]})"


def build_generic_csv_template() -> bytes:
    """범용 테스트용 CSV 템플릿 (필수: 질의)"""
    cols = [
        "질의", "LLM 평가기준", "검증 필드", "기대값",
    ]
    df = pd.DataFrame([{c: "" for c in cols}])
    b = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    return b


def build_url_csv_template() -> bytes:
    """이동 에이전트 검증용 CSV 템플릿 (필수: 질의, 기대URL)"""
    cols = [
        "ID", "질의", "기대URL",
        "성공여부", "실패사유", "실제URL", "응답시간(초)"
    ]
    df = pd.DataFrame([{c: "" for c in cols}])
    b = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    return b

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


# ============================================================
# 2) 평가 프롬프트 (기본값)
#    - 같은 폴더에 '지원자 관리 에이전트 평가 프롬프트_260202.md'가 있으면 자동 로드
# ============================================================
DEFAULT_EVAL_PROMPT_MD = """
# 지원자 관리 에이전트 평가 프롬프트

## 역할

당신은 채용솔루션의 '지원자 관리 에이전트'의 응답 품질을 평가하는 QA 전문가입니다.
사용자의 질의와 에이전트의 1차/2차 응답을 비교 분석하여 안정성, 정확도, 일관성을 평가합니다.

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

### 1. 안정성 (Stability)

응답이 정상적으로 반환되었는지 판단합니다. 에러 발생 또는 Null 응답 여부를 확인합니다.

**점수 기준 (0~5점):**

| 점수 | 기준 |
|---|---|
| 5 | 1차/2차 모두 정상 응답 |
| 3 | 1차 또는 2차 중 하나만 정상 응답 (한쪽 에러/Null) |
| 0 | 1차/2차 모두 에러 또는 Null |

**판단 원칙:**

- 안정성이 0점이면 → 정확도/일관성 평가 불가 → 해당 항목 모두 0점 처리
- 안정성이 3점이면 → 정상 응답 1개로만 정확도 평가, 일관성은 평가 불가(0점)
- 안정성이 5점이면 → 정확도/일관성 모두 평가 진행

---

### 2. 정확도 (Accuracy)

**응답이 질의 의도를 얼마나 충족했는지** 정성적으로 평가합니다.

에이전트는 질의에 따라 다음 두 가지 방식으로 데이터를 처리합니다:
- **필터 기반**: 시스템 필터를 사용하여 조건에 맞는 데이터 조회
- **열 기반**: 필터가 없는 경우 API로 전체 데이터를 가져온 후 열을 기준으로 직접 집계

두 방식이 혼합될 수 있으므로, 필터/열 구분 없이 **"질의 의도 충족도"**를 기준으로 평가합니다.

**점수 기준 (0~5점):**

| 점수 | 기준 |
|---|---|
| 5 | 질의 의도를 완벽히 이해하고, 요청한 모든 항목을 정확히 응답함 |
| 4 | 질의 의도를 이해하고 대부분 응답했으나, 일부 누락 또는 불필요한 추가 정보 포함 |
| 3 | 질의 의도를 대체로 이해했으나, 핵심 항목 일부 누락 |
| 2 | 질의 의도를 일부만 반영, 응답이 불완전함 |
| 1 | 질의 의도와 동떨어진 응답 |
| 0 | 질의와 무관한 응답 또는 평가 불가 (안정성 0점) |

**정성 평가 체크리스트:**

| 체크 항목 | 확인 내용 |
|---|---|
| 집계 대상 | 질의에서 요청한 대상(예: 남성 지원자, 26~35세)이 응답에 포함되었는가? |
| 집계 조건 | 질의에서 명시한 조건(예: 최근 3개월, 경력 5년 이상)이 반영되었는가? |
| 출력 형식 | 질의에서 요청한 형식(예: 표, 비율, Top N, 정렬)이 반영되었는가? |
| 논리적 일관성 | 응답 수치가 질의 조건과 논리적으로 맞는가? |
| 간결성 | 불필요한 정보 없이 질의에 집중했는가? |

**기간 필터 특별 규칙:**

| 상황 | 처리 방식 |
|---|---|
| 질의에 기간 미명시 + 응답에서 "1년/최근 1년/365일" 사용 | 정상 (Default 기간, 감점 없음) |
| 질의에 기간 미명시 + 응답에서 다른 기간 사용 (예: 3개월) | 유의사항 기록 (4점) |
| 질의에 "최근 3개월" 명시 + 응답에서 "최근 3개월" 사용 | 정상 |
| 질의에 "최근 3개월" 명시 + 응답에서 "1년" 또는 다른 기간 사용 | 감점 대상 (2~3점) |

---

### 3. 일관성 (Consistency)

1차 응답과 2차 응답이 의미적으로 동일한 결과(집계 수치)를 반환했는지 판단합니다.

**비교 항목:**

- 핵심 수치 (지원자 수, 평균 점수, 비율 등)
- 순위/정렬 결과 (Top N 순서)
- 데이터 구조 (테이블 행/열 내용)

**점수 기준 (0~5점):**

| 점수 | 기준 |
|---|---|
| 5 | 핵심 데이터(수치, 순위) 완전 일치 |
| 4 | 핵심 데이터 일치 + 표현/포맷 차이 (테이블 컬럼 수, 문장 표현 등) |
| 3 | 핵심 데이터 대부분 일치, 일부 수치 미세 차이 (반올림, 소수점 등) |
| 2 | 핵심 데이터 일부만 일치, 순위나 주요 수치 불일치 |
| 1 | 핵심 데이터 대부분 불일치 |
| 0 | 완전히 다른 결과 또는 평가 불가 (안정성 3점 이하) |

**판단 원칙:**

- 표현만 다르고 의미하는 바가 같으면 "일치"로 판단 (예: "152명입니다" vs "총 152명이에요")
- 숫자 포맷 차이는 감점하지 않음 (예: "990점" vs "990.0점")
- 테이블 컬럼 수나 순서 차이는 경미한 차이로 처리 (4점)

---

## 평가 출력 형식

```json
{
  "query_id": "{질의 ID}",
  "stability": {
    "score": {0, 3, 5},
    "response_1_status": "{정상 / 에러 / Null}",
    "response_2_status": "{정상 / 에러 / Null}",
    "note": "{에러 메시지 또는 특이사항}"
  },
  "accuracy": {
    "score": {0-5},
    "expected": ["{기대 필터/열 목록}"],
    "checklist": {
      "집계 대상": "{충족 / 미충족 / 부분 충족}",
      "집계 조건": "{충족 / 미충족 / 부분 충족}",
      "출력 형식": "{충족 / 미충족 / 부분 충족}",
      "논리적 일관성": "{충족 / 미충족 / 부분 충족}",
      "간결성": "{충족 / 미충족 / 부분 충족}"
    },
    "note": "{누락 항목, 추가 정보, 기간 필터 관련 사항 등}"
  },
  "consistency": {
    "score": {0-5},
    "matched": ["{일치하는 항목 목록}"],
    "diff": ["{차이나는 항목 목록}"],
    "note": "{표현 차이, 포맷 차이 등 유의사항}"
  },
  "total_score": {(stability.score + accuracy.score + consistency.score) / 3},
  "remarks": "{종합 의견 및 특이사항}"
}
```

---

## 평가 예시

### 예시 1: 필터+열 혼합 케이스 (정상)

**입력:**

```
질의 ID: C-01
질의 내용: 최근 3개월간 남성 지원자 수와 비율을 알려줘
기대 필터/열: 기간(3개월) + 성별
1차 응답: "최근 3개월(2025-11-03~2026-02-03) 기준 남성 지원자는 1,234명으로 전체의 58.2%입니다."
2차 응답: "최근 3개월 기준, 남성 지원자 수는 1,234명(58.2%)입니다."
```

**출력:**

```json
{
  "query_id": "C-01",
  "stability": {
    "score": 5,
    "response_1_status": "정상",
    "response_2_status": "정상",
    "note": ""
  },
  "accuracy": {
    "score": 5,
    "expected": ["기간(3개월)", "성별"],
    "checklist": {
      "집계 대상": "충족 - 남성 지원자 명시",
      "집계 조건": "충족 - 최근 3개월 기간 정확히 반영",
      "출력 형식": "충족 - 수와 비율 모두 제공",
      "논리적 일관성": "충족 - 수치와 비율이 논리적으로 맞음",
      "간결성": "충족 - 불필요한 정보 없음"
    },
    "note": "기대 항목 모두 정확히 반영됨"
  },
  "consistency": {
    "score": 5,
    "matched": ["남성 지원자 수(1,234명)", "비율(58.2%)"],
    "diff": [],
    "note": "표현 차이만 있고 핵심 데이터 완전 일치"
  },
  "total_score": 5.0,
  "remarks": "필터(기간)와 열(성별) 혼합 질의에 대해 완벽히 응답함."
}
```

### 예시 2: 열 기반 집계 케이스

**입력:**

```
질의 ID: C-02
질의 내용: 26세에서 35세 사이 지원자가 몇 명이야?
기대 필터/열: 나이
1차 응답: "26세~35세 지원자는 총 2,891명입니다."
2차 응답: "해당 연령대(26~35세) 지원자 수는 2,891명입니다."
```

**출력:**

```json
{
  "query_id": "C-02",
  "stability": {
    "score": 5,
    "response_1_status": "정상",
    "response_2_status": "정상",
    "note": ""
  },
  "accuracy": {
    "score": 5,
    "expected": ["나이"],
    "checklist": {
      "집계 대상": "충족 - 26~35세 연령 범위 명시",
      "집계 조건": "충족 - 연령 범위 정확히 반영",
      "출력 형식": "충족 - 지원자 수 제공",
      "논리적 일관성": "충족",
      "간결성": "충족"
    },
    "note": "나이 열 기반 집계 정상 수행"
  },
  "consistency": {
    "score": 5,
    "matched": ["지원자 수(2,891명)"],
    "diff": [],
    "note": "완전 일치"
  },
  "total_score": 5.0,
  "remarks": "필터가 없는 열(나이) 기반 집계를 정확히 수행함."
}
```

### 예시 3: 기간 조건 불일치 케이스

**입력:**

```
질의 ID: T-11
질의 내용: 최근 3개월간 지원 경로별 지원자 수를 표로 보여줘
기대 필터/열: 기간(3개월) + 지원경로
1차 응답: "최근 1년(2025-02-03~2026-02-03) 기준 지원 경로별 지원자 수입니다. [표]"
2차 응답: "최근 1년 기준 지원 경로별 현황입니다. [표]"
```

**출력:**

```json
{
  "query_id": "T-11",
  "stability": {
    "score": 5,
    "response_1_status": "정상",
    "response_2_status": "정상",
    "note": ""
  },
  "accuracy": {
    "score": 2,
    "expected": ["기간(3개월)", "지원경로"],
    "checklist": {
      "집계 대상": "충족 - 지원 경로별 집계",
      "집계 조건": "미충족 - 3개월 요청했으나 1년으로 응답",
      "출력 형식": "충족 - 표 형식 제공",
      "논리적 일관성": "부분 충족 - 데이터는 일관적이나 기간 불일치",
      "간결성": "충족"
    },
    "note": "질의에서 '최근 3개월' 명시했으나 에이전트가 '최근 1년'으로 처리함. 기간 조건 불일치로 감점."
  },
  "consistency": {
    "score": 5,
    "matched": ["지원 경로별 지원자 수", "표 형식"],
    "diff": [],
    "note": "1차/2차 동일한 기간(1년)으로 일관되게 응답"
  },
  "total_score": 4.0,
  "remarks": "지원경로 집계는 정상이나, 기간 조건을 사용자 요청과 다르게 처리하여 정확도 감점."
}
```

### 예시 4: 일부 에러 발생

**입력:**

```
질의 ID: T-15
질의 내용: 지난 분기 대비 이번 분기에 지원 경로별 유입 추이를 표로 비교해줘
기대 필터/열: 기간 + 지원경로
1차 응답: {정상 응답 - 표 포함}
2차 응답: {에러 - timeout}
```

**출력:**

```json
{
  "query_id": "T-15",
  "stability": {
    "score": 3,
    "response_1_status": "정상",
    "response_2_status": "에러",
    "note": "2차 응답 timeout 에러 발생"
  },
  "accuracy": {
    "score": 5,
    "expected": ["기간", "지원경로"],
    "checklist": {
      "집계 대상": "충족 - 지원 경로별 집계",
      "집계 조건": "충족 - 분기 비교 반영",
      "출력 형식": "충족 - 표 형식 및 비교 제공",
      "논리적 일관성": "충족",
      "간결성": "충족"
    },
    "note": "1차 응답 기준 평가. 기대 항목 모두 정확히 반영됨."
  },
  "consistency": {
    "score": 0,
    "matched": [],
    "diff": [],
    "note": "2차 응답 에러로 일관성 평가 불가"
  },
  "total_score": 2.67,
  "remarks": "2차 응답 에러로 인해 일관성 평가 불가. 1차 응답 기준 정확도는 양호."
}
```

---

## 주의사항

1. **평가 순서**: 반드시 안정성 → 정확도 → 일관성 순서로 평가하세요. 안정성 점수에 따라 이후 평가 가능 여부가 결정됩니다.

2. **정확도 평가 시**: 필터 사용 여부가 아닌, **응답이 질의 의도를 얼마나 충족했는지**를 기준으로 평가하세요. 에이전트가 필터를 사용했든 열 기반으로 직접 집계했든, 결과가 질의 의도에 맞으면 높은 점수를 부여합니다.

3. Response 구조는 샘플 외에도 다양한 형태로 제공될 수 있습니다. `assistantMessage`, `dataUIList`, `guideList` 등 모든 필드를 종합적으로 분석하세요.

4. 의미 기반 집합 필터(SKY, 인서울, 지거국, 이공계 등)는 정확한 범위 정의가 어려울 수 있으므로, 합리적인 범위 내에서 사용되었다면 정상으로 판단합니다.

5. 에이전트가 추가 질문을 던지거나 가이드를 제공한 경우(`guideList`), 이는 평가에서 감점 요소가 아닙니다.

6. 1차/2차 응답 시간 차이는 평가 지표에 포함하지 않습니다. (참고용)

7. 평가 결과는 최종적으로 CSV/엑셀로 저장될 예정이므로, JSON 형식을 정확히 준수하세요.

8. **기간 필터 판단 시**: "1년", "최근 1년", "365일"은 시스템 Default 기간이므로, 질의에 기간이 명시되지 않은 경우 이 값들이 사용되어도 감점하지 않습니다. 단, 질의에서 특정 기간(예: "최근 3개월", "작년 하반기")을 명시했는데 에이전트가 다른 기간을 사용했다면 이는 감점 대상입니다.

"""


def read_prompt_template(script_dir: str) -> str:
    """
    1) ./지원자 관리 에이전트 평가 프롬프트_260203.md 있으면 그걸 사용
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
        target_assistant: Optional[str] = None
    ) -> Tuple[List[Optional[AgentResponse]], str]:
        """
        동일 conversationId에서 N번 호출을 수행하며, 실패 시 자동 재시도.
        - n_calls: 호출 횟수 (기본 1회, 일관성 테스트를 위해 2~4회 가능)
        - max_retries: 각 단계별 최대 재시도 횟수 (기본 2회)
        - context: API 호출 시 전달할 context 객체
        - target_assistant: 특정 어시스턴트 지정 (예: RECRUIT_PLAN_ASSISTANT)
        """
        retry_delay = 2.0
        responses: List[Optional[AgentResponse]] = []
        conv_id: Optional[str] = None
        last_err = ""

        for call_idx in range(n_calls):
            resp: Optional[AgentResponse] = None

            for attempt in range(max_retries + 1):
                cid, err = await self.send_query(
                    session, query,
                    conversation_id=conv_id,
                    context=context,
                    target_assistant=target_assistant
                )
                if not cid:
                    last_err = f"send_query#{call_idx + 1} failed: {err}"
                    if attempt < max_retries:
                        await asyncio.sleep(retry_delay)
                    continue

                # 첫 호출에서 conversationId 획득
                if conv_id is None:
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


def _looks_like_error_response(raw: str) -> bool:
    """응답 원문(raw)이 에러/사과 메시지인지 휴리스틱 판별."""
    if not raw or not isinstance(raw, str):
        return False
    s = raw.strip()
    if not s:
        return False
    # JSON이면 assistantMessage 내용만 검사
    try:
        parsed = json.loads(s)
        if isinstance(parsed, dict) and "assistantMessage" in parsed:
            s = str(parsed["assistantMessage"]) if parsed["assistantMessage"] else ""
    except Exception:
        pass
    s_lower = s.lower()
    error_markers = ("죄송해요", "문제가 발생", "에러", "error", "timeout", "오류")
    return any(m in s or m in s_lower for m in error_markers)


def _infer_stability_from_responses(
    response_1_raw: Optional[str], response_2_raw: Optional[str]
) -> Dict[str, Any]:
    """1차/2차 응답 원문으로 안정성(stability) 객체를 추론."""
    err1 = _looks_like_error_response(response_1_raw or "")
    err2 = _looks_like_error_response(response_2_raw or "")
    status_1 = "에러" if err1 else "정상"
    status_2 = "에러" if err2 else "정상"
    if err1 and err2:
        score = 0
        note = "응답 내용 기반 추론: 양쪽 모두 에러 메시지"
    elif err1 or err2:
        score = 3
        note = "응답 내용 기반 추론: 한쪽 에러"
    else:
        score = 5
        note = ""
    return {
        "score": score,
        "response_1_status": status_1,
        "response_2_status": status_2,
        "note": note,
    }


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
) -> Tuple[Optional[Dict[str, Any]], Dict[str, int], str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

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
                return None, {}, f"OpenAI HTTP {resp.status}: {text[:250]}"
            data = json.loads(text)

            usage = extract_usage_fields(data)

            out_text = extract_openai_output_text(data)
            parsed = robust_json_loads(out_text)
            if parsed is None:
                return None, usage, f"OpenAI output is not JSON. raw={out_text[:200]}"
            return parsed, usage, ""
    except asyncio.TimeoutError:
        return None, {}, f"OpenAI timeout({timeout_sec}s)"
    except Exception as e:
        return None, {}, f"OpenAI error: {type(e).__name__}: {str(e)[:200]}"

async def openai_judge_with_retry(
    session: aiohttp.ClientSession,
    api_key: str,
    model: str,
    prompt_text: str,
    max_retries: int = 2,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, int], str]:
    wait = 2.0
    last_err = ""
    last_usage: Dict[str, int] = {}

    for _attempt in range(max_retries + 1):
        result, usage, err = await openai_judge_once(session, api_key, model, prompt_text)
        if usage:
            last_usage = usage
        if result is not None and not err:
            return result, last_usage, ""
        last_err = err or "unknown"
        await asyncio.sleep(wait)
        wait *= 2

    return None, last_usage, last_err


def postprocess_eval_json(
    obj: Dict[str, Any],
    response_1_raw: Optional[str] = None,
    response_2_raw: Optional[str] = None,
) -> Dict[str, Any]:
    """
    - score 필드 정수화/클램프
    - total_score 재계산(안전)
    - 누락 키 방어적으로 채움
    - accuracy 비어 있으면 filter_accuracy에서 fallback
    - stability 비어 있고 response_1_raw/response_2_raw가 있으면 응답 내용으로 추론
    """
    out = obj.copy()
    fa = out.get("filter_accuracy") if isinstance(out.get("filter_accuracy"), dict) else {}

    # stability (안정성)
    stab = out.get("stability") if isinstance(out.get("stability"), dict) else {}
    stab_score = coerce_int_0_100(stab.get("score"))
    stab["score"] = stab_score
    stab["response_1_status"] = str(stab.get("response_1_status") or "")
    stab["response_2_status"] = str(stab.get("response_2_status") or "")
    stab["note"] = str(stab.get("note") or "")
    # stability 비어 있으면 1차/2차 응답 원문으로 추론
    stability_empty = (
        stab_score == 0
        and not stab.get("response_1_status")
        and not stab.get("response_2_status")
    )
    if stability_empty and response_1_raw and response_2_raw:
        inferred = _infer_stability_from_responses(response_1_raw, response_2_raw)
        stab = {**stab, **inferred}
        stab_score = coerce_int_0_100(stab["score"])
    out["stability"] = stab

    # accuracy (정확도) - 비어 있으면 filter_accuracy에서 fallback
    acc = out.get("accuracy") if isinstance(out.get("accuracy"), dict) else {}
    acc_score = coerce_int_0_100(acc.get("score"))
    acc["score"] = acc_score
    acc["expected"] = acc.get("expected") if isinstance(acc.get("expected"), list) else []
    acc["detected"] = acc.get("detected") if isinstance(acc.get("detected"), list) else []
    acc["note"] = str(acc.get("note") or "")
    accuracy_empty = (
        acc_score == 0 and not acc.get("expected") and not acc.get("detected")
    )
    if accuracy_empty and fa:
        acc["score"] = coerce_int_0_100(fa.get("score"))
        acc["expected"] = fa.get("expected") if isinstance(fa.get("expected"), list) else []
        acc["detected"] = fa.get("detected") if isinstance(fa.get("detected"), list) else []
        acc["note"] = str(fa.get("note") or "")
    acc_score = coerce_int_0_100(acc["score"])
    out["accuracy"] = acc

    # consistency (일관성)
    con = out.get("consistency") if isinstance(out.get("consistency"), dict) else {}
    con_score = coerce_int_0_100(con.get("score"))
    con["score"] = con_score
    con["matched"] = con.get("matched") if isinstance(con.get("matched"), list) else []
    con["diff"] = con.get("diff") if isinstance(con.get("diff"), list) else []
    con["note"] = str(con.get("note") or "")
    out["consistency"] = con

    # total_score: (stability + accuracy + consistency) / 3
    out["total_score"] = round((stab_score + acc_score + con_score) / 3, 2)
    out["remarks"] = str(out.get("remarks") or "")

    return out


def derive_csv_fields_from_eval(eval_json: Dict[str, Any]) -> Dict[str, str]:
    """
    CSV 템플릿 컬럼(열/필터 일치 여부, 답변 일관성, 차이 유형, 특이사항)을
    LLM 평가 결과(JSON)에서 도출.
    """
    stab = eval_json.get("stability", {}) or {}
    acc = eval_json.get("accuracy", {}) or {}
    con = eval_json.get("consistency", {}) or {}

    stab_score = int(stab.get("score", 0))
    acc_score = int(acc.get("score", 0))
    con_score = int(con.get("score", 0))

    # 안정성이 0이면 전체 실패로 처리
    if stab_score == 0:
        filter_pass = "FAIL"
        consistency = "평가 불가"
        diff_type = "응답 실패"
    else:
        # 기준: 프롬프트 정의 그대로(4 이상은 기대필터 사용 + 추가필터)
        filter_pass = "PASS" if acc_score >= 4 else "FAIL"

        # 안정성이 3점이면 일관성 평가 불가
        if stab_score == 3:
            consistency = "평가 불가"
        else:
            consistency = "일치" if con_score >= 4 else "차이 발생"

        # 차이 유형 (검증 규칙 문서의 분류를 LLM 평가 결과로 매핑)
        diff_type = ""
        if acc_score < 4:
            diff_type = "열/필터 변경"
        else:
            if con_score < 4:
                diff_type = "통계값만 변경"
            elif con_score < 5:
                diff_type = "표현만 변경"
            else:
                diff_type = ""

    note_parts = []
    stab_note = str(stab.get("note") or "").strip()
    acc_note = str(acc.get("note") or "").strip()
    con_note = str(con.get("note") or "").strip()
    remarks = str(eval_json.get("remarks") or "").strip()

    for s in [stab_note, acc_note, con_note, remarks]:
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
    progress_cb: Optional[Callable[[int, int, str, float, int], None]] = None,
    only_missing: bool = True,
    limit_rows: Optional[int] = None,
    n_calls: int = 2,
    context: Optional[Dict[str, Any]] = None,
    target_assistant: Optional[str] = None,
    auto_save_callback: Optional[Callable[[pd.DataFrame], None]] = None,
) -> pd.DataFrame:
    """
    CSV df를 받아, 지원자 에이전트를 N차로 호출해 df에 컬럼을 채움.
    (이 단계에서는 '평가'를 하지 않음)

    - n_calls: 호출 횟수 (1~4, 기본값 2)
    - context: API 호출 시 전달할 context 객체
    - target_assistant: 특정 어시스턴트 지정 (예: RECRUIT_PLAN_ASSISTANT)
    - auto_save_callback: 10개 완료 시마다 호출되는 자동 저장 콜백
    """
    df = df.copy()

    id_col = get_col(df, "ID") or "ID"
    query_col = get_col(df, "질의") or "질의"

    # 동적으로 출력 컬럼 확보 (n_calls에 따라)
    ordinals = ["1차", "2차", "3차", "4차"]
    for i in range(n_calls):
        prefix = ordinals[i]
        for suffix in ["답변", "답변 시간(초)", "답변 raw", "buttonUrl", "감지된 필터"]:
            col_name = f"{prefix} {suffix}"
            if col_name not in df.columns:
                df[col_name] = ""

    # 대상 row 인덱스 구성
    target_idxs: List[int] = []
    for i, r in df.iterrows():
        if limit_rows is not None and len(target_idxs) >= limit_rows:
            break
        if only_missing:
            # 첫 번째 호출 컬럼만 체크
            if not is_blank(r.get("1차 답변")):
                continue
        target_idxs.append(i)

    total = len(target_idxs)
    if total == 0:
        return df

    connector = aiohttp.TCPConnector(limit=50, ssl=False)
    timeout = aiohttp.ClientTimeout(total=120)

    done = 0
    start_time = time.time()
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = []

        async def _run_one(idx: int):
            async with client.semaphore:
                query = str(df.loc[idx, query_col])
                responses, err = await client.run_n_times(
                    session, query, n_calls=n_calls,
                    context=context, target_assistant=target_assistant
                )

                out = {
                    "idx": idx,
                    "err": err,
                    "responses": responses,
                }
                return out

        for idx in target_idxs:
            tasks.append(asyncio.create_task(_run_one(idx)))

        for fut in asyncio.as_completed(tasks):
            res = await fut
            idx = res["idx"]
            err = res["err"]
            responses: List[Optional[AgentResponse]] = res["responses"]

            # 각 호출 결과를 동적 컬럼에 저장
            for i, resp in enumerate(responses):
                if resp is None:
                    continue
                prefix = ordinals[i]
                df.at[idx, f"{prefix} 답변"] = resp.assistant_message
                df.at[idx, f"{prefix} 답변 시간(초)"] = round(resp.response_time_sec, 2) if resp.response_time_sec is not None else ""
                df.at[idx, f"{prefix} 답변 raw"] = json.dumps(resp.assistant_payload, ensure_ascii=False)
                df.at[idx, f"{prefix} buttonUrl"] = resp.button_url
                parsed = parse_button_url(resp.button_url)
                df.at[idx, f"{prefix} 감지된 필터"] = ",".join(parsed["filter_types"])

            if err:
                if "특이사항" not in df.columns:
                    df["특이사항"] = ""
                df.at[idx, "특이사항"] = str(err)

            done += 1
            elapsed = time.time() - start_time
            if progress_cb:
                progress_cb(done, total, f"[{df.loc[idx, id_col]}] calls done (err={bool(err)})", elapsed, done)

            # 자동 저장: 10개 완료 시마다
            if auto_save_callback and done % 10 == 0:
                auto_save_callback(df)

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
    price_input_per_1m: float = 0.0,
    price_output_per_1m: float = 0.0,
    price_cached_input_per_1m: float = 0.0,
) -> Tuple[pd.DataFrame, int]:
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
        "안정성 점수",
        "1차 응답 상태",
        "2차 응답 상태",
        "안정성 비고",
        "정확도 점수",
        "기대 필터",
        "감지된 필터",
        "정확도 비고",
        "일관성 점수",
        "일치 항목",
        "불일치 항목",
        "일관성 비고",
        "총점",
        "종합 코멘트",
        "LLM 모델",
        "입력 토큰 수",
        "출력 토큰 수",
        "캐시 토큰 수",
        "추론 토큰 수",
        "전체 토큰 수",
        "LLM 비용(USD)",
        "LLM 평가 원본(JSON)"
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
        if is_blank(r.get("1차 답변 raw")):
            surrogate1 = build_surrogate_response_payload(r, "1차")
            if surrogate1 is not None:
                df.at[i, "1차 답변 raw"] = json.dumps(surrogate1, ensure_ascii=False)

        if is_blank(r.get("2차 답변 raw")):
            surrogate2 = build_surrogate_response_payload(r, "2차")
            if surrogate2 is not None:
                df.at[i, "2차 답변 raw"] = json.dumps(surrogate2, ensure_ascii=False)

        if is_blank(r.get("1차 답변 raw")) or is_blank(r.get("2차 답변 raw")):
            continue  # 호출 결과가 없으면 평가 불가

        if only_missing and (not is_blank(r.get("LLM 평가 원본(JSON)"))):
            continue

        # 기존 에러가 있으면 스킵(원하면 UI에서 override 가능하게 만들 수 있음)
        if isinstance(r.get("특이사항"), str) and "send_query" in r.get("특이사항"):
            continue

        target_idxs.append(i)

    total = len(target_idxs)
    if total == 0:
        return df, 0

    sem = asyncio.Semaphore(max_parallel)

    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:

        async def _judge_one(idx: int) -> Dict[str, Any]:
            async with sem:
                qid = str(df.loc[idx, id_col])
                query = str(df.loc[idx, query_col])
                expected = str(df.loc[idx, expected_col])

                r1_raw = truncate_text(str(df.loc[idx, "1차 답변 raw"]), max_chars_per_response)
                r2_raw = truncate_text(str(df.loc[idx, "2차 답변 raw"]), max_chars_per_response)

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

                eval_obj, usage, err = await openai_judge_with_retry(session, api_key, model, prompt_text)
                return {"idx": idx, "qid": qid, "eval": eval_obj, "usage": usage, "err": err}

        tasks = [asyncio.create_task(_judge_one(idx)) for idx in target_idxs]

        done = 0
        for fut in asyncio.as_completed(tasks):
            res = await fut
            idx = res["idx"]
            qid = res["qid"]
            err = res["err"]
            eval_obj = res["eval"]
            usage = res.get("usage") or {}

            if eval_obj is None:
                df.at[idx, "특이사항"] = f"LLM 평가 실패: {err}"
            else:
                r1_raw = str(df.loc[idx, "1차 답변 raw"]) if "1차 답변 raw" in df.columns else ""
                r2_raw = str(df.loc[idx, "2차 답변 raw"]) if "2차 답변 raw" in df.columns else ""
                eval_obj = postprocess_eval_json(eval_obj, response_1_raw=r1_raw, response_2_raw=r2_raw)

                # LLM 토큰/비용 기록
                df.at[idx, "LLM 모델"] = model
                if usage:
                    df.at[idx, "입력 토큰 수"] = usage.get("input_tokens", 0)
                    df.at[idx, "출력 토큰 수"] = usage.get("output_tokens", 0)
                    df.at[idx, "캐시 토큰 수"] = usage.get("cached_tokens", 0)
                    df.at[idx, "추론 토큰 수"] = usage.get("reasoning_tokens", 0)
                    df.at[idx, "전체 토큰 수"] = usage.get("total_tokens", 0)
                    df.at[idx, "LLM 비용(USD)"] = estimate_cost_usd(
                        usage,
                        price_input_per_1m=price_input_per_1m,
                        price_output_per_1m=price_output_per_1m,
                        price_cached_input_per_1m=price_cached_input_per_1m,
                    )
                df.at[idx, "LLM 평가 원본(JSON)"] = json.dumps(eval_obj, ensure_ascii=False)

                # 안정성(Stability)
                df.at[idx, "안정성 점수"] = eval_obj["stability"]["score"]
                df.at[idx, "1차 응답 상태"] = eval_obj["stability"]["response_1_status"]
                df.at[idx, "2차 응답 상태"] = eval_obj["stability"]["response_2_status"]
                df.at[idx, "안정성 비고"] = eval_obj["stability"]["note"]

                # 정확도(Accuracy)
                df.at[idx, "정확도 점수"] = eval_obj["accuracy"]["score"]
                df.at[idx, "기대 필터"] = ",".join(eval_obj["accuracy"]["expected"])
                df.at[idx, "감지된 필터"] = ",".join(eval_obj["accuracy"]["detected"])
                df.at[idx, "정확도 비고"] = eval_obj["accuracy"]["note"]

                # 일관성(Consistency)
                df.at[idx, "일관성 점수"] = eval_obj["consistency"]["score"]
                df.at[idx, "일치 항목"] = ",".join(eval_obj["consistency"]["matched"])
                df.at[idx, "불일치 항목"] = ",".join(eval_obj["consistency"]["diff"])
                df.at[idx, "일관성 비고"] = eval_obj["consistency"]["note"]

                df.at[idx, "총점"] = eval_obj["total_score"]
                df.at[idx, "종합 코멘트"] = eval_obj["remarks"]

                # CSV 템플릿 컬럼 채움
                derived = derive_csv_fields_from_eval(eval_obj)
                for k, v in derived.items():
                    if k in df.columns:
                        df.at[idx, k] = v

            done += 1
            if progress_cb:
                progress_cb(done, total, f"[{qid}] judge done (err={bool(err)})")

    return df, done


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
            error_msg = f"{type(e).__name__}: {str(e)[:4]}"

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
    st.set_page_config(page_title="채용 에이전트 검증 백오피스", page_icon="🧪", layout="wide")

    script_dir = os.path.dirname(os.path.abspath(__file__))

    # .env 자동 로드
    loaded_env = load_dotenv(os.path.join(script_dir, ".env"))

    st.title("🧪 채용 에이전트 검증 백오피스")

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

        # cURL 붙여넣기 기능
        with st.expander("📋 cURL로 토큰 자동 입력", expanded=False):
            curl_text = st.text_area(
                "cURL 명령어 붙여넣기",
                placeholder="curl 'https://...' -H 'authorization: Bearer ...' -H 'cms-access-token: ...' ...",
                height=100,
                key="curl_input"
            )
            if st.button("🔑 인증 정보 파싱", key="parse_curl"):
                if curl_text.strip():
                    parsed = parse_curl_headers(curl_text)
                    # Bearer 접두사 제거
                    auth_val = parsed.get("authorization") or ""
                    if auth_val.lower().startswith("bearer "):
                        auth_val = auth_val[7:]
                    st.session_state["parsed_bearer"] = auth_val
                    st.session_state["parsed_cms"] = parsed.get("cms-access-token") or ""
                    st.session_state["parsed_mrs"] = parsed.get("mrs-session") or ""

                    # 파싱 결과 표시
                    if auth_val or parsed.get("cms-access-token") or parsed.get("mrs-session"):
                        st.success("✅ 토큰 파싱 완료! 아래 입력 필드에 자동 적용됩니다.")
                    else:
                        st.warning("⚠️ cURL에서 토큰을 찾지 못했습니다.")
                else:
                    st.warning("cURL 명령어를 입력하세요.")

        # 파싱된 토큰이 있으면 기본값으로 사용
        default_bearer = st.session_state.get("parsed_bearer") or os.getenv("ATS_BEARER_TOKEN", "")
        default_cms = st.session_state.get("parsed_cms") or os.getenv("ATS_CMS_TOKEN", "")
        default_mrs = st.session_state.get("parsed_mrs") or os.getenv("ATS_MRS_SESSION", "")

        bearer = st.text_input("ATS_BEARER_TOKEN", value=default_bearer, type="password")
        cms = st.text_input("ATS_CMS_TOKEN", value=default_cms, type="password")
        mrs = st.text_input("ATS_MRS_SESSION", value=default_mrs, type="password")

        # 세션 확인 버튼
        if st.button("🔍 세션 확인", key="check_session"):
            if base_url and bearer and cms and mrs:
                async def check_session():
                    connector = aiohttp.TCPConnector(ssl=False)
                    timeout = aiohttp.ClientTimeout(total=30)
                    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                        url = f"{base_url.rstrip('/')}/api/v2/ai/orchestrator/query"
                        headers = {
                            "authorization": f"Bearer {bearer}",
                            "cms-access-token": cms,
                            "mrs-session": mrs,
                            "origin": origin,
                            "referer": referer,
                            "accept": "application/json, text/plain, */*",
                            "content-type": "application/json",
                        }
                        payload = {"conversationId": None, "userMessage": "테스트"}
                        try:
                            async with session.post(url, headers=headers, json=payload) as resp:
                                return resp.status == 200, resp.status
                        except Exception as e:
                            return False, str(e)

                ok, status = run_async(check_session())
                if ok:
                    st.success(f"✅ 세션 유효 (HTTP 200)")
                else:
                    st.error(f"❌ 세션 무효 또는 오류: {status}")

        st.divider()
        st.subheader("OpenAI (ChatGPT 평가)")

        # 주요 설정 (항상 표시)
        judge_parallel = st.slider("LLM 병렬수", min_value=1, max_value=10, value=3, step=1)
        max_chars = st.slider("응답 최대 길이(평가 입력)", min_value=2000, max_value=30000, value=15000, step=1000)

        # 고급 설정 (접기)
        with st.expander("⚙️ 고급 설정", expanded=False):
            openai_key = st.text_input("OPENAI_API_KEY", value=os.getenv("OPENAI_API_KEY", ""), type="password")
            openai_model = st.text_input("OPENAI_MODEL", value=os.getenv("OPENAI_MODEL", "gpt-5.2"))

            # 비용 계산용(선택): 1M 토큰당 USD
            st.caption("비용 계산용 (선택사항)")
            try:
                default_in = float(os.getenv("OPENAI_PRICE_INPUT_PER_1M", "0") or 0)
            except Exception:
                default_in = 0.0
            try:
                default_out = float(os.getenv("OPENAI_PRICE_OUTPUT_PER_1M", "0") or 0)
            except Exception:
                default_out = 0.0
            try:
                default_cached = float(os.getenv("OPENAI_PRICE_CACHED_INPUT_PER_1M", "0") or 0)
            except Exception:
                default_cached = 0.0

            price_input_per_1m = st.number_input("Input $/1M tokens", min_value=0.0, value=default_in, step=0.1, format="%.4f")
            price_output_per_1m = st.number_input("Output $/1M tokens", min_value=0.0, value=default_out, step=0.1, format="%.4f")
            price_cached_input_per_1m = st.number_input("Cached input $/1M tokens", min_value=0.0, value=default_cached, step=0.1, format="%.4f")

        st.divider()
        st.subheader("실행 옵션")
        agent_parallel = st.slider("ATS 호출 병렬수", min_value=1, max_value=10, value=3, step=1)
        n_calls = st.slider(
            "채팅 호출 횟수",
            min_value=1, max_value=4, value=1, step=1,
            help="동일 conversationId에서 같은 질문을 N번 반복 (일관성 테스트용). 1이면 일관성 평가 제외."
        )
        only_missing = st.checkbox("이미 채워진 row는 스킵", value=True)
        limit_rows = st.number_input("상위 N개만 실행 (0=전체)", min_value=0, value=0, step=1)
        limit_rows = None if int(limit_rows) == 0 else int(limit_rows)

        st.caption("✅ .env 로드됨" if loaded_env else "⚠️ .env 미로드(없거나 비어있음)")

    tab_generic, tab_applicant, tab_url, tab_prompt = st.tabs(["범용 테스트", "지원자 에이전트 검증", "이동 에이전트 검증", "프롬프트 관리"])

    # --------------------------------------------
    # Tab 2: 지원자 에이전트 검증
    # --------------------------------------------
    with tab_applicant:
        st.subheader("1) CSV 업로드")

        # 업로드용 CSV 템플릿 다운로드
        st.download_button(
            "⬇️ 업로드용 CSV 양식 다운로드",
            data=build_applicant_csv_template(),
            file_name="지원자_관리_질의_템플릿.csv",
            mime="text/csv",
        )

        uploaded = st.file_uploader("지원자 관리 질의 CSV", type=["csv"])

        # 프롬프트 템플릿 로드 + 편집
        st.subheader("2) 평가 프롬프트")
        prompt_default = read_prompt_template(script_dir)
        prompt_text = st.text_area("평가 프롬프트(수정 가능)", value=prompt_default, height=320)

        if uploaded is None:
            st.info("CSV를 업로드하면 실행할 수 있어요.")
        else:
            try:
                df_in = pd.read_csv(uploaded, encoding="utf-8")
            except Exception:
                df_in = pd.read_csv(uploaded, encoding="utf-8-sig")
            df_in = normalize_columns(df_in)

            st.write("미리보기", df_in.head(10))

            # Context 및 targetAssistant 설정
            st.subheader("3) API 설정 (선택)")
            col_ctx, col_target = st.columns(2)

            with col_ctx:
                use_context = st.checkbox("Context 사용", value=False, help="API 호출 시 context 객체를 함께 전송")
                context_obj: Optional[Dict[str, Any]] = None
                if use_context:
                    context_input = st.text_area(
                        "Context (JSON 형식)",
                        value='{"recruitPlanId": 123}',
                        height=80,
                        help='예: {"recruitPlanId": 123, "채용명": "2026년 공채"}'
                    )
                    try:
                        context_obj = json.loads(context_input)
                        st.success("✅ JSON 파싱 성공")
                    except json.JSONDecodeError as e:
                        st.error(f"❌ JSON 파싱 오류: {e}")
                        context_obj = None

            with col_target:
                use_target_assistant = st.checkbox("targetAssistant 지정", value=False, help="특정 어시스턴트를 지정하여 호출")
                target_assistant: Optional[str] = None
                if use_target_assistant:
                    target_assistant = st.text_input(
                        "targetAssistant",
                        value="RECRUIT_PLAN_ASSISTANT",
                        help='예: RECRUIT_PLAN_ASSISTANT, RECRUIT_PLAN_CREATE_ASSISTANT'
                    )

            # 실행 버튼
            st.subheader("4) 실행")
            colA, colB, colC = st.columns(3)
            run_calls = colA.button("① ATS 호출만 실행", key="tab2_run_calls")
            run_judge = colB.button("② LLM 평가만 실행", key="tab2_run_judge")
            run_all = colC.button("③ 전체 실행(호출+평가)", key="tab2_run_all")

            # 진행률 표시 영역 (개선: 업데이트 형태)
            progress = st.progress(0)
            progress_placeholder = st.empty()

            # 임시 저장 경로
            temp_save_path = os.path.join(script_dir, f"_autosave_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

            def auto_save_callback(df_partial: pd.DataFrame):
                try:
                    df_partial.to_csv(temp_save_path, index=False, encoding="utf-8-sig")
                    st.toast(f"💾 자동 저장 완료 ({temp_save_path})")
                except Exception as e:
                    st.toast(f"⚠️ 자동 저장 실패: {e}")

            def progress_cb(done: int, total: int, msg: str, elapsed: float = 0.0, completed: int = 0):
                if total > 0:
                    progress.progress(min(1.0, done / total))
                # 진행률 업데이트 (하나의 placeholder에서 갱신)
                if done > 0 and elapsed > 0:
                    avg_time = elapsed / done
                    remaining = (total - done) * avg_time
                    progress_placeholder.markdown(
                        f"**진행** {done}/{total} | **총 경과 시간** {elapsed:.1f}초 (약 {remaining:.0f}초 남음)"
                    )
                else:
                    progress_placeholder.markdown(f"**진행** {done}/{total} | **총 경과 시간** {elapsed:.1f}초")

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
                            n_calls=n_calls,
                            context=context_obj,
                            target_assistant=target_assistant,
                            auto_save_callback=auto_save_callback,
                        )
                    )
                    st.success("ATS 호출 완료")

            if run_judge or run_all:
                if not openai_key:
                    st.error("OPENAI_API_KEY를 입력하세요.")
                else:
                    df_result, eval_count = run_async(
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
                            price_input_per_1m=price_input_per_1m,
                            price_output_per_1m=price_output_per_1m,
                            price_cached_input_per_1m=price_cached_input_per_1m,
                        )
                    )
                    st.session_state["applicant_df"] = df_result
                    if eval_count == 0:
                        st.warning("LLM 평가 대상이 없습니다. (1차/2차 raw 데이터가 없거나 이미 평가 완료됨)")
                    else:
                        st.success(f"LLM 평가 완료 ({eval_count}건)")

            df_out = st.session_state["applicant_df"]

            st.subheader("5) 결과 요약")
            # 기본 요약
            total_rows = len(df_out)
            err_rows = df_out["특이사항"].astype(str).str.contains("fail|timeout|HTTP|LLM 평가 실패", case=False, na=False).sum() if "특이사항" in df_out.columns else 0

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("총 Row", total_rows)
            c2.metric("에러/특이", int(err_rows))

            if "총점" in df_out.columns:
                try:
                    avg_total = float(pd.to_numeric(df_out["총점"], errors="coerce").dropna().mean())
                except Exception:
                    avg_total = 0.0
                c3.metric("평균 총점", f"{avg_total:.1f}")
            else:
                c3.metric("평균 총점", "-")

            if "LLM 비용(USD)" in df_out.columns:
                try:
                    total_cost = float(pd.to_numeric(df_out["LLM 비용(USD)"], errors="coerce").fillna(0).sum())
                except Exception:
                    total_cost = 0.0
                c4.metric("LLM 비용(USD)", f"${total_cost:,.4f}")
            else:
                c4.metric("LLM 비용(USD)", "-")

            st.subheader("6) 결과 테이블")
            st.dataframe(make_arrow_safe(df_out), use_container_width=True, height=420)

            st.subheader("7) 다운로드")
            xlsx_bytes = dataframe_to_excel_bytes(df_out, sheet_name="applicant_results")
            st.download_button(
                "📥 결과 Excel 다운로드",
                data=xlsx_bytes,
                file_name=f"applicant_agent_results_{env}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    # --------------------------------------------
    # Tab 1: 범용 테스트
    # --------------------------------------------
    with tab_generic:
        st.subheader("범용 테스트")
        st.caption("범용 에이전트 테스트. 필수 컬럼: `질의`. 선택 컬럼: `LLM 평가기준`, `검증 필드`, `기대값`")

        # CSV 템플릿 다운로드
        st.download_button(
            "⬇️ 범용 테스트 CSV 양식 다운로드",
            data=build_generic_csv_template(),
            file_name="범용_테스트_템플릿.csv",
            mime="text/csv",
            key="download_generic_template"
        )

        # 입력 방식 선택
        input_mode = st.radio("입력 방식", ["CSV 업로드", "직접 입력"], horizontal=True)

        generic_df: Optional[pd.DataFrame] = None

        if input_mode == "CSV 업로드":
            up_generic = st.file_uploader("범용 테스트 CSV", type=["csv"], key="generic_csv")
            if up_generic is not None:
                try:
                    generic_df = pd.read_csv(up_generic, encoding="utf-8")
                except Exception:
                    generic_df = pd.read_csv(up_generic, encoding="utf-8-sig")
                generic_df = normalize_columns(generic_df)
        else:
            # 직접 입력 (4개 필드)
            st.markdown("**질의 입력**")
            direct_query = st.text_area("질의", placeholder="에이전트에게 보낼 질의를 입력하세요", height=100)
            direct_criteria = st.text_area("LLM 평가기준", placeholder="평가 기준을 입력하세요 (예: 정확한 수치 포함 여부, 응답 형식 등)", height=100)
            col_field, col_expect = st.columns(2)
            with col_field:
                direct_field = st.text_input("검증 필드", placeholder="예: assistantMessage, dataUIList[0].uiValue.buttonUrl")
            with col_expect:
                direct_expected = st.text_input("기대값", placeholder="응답에 포함되어야 할 문자열")

            if direct_query.strip():
                generic_df = pd.DataFrame([{
                    "질의": direct_query.strip(),
                    "LLM 평가기준": direct_criteria.strip(),
                    "검증 필드": direct_field.strip(),
                    "기대값": direct_expected.strip(),
                }])

        if generic_df is not None:
            # ID 자동 생성 (CSV에 ID 컬럼 없으면)
            if "ID" not in generic_df.columns:
                generic_df.insert(0, "ID", [f"Q-{i+1}" for i in range(len(generic_df))])

            # 선택 컬럼 기본값 보장
            for _col_name in ("LLM 평가기준", "검증 필드", "기대값"):
                if _col_name not in generic_df.columns:
                    generic_df[_col_name] = ""
            generic_df = generic_df.fillna("")

            st.session_state["generic_input_df"] = generic_df.copy()
            st.write("미리보기", generic_df.head(10))

            # API 설정 (범용 테스트용)
            st.subheader("API 설정 (선택)")
            col_ctx_g, col_target_g = st.columns(2)

            with col_ctx_g:
                use_generic_context = st.checkbox("Context 사용", value=False, key="generic_context_check")
                generic_context_obj: Optional[Dict[str, Any]] = None
                if use_generic_context:
                    generic_context_input = st.text_area(
                        "Context (JSON 형식)",
                        value='{"recruitPlanId": 123}',
                        height=80,
                        key="generic_context_input"
                    )
                    try:
                        generic_context_obj = json.loads(generic_context_input)
                        st.success("✅ JSON 파싱 성공")
                    except json.JSONDecodeError:
                        st.error("JSON 파싱 오류")
                        generic_context_obj = None

            with col_target_g:
                use_generic_target = st.checkbox("targetAssistant 지정", value=False, key="generic_target_check")
                generic_target_assistant: Optional[str] = None
                if use_generic_target:
                    generic_target_assistant = st.text_input(
                        "targetAssistant",
                        value="RECRUIT_PLAN_ASSISTANT",
                        key="generic_target_input",
                        help='예: RECRUIT_PLAN_ASSISTANT, RECRUIT_PLAN_CREATE_ASSISTANT'
                    )

            # ── 버튼 2개: 1단계 / 2단계 ──
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                run_step1 = st.button("1단계: 질의 보내기", key="run_generic_step1")
            with col_btn2:
                run_step2 = st.button("2단계: 평가하기", key="run_generic_step2")

            progress_generic = st.progress(0)
            progress_generic_text = st.empty()

            # ── Step 1: 질의 보내기 (병렬) ──
            if run_step1:
                if not (base_url and bearer and cms and mrs):
                    st.error("ATS 설정과 토큰을 입력하세요.")
                else:
                    async def run_generic_queries():
                        nonlocal progress_generic, progress_generic_text
                        client = ApplicantAgentClient(
                            base_url=base_url,
                            bearer_token=bearer,
                            cms_token=cms,
                            mrs_session=mrs,
                            origin=origin,
                            referer=referer,
                            max_parallel=agent_parallel,
                        )
                        connector = aiohttp.TCPConnector(limit=50, ssl=False)
                        _timeout = aiohttp.ClientTimeout(total=120)

                        input_df = st.session_state["generic_input_df"]
                        total = len(input_df)
                        done_count = 0
                        start_time = time.time()

                        # 결과 DataFrame 준비 (입력 컬럼 + 출력 컬럼)
                        res_df = input_df.copy()
                        for _c in ("응답", "응답 시간(초)", "실행 프로세스", "오류", "raw"):
                            res_df[_c] = ""

                        async with aiohttp.ClientSession(connector=connector, timeout=_timeout) as session:
                            async def _run_one(idx: int):
                                async with client.semaphore:
                                    query = str(res_df.loc[idx, "질의"])

                                    conv_id, err = await client.send_query(
                                        session, query,
                                        conversation_id=None,
                                        context=generic_context_obj,
                                        target_assistant=generic_target_assistant
                                    )

                                    if not conv_id:
                                        return {"idx": idx, "err": err, "sse": None}

                                    sse_result = await client.subscribe_sse_extended(session, conv_id)
                                    return {"idx": idx, "err": "", "sse": sse_result}

                            tasks = []
                            for i in range(total):
                                tasks.append(asyncio.create_task(_run_one(i)))

                            for fut in asyncio.as_completed(tasks):
                                result = await fut
                                idx = result["idx"]
                                err = result["err"]
                                sse = result["sse"]

                                if sse is None:
                                    # send_query 실패
                                    res_df.at[idx, "오류"] = err
                                else:
                                    # 실행 프로세스 요약
                                    exec_summary = ""
                                    for ep in sse.get("execution_processes", []):
                                        msg_summary = ep.get("messageSummary", "")
                                        if msg_summary:
                                            exec_summary += f"[{msg_summary}] "

                                    res_df.at[idx, "응답"] = sse.get("assistant_message", "")
                                    rt = sse.get("response_time_sec")
                                    res_df.at[idx, "응답 시간(초)"] = round(rt, 2) if rt else ""
                                    res_df.at[idx, "실행 프로세스"] = exec_summary.strip()
                                    res_df.at[idx, "오류"] = sse.get("error", "")
                                    res_df.at[idx, "raw"] = json.dumps({
                                        "assistantMessage": sse.get("assistant_message"),
                                        "dataUIList": sse.get("data_ui_list"),
                                        "guideList": sse.get("guide_list"),
                                    }, ensure_ascii=False)

                                done_count += 1
                                elapsed = time.time() - start_time
                                progress_generic.progress(min(1.0, done_count / total))
                                if done_count > 0 and elapsed > 0:
                                    remaining = (total - done_count) * (elapsed / done_count)
                                    progress_generic_text.markdown(
                                        f"**진행** {done_count}/{total} | "
                                        f"**총 경과 시간** {elapsed:.1f}초 (약 {remaining:.0f}초 남음)"
                                    )

                        return res_df

                    result_df = run_async(run_generic_queries())
                    st.session_state["generic_results_df"] = result_df
                    st.session_state["generic_df"] = result_df.copy()
                    st.success("1단계 완료: 질의 응답 수집 완료")

            # ── Step 2: 평가하기 ──
            if run_step2:
                if "generic_results_df" not in st.session_state:
                    st.error("먼저 1단계(질의 보내기)를 실행하세요.")
                else:
                    eval_df = st.session_state["generic_results_df"].copy()

                    # (A) 로직 평가 (동기, 즉시)
                    if "로직 검증결과" not in eval_df.columns:
                        eval_df["로직 검증결과"] = ""
                    for idx in range(len(eval_df)):
                        field_path = str(eval_df.at[idx, "검증 필드"]).strip()
                        expected = str(eval_df.at[idx, "기대값"]).strip()
                        if field_path and expected and field_path.lower() != "nan" and expected.lower() != "nan":
                            raw_str = str(eval_df.at[idx, "raw"])
                            eval_df.at[idx, "로직 검증결과"] = run_logic_check(raw_str, field_path, expected)

                    # (B) LLM 평가 (비동기, 병렬)
                    if "LLM 평가결과" not in eval_df.columns:
                        eval_df["LLM 평가결과"] = ""

                    # LLM 평가 대상 인덱스 수집
                    llm_targets = []
                    for idx in range(len(eval_df)):
                        criteria = str(eval_df.at[idx, "LLM 평가기준"]).strip()
                        if criteria and criteria.lower() != "nan":
                            llm_targets.append(idx)

                    if llm_targets and openai_key:
                        async def run_generic_llm_eval():
                            sem = asyncio.Semaphore(judge_parallel)
                            _timeout = aiohttp.ClientTimeout(total=120)

                            async with aiohttp.ClientSession(timeout=_timeout) as session:
                                async def eval_one(idx: int):
                                    async with sem:
                                        row_err = str(eval_df.at[idx, "오류"]).strip()
                                        if row_err and row_err.lower() != "nan":
                                            return idx, "평가 불가 (호출 오류)"

                                        criteria = str(eval_df.at[idx, "LLM 평가기준"])
                                        response = str(eval_df.at[idx, "응답"])
                                        query = str(eval_df.at[idx, "질의"])

                                        eval_prompt = f"""다음 질의에 대한 에이전트 응답을 평가하세요.

질의: {query}

응답: {response[:max_chars]}

평가 기준: {criteria}

평가 결과를 JSON으로 출력하세요:
{{"score": 0-5, "passed": true/false, "reason": "평가 사유"}}
"""
                                        result, _usage, err = await openai_judge_with_retry(
                                            session, openai_key, openai_model, eval_prompt
                                        )
                                        if result:
                                            return idx, json.dumps(result, ensure_ascii=False)
                                        return idx, f"평가 실패: {err}"

                                eval_tasks = [asyncio.create_task(eval_one(i)) for i in llm_targets]
                                for fut in asyncio.as_completed(eval_tasks):
                                    idx, eval_result = await fut
                                    eval_df.at[idx, "LLM 평가결과"] = eval_result

                        run_async(run_generic_llm_eval())
                    elif llm_targets and not openai_key:
                        st.warning("LLM 평가 대상이 있으나 OpenAI API 키가 설정되지 않았습니다.")

                    st.session_state["generic_df"] = eval_df
                    st.success("2단계 완료: 평가 완료")

            # ── 결과 표시 ──
            if "generic_df" in st.session_state:
                df_generic_out = st.session_state["generic_df"]
                st.subheader("결과 테이블")

                # 요약 메트릭
                total_q = len(df_generic_out)
                logic_col = df_generic_out.get("로직 검증결과")
                logic_pass = 0
                logic_fail = 0
                if logic_col is not None:
                    logic_pass = int(logic_col.astype(str).str.startswith("PASS").sum())
                    logic_fail = int(logic_col.astype(str).str.startswith("FAIL").sum())
                llm_col = df_generic_out.get("LLM 평가결과")
                llm_done = 0
                if llm_col is not None:
                    llm_done = int((llm_col.astype(str).str.strip() != "").sum())
                err_col = df_generic_out.get("오류")
                err_count = 0
                if err_col is not None:
                    err_count = int((err_col.astype(str).str.strip() != "").sum()
                                    - (err_col.astype(str).str.strip().str.lower() == "nan").sum())

                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric("총 질의 수", total_q)
                mc2.metric("로직 PASS / FAIL", f"{logic_pass} / {logic_fail}")
                mc3.metric("LLM 평가 완료", llm_done)
                mc4.metric("오류 건수", max(0, err_count))

                st.dataframe(make_arrow_safe(df_generic_out), use_container_width=True, height=420)

                xlsx_bytes = dataframe_to_excel_bytes(df_generic_out, sheet_name="generic_results")
                st.download_button(
                    "📥 범용 테스트 결과 Excel 다운로드",
                    data=xlsx_bytes,
                    file_name=f"generic_test_results_{env}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_generic"
                )
        else:
            st.info("CSV를 업로드하거나 직접 입력하세요.")

    # --------------------------------------------
    # Tab 3: 이동 에이전트 검증
    # --------------------------------------------
    with tab_url:
        st.subheader("이동 에이전트 검증")
        st.caption("CSV 컬럼 예시: ID, 질의, 기대URL (기대URL은 부분문자열 또는 /정규식/ 형태 지원)")

        # CSV 템플릿 다운로드
        st.download_button(
            "⬇️ 이동 에이전트 검증 CSV 양식 다운로드",
            data=build_url_csv_template(),
            file_name="이동_에이전트_검증_템플릿.csv",
            mime="text/csv",
            key="download_url_template"
        )

        up3 = st.file_uploader("URL 테스트 CSV", type=["csv"], key="urlcsv")

        if up3 is None:
            st.info("URL 테스트용 CSV를 업로드하세요.")
        else:
            try:
                df3 = pd.read_csv(up3, encoding="utf-8")
            except Exception:
                df3 = pd.read_csv(up3, encoding="utf-8-sig")
            df3 = normalize_columns(df3)

            st.write("미리보기", df3.head(10))

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
                for _, r in df3.iterrows():
                    rows.append(
                        {
                            "ID": str(r.get("ID", "")),
                            "질의": str(r.get("질의", "")),
                            "기대URL": str(r.get("기대URL", "")),
                        }
                    )

                run_url = st.button("URL 테스트 실행")
                progress3 = st.progress(0)
                log3 = st.empty()

                def progress_cb3(done: int, total: int, msg: str):
                    if total > 0:
                        progress3.progress(min(1.0, done / total))
                    log3.write(msg)

                if run_url:
                    df_url_out = run_async(run_url_tests_async(rows, tester, progress_cb=progress_cb3))
                    st.session_state["url_df"] = df_url_out
                    st.success("URL 테스트 완료")

                if "url_df" in st.session_state:
                    df_url_out = st.session_state["url_df"]
                    st.dataframe(make_arrow_safe(df_url_out), use_container_width=True, height=420)

                    xlsx_bytes = dataframe_to_excel_bytes(df_url_out, sheet_name="url_results")
                    st.download_button(
                        "📥 URL 결과 Excel 다운로드",
                        data=xlsx_bytes,
                        file_name=f"url_agent_results_{env}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

    # --------------------------------------------
    # Tab 4: 프롬프트 관리
    # --------------------------------------------
    with tab_prompt:
        st.subheader("Worker 프롬프트 관리")
        st.caption("Worker별 시스템 프롬프트를 조회, 수정, 초기화할 수 있습니다.")

        # 세션 상태 초기화
        if "prompt_result" not in st.session_state:
            st.session_state["prompt_result"] = None
        if "prompt_worker" not in st.session_state:
            st.session_state["prompt_worker"] = WORKER_TYPES[0]
        if "prompt_editing" not in st.session_state:
            st.session_state["prompt_editing"] = False

        # Worker 타입 선택
        selected_worker = st.selectbox(
            "Worker 타입 선택",
            WORKER_TYPES,
            index=WORKER_TYPES.index(st.session_state["prompt_worker"]) if st.session_state["prompt_worker"] in WORKER_TYPES else 0,
            format_func=lambda x: f"{x} - {WORKER_DESCRIPTIONS.get(x, '')}",
            key="prompt_worker_select",
        )

        # Worker 선택이 변경되면 이전 결과 초기화
        if st.session_state["prompt_worker"] != selected_worker:
            st.session_state["prompt_result"] = None
            st.session_state["prompt_worker"] = selected_worker
            st.session_state["prompt_editing"] = False

        # 프롬프트 조회 및 초기화 버튼
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🔍 프롬프트 조회", key="prompt_get"):
                if not base_url:
                    st.error("사이드바에서 환경을 선택하세요.")
                else:
                    with st.spinner("프롬프트 조회 중..."):
                        try:
                            client = AxPromptApiClient(
                                base_url=base_url,
                                environment=env,
                                retention_token=bearer if bearer else None,
                                mrs_session=mrs if mrs else None,
                                cms_access_token=cms if cms else None,
                            )
                            result = client.get_prompt(selected_worker)
                            st.session_state["prompt_result"] = result
                            st.session_state["prompt_worker"] = selected_worker
                            st.session_state["prompt_editing"] = False
                            st.success("프롬프트 조회 완료!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"오류 발생: {str(e)}")

        with col_btn2:
            if st.button("🔄 프롬프트 초기화", key="prompt_reset"):
                if not base_url:
                    st.error("사이드바에서 환경을 선택하세요.")
                else:
                    with st.spinner("프롬프트 초기화 중..."):
                        try:
                            client = AxPromptApiClient(
                                base_url=base_url,
                                environment=env,
                                retention_token=bearer if bearer else None,
                                mrs_session=mrs if mrs else None,
                                cms_access_token=cms if cms else None,
                            )
                            result = client.reset_prompt(selected_worker)
                            before_len = safe_len(result.before)
                            after_len = safe_len(result.after)
                            st.success("프롬프트 초기화 완료!")
                            st.info(f"변경 전: {before_len}자 -> 변경 후: {after_len}자")
                            st.session_state["prompt_result"] = result
                            st.session_state["prompt_worker"] = selected_worker
                            st.session_state["prompt_editing"] = False
                            st.rerun()
                        except Exception as e:
                            st.error(f"오류 발생: {str(e)}")

        st.divider()

        # 프롬프트 조회 결과 표시
        if st.session_state["prompt_result"] is not None:
            result = st.session_state["prompt_result"]
            worker = st.session_state.get("prompt_worker", "Unknown")

            # 현재 선택된 Worker와 결과의 Worker가 일치하는지 확인
            if worker != selected_worker:
                st.info("Worker 타입을 선택하고 '프롬프트 조회' 버튼을 클릭하세요.")
            else:
                before_text = result.before if result.before is not None else ""
                after_text = result.after if result.after is not None else ""

                # 변경 전/현재 프롬프트를 2열로 표시
                st.markdown("### 프롬프트 비교")
                col_before, col_after = st.columns(2)

                with col_before:
                    st.markdown("#### 변경 전 프롬프트")
                    st.text_area(
                        "변경 전",
                        value=before_text,
                        height=400,
                        disabled=True,
                        key="prompt_before",
                    )
                    st.caption(f"길이: {safe_len(before_text)}자")

                with col_after:
                    st.markdown("#### 현재 프롬프트")
                    st.text_area(
                        "현재",
                        value=after_text,
                        height=400,
                        disabled=True,
                        key="prompt_after",
                    )
                    st.caption(f"길이: {safe_len(after_text)}자")

                st.divider()

                # 프롬프트 수정 섹션
                st.markdown("### 프롬프트 수정")

                # 수정 모드 토글 버튼
                if not st.session_state["prompt_editing"]:
                    if st.button("✏️ 프롬프트 수정 시작", key="prompt_edit_start"):
                        st.session_state["prompt_editing"] = True
                        st.rerun()
                else:
                    # 수정 영역
                    st.info("현재 프롬프트를 기반으로 수정하세요. 변경 사항은 저장 시 적용됩니다.")

                    new_prompt = st.text_area(
                        "새로운 프롬프트 입력",
                        value=after_text,
                        height=400,
                        help="프롬프트를 수정한 후 '프롬프트 업데이트' 버튼을 클릭하세요.",
                        key="prompt_new_input",
                    )

                    # 변경 사항 요약
                    if new_prompt != after_text:
                        diff_len = len(new_prompt) - len(after_text)
                        diff_sign = "+" if diff_len > 0 else ""
                        st.info(f"변경 사항: {len(after_text)}자 -> {len(new_prompt)}자 ({diff_sign}{diff_len}자)")

                    # 버튼 영역
                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        if st.button("💾 프롬프트 업데이트", key="prompt_update"):
                            with st.spinner("프롬프트 업데이트 중..."):
                                try:
                                    client = AxPromptApiClient(
                                        base_url=base_url,
                                        environment=env,
                                        retention_token=bearer if bearer else None,
                                        mrs_session=mrs if mrs else None,
                                        cms_access_token=cms if cms else None,
                                    )
                                    update_result = client.update_prompt(worker, new_prompt)
                                    before_len = safe_len(update_result.before)
                                    after_len = safe_len(update_result.after)
                                    st.success("프롬프트 업데이트 완료!")
                                    st.info(f"변경 전: {before_len}자 -> 변경 후: {after_len}자")
                                    st.session_state["prompt_result"] = update_result
                                    st.session_state["prompt_editing"] = False
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"오류 발생: {str(e)}")

                    with col_cancel:
                        if st.button("❌ 수정 취소", key="prompt_cancel"):
                            st.session_state["prompt_editing"] = False
                            st.rerun()
        else:
            st.info("Worker 타입을 선택하고 '프롬프트 조회' 버튼을 클릭하세요.")


if __name__ == "__main__":
    main()
