"""
LangChain 메시지 타입을 활용하여 대화 히스토리/메모리 문자열을 구성한다.

중요:
- `AXNavigationPipeline.recommend()`는 `conversation_history: Optional[str]`만 받으므로
  최종적으로는 사람이 읽기 쉬운 텍스트 형태로 직렬화한다.
- LangChain은 메시지 구조를 명확히 하고(역할 구분), 추후 체인 확장 여지를 만든다.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from chat_storage_jsonl import ChatMessageRecord, ChatSummaryRecord


def to_langchain_messages(records: list[ChatMessageRecord]) -> list[BaseMessage]:
    """
    JSONL 레코드를 LangChain 메시지 객체로 변환한다.
    """
    messages: list[BaseMessage] = []
    for r in records:
        role = (r.role or "").strip().lower()
        if role == "user":
            messages.append(HumanMessage(content=r.content))
        elif role == "assistant":
            messages.append(AIMessage(content=r.content))
        elif role == "system":
            messages.append(SystemMessage(content=r.content))
        else:
            # 알 수 없는 role은 시스템 메시지로 보정한다.
            messages.append(SystemMessage(content=f"[role={r.role}] {r.content}"))
    return messages


def _render_one(role: str, content: str) -> str:
    role = role.strip().lower()
    if role == "user":
        prefix = "User"
    elif role == "assistant":
        prefix = "Assistant"
    elif role == "system":
        prefix = "System"
    else:
        prefix = role or "Unknown"
    return f"{prefix}: {content}"


def build_conversation_history_text(
    *,
    messages: list[ChatMessageRecord],
    summary: Optional[ChatSummaryRecord],
    max_messages: int = 12,
    include_system: bool = False,
) -> str:
    """
    Orchestrator에 전달할 conversation_history 텍스트를 구성한다.

    - summary가 있으면 상단에 붙인다.
    - 최근 max_messages개 메시지를 role prefix와 함께 직렬화한다.
    """
    lines: list[str] = []

    if summary and summary.content.strip():
        lines.append("대화 요약:")
        lines.append(summary.content.strip())
        lines.append("")  # blank line

    # 최근 메시지로 제한 (대화 맥락은 최신이 가장 중요하다)
    sliced = messages[-max_messages:] if max_messages > 0 else messages
    for m in sliced:
        if not include_system and (m.role or "").strip().lower() == "system":
            continue
        lines.append(_render_one(m.role, m.content))

    return "\n".join(lines).strip()


def build_orchestrator_history_text(
    *,
    messages: list[ChatMessageRecord],
    summary: Optional[ChatSummaryRecord],
    max_messages: int = 18,
    include_system: bool = False,
) -> str:
    """
    Orchestrator 라우팅에 적합한 형태로 conversation_history를 구성한다.

    설계 의도:
    - 사용자 발화는 그대로 전달한다.
    - 어시스턴트 메시지는 '본문(content)'가 길거나 설명형일 수 있으므로 그대로 전달하면
      "방법/가이드/이 뭐야" 같은 패턴이 히스토리에 축적되어 WIKI로 편향될 수 있다.
    - 따라서 어시스턴트는 "무슨 결정을 내렸는지"만 메타데이터로 축약하여 전달한다.
      (예: 선택된 agent_id, url, matched_name, reason)
    """
    lines: list[str] = []

    if summary and summary.content.strip():
        lines.append("대화 요약:")
        lines.append(summary.content.strip())
        lines.append("")

    sliced = messages[-max_messages:] if max_messages > 0 else messages
    for m in sliced:
        role = (m.role or "").strip().lower()
        if not include_system and role == "system":
            continue

        if role == "user":
            lines.append(_render_one("user", m.content))
            continue

        if role == "assistant":
            meta = m.meta if isinstance(m.meta, dict) else {}
            selected_agent_id = meta.get("selected_agent_id")
            url = meta.get("url")
            matched_name = meta.get("matched_name")
            reason_orch = None
            reason = meta.get("reason")
            if isinstance(reason, dict):
                reason_orch = reason.get("orchestrator")

            # 가능한 한 '결정'만 남긴다. 답변 본문은 제외한다.
            parts: list[str] = []
            if selected_agent_id:
                parts.append(f"selected_agent_id={selected_agent_id}")
            if matched_name:
                parts.append(f"matched_name={matched_name}")
            if url:
                parts.append(f"url={url}")
            if reason_orch:
                parts.append(f"orch_reason={reason_orch}")

            if parts:
                lines.append(f"AssistantDecision: {', '.join(str(p) for p in parts)}")
            else:
                # 메타가 없는 과거 기록 호환: 길이를 제한하여 편향을 최소화한다.
                short = (m.content or "").strip()
                if len(short) > 120:
                    short = short[:120] + "..."
                lines.append(_render_one("assistant", short))
            continue

        # 기타 role은 안전하게 포함
        lines.append(_render_one(m.role, m.content))

    return "\n".join(lines).strip()


def safe_meta_dict(value: Any) -> Optional[dict[str, Any]]:
    """
    Streamlit 표시를 위해 meta를 안전하게 dict로 정규화한다.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    try:
        if hasattr(value, "__dict__"):
            return dict(value.__dict__)
    except Exception:
        return None
    return None


def dataclass_to_dict(obj: Any) -> dict[str, Any]:
    """
    dataclass 또는 일반 객체를 dict로 변환한다.
    """
    try:
        return asdict(obj)  # type: ignore[arg-type]
    except Exception:
        if hasattr(obj, "__dict__"):
            return dict(obj.__dict__)
    return {"value": str(obj)}



