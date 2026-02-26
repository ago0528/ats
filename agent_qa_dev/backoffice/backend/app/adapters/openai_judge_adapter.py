from __future__ import annotations

from app.lib.aqb_openai_judge import openai_judge_with_retry


class OpenAIJudgeAdapter:
    async def judge(
        self,
        session,
        api_key: str,
        model: str,
        prompt: str,
        *,
        response_schema: dict | None = None,
        schema_name: str = "judge_output",
        strict_schema: bool = True,
    ):
        return await openai_judge_with_retry(
            session,
            api_key,
            model,
            prompt,
            response_schema=response_schema,
            schema_name=schema_name,
            strict_schema=strict_schema,
        )
