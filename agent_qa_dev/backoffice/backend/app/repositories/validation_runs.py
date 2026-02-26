from __future__ import annotations

import datetime as dt
import json
from typing import Any, Optional

from sqlalchemy import and_, delete, func, or_
from sqlalchemy.orm import Session

from app.core.enums import Environment, EvalStatus, RunStatus
from app.models.validation_llm_evaluation import ValidationLlmEvaluation
from app.models.validation_logic_evaluation import ValidationLogicEvaluation
from app.models.validation_query import ValidationQuery
from app.models.validation_run_activity_read import ValidationRunActivityRead
from app.models.validation_run import ValidationRun
from app.models.validation_run_item import ValidationRunItem
from app.models.validation_score_snapshot import ValidationScoreSnapshot


def _normalize_evaluation_status_filter(value: Optional[str]) -> Optional[str]:
    normalized = (value or "").strip()
    if not normalized:
        return None

    if normalized in {"평가대기", "평가중", "평가완료"}:
        return normalized

    upper = normalized.upper()
    if upper == "PENDING":
        return "평가대기"
    if upper == "RUNNING":
        return "평가중"
    if upper == "DONE":
        return "평가완료"
    return None


def _to_int_expression(value) -> Any:
    return func.coalesce(value, 0)


def _build_item_progress_query(session: Session):
    return (
        session.query(
            ValidationRunItem.run_id.label("run_id"),
            func.count(ValidationRunItem.id).label("total_items"),
            func.count(ValidationLlmEvaluation.id).label("llm_done_items"),
        )
        .outerjoin(
            ValidationLlmEvaluation,
            and_(
                ValidationLlmEvaluation.run_item_id == ValidationRunItem.id,
                ValidationLlmEvaluation.status.like("DONE%"),
            ),
        )
        .group_by(ValidationRunItem.run_id)
        .subquery()
    )


def _apply_evaluation_status_filter(
    query,
    session: Session,
    evaluation_status: str,
):
    normalized = _normalize_evaluation_status_filter(evaluation_status)
    if not normalized:
        return query

    item_progress = _build_item_progress_query(session)
    total_items = _to_int_expression(item_progress.c.total_items)
    llm_done_items = _to_int_expression(item_progress.c.llm_done_items)

    query = query.outerjoin(item_progress, item_progress.c.run_id == ValidationRun.id)

    evaluation_done = and_(
        ValidationRun.status == RunStatus.DONE,
        or_(
            and_(total_items == 0, ValidationRun.eval_status == EvalStatus.DONE),
            and_(total_items > 0, llm_done_items >= total_items),
        ),
    )
    evaluation_running = and_(
        ValidationRun.status == RunStatus.DONE,
        or_(
            ValidationRun.eval_status == EvalStatus.RUNNING,
            and_(total_items == 0, ValidationRun.eval_status == EvalStatus.PENDING),
            and_(total_items > 0, llm_done_items > 0, llm_done_items < total_items),
        ),
    )
    evaluation_pending = or_(
        ValidationRun.status != RunStatus.DONE,
        and_(ValidationRun.status == RunStatus.DONE, total_items > 0, llm_done_items == 0, ValidationRun.eval_status != EvalStatus.RUNNING),
        and_(ValidationRun.status == RunStatus.DONE, total_items == 0, ValidationRun.eval_status != EvalStatus.DONE, ValidationRun.eval_status != EvalStatus.RUNNING),
    )

    if normalized == "평가완료":
        return query.filter(evaluation_done)
    if normalized == "평가중":
        return query.filter(evaluation_running)
    if normalized == "평가대기":
        return query.filter(evaluation_pending)

    return query


def _to_json_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _to_json_payload(value: str | None) -> dict[str, float]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}
    out: dict[str, float] = {}
    for key, metric in parsed.items():
        if isinstance(metric, (int, float)):
            out[str(key)] = float(metric)
    return out


class ValidationRunRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_run(
        self,
        *,
        environment: Environment,
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

    def update_run(
        self,
        run_id: str,
        *,
        name: Optional[str] = None,
        agent_id: Optional[str] = None,
        eval_model: Optional[str] = None,
        repeat_in_conversation: Optional[int] = None,
        conversation_room_count: Optional[int] = None,
        agent_parallel_calls: Optional[int] = None,
        timeout_ms: Optional[int] = None,
        context: Optional[dict[str, Any]] = None,
        update_context: bool = False,
    ) -> Optional[ValidationRun]:
        run = self.get_run(run_id)
        if run is None:
            return None

        if name is not None:
            run.name = (name or "").strip()
        if agent_id is not None:
            run.agent_id = (agent_id or "").strip()
        if eval_model is not None:
            run.eval_model = (eval_model or "").strip()
        if repeat_in_conversation is not None:
            run.repeat_in_conversation = max(1, int(repeat_in_conversation))
        if conversation_room_count is not None:
            run.conversation_room_count = max(1, int(conversation_room_count))
        if agent_parallel_calls is not None:
            run.agent_parallel_calls = max(1, int(agent_parallel_calls))
        if timeout_ms is not None:
            run.timeout_ms = max(1000, int(timeout_ms))

        if update_context:
            try:
                options = json.loads(run.options_json or "{}")
                if not isinstance(options, dict):
                    options = {}
            except Exception:
                options = {}
            if context is None:
                options.pop("context", None)
            else:
                options["context"] = context
            run.options_json = json.dumps(options, ensure_ascii=False)

        self.db.flush()
        return run

    def list_runs(
        self,
        *,
        environment: Optional[Environment] = None,
        test_set_id: Optional[str] = None,
        status: Optional[str] = None,
        evaluation_status: Optional[str] = None,
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
        query = _apply_evaluation_status_filter(query, self.db, evaluation_status)
        return list(query.order_by(ValidationRun.created_at.desc()).offset(offset).limit(limit).all())

    def count_runs(
        self,
        *,
        environment: Optional[Environment] = None,
        test_set_id: Optional[str] = None,
        status: Optional[str] = None,
        evaluation_status: Optional[str] = None,
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
        query = _apply_evaluation_status_filter(query, self.db, evaluation_status)
        return int(query.scalar() or 0)

    def list_active_runs(
        self,
        *,
        environment: Environment,
        limit: int = 20,
    ) -> list[ValidationRun]:
        active_filter = or_(
            ValidationRun.status == RunStatus.RUNNING,
            and_(
                ValidationRun.status == RunStatus.DONE,
                ValidationRun.eval_status == EvalStatus.RUNNING,
            ),
        )
        query = (
            self.db.query(ValidationRun)
            .filter(ValidationRun.environment == environment, active_filter)
            .order_by(ValidationRun.created_at.desc())
            .limit(max(1, int(limit)))
        )
        return list(query.all())

    def list_run_ids_by_environment(self, *, environment: Environment, run_ids: list[str]) -> list[str]:
        normalized_ids = [str(run_id or "").strip() for run_id in run_ids]
        normalized_ids = [run_id for run_id in normalized_ids if run_id]
        if not normalized_ids:
            return []
        rows = (
            self.db.query(ValidationRun.id)
            .filter(
                ValidationRun.environment == environment,
                ValidationRun.id.in_(normalized_ids),
            )
            .all()
        )
        return [str(row[0] if not isinstance(row, str) else row) for row in rows]

    def get_run_activity_read_map(self, *, actor_key: str, run_ids: list[str]) -> dict[str, bool]:
        normalized_actor_key = str(actor_key or "").strip()
        normalized_run_ids = [str(run_id or "").strip() for run_id in run_ids]
        normalized_run_ids = [run_id for run_id in normalized_run_ids if run_id]
        if not normalized_actor_key or not normalized_run_ids:
            return {}

        rows = (
            self.db.query(ValidationRunActivityRead)
            .filter(
                ValidationRunActivityRead.actor_key == normalized_actor_key,
                ValidationRunActivityRead.run_id.in_(normalized_run_ids),
                ValidationRunActivityRead.read_at.isnot(None),
            )
            .all()
        )
        return {row.run_id: True for row in rows}

    def mark_run_activity_read(self, *, actor_key: str, run_ids: list[str]) -> int:
        normalized_actor_key = str(actor_key or "").strip()
        normalized_run_ids = [str(run_id or "").strip() for run_id in run_ids]
        normalized_run_ids = [run_id for run_id in normalized_run_ids if run_id]
        if not normalized_actor_key or not normalized_run_ids:
            return 0

        unique_run_ids = list(dict.fromkeys(normalized_run_ids))
        existing_rows = (
            self.db.query(ValidationRunActivityRead)
            .filter(
                ValidationRunActivityRead.actor_key == normalized_actor_key,
                ValidationRunActivityRead.run_id.in_(unique_run_ids),
            )
            .all()
        )
        existing_by_run_id = {row.run_id: row for row in existing_rows}
        now = dt.datetime.utcnow()
        touched = 0

        for run_id in unique_run_ids:
            existing = existing_by_run_id.get(run_id)
            if existing is None:
                self.db.add(
                    ValidationRunActivityRead(
                        run_id=run_id,
                        actor_key=normalized_actor_key,
                        read_at=now,
                    )
                )
            else:
                existing.read_at = now
            touched += 1

        self.db.flush()
        return touched

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

    def list_items_by_ids(self, run_id: str, item_ids: list[str]) -> list[ValidationRunItem]:
        if not item_ids:
            return []
        return list(
            self.db.query(ValidationRunItem)
            .filter(ValidationRunItem.run_id == run_id, ValidationRunItem.id.in_(item_ids))
            .order_by(ValidationRunItem.ordinal.asc())
            .all()
        )

    def get_item(self, item_id: str) -> Optional[ValidationRunItem]:
        return self.db.get(ValidationRunItem, item_id)

    def update_item_snapshots(
        self,
        item_id: str,
        *,
        expected_result_snapshot: Optional[str] = None,
    ) -> Optional[ValidationRunItem]:
        item = self.get_item(item_id)
        if item is None:
            return None
        if expected_result_snapshot is not None:
            item.expected_result_snapshot = str(expected_result_snapshot)
        self.db.flush()
        return item

    def bulk_update_item_expected_results(self, run_id: str, updates: dict[str, str]) -> int:
        if not updates:
            return 0
        rows = self.list_items_by_ids(run_id, list(updates.keys()))
        updated_count = 0
        for row in rows:
            next_expected_result = str(updates.get(row.id, ""))
            if str(row.expected_result_snapshot or "") == next_expected_result:
                continue
            row.expected_result_snapshot = next_expected_result
            updated_count += 1
        self.db.flush()
        return updated_count

    def clear_llm_evaluations_for_run(self, run_id: str) -> None:
        item_rows = self.db.query(ValidationRunItem.id).filter(ValidationRunItem.run_id == run_id).all()
        item_ids = [row[0] if not isinstance(row, str) else row for row in item_rows]
        item_ids = [item_id for item_id in item_ids if item_id is not None]
        if item_ids:
            self.db.execute(
                delete(ValidationLlmEvaluation).where(
                    ValidationLlmEvaluation.run_item_id.in_(item_ids)
                )
            )
        self.db.flush()

    def reset_eval_state_to_pending(self, run_id: str) -> None:
        run = self.get_run(run_id)
        if run is None:
            return
        run.eval_status = EvalStatus.PENDING
        run.eval_started_at = None
        run.eval_finished_at = None
        self.db.flush()

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
            .filter(ValidationRunItem.run_id == run_id, ValidationLlmEvaluation.status.like("DONE%"))
            .scalar()
            or 0
        )

    def get_run_score_snapshot(self, run_id: str) -> Optional[ValidationScoreSnapshot]:
        return (
            self.db.query(ValidationScoreSnapshot)
            .filter(ValidationScoreSnapshot.run_id == run_id, ValidationScoreSnapshot.query_group_id.is_(None))
            .order_by(ValidationScoreSnapshot.evaluated_at.desc())
            .first()
        )

    def get_run_average_response_time_sec(self, run_id: str) -> Optional[float]:
        avg_latency_ms = (
            self.db.query(func.avg(ValidationRunItem.latency_ms))
            .filter(ValidationRunItem.run_id == run_id, ValidationRunItem.latency_ms.isnot(None))
            .scalar()
        )
        if avg_latency_ms is None:
            return None
        try:
            value = float(avg_latency_ms)
        except Exception:
            return None
        if not (value and value >= 0):
            return 0.0 if value == 0 else None
        return round(value / 1000, 3)

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
        self.db.execute(
            delete(ValidationScoreSnapshot).where(ValidationScoreSnapshot.run_id == run_id)
        )
        self.db.flush()

    def delete_run(self, run_id: str) -> bool:
        run = self.get_run(run_id)
        if run is None:
            return False

        if run.status != RunStatus.PENDING:
            raise ValueError("Only PENDING runs can be deleted")

        if self.count_done_items(run.id) > 0 or self.count_error_items(run.id) > 0:
            raise ValueError("Runs with execution history cannot be deleted")

        has_dependent_run = (
            self.db.query(ValidationRun.id)
            .filter(ValidationRun.base_run_id == run_id)
            .first()
            is not None
        )
        if has_dependent_run:
            raise ValueError("Run cannot be deleted because it is referenced by other runs")

        item_rows = self.db.query(ValidationRunItem.id).filter(ValidationRunItem.run_id == run_id).all()
        item_ids = [row[0] if not isinstance(row, str) else row for row in item_rows]
        item_ids = [item_id for item_id in item_ids if item_id is not None]

        self.clear_score_snapshots_for_run(run_id)
        if item_ids:
            self.db.execute(
                delete(ValidationLogicEvaluation).where(
                    ValidationLogicEvaluation.run_item_id.in_(item_ids)
                )
            )
            self.db.execute(
                delete(ValidationLlmEvaluation).where(
                    ValidationLlmEvaluation.run_item_id.in_(item_ids)
                )
            )
            self.db.execute(
                delete(ValidationRunItem).where(ValidationRunItem.id.in_(item_ids))
            )

        self.db.execute(delete(ValidationRun).where(ValidationRun.id == run.id))
        self.db.flush()
        return True

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

    def ensure_run_activity_rows(
        self,
        *,
        environment: Environment,
        actor_key: str,
        limit: int = 1000,
    ) -> int:
        normalized_actor_key = str(actor_key or "").strip()
        if not normalized_actor_key:
            return 0
        active_runs = self.list_active_runs(environment=environment, limit=max(1, int(limit)))
        run_ids = [str(run.id or "").strip() for run in active_runs if str(run.id or "").strip()]
        if not run_ids:
            return 0

        existing_rows = (
            self.db.query(ValidationRunActivityRead.run_id)
            .filter(
                ValidationRunActivityRead.actor_key == normalized_actor_key,
                ValidationRunActivityRead.run_id.in_(run_ids),
            )
            .all()
        )
        existing_run_ids = {str(row[0]) for row in existing_rows if row and row[0]}
        now = dt.datetime.utcnow()
        inserted = 0
        for run_id in run_ids:
            if run_id in existing_run_ids:
                continue
            self.db.add(
                ValidationRunActivityRead(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    actor_key=normalized_actor_key,
                    read_at=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            inserted += 1
        if inserted:
            self.db.flush()
        return inserted

    def list_run_activity_items(
        self,
        *,
        environment: Environment,
        actor_key: str,
        limit: int = 20,
    ) -> list[tuple[ValidationRun, bool]]:
        normalized_actor_key = str(actor_key or "").strip()
        if not normalized_actor_key:
            return []

        rows = (
            self.db.query(ValidationRun, ValidationRunActivityRead.read_at)
            .join(ValidationRunActivityRead, ValidationRunActivityRead.run_id == ValidationRun.id)
            .filter(
                ValidationRun.environment == environment,
                ValidationRunActivityRead.actor_key == normalized_actor_key,
            )
            .order_by(ValidationRun.created_at.desc())
            .limit(max(1, int(limit)))
            .all()
        )
        return [(run, bool(read_at)) for run, read_at in rows]

    def count_unread_run_activity_items(
        self,
        *,
        environment: Environment,
        actor_key: str,
    ) -> int:
        normalized_actor_key = str(actor_key or "").strip()
        if not normalized_actor_key:
            return 0

        count = (
            self.db.query(func.count(ValidationRunActivityRead.id))
            .join(ValidationRun, ValidationRunActivityRead.run_id == ValidationRun.id)
            .filter(
                ValidationRun.environment == environment,
                ValidationRunActivityRead.actor_key == normalized_actor_key,
                ValidationRunActivityRead.read_at.is_(None),
            )
            .scalar()
        )
        return int(count or 0)

    def mark_all_run_activity_read(
        self,
        *,
        environment: Environment,
        actor_key: str,
    ) -> int:
        normalized_actor_key = str(actor_key or "").strip()
        if not normalized_actor_key:
            return 0

        rows = (
            self.db.query(ValidationRunActivityRead)
            .join(ValidationRun, ValidationRunActivityRead.run_id == ValidationRun.id)
            .filter(
                ValidationRun.environment == environment,
                ValidationRunActivityRead.actor_key == normalized_actor_key,
                ValidationRunActivityRead.read_at.is_(None),
            )
            .all()
        )
        if not rows:
            return 0

        now = dt.datetime.utcnow()
        for row in rows:
            row.read_at = now
            row.updated_at = now
        self.db.flush()
        return len(rows)

    def build_run_payload(self, run: ValidationRun) -> dict[str, Any]:
        score_snapshot = self.get_run_score_snapshot(run.id)
        score_summary = None
        if score_snapshot is not None:
            score_summary = {
                "totalItems": score_snapshot.total_items,
                "executedItems": score_snapshot.executed_items,
                "errorItems": score_snapshot.error_items,
                "logicPassItems": score_snapshot.logic_pass_items,
                "logicPassRate": round(score_snapshot.logic_pass_rate, 3),
                "llmDoneItems": score_snapshot.llm_done_items,
                "llmMetricAverages": _to_json_payload(score_snapshot.llm_metric_averages_json),
                "llmTotalScoreAvg": score_snapshot.llm_total_score_avg,
            }
        return {
            "id": run.id,
            "name": run.name,
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
            "averageResponseTimeSec": self.get_run_average_response_time_sec(run.id),
            "scoreSummary": score_summary,
            "totalItems": self.count_items(run.id),
            "doneItems": self.count_done_items(run.id),
            "errorItems": self.count_error_items(run.id),
            "llmDoneItems": self.count_llm_done_items(run.id),
        }
