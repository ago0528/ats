from __future__ import annotations

import datetime as dt
import json
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import Environment, EvalStatus, RunStatus
from app.models.validation_llm_evaluation import ValidationLlmEvaluation
from app.models.validation_logic_evaluation import ValidationLogicEvaluation
from app.models.validation_query import ValidationQuery
from app.models.validation_run import ValidationRun
from app.models.validation_run_item import ValidationRunItem
from app.models.validation_score_snapshot import ValidationScoreSnapshot


def _to_json_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


class ValidationRunRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_run(
        self,
        *,
        environment: Environment,
        mode: str,
        test_set_id: Optional[str] = None,
        name: str = "",
        agent_id: str,
        test_model: str,
        eval_model: str,
        repeat_in_conversation: int,
        conversation_room_count: int,
        agent_parallel_calls: int,
        timeout_ms: int,
        options: Optional[dict[str, Any]] = None,
        base_run_id: Optional[str] = None,
    ) -> ValidationRun:
        run = ValidationRun(
            environment=environment,
            mode=mode,
            test_set_id=test_set_id,
            name=name,
            status=RunStatus.PENDING,
            base_run_id=base_run_id,
            agent_id=agent_id,
            test_model=test_model,
            eval_model=eval_model,
            repeat_in_conversation=max(1, int(repeat_in_conversation)),
            conversation_room_count=max(1, int(conversation_room_count)),
            agent_parallel_calls=max(1, int(agent_parallel_calls)),
            timeout_ms=max(1000, int(timeout_ms)),
            options_json=json.dumps(options or {}, ensure_ascii=False),
        )
        self.db.add(run)
        self.db.flush()
        return run

    def get_run(self, run_id: str) -> Optional[ValidationRun]:
        return self.db.get(ValidationRun, run_id)

    def list_runs(
        self,
        *,
        environment: Optional[Environment] = None,
        test_set_id: Optional[str] = None,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[ValidationRun]:
        query = self.db.query(ValidationRun)
        if environment:
            query = query.filter(ValidationRun.environment == environment)
        normalized_test_set_id = (test_set_id or "").strip()
        if normalized_test_set_id in {"__NULL__", "null"}:
            query = query.filter(ValidationRun.test_set_id.is_(None))
        elif normalized_test_set_id:
            query = query.filter(ValidationRun.test_set_id == normalized_test_set_id)
        if status:
            query = query.filter(ValidationRun.status == status)
        return list(query.order_by(ValidationRun.created_at.desc()).offset(offset).limit(limit).all())

    def count_runs(
        self,
        *,
        environment: Optional[Environment] = None,
        test_set_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int:
        query = self.db.query(func.count(ValidationRun.id))
        if environment:
            query = query.filter(ValidationRun.environment == environment)
        normalized_test_set_id = (test_set_id or "").strip()
        if normalized_test_set_id in {"__NULL__", "null"}:
            query = query.filter(ValidationRun.test_set_id.is_(None))
        elif normalized_test_set_id:
            query = query.filter(ValidationRun.test_set_id == normalized_test_set_id)
        if status:
            query = query.filter(ValidationRun.status == status)
        return int(query.scalar() or 0)

    def set_status(self, run_id: str, status: RunStatus) -> None:
        run = self.get_run(run_id)
        if run is None:
            return
        run.status = status
        if status == RunStatus.RUNNING:
            run.started_at = dt.datetime.utcnow()
        if status in (RunStatus.DONE, RunStatus.FAILED):
            run.finished_at = dt.datetime.utcnow()

    def set_eval_status(self, run_id: str, status: EvalStatus) -> None:
        run = self.get_run(run_id)
        if run is None:
            return
        run.eval_status = status
        if status == EvalStatus.RUNNING:
            run.eval_started_at = dt.datetime.utcnow()
            run.eval_finished_at = None
        if status in (EvalStatus.DONE, EvalStatus.FAILED):
            run.eval_finished_at = dt.datetime.utcnow()

    def add_items(self, run_id: str, items: list[dict[str, Any]]) -> list[str]:
        row_ids: list[str] = []
        for index, payload in enumerate(items, start=1):
            item = ValidationRunItem(
                run_id=run_id,
                query_id=payload.get("query_id"),
                ordinal=payload.get("ordinal") or index,
                query_text_snapshot=str(payload.get("query_text_snapshot", "")),
                expected_result_snapshot=str(payload.get("expected_result_snapshot", "")),
                category_snapshot=str(payload.get("category_snapshot", "Happy path")),
                applied_criteria_json=_to_json_text(payload.get("applied_criteria_json")),
                logic_field_path_snapshot=str(payload.get("logic_field_path_snapshot", "")),
                logic_expected_value_snapshot=str(payload.get("logic_expected_value_snapshot", "")),
                context_json_snapshot=(
                    str(payload.get("context_json_snapshot")).strip()
                    if payload.get("context_json_snapshot") is not None
                    else ""
                ),
                target_assistant_snapshot=(
                    str(payload.get("target_assistant_snapshot")).strip()
                    if payload.get("target_assistant_snapshot") is not None
                    else ""
                ),
                conversation_room_index=int(payload.get("conversation_room_index", 1) or 1),
                repeat_index=int(payload.get("repeat_index", 1) or 1),
            )
            self.db.add(item)
            self.db.flush()
            row_ids.append(item.id)
        return row_ids

    def list_items(self, run_id: str, *, offset: int = 0, limit: int = 1000) -> list[ValidationRunItem]:
        return list(
            self.db.query(ValidationRunItem)
            .filter(ValidationRunItem.run_id == run_id)
            .order_by(ValidationRunItem.ordinal.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_item(self, item_id: str) -> Optional[ValidationRunItem]:
        return self.db.get(ValidationRunItem, item_id)

    def update_item_execution(
        self,
        item_id: str,
        *,
        conversation_id: str,
        raw_response: str,
        latency_ms: Optional[int],
        error: str,
        raw_json: str,
        executed_at: Optional[dt.datetime] = None,
    ) -> Optional[ValidationRunItem]:
        item = self.get_item(item_id)
        if item is None:
            return None

        item.conversation_id = conversation_id or ""
        item.raw_response = raw_response or ""
        item.latency_ms = latency_ms
        item.error = error or ""
        item.raw_json = raw_json or ""
        item.executed_at = executed_at or dt.datetime.utcnow()
        self.db.flush()
        return item

    def upsert_logic_eval(
        self,
        run_item_id: str,
        *,
        eval_items: Any,
        result: str,
        fail_reason: str = "",
    ) -> ValidationLogicEvaluation:
        entity = self.db.query(ValidationLogicEvaluation).filter(ValidationLogicEvaluation.run_item_id == run_item_id).first()
        if entity is None:
            entity = ValidationLogicEvaluation(run_item_id=run_item_id)
            self.db.add(entity)
        entity.eval_items_json = _to_json_text(eval_items)
        entity.result = result
        entity.fail_reason = fail_reason or ""
        entity.evaluated_at = dt.datetime.utcnow()
        self.db.flush()
        return entity

    def upsert_llm_eval(
        self,
        run_item_id: str,
        *,
        eval_model: str,
        metric_scores: Any,
        total_score: Optional[float],
        llm_comment: str,
        status: str,
    ) -> ValidationLlmEvaluation:
        entity = self.db.query(ValidationLlmEvaluation).filter(ValidationLlmEvaluation.run_item_id == run_item_id).first()
        if entity is None:
            entity = ValidationLlmEvaluation(run_item_id=run_item_id)
            self.db.add(entity)
        entity.eval_model = eval_model or ""
        entity.metric_scores_json = _to_json_text(metric_scores)
        entity.total_score = total_score
        entity.llm_comment = llm_comment or ""
        entity.status = status
        entity.evaluated_at = dt.datetime.utcnow()
        self.db.flush()
        return entity

    def get_logic_eval_map(self, item_ids: list[str]) -> dict[str, ValidationLogicEvaluation]:
        if not item_ids:
            return {}
        rows = self.db.query(ValidationLogicEvaluation).filter(ValidationLogicEvaluation.run_item_id.in_(item_ids)).all()
        return {row.run_item_id: row for row in rows}

    def get_llm_eval_map(self, item_ids: list[str]) -> dict[str, ValidationLlmEvaluation]:
        if not item_ids:
            return {}
        rows = self.db.query(ValidationLlmEvaluation).filter(ValidationLlmEvaluation.run_item_id.in_(item_ids)).all()
        return {row.run_item_id: row for row in rows}

    def count_items(self, run_id: str) -> int:
        return int(self.db.query(func.count(ValidationRunItem.id)).filter(ValidationRunItem.run_id == run_id).scalar() or 0)

    def count_done_items(self, run_id: str) -> int:
        return int(
            self.db.query(func.count(ValidationRunItem.id))
            .filter(
                ValidationRunItem.run_id == run_id,
                (ValidationRunItem.executed_at.isnot(None)) | (ValidationRunItem.error != ""),
            )
            .scalar()
            or 0
        )

    def count_error_items(self, run_id: str) -> int:
        return int(
            self.db.query(func.count(ValidationRunItem.id))
            .filter(ValidationRunItem.run_id == run_id, ValidationRunItem.error != "")
            .scalar()
            or 0
        )

    def count_llm_done_items(self, run_id: str) -> int:
        return int(
            self.db.query(func.count(ValidationLlmEvaluation.id))
            .join(ValidationRunItem, ValidationRunItem.id == ValidationLlmEvaluation.run_item_id)
            .filter(ValidationRunItem.run_id == run_id, ValidationLlmEvaluation.status == "DONE")
            .scalar()
            or 0
        )

    def latest_done_run_for_env(self, environment: Environment, *, exclude_run_id: Optional[str] = None) -> Optional[ValidationRun]:
        query = self.db.query(ValidationRun).filter(
            ValidationRun.environment == environment,
            ValidationRun.status == RunStatus.DONE,
        )
        if exclude_run_id:
            query = query.filter(ValidationRun.id != exclude_run_id)
        return query.order_by(ValidationRun.finished_at.desc()).first()

    def clone_run(self, run_id: str) -> ValidationRun:
        base = self.get_run(run_id)
        if base is None:
            raise ValueError("Run not found")

        base_name = (base.name or "").strip()
        cloned_name = f"{base_name} (재실행)" if base_name else "재실행"
        cloned = self.create_run(
            environment=base.environment,
            mode=base.mode,
            test_set_id=base.test_set_id,
            name=cloned_name,
            agent_id=base.agent_id,
            test_model=base.test_model,
            eval_model=base.eval_model,
            repeat_in_conversation=base.repeat_in_conversation,
            conversation_room_count=base.conversation_room_count,
            agent_parallel_calls=base.agent_parallel_calls,
            timeout_ms=base.timeout_ms,
            options=json.loads(base.options_json or "{}"),
            base_run_id=base.id,
        )
        base_items = self.list_items(base.id, limit=100000)
        payloads: list[dict[str, Any]] = []
        for idx, item in enumerate(base_items, start=1):
            payloads.append(
                {
                    "query_id": item.query_id,
                    "ordinal": idx,
                    "query_text_snapshot": item.query_text_snapshot,
                    "expected_result_snapshot": item.expected_result_snapshot,
                    "category_snapshot": item.category_snapshot,
                    "applied_criteria_json": item.applied_criteria_json,
                    "logic_field_path_snapshot": item.logic_field_path_snapshot,
                    "logic_expected_value_snapshot": item.logic_expected_value_snapshot,
                    "context_json_snapshot": item.context_json_snapshot,
                    "target_assistant_snapshot": item.target_assistant_snapshot,
                    "conversation_room_index": item.conversation_room_index,
                    "repeat_index": item.repeat_index,
                }
            )
        self.add_items(cloned.id, payloads)
        self.db.flush()
        return cloned

    def clear_score_snapshots_for_run(self, run_id: str) -> None:
        self.db.query(ValidationScoreSnapshot).filter(ValidationScoreSnapshot.run_id == run_id).delete()
        self.db.flush()

    def upsert_score_snapshot(
        self,
        *,
        run_id: str,
        test_set_id: Optional[str],
        query_group_id: Optional[str],
        total_items: int,
        executed_items: int,
        error_items: int,
        logic_pass_items: int,
        llm_done_items: int,
        llm_metric_averages: Any,
        llm_total_score_avg: Optional[float],
    ) -> ValidationScoreSnapshot:
        query = self.db.query(ValidationScoreSnapshot).filter(ValidationScoreSnapshot.run_id == run_id)
        if query_group_id is None:
            entity = query.filter(ValidationScoreSnapshot.query_group_id.is_(None)).first()
        else:
            entity = query.filter(ValidationScoreSnapshot.query_group_id == query_group_id).first()

        if entity is None:
            entity = ValidationScoreSnapshot(run_id=run_id, test_set_id=test_set_id, query_group_id=query_group_id)
            self.db.add(entity)

        entity.test_set_id = test_set_id
        entity.total_items = max(0, int(total_items))
        entity.executed_items = max(0, int(executed_items))
        entity.error_items = max(0, int(error_items))
        entity.logic_pass_items = max(0, int(logic_pass_items))
        entity.logic_pass_rate = round((entity.logic_pass_items / entity.total_items) * 100, 4) if entity.total_items else 0.0
        entity.llm_done_items = max(0, int(llm_done_items))
        entity.llm_metric_averages_json = _to_json_text(llm_metric_averages if llm_metric_averages is not None else {})
        entity.llm_total_score_avg = llm_total_score_avg
        entity.evaluated_at = dt.datetime.utcnow()
        self.db.flush()
        return entity

    def list_query_group_ids_by_query_ids(self, query_ids: list[str]) -> dict[str, str]:
        if not query_ids:
            return {}
        rows = self.db.query(ValidationQuery.id, ValidationQuery.group_id).filter(ValidationQuery.id.in_(query_ids)).all()
        return {str(query_id): str(group_id) for query_id, group_id in rows if query_id and group_id}

    def build_run_payload(self, run: ValidationRun) -> dict[str, Any]:
        return {
            "id": run.id,
            "name": run.name,
            "mode": run.mode,
            "environment": run.environment.value,
            "status": run.status.value,
            "baseRunId": run.base_run_id,
            "testSetId": run.test_set_id,
            "agentId": run.agent_id,
            "testModel": run.test_model,
            "evalModel": run.eval_model,
            "repeatInConversation": run.repeat_in_conversation,
            "conversationRoomCount": run.conversation_room_count,
            "agentParallelCalls": run.agent_parallel_calls,
            "timeoutMs": run.timeout_ms,
            "options": json.loads(run.options_json or "{}"),
            "createdAt": run.created_at,
            "startedAt": run.started_at,
            "finishedAt": run.finished_at,
            "evalStatus": run.eval_status.value if isinstance(run.eval_status, EvalStatus) else str(run.eval_status),
            "evalStartedAt": run.eval_started_at,
            "evalFinishedAt": run.eval_finished_at,
            "totalItems": self.count_items(run.id),
            "doneItems": self.count_done_items(run.id),
            "errorItems": self.count_error_items(run.id),
            "llmDoneItems": self.count_llm_done_items(run.id),
        }
