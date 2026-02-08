"""
Streamlit 채팅 UX를 위한 로컬 JSONL 저장소이다.

목표:
- 대화방(conversation) 단위로 메시지 목록을 JSONL로 영속화한다.
- Streamlit session_state와 쉽게 동기화할 수 있는 최소 API를 제공한다.

저장 포맷(JSONL, 1 line = 1 record):
{
  "type": "message",
  "conversation_id": "20251226-120102-abcdef",
  "role": "user" | "assistant" | "system",
  "content": "...",
  "ts": 1735200000.123,
  "meta": { ... optional ... }
}

{
  "type": "summary",
  "conversation_id": "...",
  "content": "...",
  "ts": ...,
  "meta": { ... optional ... }
}
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class ChatMessageRecord:
    conversation_id: str
    role: str  # "user" | "assistant" | "system"
    content: str
    ts: float
    meta: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class ChatSummaryRecord:
    conversation_id: str
    content: str
    ts: float
    meta: Optional[dict[str, Any]] = None


class JSONLChatStore:
    """
    JSONL 파일 기반 대화 저장소이다.

    - 대화방 1개 = 파일 1개
    - 파일명: {conversation_id}.jsonl
    """

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def new_conversation_id(self) -> str:
        """
        충돌 가능성이 낮은 대화방 ID를 생성한다.
        """
        # 예: 20251226-120102-<8chars>
        ts = time.strftime("%Y%m%d-%H%M%S")
        suffix = uuid.uuid4().hex[:8]
        return f"{ts}-{suffix}"

    def _path_for(self, conversation_id: str) -> Path:
        safe = conversation_id.replace("/", "_").replace("\\", "_").strip()
        return self.root_dir / f"{safe}.jsonl"

    def get_conversation_file_path(self, conversation_id: str) -> Path:
        """
        대화방의 JSONL 파일 경로를 반환한다. (UI 다운로드/진단용)
        """
        return self._path_for(conversation_id)

    def list_conversations(self) -> list[str]:
        """
        저장된 대화방 목록을 반환한다. (최신 수정 파일 우선)
        """
        files = sorted(
            self.root_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
            reverse=True,
        )
        return [p.stem for p in files]

    def delete_conversation(self, conversation_id: str) -> None:
        path = self._path_for(conversation_id)
        if path.exists():
            path.unlink()

    def append_message(self, record: ChatMessageRecord) -> None:
        path = self._path_for(record.conversation_id)
        line = json.dumps(
            {
                "type": "message",
                "conversation_id": record.conversation_id,
                "role": record.role,
                "content": record.content,
                "ts": record.ts,
                "meta": record.meta or None,
            },
            ensure_ascii=False,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def upsert_summary(self, record: ChatSummaryRecord) -> None:
        """
        요약은 append로 여러 번 기록될 수 있다.
        로드 시 최신 summary만 사용한다.
        """
        path = self._path_for(record.conversation_id)
        line = json.dumps(
            {
                "type": "summary",
                "conversation_id": record.conversation_id,
                "content": record.content,
                "ts": record.ts,
                "meta": record.meta or None,
            },
            ensure_ascii=False,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def load_messages(self, conversation_id: str) -> tuple[list[ChatMessageRecord], Optional[ChatSummaryRecord]]:
        """
        대화방의 모든 메시지와 최신 요약을 로드한다.

        Returns:
            (messages, latest_summary)
        """
        path = self._path_for(conversation_id)
        if not path.exists():
            return [], None

        messages: list[ChatMessageRecord] = []
        latest_summary: Optional[ChatSummaryRecord] = None

        with path.open("r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    # 파일 일부가 손상되었더라도 가능한 만큼 복구한다.
                    continue

                if not isinstance(obj, dict):
                    continue

                rec_type = obj.get("type")
                if rec_type == "message":
                    role = str(obj.get("role", "")).strip()
                    content = str(obj.get("content", "")).strip()
                    ts = float(obj.get("ts", 0.0) or 0.0)
                    meta_val = obj.get("meta")
                    meta = meta_val if isinstance(meta_val, dict) else None
                    if role and content:
                        messages.append(
                            ChatMessageRecord(
                                conversation_id=conversation_id,
                                role=role,
                                content=content,
                                ts=ts,
                                meta=meta,
                            )
                        )
                elif rec_type == "summary":
                    content = str(obj.get("content", "")).strip()
                    ts = float(obj.get("ts", 0.0) or 0.0)
                    meta_val = obj.get("meta")
                    meta = meta_val if isinstance(meta_val, dict) else None
                    if content:
                        latest_summary = ChatSummaryRecord(
                            conversation_id=conversation_id,
                            content=content,
                            ts=ts,
                            meta=meta,
                        )

        return messages, latest_summary


