from __future__ import annotations

import datetime as dt
import json
import os
import uuid
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
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
    llmEvalCriteria: Any = None
    logicFieldPath: str = ""
    logicExpectedValue: str = ""


class ValidationRunCreateRequest(BaseModel):
    mode: str = "REGISTERED"
    environment: Environment
    testSetId: Optional[str] = None
    agentId: Optional[str] = None
    testModel: Optional[str] = None
    evalModel: Optional[str] = None
    repeatInConversation: Optional[int] = None
    conversationRoomCount: Optional[int] = None
    agentParallelCalls: Optional[int] = None
    timeoutMs: Optional[int] = None
    queryIds: list[str] = Field(default_factory=list)
    adHocQuery: Optional[AdHocQueryPayload] = None

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        mode = (value or "").upper()
        if mode not in {"REGISTERED", "AD_HOC"}:
            raise ValueError("mode must be REGISTERED or AD_HOC")
        return mode


class RunSecretPayload(BaseModel):
    bearer: str
    cms: str
    mrs: str
    idempotencyKey: Optional[str] = None


class EvaluatePayload(BaseModel):
    openaiModel: Optional[str] = None
    maxChars: int = 15000
    maxParallel: Optional[int] = None


class SaveQueryPayload(BaseModel):
    groupId: str
    category: str = "Happy path"
    createdBy: str = "unknown"
    queryText: Optional[str] = None
    expectedResult: Optional[str] = None
    llmEvalCriteria: Any = None
    logicFieldPath: Optional[str] = None
    logicExpectedValue: Optional[str] = None


def _parse_context_json(raw: Optional[str]) -> Optional[dict]:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except Exception:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _resolve_openai_api_key() -> Optional[str]:
    return (os.getenv("BACKOFFICE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip() or None


def _json_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _serialize_json(value: str) -> Any:
    text = (value or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return text


@router.get("/validation-runs")
def list_validation_runs(
    environment: Optional[Environment] = Query(default=None),
    testSetId: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    offset: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    repo = ValidationRunRepository(db)
    rows = repo.list_runs(environment=environment, test_set_id=testSetId, status=status, offset=offset, limit=limit)
    return {
        "items": [repo.build_run_payload(row) for row in rows],
        "total": repo.count_runs(environment=environment, test_set_id=testSetId, status=status),
    }


@router.post("/validation-runs")
def create_validation_run(body: ValidationRunCreateRequest, db: Session = Depends(get_db)):
    run_repo = ValidationRunRepository(db)
    query_repo = ValidationQueryRepository(db)
    group_repo = ValidationQueryGroupRepository(db)
    setting_repo = ValidationSettingsRepository(db)

    setting = setting_repo.get_or_create(body.environment)
    agent_id = (body.agentId or "ORCHESTRATOR_WORKER_V3").strip()
    test_model = (body.testModel or setting.test_model_default).strip()
    eval_model = (body.evalModel or setting.eval_model_default).strip()
    repeat_in_conversation = body.repeatInConversation if body.repeatInConversation is not None else setting.repeat_in_conversation_default
    conversation_room_count = body.conversationRoomCount if body.conversationRoomCount is not None else setting.conversation_room_count_default
    agent_parallel_calls = body.agentParallelCalls if body.agentParallelCalls is not None else setting.agent_parallel_calls_default
    timeout_ms = body.timeoutMs if body.timeoutMs is not None else setting.timeout_ms_default

    options: dict[str, Any] = {}
    run = run_repo.create_run(
        environment=body.environment,
        mode=body.mode,
        test_set_id=body.testSetId,
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
    if body.mode == "REGISTERED":
        if not body.queryIds:
            raise HTTPException(status_code=400, detail="queryIds is required for REGISTERED mode")
        selected_queries = query_repo.list_by_ids(body.queryIds)
        if len(selected_queries) != len(body.queryIds):
            raise HTTPException(status_code=404, detail="Some queries were not found")
        groups = {row.id: row for row in group_repo.list(limit=100000)}

        for room_index in range(1, int(conversation_room_count) + 1):
            for repeat_index in range(1, int(repeat_in_conversation) + 1):
                for query in selected_queries:
                    group_default = groups.get(query.group_id).llm_eval_criteria_default_json if query.group_id in groups else ""
                    group_default_target = groups.get(query.group_id).default_target_assistant if query.group_id in groups else ""
                    criteria = query.llm_eval_criteria_json or group_default or ""
                    target_assistant = (query.target_assistant or "").strip() or (group_default_target or "").strip()
                    items_payload.append(
                        {
                            "ordinal": ordinal,
                            "query_id": query.id,
                            "query_text_snapshot": query.query_text,
                            "expected_result_snapshot": query.expected_result,
                            "category_snapshot": query.category,
                            "applied_criteria_json": criteria,
                            "logic_field_path_snapshot": query.logic_field_path,
                            "logic_expected_value_snapshot": query.logic_expected_value,
                            "context_json_snapshot": query.context_json,
                            "target_assistant_snapshot": target_assistant,
                            "conversation_room_index": room_index,
                            "repeat_index": repeat_index,
                        }
                    )
                    ordinal += 1
    else:
        if body.adHocQuery is None:
            raise HTTPException(status_code=400, detail="adHocQuery is required for AD_HOC mode")

        for room_index in range(1, int(conversation_room_count) + 1):
            for repeat_index in range(1, int(repeat_in_conversation) + 1):
                items_payload.append(
                    {
                        "ordinal": ordinal,
                        "query_id": None,
                        "query_text_snapshot": body.adHocQuery.queryText,
                        "expected_result_snapshot": body.adHocQuery.expectedResult,
                        "category_snapshot": body.adHocQuery.category or "Happy path",
                        "applied_criteria_json": _json_text(body.adHocQuery.llmEvalCriteria),
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
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return repo.build_run_payload(run)


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
                "appliedCriteria": _serialize_json(row.applied_criteria_json),
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
    if run.status != RunStatus.PENDING:
        raise HTTPException(status_code=409, detail="Only PENDING runs can be executed")

    options = json.loads(run.options_json or "{}")
    cfg = get_env_config(run.environment)
    default_context = _parse_context_json(options.get("contextJson"))
    default_target_assistant = options.get("targetAssistant")

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
            default_target_assistant,
            run.agent_parallel_calls,
            run.timeout_ms,
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
    if repo.count_done_items(run.id) == 0 and repo.count_error_items(run.id) == 0:
        raise HTTPException(status_code=409, detail="No execution results found for evaluation")

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
def export_run(run_id: str, db: Session = Depends(get_db)):
    repo = ValidationRunRepository(db)
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    items = repo.list_items(run_id, limit=100000)
    if not items:
        raise HTTPException(status_code=404, detail="No items")

    logic_map = repo.get_logic_eval_map([row.id for row in items])
    llm_map = repo.get_llm_eval_map([row.id for row in items])
    df = pd.DataFrame(
        [
            {
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
                "LLM 상태": llm_map[row.id].status if row.id in llm_map else "",
                "LLM 모델": llm_map[row.id].eval_model if row.id in llm_map else "",
                "LLM 점수": llm_map[row.id].total_score if row.id in llm_map else "",
                "LLM 코멘트": llm_map[row.id].llm_comment if row.id in llm_map else "",
                "Raw JSON": row.raw_json or "",
            }
            for row in items
        ]
    )
    xlsx = dataframe_to_excel_bytes(df, sheet_name="validation_history")
    file_name = f"validation_run_{run_id}_{dt.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(
        iter([xlsx]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


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
        llm_eval_criteria=body.llmEvalCriteria if body.llmEvalCriteria is not None else item.applied_criteria_json,
        logic_field_path=body.logicFieldPath if body.logicFieldPath is not None else item.logic_field_path_snapshot,
        logic_expected_value=body.logicExpectedValue if body.logicExpectedValue is not None else item.logic_expected_value_snapshot,
        context_json=item.context_json_snapshot,
        target_assistant=item.target_assistant_snapshot,
        created_by=body.createdBy or "unknown",
    )
    db.commit()
    return {"queryId": query.id}


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
