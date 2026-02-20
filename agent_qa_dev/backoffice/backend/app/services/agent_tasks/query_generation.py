from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.models.validation_run import ValidationRun
from app.models.validation_run_item import ValidationRunItem
from app.repositories.validation_runs import ValidationRunRepository


def build_query_suggestions(db: Session, test_set_id: str, *, limit: int = 5) -> dict[str, Any]:
    runs = list(
        db.query(ValidationRun)
        .filter(ValidationRun.test_set_id == test_set_id)
        .order_by(ValidationRun.created_at.desc())
        .limit(50)
        .all()
    )
    if not runs:
        return {
            "testSetId": test_set_id,
            "suggestedQueries": [],
            "reason": "No runs found for this test set.",
        }

    run_ids = [run.id for run in runs]
    items = list(db.query(ValidationRunItem).filter(ValidationRunItem.run_id.in_(run_ids)).all())
    if not items:
        return {
            "testSetId": test_set_id,
            "suggestedQueries": [],
            "reason": "No run items found for this test set.",
        }

    repo = ValidationRunRepository(db)
    logic_map = repo.get_logic_eval_map([item.id for item in items])

    failure_counts: dict[str, int] = defaultdict(int)
    for item in items:
        logic = logic_map.get(item.id)
        failed_by_logic = logic is not None and logic.result == "FAIL"
        failed_by_error = bool((item.error or "").strip())
        if not (failed_by_logic or failed_by_error):
            continue
        query_text = (item.query_text_snapshot or "").strip()
        if query_text:
            failure_counts[query_text] += 1

    ranked = sorted(failure_counts.items(), key=lambda row: (-row[1], row[0]))
    suggestions = [
        {
            "queryText": query_text,
            "failureCount": count,
            "suggestion": f"'{query_text}' 변형 질의를 1~2개 추가해 회귀 범위를 넓히세요.",
        }
        for query_text, count in ranked[: max(1, int(limit))]
    ]

    return {
        "testSetId": test_set_id,
        "suggestedQueries": suggestions,
        "reason": "Generated from recent failed run items.",
    }

