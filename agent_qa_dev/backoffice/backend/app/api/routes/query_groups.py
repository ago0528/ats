from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.repositories.validation_query_groups import ValidationQueryGroupRepository

router = APIRouter(tags=["validation-query-groups"])


def _parse_json_text(value: str) -> Any:
    text = (value or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return text


class QueryGroupCreateRequest(BaseModel):
    groupName: str = Field(min_length=1)
    description: str = ""
    defaultTargetAssistant: str = ""
    llmEvalCriteriaDefault: Any = None


class QueryGroupUpdateRequest(BaseModel):
    groupName: Optional[str] = None
    description: Optional[str] = None
    defaultTargetAssistant: Optional[str] = None
    llmEvalCriteriaDefault: Any = None


@router.get("/query-groups")
def list_query_groups(
    q: Optional[str] = Query(default=None),
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    repo = ValidationQueryGroupRepository(db)
    rows = repo.list(q=q, offset=offset, limit=limit)
    counts = repo.count_queries_by_group([row.id for row in rows])
    total = repo.count(q=q)
    return {
        "items": [
            {
                "id": row.id,
                "groupName": row.group_name,
                "description": row.description,
                "defaultTargetAssistant": row.default_target_assistant,
                "llmEvalCriteriaDefault": _parse_json_text(row.llm_eval_criteria_default_json),
                "createdAt": row.created_at,
                "updatedAt": row.updated_at,
                "queryCount": counts.get(row.id, 0),
            }
            for row in rows
        ],
        "total": total,
    }


@router.post("/query-groups")
def create_query_group(body: QueryGroupCreateRequest, db: Session = Depends(get_db)):
    repo = ValidationQueryGroupRepository(db)
    group = repo.create(
        group_name=body.groupName,
        description=body.description,
        default_target_assistant=body.defaultTargetAssistant,
        llm_eval_criteria_default=body.llmEvalCriteriaDefault,
    )
    db.commit()
    return {
        "id": group.id,
        "groupName": group.group_name,
        "description": group.description,
        "defaultTargetAssistant": group.default_target_assistant,
        "llmEvalCriteriaDefault": _parse_json_text(group.llm_eval_criteria_default_json),
        "createdAt": group.created_at,
        "updatedAt": group.updated_at,
    }


@router.get("/query-groups/{group_id}")
def get_query_group(group_id: str, db: Session = Depends(get_db)):
    repo = ValidationQueryGroupRepository(db)
    group = repo.get(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return {
        "id": group.id,
        "groupName": group.group_name,
        "description": group.description,
        "defaultTargetAssistant": group.default_target_assistant,
        "llmEvalCriteriaDefault": _parse_json_text(group.llm_eval_criteria_default_json),
        "createdAt": group.created_at,
        "updatedAt": group.updated_at,
    }


@router.patch("/query-groups/{group_id}")
def update_query_group(group_id: str, body: QueryGroupUpdateRequest, db: Session = Depends(get_db)):
    repo = ValidationQueryGroupRepository(db)
    group = repo.update(
        group_id,
        group_name=body.groupName,
        description=body.description,
        default_target_assistant=body.defaultTargetAssistant,
        llm_eval_criteria_default=body.llmEvalCriteriaDefault,
    )
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    db.commit()
    return {
        "id": group.id,
        "groupName": group.group_name,
        "description": group.description,
        "defaultTargetAssistant": group.default_target_assistant,
        "llmEvalCriteriaDefault": _parse_json_text(group.llm_eval_criteria_default_json),
        "createdAt": group.created_at,
        "updatedAt": group.updated_at,
    }


@router.delete("/query-groups/{group_id}")
def delete_query_group(group_id: str, db: Session = Depends(get_db)):
    repo = ValidationQueryGroupRepository(db)
    try:
        deleted = repo.delete(group_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Group not found")
    db.commit()
    return {"ok": True}
