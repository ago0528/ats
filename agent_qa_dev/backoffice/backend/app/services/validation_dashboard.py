from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.validation_query import ValidationQuery
from app.models.validation_run import ValidationRun
from app.models.validation_run_item import ValidationRunItem
from app.repositories.validation_runs import ValidationRunRepository


def _metric_scores(metric_scores_json: str) -> dict[str, float]:
    if not metric_scores_json:
        return {}
    try:
        payload = json.loads(metric_scores_json)
    except Exception:
        return {}

    if isinstance(payload, dict):
        result: dict[str, float] = {}
        for key, value in payload.items():
            if isinstance(value, (int, float)):
                result[str(key)] = float(value)
        return result
    return {}


def _parse_iso_date(value: Optional[str], *, name: str) -> Optional[dt.date]:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text)
    except Exception as exc:
        raise ValueError(f"{name} must be YYYY-MM-DD") from exc


def build_group_dashboard(db: Session, group_id: str) -> dict[str, Any]:
    query_rows = list(db.query(ValidationQuery).filter(ValidationQuery.group_id == group_id).all())
    query_ids = [row.id for row in query_rows]
    if not query_ids:
        return {
            "groupId": group_id,
            "totalItems": 0,
            "logicPassRate": 0.0,
            "llmMetricAverages": {},
            "failurePatterns": [],
        }

    repo = ValidationRunRepository(db)
    items = list(db.query(ValidationRunItem).filter(ValidationRunItem.query_id.in_(query_ids)).all())
    item_ids = [item.id for item in items]
    logic_map = repo.get_logic_eval_map(item_ids)
    llm_map = repo.get_llm_eval_map(item_ids)

    total_items = len(items)
    if total_items == 0:
        return {
            "groupId": group_id,
            "totalItems": 0,
            "logicPassRate": 0.0,
            "llmMetricAverages": {},
            "failurePatterns": [],
        }

    logic_pass_count = 0
    metric_sums: dict[str, float] = defaultdict(float)
    metric_counts: dict[str, int] = defaultdict(int)
    failure_counts: dict[str, int] = defaultdict(int)

    for item in items:
        logic = logic_map.get(item.id)
        if logic and logic.result == "PASS":
            logic_pass_count += 1
        if (item.error or "").strip():
            failure_counts[item.category_snapshot or "Unknown"] += 1
        elif logic and logic.result == "FAIL":
            failure_counts[item.category_snapshot or "Unknown"] += 1

        llm = llm_map.get(item.id)
        if not llm:
            continue
        for metric_name, metric_score in _metric_scores(llm.metric_scores_json).items():
            metric_sums[metric_name] += metric_score
            metric_counts[metric_name] += 1

    metric_avg = {
        metric_name: round(metric_sums[metric_name] / metric_counts[metric_name], 4)
        for metric_name in metric_sums
        if metric_counts[metric_name] > 0
    }
    failure_patterns = [{"category": key, "count": count} for key, count in sorted(failure_counts.items(), key=lambda x: -x[1])]

    return {
        "groupId": group_id,
        "totalItems": total_items,
        "logicPassRate": round((logic_pass_count / total_items) * 100, 2) if total_items else 0.0,
        "llmMetricAverages": metric_avg,
        "failurePatterns": failure_patterns,
    }


def build_test_set_dashboard(
    db: Session,
    test_set_id: str,
    *,
    run_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> dict[str, Any]:
    from_date = _parse_iso_date(date_from, name="dateFrom")
    to_date = _parse_iso_date(date_to, name="dateTo")

    run_query = db.query(ValidationRun).filter(ValidationRun.test_set_id == test_set_id)
    if run_id:
        run_query = run_query.filter(ValidationRun.id == run_id)
    runs = list(run_query.order_by(ValidationRun.created_at.desc()).all())

    if from_date is not None or to_date is not None:
        filtered_runs: list[ValidationRun] = []
        for row in runs:
            created_date = row.created_at.date() if row.created_at else None
            if created_date is None:
                continue
            if from_date is not None and created_date < from_date:
                continue
            if to_date is not None and created_date > to_date:
                continue
            filtered_runs.append(row)
        runs = filtered_runs

    if not runs:
        return {
            "testSetId": test_set_id,
            "runCount": 0,
            "totalItems": 0,
            "executedItems": 0,
            "errorItems": 0,
            "logicPassRate": 0.0,
            "llmMetricAverages": {},
            "llmTotalScoreAverage": None,
            "failurePatterns": [],
            "runSummaries": [],
        }

    run_ids = [row.id for row in runs]
    items = list(db.query(ValidationRunItem).filter(ValidationRunItem.run_id.in_(run_ids)).all())

    repo = ValidationRunRepository(db)
    item_ids = [item.id for item in items]
    logic_map = repo.get_logic_eval_map(item_ids)
    llm_map = repo.get_llm_eval_map(item_ids)

    total_items = len(items)
    executed_items = 0
    error_items = 0
    logic_pass_items = 0
    metric_sums: dict[str, float] = defaultdict(float)
    metric_counts: dict[str, int] = defaultdict(int)
    total_score_sum = 0.0
    total_score_count = 0
    failure_counts: dict[str, int] = defaultdict(int)
    run_summaries: dict[str, dict[str, Any]] = {
        run.id: {
            "runId": run.id,
            "status": run.status.value,
            "evalStatus": getattr(run.eval_status, "value", str(run.eval_status)),
            "createdAt": run.created_at,
            "finishedAt": run.finished_at,
            "totalItems": 0,
            "executedItems": 0,
            "errorItems": 0,
            "logicPassItems": 0,
            "llmDoneItems": 0,
        }
        for run in runs
    }

    for item in items:
        summary = run_summaries.get(item.run_id)
        if summary is None:
            continue

        summary["totalItems"] += 1
        has_execution = bool(item.executed_at) or bool((item.error or "").strip())
        if has_execution:
            executed_items += 1
            summary["executedItems"] += 1

        if (item.error or "").strip():
            error_items += 1
            summary["errorItems"] += 1
            failure_counts[item.category_snapshot or "Unknown"] += 1

        logic = logic_map.get(item.id)
        if logic and logic.result == "PASS":
            logic_pass_items += 1
            summary["logicPassItems"] += 1
        elif logic and logic.result == "FAIL":
            failure_counts[item.category_snapshot or "Unknown"] += 1

        llm = llm_map.get(item.id)
        if llm and llm.status == "DONE":
            summary["llmDoneItems"] += 1
            if isinstance(llm.total_score, (int, float)):
                total_score_sum += float(llm.total_score)
                total_score_count += 1
            for metric_name, metric_score in _metric_scores(llm.metric_scores_json).items():
                metric_sums[metric_name] += metric_score
                metric_counts[metric_name] += 1

    metric_avg = {
        metric_name: round(metric_sums[metric_name] / metric_counts[metric_name], 4)
        for metric_name in metric_sums
        if metric_counts[metric_name] > 0
    }
    failure_patterns = [{"category": key, "count": count} for key, count in sorted(failure_counts.items(), key=lambda x: -x[1])]
    llm_total_score_avg = round(total_score_sum / total_score_count, 4) if total_score_count > 0 else None

    return {
        "testSetId": test_set_id,
        "runCount": len(runs),
        "totalItems": total_items,
        "executedItems": executed_items,
        "errorItems": error_items,
        "logicPassRate": round((logic_pass_items / total_items) * 100, 2) if total_items else 0.0,
        "llmMetricAverages": metric_avg,
        "llmTotalScoreAverage": llm_total_score_avg,
        "failurePatterns": failure_patterns,
        "runSummaries": list(run_summaries.values()),
    }
