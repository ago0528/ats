from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.validation_query import ValidationQuery
from app.models.validation_query_group import ValidationQueryGroup


def _to_json_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


class ValidationQueryGroupRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, q: Optional[str] = None, offset: int = 0, limit: int = 100) -> list[ValidationQueryGroup]:
        query = self.db.query(ValidationQueryGroup)
        if q:
            query = query.filter(ValidationQueryGroup.group_name.contains(q))
        return list(query.order_by(ValidationQueryGroup.created_at.desc()).offset(offset).limit(limit).all())

    def count(self, q: Optional[str] = None) -> int:
        query = self.db.query(func.count(ValidationQueryGroup.id))
        if q:
            query = query.filter(ValidationQueryGroup.group_name.contains(q))
        return int(query.scalar() or 0)

    def get(self, group_id: str) -> Optional[ValidationQueryGroup]:
        return self.db.get(ValidationQueryGroup, group_id)

    def create(
        self,
        group_name: str,
        description: str = "",
        llm_eval_criteria_default: Any = None,
        default_target_assistant: str = "",
    ) -> ValidationQueryGroup:
        group = ValidationQueryGroup(
            group_name=group_name.strip(),
            description=description or "",
            default_target_assistant=(default_target_assistant or "").strip(),
            llm_eval_criteria_default_json=_to_json_text(llm_eval_criteria_default),
        )
        self.db.add(group)
        self.db.flush()
        return group

    def update(
        self,
        group_id: str,
        *,
        group_name: Optional[str] = None,
        description: Optional[str] = None,
        llm_eval_criteria_default: Any = None,
        default_target_assistant: Optional[str] = None,
    ) -> Optional[ValidationQueryGroup]:
        group = self.get(group_id)
        if group is None:
            return None

        if group_name is not None:
            group.group_name = group_name.strip()
        if description is not None:
            group.description = description
        if default_target_assistant is not None:
            group.default_target_assistant = (default_target_assistant or "").strip()
        if llm_eval_criteria_default is not None:
            group.llm_eval_criteria_default_json = _to_json_text(llm_eval_criteria_default)
        self.db.flush()
        return group

    def delete(self, group_id: str) -> bool:
        group = self.get(group_id)
        if group is None:
            return False
        linked_query_count = int(
            self.db.query(func.count(ValidationQuery.id)).filter(ValidationQuery.group_id == group_id).scalar() or 0
        )
        if linked_query_count > 0:
            raise ValueError("Group has linked queries")
        self.db.delete(group)
        self.db.flush()
        return True

    def count_queries_by_group(self, group_ids: list[str]) -> dict[str, int]:
        if not group_ids:
            return {}
        rows = (
            self.db.query(ValidationQuery.group_id, func.count(ValidationQuery.id))
            .filter(ValidationQuery.group_id.in_(group_ids))
            .group_by(ValidationQuery.group_id)
            .all()
        )
        return {str(group_id): int(count) for group_id, count in rows}
