from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import Environment
from app.models.validation_setting import ValidationSetting


DEFAULT_VALIDATION_SETTINGS = {
    "repeat_in_conversation_default": 1,
    "conversation_room_count_default": 1,
    "agent_parallel_calls_default": 3,
    "timeout_ms_default": 120000,
    "test_model_default": "gpt-5.2",
    "eval_model_default": "gpt-5.2",
    "pagination_page_size_limit_default": 100,
}


class ValidationSettingsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, environment: Environment) -> Optional[ValidationSetting]:
        return self.db.query(ValidationSetting).filter(ValidationSetting.environment == environment).first()

    def get_or_create(self, environment: Environment) -> ValidationSetting:
        setting = self.get(environment)
        if setting is not None:
            return setting
        setting = ValidationSetting(environment=environment, **DEFAULT_VALIDATION_SETTINGS)
        self.db.add(setting)
        self.db.flush()
        return setting

    def update(
        self,
        environment: Environment,
        *,
        repeat_in_conversation_default: Optional[int] = None,
        conversation_room_count_default: Optional[int] = None,
        agent_parallel_calls_default: Optional[int] = None,
        timeout_ms_default: Optional[int] = None,
        test_model_default: Optional[str] = None,
        eval_model_default: Optional[str] = None,
        pagination_page_size_limit_default: Optional[int] = None,
    ) -> ValidationSetting:
        setting = self.get_or_create(environment)

        if repeat_in_conversation_default is not None:
            setting.repeat_in_conversation_default = max(1, int(repeat_in_conversation_default))
        if conversation_room_count_default is not None:
            setting.conversation_room_count_default = max(1, int(conversation_room_count_default))
        if agent_parallel_calls_default is not None:
            setting.agent_parallel_calls_default = max(1, int(agent_parallel_calls_default))
        if timeout_ms_default is not None:
            setting.timeout_ms_default = max(1000, int(timeout_ms_default))
        if test_model_default is not None:
            setting.test_model_default = test_model_default.strip() or setting.test_model_default
        if eval_model_default is not None:
            setting.eval_model_default = eval_model_default.strip() or setting.eval_model_default
        if pagination_page_size_limit_default is not None:
            setting.pagination_page_size_limit_default = max(50, int(pagination_page_size_limit_default))
        self.db.flush()
        return setting

    def ensure_all_environments(self) -> None:
        for env in Environment:
            self.get_or_create(env)
        self.db.flush()
