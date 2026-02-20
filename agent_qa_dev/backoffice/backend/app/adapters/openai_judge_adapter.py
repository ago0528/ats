from __future__ import annotations

from app.lib.aqb_openai_judge import openai_judge_with_retry


class OpenAIJudgeAdapter:
    async def judge(self, session, api_key: str, model: str, prompt: str):
        return await openai_judge_with_retry(session, api_key, model, prompt)
