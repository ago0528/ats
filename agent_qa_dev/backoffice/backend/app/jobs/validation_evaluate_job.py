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

                prompt = (
                    "다음 응답을 평가하세요.\n\n"
                    f"질의: {item.query_text_snapshot}\n\n"
                    f"기대 결과: {item.expected_result_snapshot}\n\n"
                    f"응답(raw JSON): {(item.raw_json or '')[:max_chars]}\n\n"
                    f"평가 기준(JSON): {criteria_text}\n\n"
                    "반드시 JSON으로 답하세요.\n"
                    '{"metric_scores": {"정확성": 1~5}, "total_score": 1~5, "comment": "평가 근거"}'
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
                    comment = ""
                    if isinstance(result, dict):
                        if isinstance(result.get("metric_scores"), dict):
                            metric_scores = result.get("metric_scores") or {}
                        elif isinstance(result.get("score"), (int, float)):
                            metric_scores = {"overall": float(result["score"])}
                        if isinstance(result.get("total_score"), (int, float)):
                            total_score = float(result["total_score"])
                        elif isinstance(result.get("score"), (int, float)):
                            total_score = float(result["score"])
                        comment = str(result.get("comment") or result.get("reason") or "")

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
