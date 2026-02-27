from __future__ import annotations

import datetime as dt
import io
import json
import os
import uuid
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.environment import get_env_config
from app.core.enums import Environment, EvalStatus, RunStatus
from app.jobs.runner import runner
from app.jobs.validation_evaluate_job import evaluate_validation_run
from app.jobs.validation_execute_job import execute_validation_run
from app.lib.aqb_runtime_utils import dataframe_to_excel_bytes
from app.repositories.validation_queries import ValidationQueryRepository
from app.repositories.validation_query_groups import ValidationQueryGroupRepository
from app.repositories.validation_runs import ValidationRunRepository
from app.repositories.validation_settings import ValidationSettingsRepository
from app.services.validation_compare import compare_validation_runs
from app.services.validation_dashboard import build_group_dashboard, build_test_set_dashboard

router = APIRouter(tags=["validation-runs"])


class AdHocQueryPayload(BaseModel):
    queryText: str = Field(min_length=1)
    expectedResult: str = ""
    category: str = "Happy path"
    logicFieldPath: str = ""
    logicExpectedValue: str = ""


class ValidationRunCreateRequest(BaseModel):
    environment: Environment
    name: Optional[str] = None
    testSetId: Optional[str] = None
    context: Optional[dict[str, Any]] = None
    agentId: Optional[str] = None
    testModel: Optional[str] = None
    evalModel: Optional[str] = None
    repeatInConversation: Optional[int] = None
    conversationRoomCount: Optional[int] = None
    agentParallelCalls: Optional[int] = None
    timeoutMs: Optional[int] = None
    queryIds: list[str] = Field(default_factory=list)
    adHocQuery: Optional[AdHocQueryPayload] = None


class RunSecretPayload(BaseModel):
    bearer: str
    cms: str
    mrs: str
    idempotencyKey: Optional[str] = None
    itemIds: list[str] = Field(default_factory=list)


class EvaluatePayload(BaseModel):
    openaiModel: Optional[str] = None
    maxChars: int = 15000
    maxParallel: Optional[int] = None
    itemIds: list[str] = Field(default_factory=list)


class SaveQueryPayload(BaseModel):
    groupId: str
    category: str = "Happy path"
    createdBy: str = "unknown"
    queryText: Optional[str] = None
    expectedResult: Optional[str] = None
    logicFieldPath: Optional[str] = None
    logicExpectedValue: Optional[str] = None


class UpdateRunItemSnapshotPayload(BaseModel):
    expectedResult: Optional[str] = None
    latencyClass: Optional[str] = None


class ValidationRunUpdateRequest(BaseModel):
    name: Optional[str] = None
    agentId: Optional[str] = None
    evalModel: Optional[str] = None
    repeatInConversation: Optional[int] = None
    conversationRoomCount: Optional[int] = None
    agentParallelCalls: Optional[int] = None
    timeoutMs: Optional[int] = None
    context: Optional[dict[str, Any] | None] = None


RUN_ITEM_ID_COLUMN_CANDIDATES = ["Item ID", "itemId", "runItemId", "run_item_id", "item_id"]
RUN_ITEM_EXPECTED_RESULT_COLUMN_CANDIDATES = ["기대결과", "기대 결과", "expectedResult", "expected_result", "expected"]


def _parse_context_json(raw: Optional[Any]) -> Optional[dict]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        try:
            payload = json.loads(text)
        except Exception:
            return None
        if isinstance(payload, dict):
            return payload
        return None
    return None


def _resolve_openai_api_key() -> Optional[str]:
    return (os.getenv("BACKOFFICE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip() or None


def _serialize_json(value: str) -> Any:
    text = (value or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return text


def _extract_item_latency_class(criteria_text: Optional[str]) -> Optional[str]:
    payload = _serialize_json(criteria_text or "")
    if not isinstance(payload, dict):
        return None
    meta_payload = payload.get("meta")
    if not isinstance(meta_payload, dict):
        return None
    raw_value = str(meta_payload.get("latencyClass") or "").strip().upper()
    if raw_value in {"SINGLE", "MULTI", "UNCLASSIFIED"}:
        return raw_value
    return None


def _execution_stale_threshold_sec(timeout_ms: Optional[int]) -> int:
    timeout_sec = max(1, int((timeout_ms or 0) / 1000))
    return max(300, timeout_sec * 3)


def _reconcile_stuck_execution_run(repo: ValidationRunRepository, run) -> bool:
    if run.status != RunStatus.RUNNING:
        return False

    now = dt.datetime.utcnow()
    threshold_sec = _execution_stale_threshold_sec(run.timeout_ms)
    latest_executed_at = repo.latest_item_executed_at(run.id)
    reference_time = latest_executed_at or run.started_at or run.created_at
    if reference_time is None:
        return False

    elapsed_sec = (now - reference_time).total_seconds()
    if elapsed_sec <= threshold_sec:
        return False

    repo.set_status(run.id, RunStatus.FAILED)
    return True


def _metric_scores(value: str) -> dict[str, float]:
    text = (value or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    out: dict[str, float] = {}
    for key, metric in payload.items():
        if isinstance(metric, (int, float)):
            out[str(key)] = float(metric)
    return out


def _normalize_run_name(name: str | None, fallback: str) -> str:
    normalized = (name or "").strip()
    return normalized if normalized else fallback


DEFAULT_RUN_AGENT_ID = "ORCHESTRATOR_WORKER_V3"
NORMALIZED_RUN_AGENT_ID = "ORCHESTRATOR_ASSISTANT"


def _normalize_agent_mode_value(value: Optional[str]) -> str:
    normalized = (value or "").strip()
    if not normalized or normalized == DEFAULT_RUN_AGENT_ID:
        return NORMALIZED_RUN_AGENT_ID
    return normalized


def _coalesce_text(value: Optional[str], default: str) -> tuple[str, bool]:
    normalized = (value or "").strip()
    if normalized:
        return normalized, False
    default_normalized = (default or "").strip()
    return default_normalized, not normalized


def _coalesce_int(value: Optional[int], default: int, min_value: int = 1) -> tuple[int, bool]:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        parsed = 0
    if parsed >= min_value:
        return parsed, False
    return int(default or min_value), True


def _normalize_run_defaults(
    run,
    *,
    test_model_default: str,
    eval_model_default: str,
    repeat_in_conversation_default: int,
    conversation_room_count_default: int,
    agent_parallel_calls_default: int,
    timeout_ms_default: int,
) -> bool:
    changed = False
    created_at = run.created_at if isinstance(run.created_at, dt.datetime) else dt.datetime.utcnow()
    run.name, changed_name = _coalesce_text(
        run.name,
        _normalize_run_name(None, f"Run {created_at.strftime('%Y-%m-%d %H:%M:%S')}"),
    )
    changed |= changed_name

    run.agent_id, has_agent_changed = _coalesce_text(run.agent_id, NORMALIZED_RUN_AGENT_ID)
    changed |= has_agent_changed
    normalized_agent_id = _normalize_agent_mode_value(run.agent_id)
    if normalized_agent_id != run.agent_id:
        run.agent_id = normalized_agent_id
        changed = True

    run.test_model, changed_test_model = _coalesce_text(run.test_model, test_model_default)
    changed |= changed_test_model

    run.eval_model, changed_eval_model = _coalesce_text(run.eval_model, eval_model_default)
    changed |= changed_eval_model

    run.repeat_in_conversation, changed_repeat = _coalesce_int(
        run.repeat_in_conversation,
        repeat_in_conversation_default,
    )
    changed |= changed_repeat

    run.conversation_room_count, changed_room = _coalesce_int(
        run.conversation_room_count,
        conversation_room_count_default,
    )
    changed |= changed_room

    run.agent_parallel_calls, changed_parallel = _coalesce_int(
        run.agent_parallel_calls,
        agent_parallel_calls_default,
    )
    changed |= changed_parallel

    run.timeout_ms, changed_timeout = _coalesce_int(
        run.timeout_ms,
        timeout_ms_default,
        min_value=1000,
    )
    changed |= changed_timeout

    return changed


def _normalized_header_set(df: pd.DataFrame) -> set[str]:
    return {str(column).replace("\ufeff", "").strip() for column in df.columns}


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


def _load_bulk_update_dataframe(filename: str, raw: bytes) -> pd.DataFrame:
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


def _parse_expected_result_bulk_rows(df: pd.DataFrame) -> dict[str, Any]:
    headers = _normalized_header_set(df)
    has_item_id = any(candidate.replace("\ufeff", "").strip() in headers for candidate in RUN_ITEM_ID_COLUMN_CANDIDATES)
    has_expected_result = any(
        candidate.replace("\ufeff", "").strip() in headers for candidate in RUN_ITEM_EXPECTED_RESULT_COLUMN_CANDIDATES
    )
    if not has_item_id:
        raise HTTPException(
            status_code=400,
            detail="Missing required column: Item ID (Item ID/itemId/runItemId/run_item_id)",
        )
    if not has_expected_result:
        raise HTTPException(
            status_code=400,
            detail="Missing required column: 기대결과 (기대결과/기대 결과/expectedResult/expected_result)",
        )

    rows: list[dict[str, Any]] = []
    missing_item_id_rows: list[int] = []
    duplicate_item_id_rows: list[int] = []
    seen_item_ids: set[str] = set()

    for row_no, series in enumerate(df.to_dict(orient="records"), start=1):
        item_id = _extract_cell(series, RUN_ITEM_ID_COLUMN_CANDIDATES).strip()
        expected_result = _extract_cell(series, RUN_ITEM_EXPECTED_RESULT_COLUMN_CANDIDATES)
        missing_item_id = not item_id
        duplicate_item_id = False
        if missing_item_id:
            missing_item_id_rows.append(row_no)
        elif item_id in seen_item_ids:
            duplicate_item_id = True
            duplicate_item_id_rows.append(row_no)
        else:
            seen_item_ids.add(item_id)

        rows.append(
            {
                "rowNo": row_no,
                "itemId": item_id,
                "expectedResult": expected_result,
                "missingItemId": missing_item_id,
                "duplicateItemId": duplicate_item_id,
            }
        )

    return {
        "rows": rows,
        "missingItemIdRows": missing_item_id_rows,
        "duplicateItemIdRows": duplicate_item_id_rows,
    }


def _analyze_expected_result_bulk_rows(
    *,
    parsed_rows: list[dict[str, Any]],
    missing_item_id_rows: list[int],
    duplicate_item_id_rows: list[int],
    existing_items_by_id: dict[str, Any],
    all_items: list[Any],
) -> dict[str, Any]:
    preview_rows: list[dict[str, Any]] = []
    planned_updates: dict[str, str] = {}
    unmapped_item_rows: list[int] = []
    unchanged_count = 0

    final_expected_result_by_item_id = {
        str(item.id): str(item.expected_result_snapshot or "") for item in all_items
    }

    for row in parsed_rows:
        row_no = int(row["rowNo"])
        item_id = str(row.get("itemId") or "").strip()
        if row.get("missingItemId"):
            preview_rows.append(
                {
                    "rowNo": row_no,
                    "itemId": "",
                    "status": "missing-item-id",
                    "changedFields": [],
                }
            )
            continue
        if row.get("duplicateItemId"):
            preview_rows.append(
                {
                    "rowNo": row_no,
                    "itemId": item_id,
                    "status": "duplicate-item-id",
                    "changedFields": [],
                }
            )
            continue

        existing_item = existing_items_by_id.get(item_id)
        if existing_item is None:
            unmapped_item_rows.append(row_no)
            preview_rows.append(
                {
                    "rowNo": row_no,
                    "itemId": item_id,
                    "status": "unmapped-item-id",
                    "changedFields": [],
                }
            )
            continue

        next_expected_result = str(row.get("expectedResult") or "")
        if not next_expected_result.strip():
            unchanged_count += 1
            preview_rows.append(
                {
                    "rowNo": row_no,
                    "itemId": item_id,
                    "status": "unchanged",
                    "changedFields": [],
                }
            )
            continue

        current_expected_result = str(existing_item.expected_result_snapshot or "")
        if next_expected_result == current_expected_result:
            unchanged_count += 1
            preview_rows.append(
                {
                    "rowNo": row_no,
                    "itemId": item_id,
                    "status": "unchanged",
                    "changedFields": [],
                }
            )
            continue

        planned_updates[item_id] = next_expected_result
        final_expected_result_by_item_id[item_id] = next_expected_result
        preview_rows.append(
            {
                "rowNo": row_no,
                "itemId": item_id,
                "status": "planned-update",
                "changedFields": ["expectedResult"],
            }
        )

    remaining_missing_expected_count_after_apply = sum(
        1 for value in final_expected_result_by_item_id.values() if not str(value or "").strip()
    )
    invalid_rows = sorted(set(missing_item_id_rows + duplicate_item_id_rows))
    valid_rows = max(0, len(preview_rows) - len(missing_item_id_rows) - len(duplicate_item_id_rows))
    return {
        "totalRows": len(parsed_rows),
        "validRows": valid_rows,
        "plannedUpdateCount": len(planned_updates),
        "unchangedCount": unchanged_count,
        "invalidRows": invalid_rows,
        "missingItemIdRows": missing_item_id_rows,
        "duplicateItemIdRows": duplicate_item_id_rows,
        "unmappedItemRows": unmapped_item_rows,
        "previewRows": preview_rows,
        "plannedUpdates": planned_updates,
        "remainingMissingExpectedCountAfterApply": remaining_missing_expected_count_after_apply,
    }


@router.get("/validation-runs")
def list_validation_runs(
    environment: Optional[Environment] = Query(default=None),
    testSetId: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    evaluationStatus: Optional[str] = Query(default=None),
    offset: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    repo = ValidationRunRepository(db)
    setting_repo = ValidationSettingsRepository(db)
    rows = repo.list_runs(
        environment=environment,
        test_set_id=testSetId,
        status=status,
        evaluation_status=evaluationStatus,
        offset=offset,
        limit=limit,
    )
    settings_by_env: dict[Environment, object] = {}
    rows_changed = False
    for row in rows:
        if _reconcile_stuck_execution_run(repo, row):
            rows_changed = True
        cached_setting = settings_by_env.get(row.environment)
        if cached_setting is None:
            cached_setting = setting_repo.get_or_create(row.environment)
            settings_by_env[row.environment] = cached_setting
        if _normalize_run_defaults(
            row,
            test_model_default=cached_setting.test_model_default,
            eval_model_default=cached_setting.eval_model_default,
            repeat_in_conversation_default=cached_setting.repeat_in_conversation_default,
            conversation_room_count_default=cached_setting.conversation_room_count_default,
            agent_parallel_calls_default=cached_setting.agent_parallel_calls_default,
            timeout_ms_default=cached_setting.timeout_ms_default,
        ):
            rows_changed = True
    if rows_changed:
        db.commit()
    return {
        "items": [repo.build_run_payload(row) for row in rows],
        "total": repo.count_runs(
            environment=environment,
            test_set_id=testSetId,
            status=status,
            evaluation_status=evaluationStatus,
        ),
    }


@router.post("/validation-runs")
def create_validation_run(body: ValidationRunCreateRequest, db: Session = Depends(get_db)):
    run_repo = ValidationRunRepository(db)
    query_repo = ValidationQueryRepository(db)
    setting_repo = ValidationSettingsRepository(db)

    setting = setting_repo.get_or_create(body.environment)
    agent_id = _normalize_agent_mode_value(body.agentId)
    test_model = (body.testModel or setting.test_model_default).strip()
    eval_model = (body.evalModel or setting.eval_model_default).strip()
    repeat_in_conversation = body.repeatInConversation if body.repeatInConversation is not None else setting.repeat_in_conversation_default
    # conversation_room_count is treated as sequential room batches in execution.
    conversation_room_count = body.conversationRoomCount if body.conversationRoomCount is not None else setting.conversation_room_count_default
    # agent_parallel_calls is treated as query-level parallelism per room batch.
    agent_parallel_calls = body.agentParallelCalls if body.agentParallelCalls is not None else setting.agent_parallel_calls_default
    timeout_ms = body.timeoutMs if body.timeoutMs is not None else setting.timeout_ms_default

    options: dict[str, Any] = {
        "targetAssistant": agent_id,
    }
    if body.context is not None:
        options["context"] = body.context
    run_name = _normalize_run_name(
        body.name,
        f"Run {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    )
    has_query_ids = bool(body.queryIds)
    has_ad_hoc_query = body.adHocQuery is not None

    if has_query_ids and has_ad_hoc_query:
        raise HTTPException(status_code=400, detail="queryIds and adHocQuery cannot be used together")
    if not has_query_ids and not has_ad_hoc_query:
        raise HTTPException(status_code=400, detail="queryIds or adHocQuery is required")

    run = run_repo.create_run(
        environment=body.environment,
        test_set_id=body.testSetId,
        name=run_name,
        agent_id=agent_id,
        test_model=test_model,
        eval_model=eval_model,
        repeat_in_conversation=repeat_in_conversation,
        conversation_room_count=conversation_room_count,
        agent_parallel_calls=agent_parallel_calls,
        timeout_ms=timeout_ms,
        options=options,
    )

    items_payload: list[dict[str, Any]] = []
    ordinal = 1
    if has_query_ids:
        selected_queries = query_repo.list_by_ids(body.queryIds)
        if len(selected_queries) != len(body.queryIds):
            raise HTTPException(status_code=404, detail="Some queries were not found")
        for room_index in range(1, int(conversation_room_count) + 1):
            for repeat_index in range(1, int(repeat_in_conversation) + 1):
                for query in selected_queries:
                    target_assistant = (query.target_assistant or "").strip() or agent_id
                    items_payload.append(
                        {
                            "ordinal": ordinal,
                            "query_id": query.id,
                            "query_text_snapshot": query.query_text,
                            "expected_result_snapshot": query.expected_result,
                            "category_snapshot": query.category,
                            "logic_field_path_snapshot": query.logic_field_path,
                            "logic_expected_value_snapshot": query.logic_expected_value,
                            "context_json_snapshot": query.context_json,
                            "target_assistant_snapshot": target_assistant,
                            "conversation_room_index": room_index,
                            "repeat_index": repeat_index,
                        },
                    )
                    ordinal += 1
    else:
        for room_index in range(1, int(conversation_room_count) + 1):
            for repeat_index in range(1, int(repeat_in_conversation) + 1):
                items_payload.append(
                    {
                        "ordinal": ordinal,
                        "query_id": None,
                        "query_text_snapshot": body.adHocQuery.queryText,
                        "expected_result_snapshot": body.adHocQuery.expectedResult,
                        "category_snapshot": body.adHocQuery.category or "Happy path",
                        "logic_field_path_snapshot": body.adHocQuery.logicFieldPath or "",
                        "logic_expected_value_snapshot": body.adHocQuery.logicExpectedValue or "",
                        "context_json_snapshot": "",
                        "target_assistant_snapshot": "",
                        "conversation_room_index": room_index,
                        "repeat_index": repeat_index,
                    }
                )
                ordinal += 1

    run_repo.add_items(run.id, items_payload)
    db.commit()
    return run_repo.build_run_payload(run)


@router.get("/validation-runs/{run_id}")
def get_validation_run(run_id: str, db: Session = Depends(get_db)):
    repo = ValidationRunRepository(db)
    setting_repo = ValidationSettingsRepository(db)
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    setting = setting_repo.get_or_create(run.environment)
    run_changed = _reconcile_stuck_execution_run(repo, run)
    if _normalize_run_defaults(
        run,
        test_model_default=setting.test_model_default,
        eval_model_default=setting.eval_model_default,
        repeat_in_conversation_default=setting.repeat_in_conversation_default,
        conversation_room_count_default=setting.conversation_room_count_default,
        agent_parallel_calls_default=setting.agent_parallel_calls_default,
        timeout_ms_default=setting.timeout_ms_default,
    ):
        run_changed = True
    if run_changed:
        db.commit()
    return repo.build_run_payload(run)


@router.patch("/validation-runs/{run_id}")
def update_validation_run(run_id: str, body: ValidationRunUpdateRequest, db: Session = Depends(get_db)):
    repo = ValidationRunRepository(db)
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != RunStatus.PENDING:
        raise HTTPException(status_code=409, detail="Only PENDING runs can be updated")

    payload = body.model_dump(exclude_unset=True)
    updated = repo.update_run(
        run_id,
        name=payload.get("name"),
        agent_id=payload.get("agentId"),
        eval_model=payload.get("evalModel"),
        repeat_in_conversation=payload.get("repeatInConversation"),
        conversation_room_count=payload.get("conversationRoomCount"),
        agent_parallel_calls=payload.get("agentParallelCalls"),
        timeout_ms=payload.get("timeoutMs"),
        context=payload.get("context"),
        update_context="context" in payload,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Run not found")
    db.commit()
    return repo.build_run_payload(updated)


@router.delete("/validation-runs/{run_id}")
def delete_validation_run(run_id: str, db: Session = Depends(get_db)):
    repo = ValidationRunRepository(db)
    try:
        deleted = repo.delete_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Run not found")
    db.commit()
    return {"ok": True}


@router.get("/validation-runs/{run_id}/items")
def list_validation_run_items(run_id: str, offset: int = 0, limit: int = 1000, db: Session = Depends(get_db)):
    repo = ValidationRunRepository(db)
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    items = repo.list_items(run_id, offset=offset, limit=limit)
    logic_map = repo.get_logic_eval_map([row.id for row in items])
    llm_map = repo.get_llm_eval_map([row.id for row in items])
    return {
        "items": [
            {
                "id": row.id,
                "runId": row.run_id,
                "queryId": row.query_id,
                "ordinal": row.ordinal,
                "queryText": row.query_text_snapshot,
                "expectedResult": row.expected_result_snapshot,
                "category": row.category_snapshot,
                "logicFieldPath": row.logic_field_path_snapshot,
                "logicExpectedValue": row.logic_expected_value_snapshot,
                "contextJson": row.context_json_snapshot,
                "targetAssistant": row.target_assistant_snapshot,
                "conversationRoomIndex": row.conversation_room_index,
                "repeatIndex": row.repeat_index,
                "conversationId": row.conversation_id,
                "rawResponse": row.raw_response,
                "latencyMs": row.latency_ms,
                "error": row.error,
                "rawJson": row.raw_json,
                "executedAt": row.executed_at,
                "responseTimeSec": row.latency_ms / 1000 if row.latency_ms is not None else None,
                "latencyClass": _extract_item_latency_class(row.applied_criteria_json),
                "logicEvaluation": (
                    {
                        "result": logic_map[row.id].result,
                        "evalItems": _serialize_json(logic_map[row.id].eval_items_json),
                        "failReason": logic_map[row.id].fail_reason,
                        "evaluatedAt": logic_map[row.id].evaluated_at,
                    }
                    if row.id in logic_map
                    else None
                ),
                "llmEvaluation": (
                    {
                        "status": llm_map[row.id].status,
                        "evalModel": llm_map[row.id].eval_model,
                        "metricScores": _serialize_json(llm_map[row.id].metric_scores_json),
                        "totalScore": llm_map[row.id].total_score,
                        "comment": llm_map[row.id].llm_comment,
                        "evaluatedAt": llm_map[row.id].evaluated_at,
                    }
                    if row.id in llm_map
                    else None
                ),
            }
            for row in items
        ],
        "total": repo.count_items(run_id),
    }


@router.post("/validation-runs/{run_id}/execute")
async def execute_run(run_id: str, body: RunSecretPayload, db: Session = Depends(get_db)):
    repo = ValidationRunRepository(db)
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    target_item_ids = list(dict.fromkeys([str(item_id).strip() for item_id in (body.itemIds or []) if str(item_id).strip()]))
    if target_item_ids:
        if run.status == RunStatus.RUNNING and _reconcile_stuck_execution_run(repo, run):
            db.commit()
            run = repo.get_run(run_id) or run
        if run.status == RunStatus.RUNNING:
            raise HTTPException(status_code=409, detail="Run is still executing")
        if run.eval_status == EvalStatus.RUNNING:
            raise HTTPException(status_code=409, detail="Evaluation is already running")
        target_items = repo.list_items_by_ids(run.id, target_item_ids)
        if len(target_items) != len(target_item_ids):
            raise HTTPException(status_code=400, detail="Some itemIds were not found in this run")
        repo.reset_items_for_execution(run.id, target_item_ids)
        repo.clear_score_snapshots_for_run(run.id)
        repo.reset_eval_state_to_pending(run.id)
    else:
        if run.status != RunStatus.PENDING:
            raise HTTPException(status_code=409, detail="Only PENDING runs can be executed")

    options = json.loads(run.options_json or "{}")
    cfg = get_env_config(run.environment)
    default_context = _parse_context_json(options.get("context") or options.get("contextJson"))
    run_default_target_assistant = options.get("targetAssistant")

    job_id = str(uuid.uuid4())

    def _job():
        return execute_validation_run(
            run.id,
            cfg.base_url,
            cfg.origin,
            cfg.referer,
            body.bearer,
            body.cms,
            body.mrs,
            default_context,
            run_default_target_assistant,
            # Query-level parallelism (not room count).
            run.agent_parallel_calls,
            run.timeout_ms,
            target_item_ids or None,
        )

    repo.set_status(run.id, RunStatus.RUNNING)
    repo.set_eval_status(run.id, EvalStatus.PENDING)
    db.commit()
    runner.run(job_id, _job)
    return {"jobId": job_id, "status": runner.jobs[job_id]}


@router.post("/validation-runs/{run_id}/evaluate")
async def evaluate_run(run_id: str, body: EvaluatePayload, db: Session = Depends(get_db)):
    repo = ValidationRunRepository(db)
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status == RunStatus.PENDING:
        raise HTTPException(status_code=409, detail="Run must be executed before evaluation")
    if run.status == RunStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Run is still executing")
    if run.eval_status == EvalStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Evaluation is already running")

    target_item_ids = list(dict.fromkeys([str(item_id).strip() for item_id in (body.itemIds or []) if str(item_id).strip()]))
    if target_item_ids:
        run_items = repo.list_items_by_ids(run.id, target_item_ids)
        if len(run_items) != len(target_item_ids):
            raise HTTPException(status_code=400, detail="Some itemIds were not found in this run")
    else:
        run_items = repo.list_items(run.id, limit=100000)

    has_execution_result = any(
        bool(item.executed_at)
        or bool(str(item.error or "").strip())
        or bool(str(item.raw_response or "").strip())
        for item in run_items
    )
    if not has_execution_result:
        raise HTTPException(status_code=409, detail="No execution results found for evaluation")

    missing_expected_items = [
        item for item in run_items if not str(item.expected_result_snapshot or "").strip()
    ]
    if missing_expected_items:
        sample_query_ids = [
            str(item.query_id or item.id or "")
            for item in missing_expected_items[:5]
            if str(item.query_id or item.id or "").strip()
        ]
        raise HTTPException(
            status_code=409,
            detail={
                "code": "expected_result_missing",
                "message": "expected_result is required for all run items",
                "missingCount": len(missing_expected_items),
                "sampleQueryIds": sample_query_ids,
            },
        )

    job_id = str(uuid.uuid4())
    eval_model = body.openaiModel or run.eval_model
    eval_parallel = body.maxParallel if body.maxParallel is not None else run.agent_parallel_calls
    openai_key = _resolve_openai_api_key()
    if not openai_key:
        raise HTTPException(status_code=400, detail="OpenAI API key is not configured. Set BACKOFFICE_OPENAI_API_KEY or OPENAI_API_KEY.")

    def _job():
        return evaluate_validation_run(
            run.id,
            openai_key,
            eval_model,
            body.maxChars,
            int(eval_parallel),
            target_item_ids or None,
        )

    repo.set_eval_status(run.id, EvalStatus.RUNNING)
    db.commit()
    runner.run(job_id, _job)
    return {"jobId": job_id, "status": runner.jobs[job_id]}


@router.post("/validation-runs/{run_id}/rerun")
def rerun(run_id: str, db: Session = Depends(get_db)):
    repo = ValidationRunRepository(db)
    try:
        cloned = repo.clone_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return repo.build_run_payload(cloned)


@router.get("/validation-runs/{run_id}/export.xlsx")
def export_run(run_id: str, includeDebug: bool = Query(default=False), db: Session = Depends(get_db)):
    repo = ValidationRunRepository(db)
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    items = repo.list_items(run_id, limit=100000)
    if not items:
        raise HTTPException(status_code=404, detail="No items")

    logic_map = repo.get_logic_eval_map([row.id for row in items])
    llm_map = repo.get_llm_eval_map([row.id for row in items])
    rows: list[dict[str, Any]] = []
    for row in items:
        llm = llm_map.get(row.id)
        llm_metrics = _metric_scores(llm.metric_scores_json) if llm is not None else {}
        llm_comment = str(llm.llm_comment or "") if llm is not None else ""
        output_row = {
            "Run ID": run.id,
            "Item ID": row.id,
            "Ordinal": row.ordinal,
            "Query ID": row.query_id or "",
            "질의": row.query_text_snapshot,
            "기대결과": row.expected_result_snapshot,
            "카테고리": row.category_snapshot,
            "방/반복": f"{row.conversation_room_index}/{row.repeat_index}",
            "실행시각": row.executed_at.isoformat() if row.executed_at else "",
            "응답": row.raw_response or "",
            "오류": row.error or "",
            "Logic 결과": logic_map[row.id].result if row.id in logic_map else "",
            "Logic 사유": logic_map[row.id].fail_reason if row.id in logic_map else "",
            "LLM 상태": llm.status if llm is not None else "",
            "LLM 모델": llm.eval_model if llm is not None else "",
            "의도충족 점수": llm_metrics.get("intent", ""),
            "정확성 점수": llm_metrics.get("accuracy", ""),
            "일관성 점수": llm_metrics.get("consistency", ""),
            "속도(SINGLE) 점수": llm_metrics.get("latencySingle", ""),
            "속도(MULTI) 점수": llm_metrics.get("latencyMulti", ""),
            "안정성 점수": llm_metrics.get("stability", ""),
            "LLM 평가 코멘트": llm_comment,
            "Raw JSON": row.raw_json or "",
        }
        if includeDebug:
            output_row["LLM 출력(JSON)"] = llm.llm_output_json if llm is not None else ""
            output_row["프롬프트 버전"] = llm.prompt_version if llm is not None else ""
            output_row["입력 해시"] = llm.input_hash if llm is not None else ""
        rows.append(output_row)

    df = pd.DataFrame(rows)
    xlsx = dataframe_to_excel_bytes(df, sheet_name="validation_history")
    file_name = f"validation_run_{run_id}_{dt.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(
        iter([xlsx]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


@router.get("/validation-runs/{run_id}/expected-results/template.csv")
def download_run_expected_results_template(run_id: str, db: Session = Depends(get_db)):
    repo = ValidationRunRepository(db)
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    items = repo.list_items(run_id, limit=100000)
    if not items:
        raise HTTPException(status_code=404, detail="No items")

    rows = [
        {
            "Item ID": item.id,
            "Query ID": item.query_id or "",
            "방/반복": f"{item.conversation_room_index}/{item.repeat_index}",
            "질의": item.query_text_snapshot,
            "기존 기대결과": item.expected_result_snapshot,
            "기대결과": item.expected_result_snapshot,
        }
        for item in items
    ]
    csv_text = pd.DataFrame(rows).to_csv(index=False)
    csv_bytes = ("\ufeff" + csv_text).encode("utf-8")
    file_name = f"validation_run_{run_id}_expected_results_template.csv"
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


@router.post("/validation-runs/{run_id}/expected-results/bulk-update/preview")
async def preview_run_expected_results_bulk_update(
    run_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    repo = ValidationRunRepository(db)
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    filename = (file.filename or "").lower()
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")

    df = _load_bulk_update_dataframe(filename, raw)
    parsed = _parse_expected_result_bulk_rows(df)
    candidate_item_ids = [
        str(row.get("itemId") or "").strip()
        for row in parsed["rows"]
        if not row.get("missingItemId") and not row.get("duplicateItemId")
    ]
    unique_item_ids = list(dict.fromkeys(candidate_item_ids))
    existing_items = repo.list_items_by_ids(run.id, unique_item_ids)
    existing_items_by_id = {item.id: item for item in existing_items}
    all_items = repo.list_items(run.id, limit=100000)

    analysis = _analyze_expected_result_bulk_rows(
        parsed_rows=parsed["rows"],
        missing_item_id_rows=parsed["missingItemIdRows"],
        duplicate_item_id_rows=parsed["duplicateItemIdRows"],
        existing_items_by_id=existing_items_by_id,
        all_items=all_items,
    )
    return {
        "totalRows": analysis["totalRows"],
        "validRows": analysis["validRows"],
        "plannedUpdateCount": analysis["plannedUpdateCount"],
        "unchangedCount": analysis["unchangedCount"],
        "invalidRows": analysis["invalidRows"],
        "missingItemIdRows": analysis["missingItemIdRows"],
        "duplicateItemIdRows": analysis["duplicateItemIdRows"],
        "unmappedItemRows": analysis["unmappedItemRows"],
        "previewRows": analysis["previewRows"],
        "remainingMissingExpectedCountAfterApply": analysis["remainingMissingExpectedCountAfterApply"],
    }


@router.post("/validation-runs/{run_id}/expected-results/bulk-update")
async def bulk_update_run_expected_results(
    run_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    repo = ValidationRunRepository(db)
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status == RunStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Run is still executing")
    if run.eval_status == EvalStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Evaluation is already running")

    filename = (file.filename or "").lower()
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")

    df = _load_bulk_update_dataframe(filename, raw)
    parsed = _parse_expected_result_bulk_rows(df)
    candidate_item_ids = [
        str(row.get("itemId") or "").strip()
        for row in parsed["rows"]
        if not row.get("missingItemId") and not row.get("duplicateItemId")
    ]
    unique_item_ids = list(dict.fromkeys(candidate_item_ids))
    existing_items = repo.list_items_by_ids(run.id, unique_item_ids)
    existing_items_by_id = {item.id: item for item in existing_items}
    all_items = repo.list_items(run.id, limit=100000)
    analysis = _analyze_expected_result_bulk_rows(
        parsed_rows=parsed["rows"],
        missing_item_id_rows=parsed["missingItemIdRows"],
        duplicate_item_id_rows=parsed["duplicateItemIdRows"],
        existing_items_by_id=existing_items_by_id,
        all_items=all_items,
    )

    updated_count = repo.bulk_update_item_expected_results(run.id, analysis["plannedUpdates"])
    eval_reset = False
    if updated_count > 0:
        repo.clear_llm_evaluations_for_run(run.id)
        repo.clear_score_snapshots_for_run(run.id)
        repo.reset_eval_state_to_pending(run.id)
        eval_reset = True

    all_items_after = repo.list_items(run.id, limit=100000)
    remaining_missing_expected_count = sum(
        1 for item in all_items_after if not str(item.expected_result_snapshot or "").strip()
    )
    db.commit()
    return {
        "requestedRowCount": analysis["totalRows"],
        "updatedCount": int(updated_count),
        "unchangedCount": analysis["unchangedCount"],
        "skippedMissingItemIdCount": len(analysis["missingItemIdRows"]),
        "skippedDuplicateItemIdCount": len(analysis["duplicateItemIdRows"]),
        "skippedUnmappedCount": len(analysis["unmappedItemRows"]),
        "evalReset": eval_reset,
        "remainingMissingExpectedCount": remaining_missing_expected_count,
    }


@router.post("/validation-runs/{run_id}/items/{item_id}/save-query")
def save_run_item_as_query(run_id: str, item_id: str, body: SaveQueryPayload, db: Session = Depends(get_db)):
    run_repo = ValidationRunRepository(db)
    query_repo = ValidationQueryRepository(db)
    group_repo = ValidationQueryGroupRepository(db)

    run = run_repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    item = run_repo.get_item(item_id)
    if item is None or item.run_id != run.id:
        raise HTTPException(status_code=404, detail="Run item not found")
    if group_repo.get(body.groupId) is None:
        raise HTTPException(status_code=404, detail="Group not found")

    query = query_repo.create(
        query_text=body.queryText or item.query_text_snapshot,
        expected_result=body.expectedResult or item.expected_result_snapshot,
        category=body.category or item.category_snapshot,
        group_id=body.groupId,
        logic_field_path=body.logicFieldPath if body.logicFieldPath is not None else item.logic_field_path_snapshot,
        logic_expected_value=body.logicExpectedValue if body.logicExpectedValue is not None else item.logic_expected_value_snapshot,
        context_json=item.context_json_snapshot,
        target_assistant=item.target_assistant_snapshot,
        created_by=body.createdBy or "unknown",
    )
    db.commit()
    return {"queryId": query.id}


@router.patch("/validation-runs/{run_id}/items/{item_id}")
def update_run_item_snapshot(run_id: str, item_id: str, body: UpdateRunItemSnapshotPayload, db: Session = Depends(get_db)):
    repo = ValidationRunRepository(db)
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    item = repo.get_item(item_id)
    if item is None or item.run_id != run.id:
        raise HTTPException(status_code=404, detail="Run item not found")

    payload = body.model_dump(exclude_unset=True)
    has_latency_class = "latencyClass" in payload
    next_latency_class: Optional[str] = None
    if has_latency_class:
        raw_latency_class = str(payload.get("latencyClass") or "").strip().upper()
        if not raw_latency_class:
            next_latency_class = None
        elif raw_latency_class in {"SINGLE", "MULTI", "UNCLASSIFIED"}:
            next_latency_class = raw_latency_class
        else:
            raise HTTPException(status_code=400, detail="latencyClass must be SINGLE, MULTI, or UNCLASSIFIED")

    updated = repo.update_item_snapshots(
        item.id,
        expected_result_snapshot=(
            str(payload.get("expectedResult") or "")
            if "expectedResult" in payload
            else None
        ),
        latency_class=next_latency_class,
        update_latency_class=has_latency_class,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Run item not found")

    db.commit()
    return {
        "id": updated.id,
        "runId": updated.run_id,
        "expectedResult": updated.expected_result_snapshot,
        "latencyClass": _extract_item_latency_class(updated.applied_criteria_json),
    }


@router.get("/validation-runs/{run_id}/compare")
def compare_run(run_id: str, baseRunId: Optional[str] = Query(default=None), db: Session = Depends(get_db)):
    repo = ValidationRunRepository(db)
    try:
        return compare_validation_runs(repo, run_id, base_run_id=baseRunId)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/validation-dashboard/groups/{group_id}")
def group_dashboard(group_id: str, db: Session = Depends(get_db)):
    return build_group_dashboard(db, group_id)


@router.get("/validation-dashboard/test-sets/{test_set_id}")
def test_set_dashboard(
    test_set_id: str,
    runId: Optional[str] = Query(default=None),
    dateFrom: Optional[str] = Query(default=None),
    dateTo: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        return build_test_set_dashboard(db, test_set_id, run_id=runId, date_from=dateFrom, date_to=dateTo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
