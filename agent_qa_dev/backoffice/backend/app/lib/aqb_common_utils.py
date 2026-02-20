from __future__ import annotations

import json
from typing import Any

import pandas as pd


def build_generic_csv_template() -> bytes:
    cols = ["질의", "LLM 평가기준", "검증 필드", "기대값"]
    df = pd.DataFrame([{c: "" for c in cols}])
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def resolve_field_path(data: Any, path: str) -> Any:
    if data is None or not path:
        return None

    tokens: list[str] = []
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
                cur = cur[int(tok[1:-1])]
            except (IndexError, TypeError, ValueError, KeyError):
                return None
        else:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(tok)
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

