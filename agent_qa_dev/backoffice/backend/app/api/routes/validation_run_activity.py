from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.enums import Environment
from app.repositories.validation_runs import ValidationRunRepository

router = APIRouter(tags=["validation-run-activity"])


class ValidationRunActivityReadRequest(BaseModel):
    environment: Environment
    actorKey: Optional[str] = None
    runIds: list[str] = Field(default_factory=list)
    markAll: bool = False


def _normalize_actor_key(raw_actor_key: Optional[str]) -> str:
    normalized_actor_key = str(raw_actor_key or "").strip()
    if not normalized_actor_key:
        raise HTTPException(status_code=400, detail="actorKey is required")
    return normalized_actor_key


@router.get("/validation-run-activity")
def list_validation_run_activity(
    environment: Environment = Query(...),
    actorKey: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    actor_key = _normalize_actor_key(actorKey)
    repo = ValidationRunRepository(db)
    inserted_count = repo.ensure_run_activity_rows(
        environment=environment,
        actor_key=actor_key,
        limit=1000,
    )
    if inserted_count > 0:
        db.commit()

    activity_items = repo.list_run_activity_items(
        environment=environment,
        actor_key=actor_key,
        limit=limit,
    )
    unread_count = repo.count_unread_run_activity_items(
        environment=environment,
        actor_key=actor_key,
    )

    items: list[dict[str, object]] = []

    for run, is_read in activity_items:
        run_payload = repo.build_run_payload(run)
        run_name = str(run_payload.get("name") or "").strip() or str(run_payload.get("id") or "").strip()

        items.append(
            {
                "runId": run_payload.get("id"),
                "runName": run_name,
                "testSetId": run_payload.get("testSetId"),
                "status": run_payload.get("status"),
                "evalStatus": run_payload.get("evalStatus"),
                "totalItems": run_payload.get("totalItems"),
                "doneItems": run_payload.get("doneItems"),
                "errorItems": run_payload.get("errorItems"),
                "llmDoneItems": run_payload.get("llmDoneItems"),
                "createdAt": run_payload.get("createdAt"),
                "startedAt": run_payload.get("startedAt"),
                "evalStartedAt": run_payload.get("evalStartedAt"),
                "isRead": is_read,
            }
        )

    return {
        "items": items,
        "unreadCount": unread_count,
    }


@router.post("/validation-run-activity/read")
def mark_validation_run_activity_read(
    body: ValidationRunActivityReadRequest,
    db: Session = Depends(get_db),
):
    actor_key = _normalize_actor_key(body.actorKey)
    repo = ValidationRunRepository(db)

    if body.markAll:
        repo.ensure_run_activity_rows(
            environment=body.environment,
            actor_key=actor_key,
            limit=1000,
        )
        updated_count = repo.mark_all_run_activity_read(
            environment=body.environment,
            actor_key=actor_key,
        )
    else:
        run_ids = repo.list_run_ids_by_environment(
            environment=body.environment,
            run_ids=body.runIds,
        )
        if not run_ids:
            raise HTTPException(status_code=400, detail="runIds is required when markAll is false")
        updated_count = repo.mark_run_activity_read(
            actor_key=actor_key,
            run_ids=run_ids,
        )
    db.commit()
    return {"updatedCount": updated_count}
