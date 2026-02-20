from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.services.validation_dashboard import build_test_set_dashboard


def build_validation_report(db: Session, test_set_id: str, *, run_id: Optional[str] = None) -> dict[str, Any]:
    dashboard = build_test_set_dashboard(db, test_set_id, run_id=run_id)
    run_count = int(dashboard.get("runCount") or 0)
    total_items = int(dashboard.get("totalItems") or 0)
    error_items = int(dashboard.get("errorItems") or 0)
    logic_pass_rate = float(dashboard.get("logicPassRate") or 0.0)
    score_avg = dashboard.get("llmTotalScoreAverage")

    summary = (
        f"테스트세트 {test_set_id}: run {run_count}건, item {total_items}건, "
        f"오류 {error_items}건, logic pass {logic_pass_rate:.2f}%"
    )
    if isinstance(score_avg, (int, float)):
        summary += f", LLM 총점 평균 {float(score_avg):.2f}"

    return {
        "testSetId": test_set_id,
        "runId": run_id,
        "summary": summary,
        "dashboard": dashboard,
    }

