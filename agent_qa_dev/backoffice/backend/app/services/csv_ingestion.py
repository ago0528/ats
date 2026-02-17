from __future__ import annotations

import csv
import io
import json

REQUIRED_COLUMNS = ["질의", "LLM 평가기준", "검증 필드", "기대값"]


def parse_csv_bytes(file_bytes: bytes) -> list[dict]:
    text = file_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = [dict(r) for r in reader]
    return normalize_rows(rows)


def parse_rows_json(rows_json: str) -> list[dict]:
    obj = json.loads(rows_json)
    if not isinstance(obj, list):
        raise ValueError("rowsJson must be a JSON array")
    return normalize_rows([dict(x) for x in obj])


def normalize_row(
    query: str,
    llm_criteria: str = "",
    field_path: str = "",
    expected_value: str = "",
) -> dict:
    return {
        "질의": str(query or "").strip(),
        "LLM 평가기준": "" if llm_criteria is None else str(llm_criteria),
        "검증 필드": "" if field_path is None else str(field_path),
        "기대값": "" if expected_value is None else str(expected_value),
        "ID": "Q-1",
    }


def normalize_rows(rows: list[dict]) -> list[dict]:
    out = []
    for i, row in enumerate(rows, start=1):
        n = {k.strip(): ("" if v is None else str(v)) for k, v in row.items()}
        for col in REQUIRED_COLUMNS:
            n.setdefault(col, "")
        n.setdefault("ID", f"Q-{i}")
        if not n.get("ID"):
            n["ID"] = f"Q-{i}"
        if not n.get("질의", "").strip():
            continue
        out.append(n)
    return out
