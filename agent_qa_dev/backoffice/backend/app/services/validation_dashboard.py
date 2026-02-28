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
from app.services.validation_scoring import (
    average,
    extract_response_time_sec,
    parse_raw_payload,
    quantile,
    score_bucket,
    score_stability,
)


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


def _is_llm_done(status: Optional[str]) -> bool:
    return str(status or "").upper().startswith("DONE")


def _init_score_buckets() -> dict[str, int]:
    return {str(index): 0 for index in range(6)}


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
            "llmMetricAverages": {},
            "failurePatterns": [],
        }

    repo = ValidationRunRepository(db)
    items = list(db.query(ValidationRunItem).filter(ValidationRunItem.query_id.in_(query_ids)).all())
    item_ids = [item.id for item in items]
    llm_map = repo.get_llm_eval_map(item_ids)

    total_items = len(items)
    if total_items == 0:
        return {
            "groupId": group_id,
            "totalItems": 0,
            "llmMetricAverages": {},
            "failurePatterns": [],
        }

    metric_sums: dict[str, float] = defaultdict(float)
    metric_counts: dict[str, int] = defaultdict(int)
    failure_counts: dict[str, int] = defaultdict(int)

    for item in items:
        if (item.error or "").strip():
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
            "llmMetricAverages": {},
            "llmTotalScoreAverage": None,
            "failurePatterns": [],
            "runSummaries": [],
            "scoring": {
                "intent": {"score": None, "sampleCount": 0},
                "accuracy": {
                    "score": None,
                    "sampleCount": 0,
                },
                "consistency": {"status": "PENDING", "score": None, "eligibleQueryCount": 0, "consistentQueryCount": 0},
                "latencySingle": {"avgSec": None, "p50Sec": None, "p90Sec": None, "count": 0},
                "latencyMulti": {"avgSec": None, "p50Sec": None, "p90Sec": None, "count": 0},
                "latencyUnclassifiedCount": 0,
                "stability": {"score": None, "errorRate": 0.0, "emptyRate": 0.0},
            },
            "distributions": {
                "scoreBuckets": _init_score_buckets(),
            },
        }

    run_ids = [row.id for row in runs]
    items = list(db.query(ValidationRunItem).filter(ValidationRunItem.run_id.in_(run_ids)).all())

    repo = ValidationRunRepository(db)
    item_ids = [item.id for item in items]
    llm_map = repo.get_llm_eval_map(item_ids)

    total_items = len(items)
    executed_items = 0
    error_items = 0
    metric_sums: dict[str, float] = defaultdict(float)
    metric_counts: dict[str, int] = defaultdict(int)
    total_score_sum = 0.0
    total_score_count = 0
    failure_counts: dict[str, int] = defaultdict(int)
    item_score_buckets = _init_score_buckets()
    intent_scores: list[float] = []
    accuracy_scores: list[float] = []
    stability_scores: list[float] = []
    consistency_by_query: dict[str, float] = {}
    latency_single_secs: list[float] = []
    latency_multi_secs: list[float] = []
    latency_unclassified_count = 0
    empty_response_count = 0
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

        raw_payload, raw_parse_ok = parse_raw_payload(item.raw_json or "")
        stability_score_value = score_stability(
            error_text=item.error or "",
            raw_payload=raw_payload,
            raw_parse_ok=raw_parse_ok,
        )
        if stability_score_value < 5.0 and not (item.error or "").strip():
            empty_response_count += 1

        response_time_sec = extract_response_time_sec(raw_payload, item.latency_ms)

        llm = llm_map.get(item.id)
        intent_score_value = None
        accuracy_score_value = None
        stability_metric_value = None
        latency_single_score_value = None
        latency_multi_score_value = None
        consistency_score_value = None
        if llm:
            if _is_llm_done(getattr(llm, "status", None)):
                summary["llmDoneItems"] += 1
                if isinstance(llm.total_score, (int, float)):
                    total_score_sum += float(llm.total_score)
                    total_score_count += 1
                metrics = _metric_scores(llm.metric_scores_json)
                intent_score_value = metrics.get("intent")
                accuracy_score_value = metrics.get("accuracy")
                consistency_score_value = metrics.get("consistency")
                latency_single_score_value = metrics.get("latencySingle")
                latency_multi_score_value = metrics.get("latencyMulti")
                stability_metric_value = metrics.get("stability")
                for metric_name, metric_score in metrics.items():
                    metric_sums[metric_name] += metric_score
                    metric_counts[metric_name] += 1

        if response_time_sec is not None:
            has_single = isinstance(latency_single_score_value, (int, float))
            has_multi = isinstance(latency_multi_score_value, (int, float))
            if has_single and not has_multi:
                latency_single_secs.append(response_time_sec)
            elif has_multi and not has_single:
                latency_multi_secs.append(response_time_sec)
            else:
                latency_unclassified_count += 1

        if isinstance(consistency_score_value, (int, float)):
            query_key = str(item.query_id or item.query_text_snapshot or item.id)
            if query_key and query_key not in consistency_by_query:
                consistency_by_query[query_key] = float(consistency_score_value)

        if isinstance(intent_score_value, (int, float)):
            intent_scores.append(float(intent_score_value))
        if isinstance(accuracy_score_value, (int, float)):
            accuracy_scores.append(float(accuracy_score_value))

        stability_for_scoring = (
            float(stability_metric_value)
            if isinstance(stability_metric_value, (int, float))
            else float(stability_score_value)
        )
        stability_scores.append(stability_for_scoring)

        quality_score = average(
            [
                float(intent_score_value) if isinstance(intent_score_value, (int, float)) else 0.0,
                float(accuracy_score_value) if isinstance(accuracy_score_value, (int, float)) else 0.0,
                stability_for_scoring,
            ]
        )
        score_key = score_bucket(quality_score)
        if score_key is not None:
            item_score_buckets[score_key] += 1

    metric_avg = {
        metric_name: round(metric_sums[metric_name] / metric_counts[metric_name], 4)
        for metric_name in metric_sums
        if metric_counts[metric_name] > 0
    }
    failure_patterns = [{"category": key, "count": count} for key, count in sorted(failure_counts.items(), key=lambda x: -x[1])]
    llm_total_score_avg = round(total_score_sum / total_score_count, 4) if total_score_count > 0 else None
    consistency_values = list(consistency_by_query.values())
    consistency_avg = average(consistency_values)
    consistency_summary = {
        "status": "READY" if consistency_values else "PENDING",
        "score": round(consistency_avg, 4) if consistency_avg is not None else None,
        "eligibleQueryCount": len(consistency_values),
        "consistentQueryCount": len(consistency_values),
    }

    latency_single_avg_sec = average(latency_single_secs)
    latency_single_p50 = quantile(latency_single_secs, 0.5)
    latency_single_p90 = quantile(latency_single_secs, 0.9)
    latency_multi_avg_sec = average(latency_multi_secs)
    latency_multi_p50 = quantile(latency_multi_secs, 0.5)
    latency_multi_p90 = quantile(latency_multi_secs, 0.9)
    stability_avg = average(stability_scores)
    intent_avg = average(intent_scores)
    accuracy_avg = average(accuracy_scores)

    scoring = {
        "intent": {
            "score": round(intent_avg, 4) if intent_avg is not None else None,
            "sampleCount": len(intent_scores),
        },
        "accuracy": {
            "score": round(accuracy_avg, 4) if accuracy_avg is not None else None,
            "sampleCount": len(accuracy_scores),
        },
        "consistency": consistency_summary,
        "latencySingle": {
            "avgSec": round(latency_single_avg_sec, 4) if latency_single_avg_sec is not None else None,
            "p50Sec": round(latency_single_p50, 4) if latency_single_p50 is not None else None,
            "p90Sec": round(latency_single_p90, 4) if latency_single_p90 is not None else None,
            "count": len(latency_single_secs),
        },
        "latencyMulti": {
            "avgSec": round(latency_multi_avg_sec, 4) if latency_multi_avg_sec is not None else None,
            "p50Sec": round(latency_multi_p50, 4) if latency_multi_p50 is not None else None,
            "p90Sec": round(latency_multi_p90, 4) if latency_multi_p90 is not None else None,
            "count": len(latency_multi_secs),
        },
        "latencyUnclassifiedCount": int(latency_unclassified_count),
        "stability": {
            "score": round(stability_avg, 4) if stability_avg is not None else None,
            "errorRate": round((error_items / total_items), 4) if total_items else 0.0,
            "emptyRate": round((empty_response_count / total_items), 4) if total_items else 0.0,
        },
    }

    distributions = {
        "scoreBuckets": item_score_buckets,
    }

    return {
        "testSetId": test_set_id,
        "runCount": len(runs),
        "totalItems": total_items,
        "executedItems": executed_items,
        "errorItems": error_items,
        "llmMetricAverages": metric_avg,
        "llmTotalScoreAverage": llm_total_score_avg,
        "failurePatterns": failure_patterns,
        "runSummaries": list(run_summaries.values()),
        "scoring": scoring,
        "distributions": distributions,
    }
