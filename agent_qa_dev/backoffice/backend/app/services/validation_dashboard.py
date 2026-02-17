from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.models.validation_query import ValidationQuery
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
