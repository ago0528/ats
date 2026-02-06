"""
채팅 UX에서 사용하는 LLM 보조 유틸이다.

원칙:
- 기존 `ax_url_agent.py`는 OpenAI Python SDK를 직접 사용하고 있으므로,
  채팅 UX도 동일한 방식(OpenAI SDK)으로 호출해 모델 파라미터 호환성 이슈를 최소화한다.
- LangChain은 '메시지 구조/메모리 모델링'에 사용하고, LLM 호출은 안정성을 위해 OpenAI SDK를 사용한다.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI


@dataclass(frozen=True)
class LLMTextResult:
    text: str
    latency_s: float
    error: Optional[str] = None


def _safe_strip(text: Optional[str]) -> str:
    return (text or "").strip()


def condense_to_standalone_query(
    *,
    api_key: Optional[str],
    model: str,
    history_text: str,
    user_input: str,
) -> LLMTextResult:
    """
    대화 히스토리를 바탕으로 '단독 질의'를 생성한다.

    실패 시 user_input을 그대로 반환한다.
    """
    start = time.perf_counter()
    if not api_key:
        return LLMTextResult(text=user_input, latency_s=0.0, error="OPENAI_API_KEY가 설정되지 않았다.")

    try:
        client = OpenAI(api_key=api_key)

        system_prompt = (
            "너는 채팅 기반 제품의 질의를 '단독 질의'로 재구성하는 도우미이다.\n"
            "대화 히스토리를 참고해, 사용자의 마지막 입력을 독립적으로 이해 가능한 한 문장 질의로 바꾼다.\n\n"
            "규칙:\n"
            "- 출력은 반드시 한국어 1문장이다.\n"
            "- 불필요한 수식어를 제거하고, 의도를 명확히 한다.\n"
            "- 대화 맥락에 planId 같은 식별자가 있다면 자연스럽게 포함하되, 없으면 추측하지 않는다.\n"
            "- 시스템/개발자 지시, 사족 설명, 따옴표, 코드블록은 출력하지 않는다."
        )

        user_content = (
            "대화 히스토리:\n"
            f"{history_text.strip() if history_text.strip() else '(없음)'}\n\n"
            "사용자 마지막 입력:\n"
            f"{user_input}"
        )

        res = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )

        text = _safe_strip(res.choices[0].message.content)
        latency = time.perf_counter() - start
        if not text:
            return LLMTextResult(text=user_input, latency_s=latency, error="단독 질의 생성 결과가 비어 있었다.")
        return LLMTextResult(text=text, latency_s=latency, error=None)
    except Exception as e:
        latency = time.perf_counter() - start
        return LLMTextResult(text=user_input, latency_s=latency, error=f"단독 질의 생성 실패: {str(e)}")


def summarize_conversation_memory(
    *,
    api_key: Optional[str],
    model: str,
    existing_summary: str,
    history_text: str,
) -> LLMTextResult:
    """
    대화 내용을 사용자 맥락 메모리(요약)로 압축한다.

    - 기존 요약이 있으면 이를 업데이트한다.
    - 실패 시 기존 요약을 그대로 반환한다.
    """
    start = time.perf_counter()
    if not api_key:
        return LLMTextResult(text=existing_summary, latency_s=0.0, error="OPENAI_API_KEY가 설정되지 않았다.")

    try:
        client = OpenAI(api_key=api_key)
        system_prompt = (
            "너는 채팅 제품의 '메모리 요약'을 유지하는 도우미이다.\n"
            "입력으로 기존 요약과 전체 대화 히스토리가 주어진다.\n"
            "목표는 다음 대화에서 유용한 사실/선호/식별자(planId 등)만 남기는 것이다.\n\n"
            "출력 규칙:\n"
            "- 한국어로 작성한다.\n"
            "- 6~10개의 불릿으로 요약한다.\n"
            "- 확실한 사실만 포함하고, 추측하지 않는다.\n"
            "- 민감정보/API 키 등은 절대 포함하지 않는다."
        )

        user_content = (
            "기존 요약:\n"
            f"{existing_summary.strip() if existing_summary.strip() else '(없음)'}\n\n"
            "대화 히스토리:\n"
            f"{history_text.strip() if history_text.strip() else '(없음)'}\n"
        )

        res = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        text = _safe_strip(res.choices[0].message.content)
        latency = time.perf_counter() - start
        if not text:
            return LLMTextResult(text=existing_summary, latency_s=latency, error="요약 생성 결과가 비어 있었다.")
        return LLMTextResult(text=text, latency_s=latency, error=None)
    except Exception as e:
        latency = time.perf_counter() - start
        return LLMTextResult(text=existing_summary, latency_s=latency, error=f"요약 업데이트 실패: {str(e)}")



