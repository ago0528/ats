from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

import pandas as pd

_NUMERIC_COLUMNS_HINT = {
    "1차 답변 시간(초)", "2차 답변 시간(초)", "응답 시간(초)",
    "안정성 점수", "정확도 점수", "일관성 점수", "총점",
    "입력 토큰 수", "출력 토큰 수", "캐시 토큰 수", "추론 토큰 수", "전체 토큰 수",
    "LLM 비용(USD)",
}

_DOTENV_LINE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")


def make_arrow_safe(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()

    for c in df2.columns:
        if c in _NUMERIC_COLUMNS_HINT:
            df2[c] = pd.to_numeric(df2[c], errors="coerce")
            continue

        if df2[c].dtype == "object":
            try:
                df2[c] = df2[c].astype("string")
            except Exception:
                df2[c] = df2[c].astype(str)

    return df2


def build_applicant_csv_template() -> bytes:
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
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def build_generic_csv_template() -> bytes:
    cols = ["질의", "LLM 평가기준", "검증 필드", "기대값"]
    df = pd.DataFrame([{c: "" for c in cols}])
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def build_url_csv_template() -> bytes:
    cols = ["ID", "질의", "기대URL", "성공여부", "실패사유", "실제URL", "응답시간(초)"]
    df = pd.DataFrame([{c: "" for c in cols}])
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def load_dotenv(dotenv_path: str) -> Dict[str, str]:
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
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            if k not in os.environ:
                os.environ[k] = v
            loaded[k] = v
    return loaded


def resolve_field_path(data: Any, path: str) -> Any:
    if data is None or not path:
        return None

    tokens: List[str] = []
    for part in path.split("."):
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
    if not field_path or not expected_value:
        return ""
    try:
        data = json.loads(raw_json_str)
    except (json.JSONDecodeError, TypeError):
        return "FAIL: raw JSON 파싱 실패"

    actual = resolve_field_path(data, field_path)
    if actual is None:
        return f"FAIL: 필드 '{field_path}' 를 찾을 수 없음"

    actual_str = str(actual)
    if expected_value in actual_str:
        return f"PASS: '{expected_value}' 포함 확인 (실제값: {actual_str[:200]})"
    return f"FAIL: '{expected_value}' 미포함 (실제값: {actual_str[:200]})"
