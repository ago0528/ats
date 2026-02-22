from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any, Optional

import aiohttp

from app.adapters.openai_judge_adapter import OpenAIJudgeAdapter
from app.core.db import SessionLocal
from app.core.enums import EvalStatus
from app.repositories.validation_runs import ValidationRunRepository
from app.services.logic_check import run_logic_check


def _parse_metric_scores(metric_scores_json: str) -> dict[str, float]:
    if not metric_scores_json:
        return {}
    try:
        payload = json.loads(metric_scores_json)
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}

    out: dict[str, float] = {}
    for key, value in payload.items():
        if isinstance(value, (int, float)):
            out[str(key)] = float(value)
    return out


def _coerce_float(value: Any) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    normalized = float(value)
    if not (normalized == normalized):
        return None
    return normalized


def _parse_pass_flag(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 0:
            return False
        if value == 1:
            return True
        return None
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "y", "yes", "pass", "passed", "ok", "success"}:
            return True
        if normalized in {"false", "0", "n", "no", "fail", "failed", "reject", "invalid"}:
            return False
    return None


def _build_score_snapshots(repo: ValidationRunRepository, run_id: str, run_items: list[Any]) -> None:
    run = repo.get_run(run_id)
    if run is None:
        return

    item_ids = [item.id for item in run_items]
    logic_map = repo.get_logic_eval_map(item_ids)
    llm_map = repo.get_llm_eval_map(item_ids)
    query_ids = [item.query_id for item in run_items if item.query_id]
    query_to_group = repo.list_query_group_ids_by_query_ids(query_ids)

    aggregates: dict[Optional[str], dict[str, Any]] = defaultdict(
        lambda: {
            "totalItems": 0,
            "executedItems": 0,
            "errorItems": 0,
            "logicPassItems": 0,
            "llmDoneItems": 0,
            "metricSums": defaultdict(float),
            "metricCounts": defaultdict(int),
            "totalScoreSum": 0.0,
            "totalScoreCount": 0,
        }
    )

    for item in run_items:
        group_id = query_to_group.get(item.query_id) if item.query_id else None
        target_groups = [None]
        if group_id:
            target_groups.append(group_id)

        for target_group in target_groups:
            agg = aggregates[target_group]
            agg["totalItems"] += 1

            has_execution = bool(item.executed_at) or bool((item.error or "").strip())
            if has_execution:
                agg["executedItems"] += 1

            if (item.error or "").strip():
                agg["errorItems"] += 1

            logic = logic_map.get(item.id)
            if logic and logic.result == "PASS":
                agg["logicPassItems"] += 1

            llm = llm_map.get(item.id)
            if llm and llm.status == "DONE":
                agg["llmDoneItems"] += 1
                if isinstance(llm.total_score, (int, float)):
                    agg["totalScoreSum"] += float(llm.total_score)
                    agg["totalScoreCount"] += 1
                for metric_name, metric_score in _parse_metric_scores(llm.metric_scores_json).items():
                    agg["metricSums"][metric_name] += metric_score
                    agg["metricCounts"][metric_name] += 1

    repo.clear_score_snapshots_for_run(run_id)
    for group_id, agg in aggregates.items():
        metric_avg = {
            metric_name: round(agg["metricSums"][metric_name] / agg["metricCounts"][metric_name], 4)
            for metric_name in agg["metricSums"]
            if agg["metricCounts"][metric_name] > 0
        }
        score_avg = (
            round(agg["totalScoreSum"] / agg["totalScoreCount"], 4)
            if agg["totalScoreCount"] > 0
            else None
        )
        repo.upsert_score_snapshot(
            run_id=run_id,
            test_set_id=run.test_set_id,
            query_group_id=group_id,
            total_items=agg["totalItems"],
            executed_items=agg["executedItems"],
            error_items=agg["errorItems"],
            logic_pass_items=agg["logicPassItems"],
            llm_done_items=agg["llmDoneItems"],
            llm_metric_averages=metric_avg,
            llm_total_score_avg=score_avg,
        )


async def evaluate_validation_run(
    run_id: str,
    openai_key: Optional[str],
    openai_model: str,
    max_chars: int,
    max_parallel: int,
):
    db = SessionLocal()
    repo = ValidationRunRepository(db)
    repo.set_eval_status(run_id, EvalStatus.RUNNING)
    db.commit()

    try:
        run_items = repo.list_items(run_id, limit=100000)
        if not run_items:
            repo.set_eval_status(run_id, EvalStatus.DONE)
            db.commit()
            return

        logic_result_by_item: dict[str, str] = {}
        logic_fail_reason_by_item: dict[str, str] = {}
        for item in run_items:
            if item.logic_field_path_snapshot and item.logic_expected_value_snapshot:
                logic_raw_result = run_logic_check(
                    item.raw_json or "",
                    item.logic_field_path_snapshot,
                    item.logic_expected_value_snapshot,
                )
            else:
                logic_raw_result = "SKIPPED_NO_CRITERIA"

            logic_upper = str(logic_raw_result).upper()
            if logic_upper.startswith("PASS"):
                logic_result = "PASS"
                fail_reason = ""
            elif logic_upper.startswith("FAIL"):
                logic_result = "FAIL"
                fail_reason = str(logic_raw_result)
            else:
                logic_result = "SKIPPED"
                fail_reason = ""

            logic_result_by_item[item.id] = logic_result
            logic_fail_reason_by_item[item.id] = fail_reason
            repo.upsert_logic_eval(
                item.id,
                eval_items={
                    "fieldPath": item.logic_field_path_snapshot,
                    "expectedValue": item.logic_expected_value_snapshot,
                },
                result=logic_result,
                fail_reason=fail_reason,
            )
        db.commit()

        adapter = OpenAIJudgeAdapter()
        sem = asyncio.Semaphore(max(1, int(max_parallel or 1)))
        timeout = aiohttp.ClientTimeout(total=120)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async def _evaluate_item(item) -> None:
                if (item.error or "").strip():
                    repo.upsert_llm_eval(
                        item.id,
                        eval_model=openai_model,
                        metric_scores={},
                        total_score=None,
                        llm_comment="Execution failed. LLM evaluation skipped.",
                        status="SKIPPED_ERROR",
                    )
                    return

                criteria_text = (item.applied_criteria_json or "").strip()
                if not criteria_text:
                    repo.upsert_llm_eval(
                        item.id,
                        eval_model=openai_model,
                        metric_scores={},
                        total_score=None,
                        llm_comment="No criteria provided.",
                        status="SKIPPED_NO_CRITERIA",
                    )
                    return

                if not openai_key:
                    repo.upsert_llm_eval(
                        item.id,
                        eval_model=openai_model,
                        metric_scores={},
                        total_score=None,
                        llm_comment="OpenAI API key is missing.",
                        status="SKIPPED_NO_KEY",
                    )
                    return

                logic_result = logic_result_by_item.get(item.id, "SKIPPED")
                raw_response_preview = (item.raw_response or "").strip()[:max_chars]
                raw_json_preview = (item.raw_json or "").strip()[:max_chars]
                criteria_preview = criteria_text[:max_chars]
                logic_expected = (item.logic_expected_value_snapshot or "").strip()[:max_chars]
                logic_fail_reason = (logic_fail_reason_by_item.get(item.id) or "").strip()[:max_chars]
                logic_fail_reason_text = f", failReason={logic_fail_reason}" if logic_fail_reason else ""
                prompt = (
                    "다음 응답을 LLM as a judge 방식으로 평가하세요.\n\n"
                    "규칙:\n"
                    "1) 출력은 JSON 객체만 허용.\n"
                    "2) 키는 반드시 metric_scores, total_score, passed, comment 이어야 함.\n"
                    "3) metric_scores 값은 숫자(1~5)이며, 가능한 경우 여러 항목을 반환.\n\n"
                    f"질의: {item.query_text_snapshot}\n\n"
                    f"기대 결과: {item.expected_result_snapshot}\n\n"
                    f"실행 Raw 응답: {raw_response_preview}\n\n"
                    f"실행 Raw JSON: {raw_json_preview}\n\n"
                    f"로직 규칙: fieldPath={item.logic_field_path_snapshot or '-'}, expected={logic_expected}, result={logic_result}{logic_fail_reason_text}\n\n"
                    f"평가 기준(JSON): {criteria_preview}\n\n"
                    '{"metric_scores": {"정확성": 1~5}, "total_score": 1~5, "passed": true, "comment": "평가 근거"}'
                )

                try:
                    async with sem:
                        result, _usage, err = await adapter.judge(session, openai_key, openai_model, prompt)

                    if result is None:
                        repo.upsert_llm_eval(
                            item.id,
                            eval_model=openai_model,
                            metric_scores={},
                            total_score=None,
                            llm_comment=err or "Evaluation failed",
                            status=f"FAILED:{err or 'unknown'}",
                        )
                        return

                    metric_scores = {}
                    total_score = None
                    passed = None
                    comment = ""
                    if isinstance(result, dict):
                        if isinstance(result.get("metric_scores"), dict):
                            metric_scores = result.get("metric_scores") or {}
                        elif isinstance(result.get("score"), (int, float)):
                            metric_scores = {"overall": float(result["score"])}

                        passed = _parse_pass_flag(result.get("passed"))

                        if _coerce_float(result.get("total_score")) is not None:
                            total_score = _coerce_float(result["total_score"])
                        elif _coerce_float(result.get("score")) is not None:
                            total_score = float(result["score"])

                        if passed is None and total_score is not None:
                            passed = total_score >= 3.0

                        if passed is True and total_score is None:
                            total_score = 5.0
                        if passed is False and total_score is None:
                            total_score = 1.0

                        comment = str(result.get("comment") or result.get("reason") or "")
                        if passed is True:
                            comment = f"{comment} (passed=true)".strip()
                        elif passed is False:
                            comment = f"{comment} (passed=false)".strip()
                        elif comment == "":
                            comment = "No comment."

                    repo.upsert_llm_eval(
                        item.id,
                        eval_model=openai_model,
                        metric_scores=metric_scores,
                        total_score=total_score,
                        llm_comment=comment,
                        status="DONE",
                    )
                except Exception as exc:
                    repo.upsert_llm_eval(
                        item.id,
                        eval_model=openai_model,
                        metric_scores={},
                        total_score=None,
                        llm_comment=str(exc),
                        status=f"FAILED:{exc}",
                    )

            await asyncio.gather(*[_evaluate_item(item) for item in run_items])
            db.commit()

        _build_score_snapshots(repo, run_id, run_items)
        db.commit()

        repo.set_eval_status(run_id, EvalStatus.DONE)
        db.commit()
    except Exception:
        repo.set_eval_status(run_id, EvalStatus.FAILED)
        db.commit()
        raise
    finally:
        db.close()
