from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.repositories.validation_query_groups import ValidationQueryGroupRepository

router = APIRouter(tags=["validation-query-groups"])


class QueryGroupCreateRequest(BaseModel):
    groupName: str = Field(min_length=1)
    description: str = ""


class QueryGroupUpdateRequest(BaseModel):
    groupName: Optional[str] = None
    description: Optional[str] = None


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
    )
    db.commit()
    return {
        "id": group.id,
        "groupName": group.group_name,
        "description": group.description,
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
    )
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    db.commit()
    return {
        "id": group.id,
        "groupName": group.group_name,
        "description": group.description,
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
