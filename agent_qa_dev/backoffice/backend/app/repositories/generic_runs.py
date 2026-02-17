from __future__ import annotations

import datetime as dt
import json
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import Environment, RunStatus
from app.models.generic_run import GenericRun
from app.models.generic_run_row import GenericRunRow


class GenericRunRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_run(self, environment: Environment, options: dict) -> GenericRun:
        run = GenericRun(environment=environment, status=RunStatus.PENDING, options_json=json.dumps(options, ensure_ascii=False))
        self.db.add(run)
        self.db.flush()
        return run

    def add_rows(self, run_id: str, rows: list[dict]) -> list[str]:
        objs = []
        row_ids: list[str] = []
        for i, row in enumerate(rows, start=1):
            row_id = str(row.get("ID") or f"Q-{i}")
            row_obj = GenericRunRow(
                run_id=run_id,
                ordinal=i,
                query_id=row_id,
                query=str(row.get("질의") or ""),
                llm_criteria=str(row.get("LLM 평가기준") or ""),
                field_path=str(row.get("검증 필드") or ""),
                expected_value=str(row.get("기대값") or ""),
            )
            objs.append(row_obj)
            row_ids.append(row_obj.id)
        self.db.add_all(objs)
        return row_ids

    def add_row(
        self,
        run_id: str,
        query: str,
        llm_criteria: str = "",
        field_path: str = "",
        expected_value: str = "",
    ) -> str:
        max_ord = self.db.query(func.max(GenericRunRow.ordinal)).filter(GenericRunRow.run_id == run_id).scalar()
        next_ord = (int(max_ord) if max_ord is not None else 0) + 1
        row = GenericRunRow(
            run_id=run_id,
            ordinal=next_ord,
            query_id=f"Q-{next_ord}",
            query=str(query),
            llm_criteria=str(llm_criteria or ""),
            field_path=str(field_path or ""),
            expected_value=str(expected_value or ""),
        )
        self.db.add(row)
        self.db.flush()
        return row.id

    def get_run(self, run_id: str) -> Optional[GenericRun]:
        return self.db.get(GenericRun, run_id)

    def set_status(self, run_id: str, status: RunStatus) -> None:
        run = self.get_run(run_id)
        if run is None:
            return
        run.status = status
        if status == RunStatus.RUNNING:
            run.started_at = dt.datetime.utcnow()
        if status in (RunStatus.DONE, RunStatus.FAILED):
            run.finished_at = dt.datetime.utcnow()

    def list_rows(
        self,
        run_id: str,
        q: Optional[str] = None,
        logic_status: Optional[str] = None,
        has_error: Optional[bool] = None,
        offset: int = 0,
        limit: int = 100,
    ):
        stmt = select(GenericRunRow).where(GenericRunRow.run_id == run_id)
        if q:
            stmt = stmt.where(GenericRunRow.query.contains(q))
        if logic_status:
            stmt = stmt.where(GenericRunRow.logic_result.startswith(logic_status))
        if has_error is True:
            stmt = stmt.where(GenericRunRow.error != "")
        if has_error is False:
            stmt = stmt.where(GenericRunRow.error == "")
        stmt = stmt.order_by(GenericRunRow.ordinal).offset(offset).limit(limit)
        return list(self.db.scalars(stmt))

    def count_rows(self, run_id: str) -> int:
        stmt = select(func.count()).select_from(GenericRunRow).where(GenericRunRow.run_id == run_id)
        return int(self.db.execute(stmt).scalar_one())

    def count_done_rows(self, run_id: str) -> int:
        stmt = select(func.count()).select_from(GenericRunRow).where(
            GenericRunRow.run_id == run_id,
            GenericRunRow.response_text != "",
        )
        return int(self.db.execute(stmt).scalar_one())

    def count_error_rows(self, run_id: str) -> int:
        stmt = select(func.count()).select_from(GenericRunRow).where(
            GenericRunRow.run_id == run_id,
            GenericRunRow.error != "",
        )
        return int(self.db.execute(stmt).scalar_one())

    def count_llm_done_rows(self, run_id: str) -> int:
        stmt = select(func.count()).select_from(GenericRunRow).where(
            GenericRunRow.run_id == run_id,
            GenericRunRow.llm_eval_status == "DONE",
        )
        return int(self.db.execute(stmt).scalar_one())

    def latest_done_run_for_env(self, env: Environment, exclude_run_id: Optional[str] = None) -> Optional[GenericRun]:
        stmt = select(GenericRun).where(GenericRun.environment == env, GenericRun.status == RunStatus.DONE)
        if exclude_run_id:
            stmt = stmt.where(GenericRun.id != exclude_run_id)
        stmt = stmt.order_by(GenericRun.finished_at.desc())
        return self.db.scalars(stmt).first()
