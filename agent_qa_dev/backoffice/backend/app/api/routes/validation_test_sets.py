from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.enums import Environment
from app.repositories.validation_queries import ValidationQueryRepository
from app.repositories.validation_query_groups import ValidationQueryGroupRepository
from app.repositories.validation_runs import ValidationRunRepository
from app.repositories.validation_settings import ValidationSettingsRepository
from app.repositories.validation_test_sets import ValidationTestSetRepository

router = APIRouter(tags=["validation-test-sets"])


def _parse_json_text(value: str) -> dict[str, Any]:
    text = (value or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return {}
    return {}


def _validate_query_ids(query_repo: ValidationQueryRepository, query_ids: list[str]) -> list[str]:
    normalized = [query_id for query_id in [str(item).strip() for item in query_ids] if query_id]
    if len(normalized) != len(set(normalized)):
        raise HTTPException(status_code=400, detail="queryIds must not contain duplicates")
    if not normalized:
        return []
    rows = query_repo.list_by_ids(normalized)
    if len(rows) != len(normalized):
        raise HTTPException(status_code=404, detail="Some queries were not found")
    return normalized


def _resolve_config_value(
    *,
    override: Optional[Any],
    config: dict[str, Any],
    key: str,
    default: Any,
) -> Any:
    if override is not None:
        return override
    if key in config and config.get(key) is not None:
        return config.get(key)
    return default


class ValidationTestSetConfig(BaseModel):
    agentId: Optional[str] = None
    testModel: Optional[str] = None
    evalModel: Optional[str] = None
    repeatInConversation: Optional[int] = None
    conversationRoomCount: Optional[int] = None
    agentParallelCalls: Optional[int] = None
    timeoutMs: Optional[int] = None


class ValidationTestSetCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    queryIds: list[str] = Field(default_factory=list)
    config: ValidationTestSetConfig = Field(default_factory=ValidationTestSetConfig)


class ValidationTestSetUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    queryIds: Optional[list[str]] = None
    config: Optional[ValidationTestSetConfig] = None


class ValidationTestSetCloneRequest(BaseModel):
    name: Optional[str] = None


class ValidationTestSetRunCreateRequest(BaseModel):
    environment: Environment
    agentId: Optional[str] = None
    testModel: Optional[str] = None
    evalModel: Optional[str] = None
    repeatInConversation: Optional[int] = None
    conversationRoomCount: Optional[int] = None
    agentParallelCalls: Optional[int] = None
    timeoutMs: Optional[int] = None


@router.get("/validation-test-sets")
def list_validation_test_sets(
    q: Optional[str] = Query(default=None),
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    repo = ValidationTestSetRepository(db)
    rows = repo.list(q=q, offset=offset, limit=limit)
    counts = repo.count_items_by_test_set_ids([row.id for row in rows])
    return {
        "items": [repo.build_payload(row, item_count=counts.get(row.id, 0)) for row in rows],
        "total": repo.count(q=q),
    }


@router.post("/validation-test-sets")
def create_validation_test_set(body: ValidationTestSetCreateRequest, db: Session = Depends(get_db)):
    query_repo = ValidationQueryRepository(db)
    validated_query_ids = _validate_query_ids(query_repo, body.queryIds)

    repo = ValidationTestSetRepository(db)
    created = repo.create(
        name=body.name,
        description=body.description,
        query_ids=validated_query_ids,
        config=body.config.model_dump(exclude_none=True),
    )
    db.commit()
    return repo.build_payload(created, item_count=len(validated_query_ids))


@router.get("/validation-test-sets/{test_set_id}")
def get_validation_test_set(test_set_id: str, db: Session = Depends(get_db)):
    repo = ValidationTestSetRepository(db)
    query_repo = ValidationQueryRepository(db)
    group_repo = ValidationQueryGroupRepository(db)
    entity = repo.get(test_set_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Test set not found")

    items = repo.list_items(test_set_id)
    query_rows = query_repo.list_by_ids([item.query_id for item in items])
    query_map = {row.id: row for row in query_rows}
    group_map = {row.id: row for row in group_repo.list(limit=100000)}
    payload = repo.build_payload(entity, item_count=len(items))
    payload["queryIds"] = [item.query_id for item in items]
    payload["items"] = [
        {
            "id": item.id,
            "queryId": item.query_id,
            "ordinal": item.ordinal,
            "queryText": query_map[item.query_id].query_text if item.query_id in query_map else "",
            "category": query_map[item.query_id].category if item.query_id in query_map else "",
            "groupId": (query_map[item.query_id].group_id if item.query_id in query_map else "") or None,
            "groupName": (
                group_map.get(query_map[item.query_id].group_id).group_name
                if item.query_id in query_map and query_map[item.query_id].group_id in group_map
                else ""
            ),
            "targetAssistant": query_map[item.query_id].target_assistant if item.query_id in query_map else "",
        }
        for item in items
    ]
    return payload


@router.patch("/validation-test-sets/{test_set_id}")
def update_validation_test_set(test_set_id: str, body: ValidationTestSetUpdateRequest, db: Session = Depends(get_db)):
    query_repo = ValidationQueryRepository(db)
    validated_query_ids: Optional[list[str]] = None
    if body.queryIds is not None:
        validated_query_ids = _validate_query_ids(query_repo, body.queryIds)

    repo = ValidationTestSetRepository(db)
    updated = repo.update(
        test_set_id,
        name=body.name,
        description=body.description,
        query_ids=validated_query_ids,
        config=(body.config.model_dump(exclude_none=True) if body.config is not None else None),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Test set not found")
    db.commit()
    item_count = len(validated_query_ids) if validated_query_ids is not None else len(repo.list_items(updated.id))
    return repo.build_payload(updated, item_count=item_count)


@router.delete("/validation-test-sets/{test_set_id}")
def delete_validation_test_set(test_set_id: str, db: Session = Depends(get_db)):
    repo = ValidationTestSetRepository(db)
    deleted = repo.delete(test_set_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Test set not found")
    db.commit()
    return {"ok": True}


@router.post("/validation-test-sets/{test_set_id}/clone")
def clone_validation_test_set(test_set_id: str, body: ValidationTestSetCloneRequest, db: Session = Depends(get_db)):
    repo = ValidationTestSetRepository(db)
    try:
        cloned = repo.clone(test_set_id, name=body.name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return repo.build_payload(cloned)


@router.post("/validation-test-sets/{test_set_id}/runs")
def create_run_from_validation_test_set(test_set_id: str, body: ValidationTestSetRunCreateRequest, db: Session = Depends(get_db)):
    test_set_repo = ValidationTestSetRepository(db)
    run_repo = ValidationRunRepository(db)
    query_group_repo = ValidationQueryGroupRepository(db)
    setting_repo = ValidationSettingsRepository(db)

    test_set = test_set_repo.get(test_set_id)
    if test_set is None:
        raise HTTPException(status_code=404, detail="Test set not found")

    setting = setting_repo.get_or_create(body.environment)
    config = _parse_json_text(test_set.config_json)

    agent_id = str(_resolve_config_value(override=body.agentId, config=config, key="agentId", default="ORCHESTRATOR_WORKER_V3")).strip() or "ORCHESTRATOR_WORKER_V3"
    test_model = str(_resolve_config_value(override=body.testModel, config=config, key="testModel", default=setting.test_model_default)).strip() or setting.test_model_default
    eval_model = str(_resolve_config_value(override=body.evalModel, config=config, key="evalModel", default=setting.eval_model_default)).strip() or setting.eval_model_default
    repeat_in_conversation = int(_resolve_config_value(
        override=body.repeatInConversation,
        config=config,
        key="repeatInConversation",
        default=setting.repeat_in_conversation_default,
    ) or setting.repeat_in_conversation_default)
    conversation_room_count = int(_resolve_config_value(
        override=body.conversationRoomCount,
        config=config,
        key="conversationRoomCount",
        default=setting.conversation_room_count_default,
    ) or setting.conversation_room_count_default)
    agent_parallel_calls = int(_resolve_config_value(
        override=body.agentParallelCalls,
        config=config,
        key="agentParallelCalls",
        default=setting.agent_parallel_calls_default,
    ) or setting.agent_parallel_calls_default)
    timeout_ms = int(_resolve_config_value(
        override=body.timeoutMs,
        config=config,
        key="timeoutMs",
        default=setting.timeout_ms_default,
    ) or setting.timeout_ms_default)

    test_set_items = test_set_repo.list_items(test_set_id)
    ordered_queries = test_set_repo.list_query_rows_for_test_set(test_set_id)
    if not ordered_queries:
        raise HTTPException(status_code=400, detail="Test set has no queries")
    if len(ordered_queries) != len(test_set_items):
        raise HTTPException(status_code=409, detail="Test set includes missing queries")

    groups = {row.id: row for row in query_group_repo.list(limit=100000)}

    run = run_repo.create_run(
        environment=body.environment,
        mode="REGISTERED",
        agent_id=agent_id,
        test_model=test_model,
        eval_model=eval_model,
        repeat_in_conversation=repeat_in_conversation,
        conversation_room_count=conversation_room_count,
        agent_parallel_calls=agent_parallel_calls,
        timeout_ms=timeout_ms,
        options={"source": "validation-test-set"},
        test_set_id=test_set_id,
    )

    items_payload: list[dict[str, Any]] = []
    ordinal = 1
    for room_index in range(1, int(conversation_room_count) + 1):
        for repeat_index in range(1, int(repeat_in_conversation) + 1):
            for query in ordered_queries:
                group_default = groups.get(query.group_id).llm_eval_criteria_default_json if query.group_id in groups else ""
                group_default_target = groups.get(query.group_id).default_target_assistant if query.group_id in groups else ""
                criteria = query.llm_eval_criteria_json or group_default or ""
                target_assistant = (query.target_assistant or "").strip() or (group_default_target or "").strip()
                items_payload.append(
                    {
                        "ordinal": ordinal,
                        "query_id": query.id,
                        "query_text_snapshot": query.query_text,
                        "expected_result_snapshot": query.expected_result,
                        "category_snapshot": query.category,
                        "applied_criteria_json": criteria,
                        "logic_field_path_snapshot": query.logic_field_path,
                        "logic_expected_value_snapshot": query.logic_expected_value,
                        "context_json_snapshot": query.context_json,
                        "target_assistant_snapshot": target_assistant,
                        "conversation_room_index": room_index,
                        "repeat_index": repeat_index,
                    },
                )
                ordinal += 1

    run_repo.add_items(run.id, items_payload)
    db.commit()
    return run_repo.build_run_payload(run)
