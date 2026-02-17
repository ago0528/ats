from __future__ import annotations

import io
import json
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.repositories.validation_queries import ValidationQueryRepository
from app.repositories.validation_query_groups import ValidationQueryGroupRepository

router = APIRouter(tags=["validation-queries"])

ALLOWED_CATEGORIES = {"Happy path", "Edge case", "Adversarial input"}


def _parse_json_text(value: str) -> Any:
    text = (value or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return text


def _normalize_category(value: str) -> str:
    normalized = (value or "").strip()
    if normalized in ALLOWED_CATEGORIES:
        return normalized
    return "Happy path"


def _extract_cell(row: dict[str, Any], candidates: list[str], default: str = "") -> str:
    normalized_candidates = {candidate.replace("\ufeff", "").strip() for candidate in candidates}
    for raw_key, cell in row.items():
        key = str(raw_key).replace("\ufeff", "").strip()
        if key not in normalized_candidates:
            continue
        if cell is None or pd.isna(cell):
            continue
        text = str(cell).strip()
        if not text or text.lower() == "nan":
            continue
        return text
    return default


def _present_group_id(value: Optional[str]) -> Optional[str]:
    text = (value or "").strip()
    return text or None


def _parse_csv_query_values(raw: Optional[str]) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def _load_bulk_upload_dataframe(filename: str, raw: bytes) -> pd.DataFrame:
    try:
        if filename.endswith(".xlsx") or filename.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(raw))
        else:
            df = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {exc}") from exc

    if df.empty:
        raise HTTPException(status_code=400, detail="No rows found")
    return df


def _parse_bulk_upload_rows(
    df: pd.DataFrame,
    *,
    group_map_by_id: dict[str, Any],
    group_id_by_name: dict[str, str],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    invalid_rows: list[int] = []
    missing_query_rows: list[int] = []
    unknown_group_rows: list[int] = []
    unknown_group_values: set[str] = set()

    for idx, series in enumerate(df.to_dict(orient="records"), start=1):
        query_text = _extract_cell(series, ["query_text", "query", "질의"])
        if not query_text:
            invalid_rows.append(idx)
            missing_query_rows.append(idx)
            continue

        expected_result = _extract_cell(series, ["expected_result", "expected", "기대결과", "기대값"])
        category = _normalize_category(_extract_cell(series, ["category", "카테고리"], default="Happy path"))
        group_value = _extract_cell(series, ["group_id", "groupId", "group", "group_name", "그룹"]).strip()
        llm_eval_criteria = _extract_cell(series, ["llm_eval_criteria", "LLM 평가기준"])
        logic_field_path = _extract_cell(series, ["logic_field_path", "검증 필드", "field_path"])
        logic_expected_value = _extract_cell(series, ["logic_expected_value", "검증 기대값", "logic_expected", "expected_value"])
        target_assistant = _extract_cell(series, ["target_assistant", "targetAssistant", "대상어시스턴트"])
        context_json = _extract_cell(series, ["context_json", "contextJson", "context", "컨텍스트"])

        if group_value and group_value not in group_map_by_id and group_value not in group_id_by_name:
            unknown_group_rows.append(idx)
            unknown_group_values.add(group_value)

        rows.append(
            {
                "query_text": query_text,
                "expected_result": expected_result,
                "category": category,
                "group_value": group_value,
                "llm_eval_criteria": llm_eval_criteria,
                "logic_field_path": logic_field_path,
                "logic_expected_value": logic_expected_value,
                "target_assistant": target_assistant,
                "context_json": context_json,
            }
        )

    return {
        "rows": rows,
        "invalid_rows": invalid_rows,
        "missing_query_rows": missing_query_rows,
        "unknown_group_rows": unknown_group_rows,
        "unknown_group_values": sorted(unknown_group_values),
    }


def _build_all_rows_invalid_detail(*, missing_query_rows: list[int], unknown_group_rows: list[int], unknown_group_values: list[str]) -> str:
    detail_parts = ["All rows are invalid"]
    if missing_query_rows:
        detail_parts.append(f"missing '질의' rows: {', '.join(str(row) for row in missing_query_rows)}")
    if unknown_group_rows:
        detail_parts.append(f"unknown '그룹' rows: {', '.join(str(row) for row in unknown_group_rows)}")
    if unknown_group_values:
        detail_parts.append(f"unknown group values: {', '.join(unknown_group_values)}")
    detail_parts.append("leave '그룹' empty to register without a group")
    return "; ".join(detail_parts)


class QueryCreateRequest(BaseModel):
    queryText: str = Field(min_length=1)
    expectedResult: str = ""
    category: str = "Happy path"
    groupId: Optional[str] = None
    llmEvalCriteria: Any = None
    logicFieldPath: str = ""
    logicExpectedValue: str = ""
    contextJson: str = ""
    targetAssistant: str = ""
    createdBy: str = "unknown"


class QueryUpdateRequest(BaseModel):
    queryText: Optional[str] = None
    expectedResult: Optional[str] = None
    category: Optional[str] = None
    groupId: Optional[str] = None
    llmEvalCriteria: Any = None
    logicFieldPath: Optional[str] = None
    logicExpectedValue: Optional[str] = None
    contextJson: Optional[str] = None
    targetAssistant: Optional[str] = None


@router.get("/queries")
def list_queries(
    q: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    groupId: Optional[str] = Query(default=None),
    queryIds: Optional[str] = Query(default=None),
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    query_repo = ValidationQueryRepository(db)
    group_repo = ValidationQueryGroupRepository(db)
    normalized_query_ids = _parse_csv_query_values(queryIds)
    category_values = _parse_csv_query_values(category)
    group_ids = _parse_csv_query_values(groupId)
    if normalized_query_ids:
        all_rows = query_repo.list_by_ids(normalized_query_ids)
        total = len(all_rows)
        rows = all_rows[offset: offset + limit]
    else:
        rows = query_repo.list(
            q=q,
            categories=category_values or None,
            group_ids=group_ids or None,
            offset=offset,
            limit=limit,
        )
        total = query_repo.count(q=q, categories=category_values or None, group_ids=group_ids or None)
    latest_summary = query_repo.get_latest_run_summary([row.id for row in rows])

    group_map = {group.id: group for group in group_repo.list(limit=100000)}
    return {
        "items": [
            {
                "id": row.id,
                "queryText": row.query_text,
                "expectedResult": row.expected_result,
                "category": row.category,
                "groupId": _present_group_id(row.group_id),
                "groupName": group_map[row.group_id].group_name if row.group_id and row.group_id in group_map else "",
                "llmEvalCriteria": _parse_json_text(row.llm_eval_criteria_json),
                "logicFieldPath": row.logic_field_path,
                "logicExpectedValue": row.logic_expected_value,
                "contextJson": row.context_json,
                "targetAssistant": row.target_assistant,
                "createdBy": row.created_by,
                "createdAt": row.created_at,
                "updatedAt": row.updated_at,
                "latestRunSummary": latest_summary.get(row.id, {}),
            }
            for row in rows
        ],
        "total": total,
    }


@router.post("/queries")
def create_query(body: QueryCreateRequest, db: Session = Depends(get_db)):
    if body.groupId:
        group_repo = ValidationQueryGroupRepository(db)
        if group_repo.get(body.groupId) is None:
            raise HTTPException(status_code=404, detail="Group not found")
    query_repo = ValidationQueryRepository(db)
    row = query_repo.create(
        query_text=body.queryText,
        expected_result=body.expectedResult,
        category=_normalize_category(body.category),
        group_id=body.groupId,
        llm_eval_criteria=body.llmEvalCriteria,
        logic_field_path=body.logicFieldPath,
        logic_expected_value=body.logicExpectedValue,
        context_json=body.contextJson,
        target_assistant=body.targetAssistant,
        created_by=body.createdBy,
    )
    db.commit()
    return {
        "id": row.id,
        "queryText": row.query_text,
        "expectedResult": row.expected_result,
        "category": row.category,
        "groupId": _present_group_id(row.group_id),
        "llmEvalCriteria": _parse_json_text(row.llm_eval_criteria_json),
        "logicFieldPath": row.logic_field_path,
        "logicExpectedValue": row.logic_expected_value,
        "contextJson": row.context_json,
        "targetAssistant": row.target_assistant,
        "createdBy": row.created_by,
        "createdAt": row.created_at,
        "updatedAt": row.updated_at,
    }


@router.get("/queries/template")
def download_query_template():
    csv_text = (
        '질의,카테고리,그룹,targetAssistant,contextJson\n'
        '리드타임 3개월 정도의 수시 채용을 설계해줘. 전형은 역량검사 -> 서류 -> 1차 면접(일정조율) -> 2차 면접으로 진행할래,Happy path,,RECRUIT_PLAN_CREATE_ASSISTANT,\n'
        '미응시 지원자에게 독려 메일 보내고 싶어,Happy path,,RECRUIT_PLAN_ASSISTANT,\n'
    )
    csv_bytes = ("\ufeff" + csv_text).encode("utf-8")
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="query_template.csv"',
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        },
    )


@router.get("/queries/{query_id}")
def get_query(query_id: str, db: Session = Depends(get_db)):
    query_repo = ValidationQueryRepository(db)
    row = query_repo.get(query_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Query not found")
    return {
        "id": row.id,
        "queryText": row.query_text,
        "expectedResult": row.expected_result,
        "category": row.category,
        "groupId": _present_group_id(row.group_id),
        "llmEvalCriteria": _parse_json_text(row.llm_eval_criteria_json),
        "logicFieldPath": row.logic_field_path,
        "logicExpectedValue": row.logic_expected_value,
        "contextJson": row.context_json,
        "targetAssistant": row.target_assistant,
        "createdBy": row.created_by,
        "createdAt": row.created_at,
        "updatedAt": row.updated_at,
    }


@router.patch("/queries/{query_id}")
def update_query(query_id: str, body: QueryUpdateRequest, db: Session = Depends(get_db)):
    payload = body.model_dump(exclude_unset=True)
    if "groupId" in payload and payload.get("groupId"):
        group_repo = ValidationQueryGroupRepository(db)
        if group_repo.get(str(payload.get("groupId"))) is None:
            raise HTTPException(status_code=404, detail="Group not found")

    query_repo = ValidationQueryRepository(db)
    row = query_repo.update(
        query_id,
        query_text=body.queryText,
        expected_result=body.expectedResult,
        category=_normalize_category(body.category) if body.category is not None else None,
        group_id=(str(payload.get("groupId")) if payload.get("groupId") is not None else None),
        update_group_id=("groupId" in payload),
        llm_eval_criteria=body.llmEvalCriteria,
        logic_field_path=body.logicFieldPath,
        logic_expected_value=body.logicExpectedValue,
        context_json=body.contextJson,
        target_assistant=body.targetAssistant,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Query not found")
    db.commit()
    return {
        "id": row.id,
        "queryText": row.query_text,
        "expectedResult": row.expected_result,
        "category": row.category,
        "groupId": _present_group_id(row.group_id),
        "llmEvalCriteria": _parse_json_text(row.llm_eval_criteria_json),
        "logicFieldPath": row.logic_field_path,
        "logicExpectedValue": row.logic_expected_value,
        "contextJson": row.context_json,
        "targetAssistant": row.target_assistant,
        "createdBy": row.created_by,
        "createdAt": row.created_at,
        "updatedAt": row.updated_at,
    }


@router.delete("/queries/{query_id}")
def delete_query(query_id: str, db: Session = Depends(get_db)):
    query_repo = ValidationQueryRepository(db)
    deleted = query_repo.delete(query_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Query not found")
    db.commit()
    return {"ok": True}


@router.post("/queries/bulk-upload/preview")
async def preview_bulk_upload_queries(
    groupId: Optional[str] = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    group_repo = ValidationQueryGroupRepository(db)
    groups = group_repo.list(limit=100000)
    group_map_by_id = {group.id: group for group in groups}
    group_id_by_name = {group.group_name.strip(): group.id for group in groups}

    if groupId:
        if groupId not in group_map_by_id:
            raise HTTPException(status_code=404, detail="Group not found")

    filename = (file.filename or "").lower()
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")

    df = _load_bulk_upload_dataframe(filename, raw)
    parsed = _parse_bulk_upload_rows(df, group_map_by_id=group_map_by_id, group_id_by_name=group_id_by_name)

    if not parsed["rows"]:
        raise HTTPException(
            status_code=400,
            detail=_build_all_rows_invalid_detail(
                missing_query_rows=parsed["missing_query_rows"],
                unknown_group_rows=parsed["unknown_group_rows"],
                unknown_group_values=parsed["unknown_group_values"],
            ),
        )

    return {
        "totalRows": int(len(df.index)),
        "validRows": len(parsed["rows"]),
        "invalidRows": parsed["invalid_rows"],
        "missingQueryRows": parsed["missing_query_rows"],
        "groupsToCreate": parsed["unknown_group_values"],
        "groupsToCreateRows": parsed["unknown_group_rows"],
    }


@router.post("/queries/bulk-upload")
async def bulk_upload_queries(
    groupId: Optional[str] = Form(default=None),
    createdBy: str = Form("unknown"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    group_repo = ValidationQueryGroupRepository(db)
    groups = group_repo.list(limit=100000)
    group_map_by_id = {group.id: group for group in groups}
    group_id_by_name = {group.group_name.strip(): group.id for group in groups}

    if groupId:
        # 이전 클라이언트와의 호환성을 위해 받아만 두고 사용하지는 않습니다.
        if groupId not in group_map_by_id:
            raise HTTPException(status_code=404, detail="Group not found")

    filename = (file.filename or "").lower()
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")

    df = _load_bulk_upload_dataframe(filename, raw)
    parsed = _parse_bulk_upload_rows(df, group_map_by_id=group_map_by_id, group_id_by_name=group_id_by_name)

    if not parsed["rows"]:
        raise HTTPException(
            status_code=400,
            detail=_build_all_rows_invalid_detail(
                missing_query_rows=parsed["missing_query_rows"],
                unknown_group_rows=parsed["unknown_group_rows"],
                unknown_group_values=parsed["unknown_group_values"],
            ),
        )

    created_group_names: list[str] = []
    for group_name in parsed["unknown_group_values"]:
        if group_name in group_id_by_name:
            continue
        created = group_repo.create(group_name=group_name)
        group_map_by_id[created.id] = created
        group_id_by_name[created.group_name.strip()] = created.id
        created_group_names.append(created.group_name)

    rows: list[dict[str, Any]] = []
    for row in parsed["rows"]:
        group_value = str(row.get("group_value") or "").strip()
        resolved_group_id = ""
        if group_value:
            if group_value in group_map_by_id:
                resolved_group_id = group_value
            elif group_value in group_id_by_name:
                resolved_group_id = group_id_by_name[group_value]
        rows.append(
            {
                "query_text": row["query_text"],
                "expected_result": row["expected_result"],
                "category": row["category"],
                "group_id": resolved_group_id,
                "llm_eval_criteria": row["llm_eval_criteria"],
                "logic_field_path": row["logic_field_path"],
                "logic_expected_value": row["logic_expected_value"],
                "target_assistant": row["target_assistant"],
                "context_json": row["context_json"],
            }
        )

    query_repo = ValidationQueryRepository(db)
    created_ids = query_repo.bulk_create(rows, created_by=createdBy or "unknown")
    db.commit()

    return {
        "createdCount": len(created_ids),
        "invalidRows": parsed["invalid_rows"],
        "queryIds": created_ids,
        "unmappedGroupRows": [],
        "unmappedGroupValues": [],
        "createdGroupNames": created_group_names,
    }
