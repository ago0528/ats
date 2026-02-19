from __future__ import annotations

import datetime as dt
import json
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.validation_llm_evaluation import ValidationLlmEvaluation
from app.models.validation_logic_evaluation import ValidationLogicEvaluation
from app.models.validation_query import ValidationQuery
from app.models.validation_run_item import ValidationRunItem
from app.models.validation_test_set import ValidationTestSet
from app.models.validation_test_set_item import ValidationTestSetItem


def _to_json_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


class ValidationQueryRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(
        self,
        *,
        q: Optional[str] = None,
        categories: Optional[list[str]] = None,
        group_ids: Optional[list[str]] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ValidationQuery]:
        query = self.db.query(ValidationQuery)
        if q:
            query = query.filter(ValidationQuery.query_text.contains(q))
        if categories:
            query = query.filter(ValidationQuery.category.in_(categories))
        if group_ids:
            query = query.filter(ValidationQuery.group_id.in_(group_ids))
        return list(query.order_by(ValidationQuery.created_at.desc()).offset(offset).limit(limit).all())

    def count(self, *, q: Optional[str] = None, categories: Optional[list[str]] = None, group_ids: Optional[list[str]] = None) -> int:
        query = self.db.query(func.count(ValidationQuery.id))
        if q:
            query = query.filter(ValidationQuery.query_text.contains(q))
        if categories:
            query = query.filter(ValidationQuery.category.in_(categories))
        if group_ids:
            query = query.filter(ValidationQuery.group_id.in_(group_ids))
        return int(query.scalar() or 0)

    def get(self, query_id: str) -> Optional[ValidationQuery]:
        return self.db.get(ValidationQuery, query_id)

    def list_by_ids(self, query_ids: list[str]) -> list[ValidationQuery]:
        if not query_ids:
            return []
        rows = list(self.db.query(ValidationQuery).filter(ValidationQuery.id.in_(query_ids)).all())
        by_id = {row.id: row for row in rows}
        return [by_id[qid] for qid in query_ids if qid in by_id]

    def get_test_set_usage(self, query_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not query_ids:
            return {}

        rows = (
            self.db.query(
                ValidationTestSetItem.query_id,
                ValidationTestSetItem.test_set_id,
                ValidationTestSet.name,
            )
            .join(ValidationTestSet, ValidationTestSet.id == ValidationTestSetItem.test_set_id)
            .filter(ValidationTestSetItem.query_id.in_(query_ids))
            .order_by(ValidationTestSet.name.asc(), ValidationTestSetItem.test_set_id.asc())
            .all()
        )
        if not rows:
            return {}

        usage: dict[str, dict[str, Any]] = {}
        for query_id, test_set_id, test_set_name in rows:
            if not query_id:
                continue
            if query_id not in usage:
                usage[query_id] = {
                    "testSetIds": set(),
                    "testSetNames": [],
                }
            test_set_ids = usage[query_id]["testSetIds"]
            if test_set_id in test_set_ids:
                continue
            test_set_ids.add(test_set_id)
            usage[query_id]["testSetNames"].append(str(test_set_name or "").strip())

        return {
            query_id: {
                "count": len(payload["testSetIds"]),
                "testSetNames": [name for name in payload["testSetNames"] if name],
            }
            for query_id, payload in usage.items()
        }

    def list_ids(
        self,
        *,
        q: Optional[str] = None,
        categories: Optional[list[str]] = None,
        group_ids: Optional[list[str]] = None,
        excluded_ids: Optional[list[str]] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[str]:
        query = self.db.query(ValidationQuery.id)
        if q:
            query = query.filter(ValidationQuery.query_text.contains(q))
        if categories:
            query = query.filter(ValidationQuery.category.in_(categories))
        if group_ids:
            query = query.filter(ValidationQuery.group_id.in_(group_ids))
        if excluded_ids:
            query = query.filter(~ValidationQuery.id.in_(excluded_ids))
        rows = (
            query.order_by(ValidationQuery.created_at.desc(), ValidationQuery.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [str(row[0]) for row in rows]

    def create(
        self,
        *,
        query_text: str,
        expected_result: str,
        category: str,
        group_id: Optional[str] = None,
        llm_eval_criteria: Any = None,
        logic_field_path: str = "",
        logic_expected_value: str = "",
        context_json: str = "",
        target_assistant: str = "",
        created_by: str = "unknown",
    ) -> ValidationQuery:
        query = ValidationQuery(
            query_text=query_text.strip(),
            expected_result=expected_result or "",
            category=category or "Happy path",
            group_id=group_id or "",
            llm_eval_criteria_json=_to_json_text(llm_eval_criteria),
            logic_field_path=logic_field_path or "",
            logic_expected_value=logic_expected_value or "",
            context_json=context_json or "",
            target_assistant=target_assistant or "",
            created_by=created_by or "unknown",
        )
        self.db.add(query)
        self.db.flush()
        return query

    def bulk_create(self, rows: list[dict[str, Any]], *, created_by: str = "unknown") -> list[str]:
        created_ids: list[str] = []
        for row in rows:
            created = self.create(
                query_text=str(row.get("query_text", "")),
                expected_result=str(row.get("expected_result", "")),
                category=str(row.get("category", "Happy path")),
                group_id=(str(row.get("group_id")).strip() if row.get("group_id") is not None else None),
                llm_eval_criteria=row.get("llm_eval_criteria"),
                logic_field_path=str(row.get("logic_field_path", "")),
                logic_expected_value=str(row.get("logic_expected_value", "")),
                context_json=(str(row.get("context_json")).strip() if row.get("context_json") is not None else ""),
                target_assistant=(str(row.get("target_assistant")).strip() if row.get("target_assistant") is not None else ""),
                created_by=created_by,
            )
            created_ids.append(created.id)
        return created_ids

    def update(
        self,
        query_id: str,
        *,
        query_text: Optional[str] = None,
        expected_result: Optional[str] = None,
        category: Optional[str] = None,
        group_id: Optional[str] = None,
        update_group_id: bool = False,
        llm_eval_criteria: Any = None,
        logic_field_path: Optional[str] = None,
        logic_expected_value: Optional[str] = None,
        context_json: Optional[str] = None,
        target_assistant: Optional[str] = None,
    ) -> Optional[ValidationQuery]:
        query = self.get(query_id)
        if query is None:
            return None

        if query_text is not None:
            query.query_text = query_text.strip()
        if expected_result is not None:
            query.expected_result = expected_result
        if category is not None:
            query.category = category
        if update_group_id:
            query.group_id = group_id or ""
        if llm_eval_criteria is not None:
            query.llm_eval_criteria_json = _to_json_text(llm_eval_criteria)
        if logic_field_path is not None:
            query.logic_field_path = logic_field_path
        if logic_expected_value is not None:
            query.logic_expected_value = logic_expected_value
        if context_json is not None:
            query.context_json = context_json
        if target_assistant is not None:
            query.target_assistant = target_assistant
        query.updated_at = dt.datetime.utcnow()
        self.db.flush()
        return query

    def delete(self, query_id: str) -> bool:
        query = self.get(query_id)
        if query is None:
            return False
        self.db.delete(query)
        self.db.flush()
        return True

    def get_latest_run_summary(self, query_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not query_ids:
            return {}

        rows = (
            self.db.query(ValidationRunItem)
            .filter(ValidationRunItem.query_id.in_(query_ids))
            .order_by(ValidationRunItem.executed_at.desc(), ValidationRunItem.ordinal.desc())
            .all()
        )
        if not rows:
            return {}

        row_by_query: dict[str, ValidationRunItem] = {}
        for row in rows:
            if not row.query_id or row.query_id in row_by_query:
                continue
            row_by_query[row.query_id] = row

        item_ids = [row.id for row in row_by_query.values()]
        logic_map = {
            item.run_item_id: item
            for item in self.db.query(ValidationLogicEvaluation).filter(ValidationLogicEvaluation.run_item_id.in_(item_ids)).all()
        }
        llm_map = {
            item.run_item_id: item
            for item in self.db.query(ValidationLlmEvaluation).filter(ValidationLlmEvaluation.run_item_id.in_(item_ids)).all()
        }

        summary: dict[str, dict[str, Any]] = {}
        for query_id, row in row_by_query.items():
            logic = logic_map.get(row.id)
            llm = llm_map.get(row.id)
            summary[query_id] = {
                "executedAt": row.executed_at,
                "logicResult": logic.result if logic else "",
                "llmStatus": llm.status if llm else "",
            }
        return summary
