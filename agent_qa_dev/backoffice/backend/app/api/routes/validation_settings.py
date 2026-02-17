from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.enums import Environment
from app.repositories.validation_settings import ValidationSettingsRepository

router = APIRouter(tags=["validation-settings"])


class ValidationSettingPatchRequest(BaseModel):
    repeatInConversationDefault: Optional[int] = None
    conversationRoomCountDefault: Optional[int] = None
    agentParallelCallsDefault: Optional[int] = None
    timeoutMsDefault: Optional[int] = None
    testModelDefault: Optional[str] = None
    evalModelDefault: Optional[str] = None


def _serialize(entity):
    return {
        "environment": entity.environment.value,
        "repeatInConversationDefault": entity.repeat_in_conversation_default,
        "conversationRoomCountDefault": entity.conversation_room_count_default,
        "agentParallelCallsDefault": entity.agent_parallel_calls_default,
        "timeoutMsDefault": entity.timeout_ms_default,
        "testModelDefault": entity.test_model_default,
        "evalModelDefault": entity.eval_model_default,
        "updatedAt": entity.updated_at,
    }


@router.get("/validation-settings/{environment}")
def get_validation_setting(environment: Environment, db: Session = Depends(get_db)):
    repo = ValidationSettingsRepository(db)
    entity = repo.get_or_create(environment)
    db.commit()
    return _serialize(entity)


@router.patch("/validation-settings/{environment}")
def update_validation_setting(environment: Environment, body: ValidationSettingPatchRequest, db: Session = Depends(get_db)):
    repo = ValidationSettingsRepository(db)
    entity = repo.update(
        environment,
        repeat_in_conversation_default=body.repeatInConversationDefault,
        conversation_room_count_default=body.conversationRoomCountDefault,
        agent_parallel_calls_default=body.agentParallelCallsDefault,
        timeout_ms_default=body.timeoutMsDefault,
        test_model_default=body.testModelDefault,
        eval_model_default=body.evalModelDefault,
    )
    db.commit()
    return _serialize(entity)
