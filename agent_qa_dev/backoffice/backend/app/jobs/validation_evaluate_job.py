from __future__ import annotations

import asyncio
import json
from typing import Optional

import aiohttp

from app.adapters.openai_judge_adapter import OpenAIJudgeAdapter
from app.core.db import SessionLocal
from app.repositories.validation_runs import ValidationRunRepository
from app.services.logic_check import run_logic_check


async def evaluate_validation_run(
    run_id: str,
    openai_key: Optional[str],
    openai_model: str,
    max_chars: int,
    max_parallel: int,
):
    db = SessionLocal()
    repo = ValidationRunRepository(db)
    try:
        run_items = repo.list_items(run_id, limit=100000)
        if not run_items:
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
    finally:
        db.close()
