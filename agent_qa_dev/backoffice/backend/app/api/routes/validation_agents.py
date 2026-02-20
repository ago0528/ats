from __future__ import annotations

import datetime as dt
import json
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import SessionLocal, get_db
from app.jobs.runner import runner
from app.models.automation_job import AutomationJob
from app.services.agent_tasks.query_generation import build_query_suggestions
from app.services.agent_tasks.report_generation import build_validation_report

router = APIRouter(tags=["validation-agents"])


def _json_text(value: Any) -> str:
    if value is None:
        return "{}"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_value(raw: str) -> Any:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return text


def _build_job_payload(entity: AutomationJob) -> dict[str, Any]:
    return {
        "id": entity.id,
        "jobType": entity.job_type,
        "status": entity.status,
        "payload": _json_value(entity.payload_json),
        "result": _json_value(entity.result_json),
        "error": entity.error,
        "createdAt": entity.created_at,
        "startedAt": entity.started_at,
        "finishedAt": entity.finished_at,
    }


class QueryGenerationJobRequest(BaseModel):
    testSetId: str
    limit: int = Field(default=5, ge=1, le=50)


class ReportGenerationJobRequest(BaseModel):
    testSetId: str
    runId: Optional[str] = None


@router.post("/validation-agents/query-generator")
def create_query_generation_job(body: QueryGenerationJobRequest, db: Session = Depends(get_db)):
    job_id = str(uuid.uuid4())
    entity = AutomationJob(
        id=job_id,
        job_type="QUERY_GENERATION",
        status="PENDING",
        payload_json=_json_text(body.model_dump()),
    )
    db.add(entity)
    db.commit()

    def _job():
        async def _coro():
            task_db = SessionLocal()
            try:
                job = task_db.get(AutomationJob, job_id)
                if job is None:
                    return
                job.status = "RUNNING"
                job.started_at = dt.datetime.utcnow()
                task_db.commit()

                result = build_query_suggestions(task_db, body.testSetId, limit=body.limit)
                job.result_json = _json_text(result)
                job.error = ""
                job.status = "DONE"
                job.finished_at = dt.datetime.utcnow()
                task_db.commit()
            except Exception as exc:
                job = task_db.get(AutomationJob, job_id)
                if job is not None:
                    job.status = "FAILED"
                    job.error = str(exc)
                    job.finished_at = dt.datetime.utcnow()
                    task_db.commit()
                raise
            finally:
                task_db.close()

        return _coro()

    runner.run(job_id, _job)
    return {"jobId": job_id, "status": runner.jobs[job_id]}


@router.post("/validation-agents/report-writer")
def create_report_generation_job(body: ReportGenerationJobRequest, db: Session = Depends(get_db)):
    job_id = str(uuid.uuid4())
    entity = AutomationJob(
        id=job_id,
        job_type="REPORT_GENERATION",
        status="PENDING",
        payload_json=_json_text(body.model_dump()),
    )
    db.add(entity)
    db.commit()

    def _job():
        async def _coro():
            task_db = SessionLocal()
            try:
                job = task_db.get(AutomationJob, job_id)
                if job is None:
                    return
                job.status = "RUNNING"
                job.started_at = dt.datetime.utcnow()
                task_db.commit()

                result = build_validation_report(task_db, body.testSetId, run_id=body.runId)
                job.result_json = _json_text(result)
                job.error = ""
                job.status = "DONE"
                job.finished_at = dt.datetime.utcnow()
                task_db.commit()
            except Exception as exc:
                job = task_db.get(AutomationJob, job_id)
                if job is not None:
                    job.status = "FAILED"
                    job.error = str(exc)
                    job.finished_at = dt.datetime.utcnow()
                    task_db.commit()
                raise
            finally:
                task_db.close()

        return _coro()

    runner.run(job_id, _job)
    return {"jobId": job_id, "status": runner.jobs[job_id]}


@router.get("/validation-agents/jobs/{job_id}")
def get_validation_agent_job(job_id: str, db: Session = Depends(get_db)):
    entity = db.get(AutomationJob, job_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _build_job_payload(entity)
