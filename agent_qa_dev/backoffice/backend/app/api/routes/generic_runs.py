from __future__ import annotations

import datetime as dt
import json
import uuid
import logging
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.environment import get_env_config
from app.core.enums import Environment
from app.jobs.generic_evaluate_job import evaluate_generic_run
from app.jobs.generic_execute_job import execute_generic_run
from app.jobs.runner import runner
from app.lib.aqb_common_utils import build_generic_csv_template
from app.lib.aqb_runtime_utils import dataframe_to_excel_bytes
from app.models.generic_run_row import GenericRunRow
from app.repositories.generic_runs import GenericRunRepository
from app.services.csv_ingestion import parse_csv_bytes, parse_rows_json
from app.services.run_compare import compare_runs

router = APIRouter(tags=["generic-runs"])


class RunSecretPayload(BaseModel):
    bearer: str
    cms: str
    mrs: str
    openaiKey: Optional[str] = None
    idempotencyKey: Optional[str] = None


class EvaluatePayload(BaseModel):
    openaiKey: Optional[str] = None
    openaiModel: str = "gpt-5.2"
    maxChars: int = 15000
    maxParallel: int = 3


class AddRowRequest(BaseModel):
    query: str
    llmCriteria: str = ""
    fieldPath: str = ""
    expectedValue: str = ""

    @field_validator("query")
    @classmethod
    def query_must_not_blank(cls, value: str) -> str:
        if not str(value or "").strip():
            raise ValueError("query is required")
        return str(value)


class DirectRunRequest(BaseModel):
    environment: Environment
    query: str
    contextJson: Optional[str] = None
    targetAssistant: Optional[str] = None
    maxParallel: int = 3
    maxChars: int = 15000
    openaiModel: str = "gpt-5.2"
    priceConfig: Optional[str] = None
    llmCriteria: str = ""
    fieldPath: str = ""
    expectedValue: str = ""
    bearer: str
    cms: str
    mrs: str
    openaiKey: Optional[str] = None

    @field_validator("query")
    @classmethod
    def query_must_not_blank(cls, value: str) -> str:
        if not str(value or "").strip():
            raise ValueError("query is required")
        return str(value)

    @field_validator("maxParallel")
    @classmethod
    def max_parallel_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("maxParallel must be >= 1")
        return value


def _build_context(options: dict[str, Any]) -> Optional[dict]:
    context = None
    raw = options.get("contextJson")
    if raw:
        try:
            parsed = json.loads(str(raw))
            if isinstance(parsed, dict):
                context = parsed
        except Exception:
            context = None
    return context


def _build_run_payload(run_id: str, run, options: dict[str, Any], repo: GenericRunRepository):
    return {
        "runId": run_id,
        "environment": run.environment.value,
        "status": run.status.value,
        "baseRunId": run.base_run_id,
        "createdAt": run.created_at,
        "startedAt": run.started_at,
        "finishedAt": run.finished_at,
        "totalRows": repo.count_rows(run_id),
        "doneRows": repo.count_done_rows(run_id),
        "errorRows": repo.count_error_rows(run_id),
        "llmDoneRows": repo.count_llm_done_rows(run_id),
        "options": options,
    }


@router.get("/generic-runs/template")
def download_template():
    csv_bytes = build_generic_csv_template()
    file_name = "generic_template.csv"
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


@router.post("/generic-runs")
async def create_generic_run(
    environment: Environment = Form(...),
    maxParallel: int = Form(3),
    contextJson: Optional[str] = Form(None),
    targetAssistant: Optional[str] = Form(None),
    openaiModel: Optional[str] = Form(None),
    priceConfig: Optional[str] = Form(None),
    rowsJson: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    repo = GenericRunRepository(db)
    options = {
        "maxParallel": maxParallel,
        "contextJson": contextJson,
        "targetAssistant": targetAssistant,
    }

    if file is None and not rowsJson:
        raise HTTPException(400, "file or rowsJson is required")

    if file is not None:
        rows = parse_csv_bytes(await file.read())
    else:
        rows = parse_rows_json(rowsJson or "[]")

    run = repo.create_run(environment, options)
    row_ids = repo.add_rows(run.id, rows)
    db.commit()

    return {
        "runId": run.id,
        "status": run.status.value,
        "rows": len(row_ids),
    }


@router.post("/generic-runs/direct")
async def create_direct_run(payload: DirectRunRequest, db: Session = Depends(get_db)):
    repo = GenericRunRepository(db)
    try:
        options = {
            "maxParallel": payload.maxParallel,
            "contextJson": payload.contextJson,
            "targetAssistant": payload.targetAssistant,
        }
        run = repo.create_run(payload.environment, options)
        row_id = repo.add_row(
            run.id,
            query=payload.query,
            llm_criteria=payload.llmCriteria,
            field_path=payload.fieldPath,
            expected_value=payload.expectedValue,
        )
        db.commit()

        cfg = get_env_config(payload.environment)
        context = _build_context(payload.model_dump())

        job_id = str(uuid.uuid4())

        def _job():
            return execute_generic_run(
                run.id,
                cfg.base_url,
                cfg.origin,
                cfg.referer,
                payload.bearer,
                payload.cms,
                payload.mrs,
                context,
                payload.targetAssistant,
                int(payload.maxParallel or 3),
            )

        runner.run(job_id, _job)
        return {
            "runId": run.id,
            "rowId": row_id,
            "executeJobId": job_id,
            "status": "RUNNING",
        }
    except Exception as exc:
        db.rollback()
        logging.exception("failed to create direct run")
        raise HTTPException(status_code=500, detail=f"direct run creation failed: {exc}")


@router.post("/generic-runs/{run_id}/rows")
def add_row_to_run(
    run_id: str,
    payload: AddRowRequest,
    db: Session = Depends(get_db),
):
    repo = GenericRunRepository(db)
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(404, "Run not found")

    row_id = repo.add_row(
        run_id=run_id,
        query=payload.query,
        llm_criteria=payload.llmCriteria,
        field_path=payload.fieldPath,
        expected_value=payload.expectedValue,
    )
    db.commit()
    return {"rowId": row_id, "status": run.status.value}


@router.post("/generic-runs/{run_id}/execute")
async def execute_run(run_id: str, payload: RunSecretPayload, db: Session = Depends(get_db)):
    repo = GenericRunRepository(db)
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(404, "Run not found")

    cfg = get_env_config(run.environment)
    options = json.loads(run.options_json)
    context = _build_context(options)

    job_id = str(uuid.uuid4())

    def _job():
        return execute_generic_run(
            run.id,
            cfg.base_url,
            cfg.origin,
            cfg.referer,
            payload.bearer,
            payload.cms,
            payload.mrs,
            context,
            options.get("targetAssistant"),
            int(options.get("maxParallel") or 3),
        )

    runner.run(job_id, _job)
    return {"jobId": job_id, "status": runner.jobs[job_id]}


@router.post("/generic-runs/{run_id}/evaluate")
async def evaluate_run(run_id: str, payload: EvaluatePayload, db: Session = Depends(get_db)):
    repo = GenericRunRepository(db)
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(404, "Run not found")

    options = json.loads(run.options_json)
    job_id = str(uuid.uuid4())

    def _job():
        return evaluate_generic_run(
            run.id,
            payload.openaiKey,
            payload.openaiModel,
            payload.maxChars,
            int(payload.maxParallel),
        )

    runner.run(job_id, _job)
    return {"jobId": job_id, "status": runner.jobs[job_id]}


@router.get("/generic-runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)):
    repo = GenericRunRepository(db)
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(404, "Run not found")

    options = json.loads(run.options_json)
    return _build_run_payload(run.id, run, options, repo)


@router.get("/generic-runs/{run_id}/rows")
def get_rows(
    run_id: str,
    q: Optional[str] = None,
    logicStatus: Optional[str] = None,
    hasError: Optional[bool] = None,
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    repo = GenericRunRepository(db)
    rows = repo.list_rows(run_id, q=q, logic_status=logicStatus, has_error=hasError, offset=offset, limit=limit)
    return {
        "rows": [
            {
                "id": r.id,
                "ordinal": r.ordinal,
                "queryId": r.query_id,
                "query": r.query,
                "llmCriteria": r.llm_criteria,
                "fieldPath": r.field_path,
                "expectedValue": r.expected_value,
                "responseText": r.response_text,
                "responseTimeSec": r.response_time_sec,
                "executionProcess": r.execution_process,
                "error": r.error,
                "logicResult": r.logic_result,
                "llmEvalJson": r.llm_eval_json,
                "llmEvalStatus": r.llm_eval_status,
                "rawJson": r.raw_json,
            }
            for r in rows
        ]
    }


@router.get("/generic-runs/{run_id}/compare")
def run_compare(run_id: str, baseRunId: Optional[str] = None, db: Session = Depends(get_db)):
    repo = GenericRunRepository(db)
    try:
        return compare_runs(repo, run_id, baseRunId)
    except PermissionError as e:
        raise HTTPException(400, str(e)) from e
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/generic-runs/{run_id}/export.xlsx")
def export_run(run_id: str, db: Session = Depends(get_db)):
    rows = list(db.query(GenericRunRow).filter(GenericRunRow.run_id == run_id).order_by(GenericRunRow.ordinal).all())
    if not rows:
        raise HTTPException(404, "No rows")
    df = pd.DataFrame(
        [
            {
                "ID": r.query_id,
                "질의": r.query,
                "LLM 평가기준": r.llm_criteria,
                "검증 필드": r.field_path,
                "기대값": r.expected_value,
                "응답": r.response_text,
                "응답 시간(초)": r.response_time_sec,
                "실행 프로세스": r.execution_process,
                "오류": r.error,
                "raw": r.raw_json,
                "로직 검증결과": r.logic_result,
                "LLM 평가결과": r.llm_eval_json,
            }
            for r in rows
        ]
    )
    xlsx = dataframe_to_excel_bytes(df, sheet_name="generic_results")
    file_name = f"generic_test_results_{dt.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(
        iter([xlsx]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
