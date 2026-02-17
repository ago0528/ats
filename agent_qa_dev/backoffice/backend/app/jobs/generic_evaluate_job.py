from __future__ import annotations

import asyncio
import json
from typing import Optional

import aiohttp

from app.adapters.openai_judge_adapter import OpenAIJudgeAdapter
from app.core.db import SessionLocal
from app.models.generic_run_row import GenericRunRow
from app.services.logic_check import run_logic_check


async def evaluate_generic_run(
    run_id: str,
    openai_key: Optional[str],
    openai_model: str,
    max_chars: int,
    max_parallel: int,
):
    db = SessionLocal()
    try:
        rows = list(db.query(GenericRunRow).filter(GenericRunRow.run_id == run_id).order_by(GenericRunRow.ordinal).all())

        for row in rows:
            if row.field_path and row.expected_value:
                row.logic_result = run_logic_check(row.raw_json or "", row.field_path, row.expected_value)
            else:
                row.logic_result = "SKIPPED_NO_CRITERIA"
        db.commit()

        targets = [r for r in rows if r.llm_criteria and not r.error]
        if not targets:
            for row in rows:
                if not row.llm_criteria:
                    row.llm_eval_status = "SKIPPED_NO_CRITERIA"
            db.commit()
            return

        if not openai_key:
            for row in targets:
                row.llm_eval_status = "SKIPPED_NO_KEY"
            db.commit()
            return

        adapter = OpenAIJudgeAdapter()
        sem = asyncio.Semaphore(max(1, max_parallel))
        timeout = aiohttp.ClientTimeout(total=120)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async def _judge_one(target: GenericRunRow) -> None:
                async with sem:
                    prompt = (
                        "다음 질의에 대한 에이전트 응답을 평가하세요.\n\n"
                        f"질의: {target.query}\n\n"
                        f"응답(raw JSON): {(target.raw_json or '')[:max_chars]}\n\n"
                        f"평가 기준: {target.llm_criteria}\n\n"
                        "평가 결과를 JSON으로 출력하세요:\n"
                        '{"score": 0-5, "passed": true/false, "reason": "평가 사유"}'
                    )
                    try:
                        result, _usage, err = await adapter.judge(session, openai_key, openai_model, prompt)
                        if result is not None:
                            target.llm_eval_json = json.dumps(result, ensure_ascii=False)
                            target.llm_eval_status = "DONE"
                        else:
                            target.llm_eval_status = f"FAILED:{err}"
                    except Exception as e:  # defensive: keep row-level progress for others
                        target.llm_eval_status = f"FAILED:{e}"

            await asyncio.gather(*[_judge_one(r) for r in targets])
            db.commit()
    finally:
        db.close()
