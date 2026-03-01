from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.validation_eval_prompt_audit_log import ValidationEvalPromptAuditLog
from app.models.validation_eval_prompt_config import ValidationEvalPromptConfig

VALIDATION_SCORING_PROMPT_KEY = "validation_scoring"
DEFAULT_SCORING_PROMPT_VERSION_LABEL = "validation-scoring-default.v1"
_VERSION_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_DEFAULT_PROMPT_PATH = Path(__file__).resolve().parents[1] / "evaluation" / "validation_scoring_default_prompt.md"


@dataclass
class EvaluationPromptSnapshot:
    prompt_key: str
    current_prompt: str
    previous_prompt: str
    current_version_label: str
    previous_version_label: str
    updated_by: str


class ValidationEvalPromptConfigRepository:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def is_valid_version_label(value: str) -> bool:
        text = str(value or "").strip()
        if not text:
            return False
        return _VERSION_LABEL_PATTERN.fullmatch(text) is not None

    @staticmethod
    def normalize_prompt_text(value: str) -> str:
        return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()

    def _record_audit(
        self,
        *,
        prompt_key: str,
        action: str,
        before_version_label: str,
        after_version_label: str,
        before_prompt: str,
        after_prompt: str,
        actor: str,
    ) -> None:
        self.db.add(
            ValidationEvalPromptAuditLog(
                prompt_key=prompt_key,
                action=action,
                before_version_label=str(before_version_label or ""),
                after_version_label=str(after_version_label or ""),
                before_len=len(before_prompt or ""),
                after_len=len(after_prompt or ""),
                actor=str(actor or "system"),
            )
        )

    @staticmethod
    def load_default_prompt() -> str:
        text = _DEFAULT_PROMPT_PATH.read_text(encoding="utf-8")
        normalized = ValidationEvalPromptConfigRepository.normalize_prompt_text(text)
        if not normalized:
            raise ValueError("validation_scoring_default_prompt.md is empty")
        return normalized

    def _find_config(self, prompt_key: str) -> ValidationEvalPromptConfig | None:
        return (
            self.db.query(ValidationEvalPromptConfig)
            .filter(ValidationEvalPromptConfig.prompt_key == prompt_key)
            .one_or_none()
        )

    def get_or_create_scoring_prompt(self, *, actor: str = "system") -> ValidationEvalPromptConfig:
        prompt_key = VALIDATION_SCORING_PROMPT_KEY
        entity = self._find_config(prompt_key)
        if entity is not None:
            return entity

        default_prompt = self.load_default_prompt()
        entity = ValidationEvalPromptConfig(
            prompt_key=prompt_key,
            current_prompt=default_prompt,
            previous_prompt="",
            current_version_label=DEFAULT_SCORING_PROMPT_VERSION_LABEL,
            previous_version_label="",
            updated_by=str(actor or "system"),
        )
        self.db.add(entity)
        self.db.flush()
        self._record_audit(
            prompt_key=prompt_key,
            action="INIT",
            before_version_label="",
            after_version_label=entity.current_version_label,
            before_prompt="",
            after_prompt=entity.current_prompt,
            actor=entity.updated_by,
        )
        self.db.flush()
        return entity

    @staticmethod
    def to_snapshot(entity: ValidationEvalPromptConfig) -> EvaluationPromptSnapshot:
        return EvaluationPromptSnapshot(
            prompt_key=str(entity.prompt_key or ""),
            current_prompt=str(entity.current_prompt or ""),
            previous_prompt=str(entity.previous_prompt or ""),
            current_version_label=str(entity.current_version_label or ""),
            previous_version_label=str(entity.previous_version_label or ""),
            updated_by=str(entity.updated_by or "system"),
        )

    def update_scoring_prompt(
        self,
        *,
        prompt: str,
        version_label: str,
        actor: str,
    ) -> ValidationEvalPromptConfig:
        entity = self.get_or_create_scoring_prompt(actor=actor)
        normalized_prompt = self.normalize_prompt_text(prompt)
        if not normalized_prompt:
            raise ValueError("prompt must not be empty")
        normalized_version = str(version_label or "").strip()
        if not self.is_valid_version_label(normalized_version):
            raise ValueError("versionLabel format is invalid")

        before_prompt = str(entity.current_prompt or "")
        before_version_label = str(entity.current_version_label or "")
        entity.previous_prompt = before_prompt
        entity.previous_version_label = before_version_label
        entity.current_prompt = normalized_prompt
        entity.current_version_label = normalized_version
        entity.updated_by = str(actor or "system")
        self.db.flush()

        self._record_audit(
            prompt_key=entity.prompt_key,
            action="UPDATE",
            before_version_label=before_version_label,
            after_version_label=entity.current_version_label,
            before_prompt=before_prompt,
            after_prompt=entity.current_prompt,
            actor=entity.updated_by,
        )
        self.db.flush()
        return entity

    def revert_scoring_prompt_previous(
        self,
        *,
        version_label: str,
        actor: str,
    ) -> ValidationEvalPromptConfig:
        entity = self.get_or_create_scoring_prompt(actor=actor)
        previous_prompt = str(entity.previous_prompt or "")
        if not previous_prompt:
            raise ValueError("no previous prompt to revert")

        normalized_version = str(version_label or "").strip()
        if not self.is_valid_version_label(normalized_version):
            raise ValueError("versionLabel format is invalid")

        before_prompt = str(entity.current_prompt or "")
        before_version_label = str(entity.current_version_label or "")

        entity.current_prompt, entity.previous_prompt = entity.previous_prompt, entity.current_prompt
        entity.current_version_label, entity.previous_version_label = normalized_version, before_version_label
        entity.updated_by = str(actor or "system")
        self.db.flush()

        self._record_audit(
            prompt_key=entity.prompt_key,
            action="REVERT_PREVIOUS",
            before_version_label=before_version_label,
            after_version_label=entity.current_version_label,
            before_prompt=before_prompt,
            after_prompt=entity.current_prompt,
            actor=entity.updated_by,
        )
        self.db.flush()
        return entity

    def reset_scoring_prompt_to_default(
        self,
        *,
        version_label: str,
        actor: str,
    ) -> ValidationEvalPromptConfig:
        entity = self.get_or_create_scoring_prompt(actor=actor)
        normalized_version = str(version_label or "").strip()
        if not self.is_valid_version_label(normalized_version):
            raise ValueError("versionLabel format is invalid")

        default_prompt = self.load_default_prompt()
        before_prompt = str(entity.current_prompt or "")
        before_version_label = str(entity.current_version_label or "")

        entity.previous_prompt = before_prompt
        entity.previous_version_label = before_version_label
        entity.current_prompt = default_prompt
        entity.current_version_label = normalized_version
        entity.updated_by = str(actor or "system")
        self.db.flush()

        self._record_audit(
            prompt_key=entity.prompt_key,
            action="RESET_DEFAULT",
            before_version_label=before_version_label,
            after_version_label=entity.current_version_label,
            before_prompt=before_prompt,
            after_prompt=entity.current_prompt,
            actor=entity.updated_by,
        )
        self.db.flush()
        return entity
