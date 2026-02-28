from __future__ import annotations

import io
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.repositories.validation_queries import ValidationQueryRepository
from app.repositories.validation_query_groups import ValidationQueryGroupRepository
from app.services.validation_scoring import normalize_latency_class

router = APIRouter(tags=["validation-queries"])

ALLOWED_CATEGORIES = {"Happy path", "Edge case", "Adversarial input"}
QUERY_ID_COLUMN_CANDIDATES = ["쿼리 ID", "query_id", "queryId", "id"]
QUERY_TEXT_COLUMN_CANDIDATES = ["query_text", "query", "질의"]
CATEGORY_COLUMN_CANDIDATES = ["category", "카테고리"]
GROUP_COLUMN_CANDIDATES = ["group_id", "groupId", "group", "group_name", "그룹"]
EXPECTED_RESULT_COLUMN_CANDIDATES = ["expected_result", "expectedResult", "expected", "기대 결과", "기대결과", "기대값"]
LATENCY_CLASS_COLUMN_CANDIDATES = ["latencyClass", "latency_class", "응답속도유형", "응답속도 유형"]


def _build_internal_eval_meta(latency_class: Optional[str]) -> dict[str, Any]:
    if not latency_class:
        return {}
    return {"meta": {"latencyClass": latency_class}}


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
    invalid_latency_class_rows: list[int] = []

    for idx, series in enumerate(df.to_dict(orient="records"), start=1):
        query_text = _extract_cell(series, ["query_text", "query", "질의"])
        if not query_text:
            invalid_rows.append(idx)
            missing_query_rows.append(idx)
            continue

        expected_result = _extract_cell(series, ["expected_result", "expectedResult", "expected", "기대 결과", "기대결과", "기대값"])
        category = _normalize_category(_extract_cell(series, ["category", "카테고리"], default="Happy path"))
        group_value = _extract_cell(series, ["group_id", "groupId", "group", "group_name", "그룹"]).strip()
        latency_class_raw = _extract_cell(series, LATENCY_CLASS_COLUMN_CANDIDATES)
        latency_class = normalize_latency_class(latency_class_raw)
        if latency_class_raw and latency_class is None:
            invalid_rows.append(idx)
            invalid_latency_class_rows.append(idx)
            continue
        eval_meta = _build_internal_eval_meta(latency_class)

        if group_value and group_value not in group_map_by_id and group_value not in group_id_by_name:
            unknown_group_rows.append(idx)
            unknown_group_values.add(group_value)

        rows.append(
            {
                "query_text": query_text,
                "expected_result": expected_result,
                "category": category,
                "group_value": group_value,
                "llm_eval_meta": eval_meta,
            }
        )

    return {
        "rows": rows,
        "invalid_rows": invalid_rows,
        "missing_query_rows": missing_query_rows,
        "unknown_group_rows": unknown_group_rows,
        "unknown_group_values": sorted(unknown_group_values),
        "invalid_latency_class_rows": invalid_latency_class_rows,
    }


def _build_all_rows_invalid_detail(
    *,
    missing_query_rows: list[int],
    unknown_group_rows: list[int],
    unknown_group_values: list[str],
    invalid_latency_class_rows: list[int],
) -> str:
    detail_parts = ["All rows are invalid"]
    if missing_query_rows:
        detail_parts.append(f"missing '질의' rows: {', '.join(str(row) for row in missing_query_rows)}")
    if invalid_latency_class_rows:
        detail_parts.append(
            f"invalid 'latencyClass' rows (SINGLE|MULTI only): {', '.join(str(row) for row in invalid_latency_class_rows)}"
        )
    if unknown_group_rows:
        detail_parts.append(f"unknown '그룹' rows: {', '.join(str(row) for row in unknown_group_rows)}")
    if unknown_group_values:
        detail_parts.append(f"unknown group values: {', '.join(unknown_group_values)}")
    detail_parts.append("leave '그룹' empty to register without a group")
    return "; ".join(detail_parts)


def _normalized_header_set(df: pd.DataFrame) -> set[str]:
    return {str(column).replace("\ufeff", "").strip() for column in df.columns}


def _has_any_column(headers: set[str], candidates: list[str]) -> bool:
    normalized_candidates = {candidate.replace("\ufeff", "").strip() for candidate in candidates}
    return any(candidate in headers for candidate in normalized_candidates)


def _parse_bulk_update_rows(df: pd.DataFrame) -> dict[str, Any]:
    headers = _normalized_header_set(df)
    has_query_text = _has_any_column(headers, QUERY_TEXT_COLUMN_CANDIDATES)
    has_category = _has_any_column(headers, CATEGORY_COLUMN_CANDIDATES)
    has_group = _has_any_column(headers, GROUP_COLUMN_CANDIDATES)
    has_expected_result = _has_any_column(headers, EXPECTED_RESULT_COLUMN_CANDIDATES)

    rows: list[dict[str, Any]] = []
    missing_query_id_rows: list[int] = []
    duplicate_query_id_rows: list[int] = []
    seen_query_ids: set[str] = set()

    for row_no, series in enumerate(df.to_dict(orient="records"), start=1):
        query_id = _extract_cell(series, QUERY_ID_COLUMN_CANDIDATES).strip()
        if not query_id:
            missing_query_id_rows.append(row_no)
        elif query_id in seen_query_ids:
            duplicate_query_id_rows.append(row_no)
        else:
            seen_query_ids.add(query_id)

        rows.append(
            {
                "rowNo": row_no,
                "queryId": query_id,
                "queryText": _extract_cell(series, QUERY_TEXT_COLUMN_CANDIDATES) if has_query_text else None,
                "category": (
                    _normalize_category(_extract_cell(series, CATEGORY_COLUMN_CANDIDATES, default="Happy path"))
                    if has_category
                    else None
                ),
                "groupValue": _extract_cell(series, GROUP_COLUMN_CANDIDATES).strip() if has_group else None,
                "expectedResult": _extract_cell(series, EXPECTED_RESULT_COLUMN_CANDIDATES) if has_expected_result else None,
                "hasQueryText": has_query_text,
                "hasCategory": has_category,
                "hasGroup": has_group,
                "hasExpectedResult": has_expected_result,
                "missingQueryId": row_no in missing_query_id_rows,
                "duplicateQueryId": row_no in duplicate_query_id_rows,
            }
        )

    return {
        "rows": rows,
        "missingQueryIdRows": missing_query_id_rows,
        "duplicateQueryIdRows": duplicate_query_id_rows,
    }


def _analyze_bulk_update_rows(
    *,
    parsed_rows: list[dict[str, Any]],
    missing_query_id_rows: list[int],
    duplicate_query_id_rows: list[int],
    existing_queries_by_id: dict[str, Any],
    group_map_by_id: dict[str, Any],
    group_id_by_name: dict[str, str],
) -> dict[str, Any]:
    preview_rows: list[dict[str, Any]] = []
    planned_updates: list[dict[str, Any]] = []
    unmapped_query_rows: list[int] = []
    unmapped_query_ids: list[str] = []
    unknown_group_rows: list[int] = []
    unknown_group_values: set[str] = set()
    unchanged_count = 0

    for row in parsed_rows:
        row_no = int(row["rowNo"])
        query_id = str(row.get("queryId") or "").strip()
        uploaded_query_text = str(row.get("queryText") or "").strip() if row.get("hasQueryText") else ""

        if row.get("missingQueryId"):
            preview_rows.append(
                {
                    "rowNo": row_no,
                    "queryId": "",
                    "queryText": uploaded_query_text,
                    "status": "missing-query-id",
                    "changedFields": [],
                }
            )
            continue

        if row.get("duplicateQueryId"):
            preview_rows.append(
                {
                    "rowNo": row_no,
                    "queryId": query_id,
                    "queryText": uploaded_query_text,
                    "status": "duplicate-query-id",
                    "changedFields": [],
                }
            )
            continue

        existing = existing_queries_by_id.get(query_id)
        if existing is None:
            unmapped_query_rows.append(row_no)
            if query_id and query_id not in unmapped_query_ids:
                unmapped_query_ids.append(query_id)
            preview_rows.append(
                {
                    "rowNo": row_no,
                    "queryId": query_id,
                    "queryText": uploaded_query_text,
                    "status": "unmapped-query-id",
                    "changedFields": [],
                }
            )
            continue

        changed_fields: list[str] = []
        plan_payload: dict[str, Any] = {
            "queryId": query_id,
            "queryText": None,
            "category": None,
            "groupValue": None,
            "updateGroupId": bool(row.get("hasGroup")),
            "expectedResult": None,
        }

        if row.get("hasQueryText"):
            next_query_text = str(row.get("queryText") or "")
            if next_query_text.strip() != str(existing.query_text or ""):
                changed_fields.append("queryText")
                plan_payload["queryText"] = next_query_text

        if row.get("hasCategory"):
            next_category = str(row.get("category") or "Happy path")
            if next_category != str(existing.category or ""):
                changed_fields.append("category")
                plan_payload["category"] = next_category

        if row.get("hasGroup"):
            group_value = str(row.get("groupValue") or "").strip()
            plan_payload["groupValue"] = group_value

            resolved_group_id: Optional[str]
            if not group_value:
                resolved_group_id = ""
            elif group_value in group_map_by_id:
                resolved_group_id = group_value
            elif group_value in group_id_by_name:
                resolved_group_id = group_id_by_name[group_value]
            else:
                resolved_group_id = None
                unknown_group_rows.append(row_no)
                unknown_group_values.add(group_value)

            if resolved_group_id is None or resolved_group_id != str(existing.group_id or ""):
                changed_fields.append("group")

        if row.get("hasExpectedResult"):
            next_expected_result = str(row.get("expectedResult") or "")
            if next_expected_result != str(existing.expected_result or ""):
                changed_fields.append("expectedResult")
                plan_payload["expectedResult"] = next_expected_result

        if changed_fields:
            planned_updates.append(plan_payload)
            status = "planned-update"
        else:
            unchanged_count += 1
            status = "unchanged"

        preview_rows.append(
            {
                "rowNo": row_no,
                "queryId": query_id,
                "queryText": uploaded_query_text or str(existing.query_text or ""),
                "status": status,
                "changedFields": changed_fields,
            }
        )

    valid_rows = len(preview_rows) - len(missing_query_id_rows) - len(duplicate_query_id_rows)
    return {
        "totalRows": len(parsed_rows),
        "validRows": max(0, valid_rows),
        "plannedUpdateCount": len(planned_updates),
        "unchangedCount": unchanged_count,
        "unmappedQueryCount": len(unmapped_query_rows),
        "missingQueryIdRows": missing_query_id_rows,
        "duplicateQueryIdRows": duplicate_query_id_rows,
        "unmappedQueryRows": unmapped_query_rows,
        "unmappedQueryIds": unmapped_query_ids,
        "groupsToCreate": sorted(unknown_group_values),
        "groupsToCreateRows": unknown_group_rows,
        "previewRows": preview_rows,
        "plannedUpdates": planned_updates,
    }


class QueryCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queryText: str = Field(min_length=1)
    expectedResult: str = ""
    category: str = "Happy path"
    groupId: Optional[str] = None
    createdBy: str = "unknown"


class QueryUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queryText: Optional[str] = None
    expectedResult: Optional[str] = None
    category: Optional[str] = None
    groupId: Optional[str] = None


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
    test_set_usage = query_repo.get_test_set_usage([row.id for row in rows])

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
                "createdBy": row.created_by,
                "createdAt": row.created_at,
                "updatedAt": row.updated_at,
                "latestRunSummary": latest_summary.get(row.id, {}),
                "testSetUsage": test_set_usage.get(row.id, {"count": 0, "testSetNames": []}),
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
        created_by=body.createdBy,
    )
    db.commit()
    return {
        "id": row.id,
        "queryText": row.query_text,
        "expectedResult": row.expected_result,
        "category": row.category,
        "groupId": _present_group_id(row.group_id),
        "createdBy": row.created_by,
        "createdAt": row.created_at,
        "updatedAt": row.updated_at,
    }


@router.get("/queries/template")
def download_query_template():
    csv_text = (
        "질의,카테고리,그룹,기대 결과,latencyClass\n"
        "리드타임 3개월 정도의 수시 채용을 설계해줘. 전형은 역량검사 -> 서류 -> 1차 면접(일정조율) -> 2차 면접으로 진행할래,Happy path,,채용 플랜이 단계별로 제시됨,MULTI\n"
        "미응시 지원자에게 독려 메일 보내고 싶어,Happy path,,독려 메일 작업으로 연결됨,SINGLE\n"
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
                invalid_latency_class_rows=parsed["invalid_latency_class_rows"],
            ),
        )

    return {
        "totalRows": int(len(df.index)),
        "validRows": len(parsed["rows"]),
        "invalidRows": parsed["invalid_rows"],
        "missingQueryRows": parsed["missing_query_rows"],
        "groupsToCreate": parsed["unknown_group_values"],
        "groupsToCreateRows": parsed["unknown_group_rows"],
        "invalidLatencyClassRows": parsed["invalid_latency_class_rows"],
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
                invalid_latency_class_rows=parsed["invalid_latency_class_rows"],
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
                "llm_eval_meta": row["llm_eval_meta"],
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
        "invalidLatencyClassRows": parsed["invalid_latency_class_rows"],
    }


@router.post("/queries/bulk-update/preview")
async def preview_bulk_update_queries(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    group_repo = ValidationQueryGroupRepository(db)
    query_repo = ValidationQueryRepository(db)
    groups = group_repo.list(limit=100000)
    group_map_by_id = {group.id: group for group in groups}
    group_id_by_name = {group.group_name.strip(): group.id for group in groups}

    filename = (file.filename or "").lower()
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")

    df = _load_bulk_upload_dataframe(filename, raw)
    parsed = _parse_bulk_update_rows(df)
    candidate_query_ids = [
        str(row.get("queryId") or "").strip()
        for row in parsed["rows"]
        if not row.get("missingQueryId") and not row.get("duplicateQueryId")
    ]
    unique_query_ids = list(dict.fromkeys(candidate_query_ids))
    existing_queries = query_repo.list_by_ids(unique_query_ids)
    existing_queries_by_id = {row.id: row for row in existing_queries}

    analysis = _analyze_bulk_update_rows(
        parsed_rows=parsed["rows"],
        missing_query_id_rows=parsed["missingQueryIdRows"],
        duplicate_query_id_rows=parsed["duplicateQueryIdRows"],
        existing_queries_by_id=existing_queries_by_id,
        group_map_by_id=group_map_by_id,
        group_id_by_name=group_id_by_name,
    )
    return {
        "totalRows": analysis["totalRows"],
        "validRows": analysis["validRows"],
        "plannedUpdateCount": analysis["plannedUpdateCount"],
        "unchangedCount": analysis["unchangedCount"],
        "unmappedQueryCount": analysis["unmappedQueryCount"],
        "missingQueryIdRows": analysis["missingQueryIdRows"],
        "duplicateQueryIdRows": analysis["duplicateQueryIdRows"],
        "unmappedQueryRows": analysis["unmappedQueryRows"],
        "unmappedQueryIds": analysis["unmappedQueryIds"],
        "groupsToCreate": analysis["groupsToCreate"],
        "groupsToCreateRows": analysis["groupsToCreateRows"],
        "previewRows": analysis["previewRows"],
    }


@router.post("/queries/bulk-update")
async def bulk_update_queries(
    file: UploadFile = File(...),
    allowCreateGroups: bool = Form(default=False),
    skipUnmappedQueryIds: bool = Form(default=False),
    db: Session = Depends(get_db),
):
    group_repo = ValidationQueryGroupRepository(db)
    query_repo = ValidationQueryRepository(db)
    groups = group_repo.list(limit=100000)
    group_map_by_id = {group.id: group for group in groups}
    group_id_by_name = {group.group_name.strip(): group.id for group in groups}

    filename = (file.filename or "").lower()
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")

    df = _load_bulk_upload_dataframe(filename, raw)
    parsed = _parse_bulk_update_rows(df)
    candidate_query_ids = [
        str(row.get("queryId") or "").strip()
        for row in parsed["rows"]
        if not row.get("missingQueryId") and not row.get("duplicateQueryId")
    ]
    unique_query_ids = list(dict.fromkeys(candidate_query_ids))
    existing_queries = query_repo.list_by_ids(unique_query_ids)
    existing_queries_by_id = {row.id: row for row in existing_queries}

    analysis = _analyze_bulk_update_rows(
        parsed_rows=parsed["rows"],
        missing_query_id_rows=parsed["missingQueryIdRows"],
        duplicate_query_id_rows=parsed["duplicateQueryIdRows"],
        existing_queries_by_id=existing_queries_by_id,
        group_map_by_id=group_map_by_id,
        group_id_by_name=group_id_by_name,
    )

    if analysis["groupsToCreate"] and not allowCreateGroups:
        raise HTTPException(
            status_code=400,
            detail="Unknown groups detected. Confirm group creation and retry.",
        )

    if analysis["unmappedQueryCount"] > 0 and not skipUnmappedQueryIds:
        raise HTTPException(
            status_code=400,
            detail="Unmapped query IDs detected. Confirm skipping and retry.",
        )

    created_group_names: list[str] = []
    if allowCreateGroups:
        for group_name in analysis["groupsToCreate"]:
            normalized_group_name = str(group_name or "").strip()
            if not normalized_group_name or normalized_group_name in group_id_by_name:
                continue
            created = group_repo.create(group_name=normalized_group_name)
            group_map_by_id[created.id] = created
            group_id_by_name[created.group_name.strip()] = created.id
            created_group_names.append(created.group_name)

    updated_count = 0
    for plan in analysis["plannedUpdates"]:
        group_value = str(plan.get("groupValue") or "").strip()
        resolved_group_id = None
        update_group_id = bool(plan.get("updateGroupId"))
        if update_group_id:
            if not group_value:
                resolved_group_id = ""
            elif group_value in group_map_by_id:
                resolved_group_id = group_value
            elif group_value in group_id_by_name:
                resolved_group_id = group_id_by_name[group_value]
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown group value for bulk update row (queryId={plan.get('queryId')}).",
                )

        updated = query_repo.update(
            str(plan.get("queryId") or ""),
            query_text=plan.get("queryText"),
            expected_result=plan.get("expectedResult"),
            category=plan.get("category"),
            group_id=resolved_group_id,
            update_group_id=update_group_id,
        )
        if updated is not None:
            updated_count += 1

    db.commit()
    return {
        "requestedRowCount": analysis["totalRows"],
        "updatedCount": updated_count,
        "unchangedCount": analysis["unchangedCount"],
        "skippedUnmappedCount": analysis["unmappedQueryCount"],
        "skippedMissingIdCount": len(analysis["missingQueryIdRows"]),
        "skippedDuplicateQueryIdCount": len(analysis["duplicateQueryIdRows"]),
        "createdGroupNames": created_group_names,
    }
