from __future__ import annotations

import datetime as dt
import json
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.validation_query import ValidationQuery
from app.models.validation_test_set import ValidationTestSet
from app.models.validation_test_set_item import ValidationTestSetItem


def _to_json_text(value: Any) -> str:
    if value is None:
        return "{}"
    if isinstance(value, str):
        text = value.strip()
        return text or "{}"
    return json.dumps(value, ensure_ascii=False)


def _parse_json_text(value: str) -> dict[str, Any]:
    text = (value or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return {}
    return {}


class ValidationTestSetRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, *, q: Optional[str] = None, offset: int = 0, limit: int = 100) -> list[ValidationTestSet]:
        query = self.db.query(ValidationTestSet)
        if q:
            query = query.filter(ValidationTestSet.name.contains(q))
        return list(query.order_by(ValidationTestSet.updated_at.desc()).offset(offset).limit(limit).all())

    def count(self, *, q: Optional[str] = None) -> int:
        query = self.db.query(func.count(ValidationTestSet.id))
        if q:
            query = query.filter(ValidationTestSet.name.contains(q))
        return int(query.scalar() or 0)

    def get(self, test_set_id: str) -> Optional[ValidationTestSet]:
        return self.db.get(ValidationTestSet, test_set_id)

    def list_items(self, test_set_id: str) -> list[ValidationTestSetItem]:
        return list(
            self.db.query(ValidationTestSetItem)
            .filter(ValidationTestSetItem.test_set_id == test_set_id)
            .order_by(ValidationTestSetItem.ordinal.asc())
            .all()
        )

    def list_query_rows_for_test_set(self, test_set_id: str) -> list[ValidationQuery]:
        items = self.list_items(test_set_id)
        if not items:
            return []
        query_ids = [item.query_id for item in items]
        rows = list(self.db.query(ValidationQuery).filter(ValidationQuery.id.in_(query_ids)).all())
        by_id = {row.id: row for row in rows}
        return [by_id[query_id] for query_id in query_ids if query_id in by_id]

    def count_items_by_test_set_ids(self, test_set_ids: list[str]) -> dict[str, int]:
        if not test_set_ids:
            return {}
        rows = (
            self.db.query(ValidationTestSetItem.test_set_id, func.count(ValidationTestSetItem.id))
            .filter(ValidationTestSetItem.test_set_id.in_(test_set_ids))
            .group_by(ValidationTestSetItem.test_set_id)
            .all()
        )
        return {str(test_set_id): int(count) for test_set_id, count in rows}

    def create(
        self,
        *,
        name: str,
        description: str = "",
        config: Optional[dict[str, Any]] = None,
        query_ids: Optional[list[str]] = None,
    ) -> ValidationTestSet:
        entity = ValidationTestSet(
            name=name.strip(),
            description=description or "",
            config_json=_to_json_text(config or {}),
        )
        self.db.add(entity)
        self.db.flush()

        self.replace_items(entity.id, query_ids or [])
        return entity

    def update(
        self,
        test_set_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        config: Optional[dict[str, Any]] = None,
        query_ids: Optional[list[str]] = None,
    ) -> Optional[ValidationTestSet]:
        entity = self.get(test_set_id)
        if entity is None:
            return None

        if name is not None:
            entity.name = name.strip()
        if description is not None:
            entity.description = description
        if config is not None:
            entity.config_json = _to_json_text(config)
        if query_ids is not None:
            self.replace_items(test_set_id, query_ids)
        entity.updated_at = dt.datetime.utcnow()
        self.db.flush()
        return entity

    def replace_items(self, test_set_id: str, query_ids: list[str]) -> None:
        unique_query_ids = list(dict.fromkeys([query_id for query_id in query_ids if str(query_id).strip()]))

        self.db.query(ValidationTestSetItem).filter(ValidationTestSetItem.test_set_id == test_set_id).delete()
        self.db.flush()

        for idx, query_id in enumerate(unique_query_ids, start=1):
            self.db.add(
                ValidationTestSetItem(
                    test_set_id=test_set_id,
                    query_id=query_id,
                    ordinal=idx,
                ),
            )
        self.db.flush()

    def delete(self, test_set_id: str) -> bool:
        entity = self.get(test_set_id)
        if entity is None:
            return False
        self.db.query(ValidationTestSetItem).filter(ValidationTestSetItem.test_set_id == test_set_id).delete()
        self.db.delete(entity)
        self.db.flush()
        return True

    def clone(self, test_set_id: str, *, name: Optional[str] = None) -> ValidationTestSet:
        source = self.get(test_set_id)
        if source is None:
            raise ValueError("Test set not found")

        source_items = self.list_items(test_set_id)
        clone_name = (name or f"{source.name} (복제)").strip()
        cloned = ValidationTestSet(
            name=clone_name,
            description=source.description,
            config_json=source.config_json,
        )
        self.db.add(cloned)
        self.db.flush()
        for item in source_items:
            self.db.add(
                ValidationTestSetItem(
                    test_set_id=cloned.id,
                    query_id=item.query_id,
                    ordinal=item.ordinal,
                ),
            )
        self.db.flush()
        return cloned

    def build_payload(self, row: ValidationTestSet, *, item_count: Optional[int] = None) -> dict[str, Any]:
        if item_count is None:
            item_count = len(self.list_items(row.id))
        return {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "config": _parse_json_text(row.config_json),
            "itemCount": item_count,
            "createdAt": row.created_at,
            "updatedAt": row.updated_at,
        }
