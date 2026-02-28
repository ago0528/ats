from __future__ import annotations

import json
import datetime as dt
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.enums import Environment
from app.repositories.validation_queries import ValidationQueryRepository
from app.repositories.validation_query_groups import ValidationQueryGroupRepository
from app.repositories.validation_runs import ValidationRunRepository
from app.repositories.validation_settings import ValidationSettingsRepository
from app.repositories.validation_test_sets import ValidationTestSetRepository

router = APIRouter(tags=["validation-test-sets"])
QUERY_SELECTION_LIMIT = 5000
DEFAULT_TEST_SET_AGENT_ID = "ORCHESTRATOR_WORKER_V3"
NORMALIZED_TEST_SET_AGENT_ID = "ORCHESTRATOR_ASSISTANT"


def _normalize_agent_mode_value(value: Optional[str]) -> str:
    normalized = (value or "").strip()
    if not normalized or normalized == DEFAULT_TEST_SET_AGENT_ID:
        return NORMALIZED_TEST_SET_AGENT_ID
    return normalized


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


def _parse_context_value(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}
        try:
            payload = json.loads(text)
        except Exception:
            return {}
        if isinstance(payload, dict):
            return payload
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


def _normalize_values(items: list[str]) -> list[str]:
    return [str(item).strip() for item in items if str(item).strip()]


def _resolve_query_ids_from_selection(
    query_repo: ValidationQueryRepository,
    selection: "ValidationTestSetQuerySelection",
) -> list[str]:
    if selection.mode == "ids":
        resolved_query_ids = _validate_query_ids(query_repo, selection.queryIds)
        excluded_ids = set(_normalize_values(selection.excludedQueryIds))
        filtered_query_ids = [query_id for query_id in resolved_query_ids if query_id not in excluded_ids]
        if not filtered_query_ids:
            raise HTTPException(status_code=400, detail="No queries matched selection")
        return filtered_query_ids

    if selection.filter is None:
        raise HTTPException(status_code=400, detail="querySelection.filter is required when mode is 'filtered'")

    categories = _normalize_values(selection.filter.category)
    group_ids = _normalize_values(selection.filter.groupId)
    excluded_ids = _normalize_values(selection.excludedQueryIds)
    query_text = str(selection.filter.q or "").strip()

    resolved_query_ids = query_repo.list_ids(
        q=query_text or None,
        categories=categories or None,
        group_ids=group_ids or None,
        excluded_ids=excluded_ids or None,
        limit=QUERY_SELECTION_LIMIT + 1,
    )
    if len(resolved_query_ids) > QUERY_SELECTION_LIMIT:
        raise HTTPException(status_code=400, detail=f"Selected queries exceed limit ({QUERY_SELECTION_LIMIT})")
    if not resolved_query_ids:
        raise HTTPException(status_code=400, detail="No queries matched selection")
    return resolved_query_ids


def _resolve_query_ids_for_request(
    query_repo: ValidationQueryRepository,
    *,
    query_ids: list[str],
    query_selection: Optional["ValidationTestSetQuerySelection"],
    allow_empty: bool,
) -> list[str]:
    has_query_ids = len(_normalize_values(query_ids)) > 0
    if has_query_ids and query_selection is not None:
        raise HTTPException(status_code=400, detail="Use either queryIds or querySelection")

    resolved_query_ids: list[str]
    if query_selection is not None:
        resolved_query_ids = _resolve_query_ids_from_selection(query_repo, query_selection)
    else:
        resolved_query_ids = _validate_query_ids(query_repo, query_ids)

    if not allow_empty and not resolved_query_ids:
        raise HTTPException(status_code=400, detail="No queries selected")
    return resolved_query_ids


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


def _coalesce_text(value: Any, default: str) -> tuple[str, bool]:
    normalized = ("" if value is None else str(value)).strip()
    if normalized:
        return normalized, False
    return ("" if default is None else str(default)), True


def _coalesce_int(value: Any, default: int, min_value: int = 1) -> tuple[int, bool]:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        parsed = 0
    if parsed >= min_value:
        return parsed, False
    return int(default), True


def _normalize_test_set_config(
    config: dict[str, Any],
    *,
    test_model_default: str,
    eval_model_default: str,
    repeat_in_conversation_default: int,
    conversation_room_count_default: int,
    agent_parallel_calls_default: int,
    timeout_ms_default: int,
) -> tuple[dict[str, Any], bool]:
    normalized = dict(config or {})
    changed = False

    normalized["agentId"], changed_agent = _coalesce_text(
        normalized.get("agentId"),
        NORMALIZED_TEST_SET_AGENT_ID,
    )
    changed |= changed_agent
    normalized_agent_id = _normalize_agent_mode_value(normalized["agentId"])
    if normalized_agent_id != normalized["agentId"]:
        normalized["agentId"] = normalized_agent_id
        changed |= True

    normalized["testModel"], changed_model = _coalesce_text(normalized.get("testModel"), test_model_default)
    changed |= changed_model

    normalized["evalModel"], changed_eval = _coalesce_text(normalized.get("evalModel"), eval_model_default)
    changed |= changed_eval

    normalized["context"] = _parse_context_value(normalized.get("context"))

    normalized["repeatInConversation"], changed_repeat = _coalesce_int(
        normalized.get("repeatInConversation"),
        repeat_in_conversation_default,
    )
    changed |= changed_repeat

    normalized["conversationRoomCount"], changed_room = _coalesce_int(
        normalized.get("conversationRoomCount"),
        conversation_room_count_default,
    )
    changed |= changed_room

    normalized["agentParallelCalls"], changed_parallel = _coalesce_int(
        normalized.get("agentParallelCalls"),
        agent_parallel_calls_default,
    )
    changed |= changed_parallel

    normalized["timeoutMs"], changed_timeout = _coalesce_int(
        normalized.get("timeoutMs"),
        timeout_ms_default,
        min_value=1000,
    )
    changed |= changed_timeout

    return normalized, changed


class ValidationTestSetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agentId: Optional[str] = None
    testModel: Optional[str] = None
    evalModel: Optional[str] = None
    context: Optional[dict[str, Any]] = None
    repeatInConversation: Optional[int] = None
    conversationRoomCount: Optional[int] = None
    agentParallelCalls: Optional[int] = None
    timeoutMs: Optional[int] = None


class ValidationTestSetQuerySelectionFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str = ""
    category: list[str] = Field(default_factory=list)
    groupId: list[str] = Field(default_factory=list)


class ValidationTestSetQuerySelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["ids", "filtered"]
    queryIds: list[str] = Field(default_factory=list)
    filter: Optional[ValidationTestSetQuerySelectionFilter] = None
    excludedQueryIds: list[str] = Field(default_factory=list)


class ValidationTestSetCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str = ""
    queryIds: list[str] = Field(default_factory=list)
    querySelection: Optional[ValidationTestSetQuerySelection] = None
    config: ValidationTestSetConfig = Field(default_factory=ValidationTestSetConfig)


class ValidationTestSetUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    description: Optional[str] = None
    queryIds: Optional[list[str]] = None
    config: Optional[ValidationTestSetConfig] = None


class ValidationTestSetCloneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None


class ValidationTestSetAppendQueriesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queryIds: list[str] = Field(default_factory=list)
    querySelection: Optional[ValidationTestSetQuerySelection] = None


class ValidationTestSetRunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    environment: Environment
    name: Optional[str] = None
    context: Optional[dict[str, Any]] = None
    agentId: Optional[str] = None
    testModel: Optional[str] = None
    evalModel: Optional[str] = None
    repeatInConversation: Optional[int] = None
    conversationRoomCount: Optional[int] = None
    agentParallelCalls: Optional[int] = None
    timeoutMs: Optional[int] = None


@router.get("/validation-test-sets")
def list_validation_test_sets(
    environment: Optional[Environment] = Query(default=None),
    q: Optional[str] = Query(default=None),
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    repo = ValidationTestSetRepository(db)
    setting_repo = ValidationSettingsRepository(db)
    setting = setting_repo.get_or_create(environment) if environment is not None else None

    rows = repo.list(q=q, offset=offset, limit=limit)
    defaults_changed = False
    if setting is not None:
        for row in rows:
            config = _parse_json_text(row.config_json)
            normalized_config, has_change = _normalize_test_set_config(
                config,
                test_model_default=setting.test_model_default,
                eval_model_default=setting.eval_model_default,
                repeat_in_conversation_default=setting.repeat_in_conversation_default,
                conversation_room_count_default=setting.conversation_room_count_default,
                agent_parallel_calls_default=setting.agent_parallel_calls_default,
                timeout_ms_default=setting.timeout_ms_default,
            )
            if has_change:
                row.config_json = json.dumps(normalized_config, ensure_ascii=False)
                defaults_changed = True
    if defaults_changed:
        db.commit()

    counts = repo.count_items_by_test_set_ids([row.id for row in rows])
    return {
        "items": [repo.build_payload(row, item_count=counts.get(row.id, 0)) for row in rows],
        "total": repo.count(q=q),
    }


@router.post("/validation-test-sets")
def create_validation_test_set(body: ValidationTestSetCreateRequest, db: Session = Depends(get_db)):
    query_repo = ValidationQueryRepository(db)
    validated_query_ids = _resolve_query_ids_for_request(
        query_repo,
        query_ids=body.queryIds,
        query_selection=body.querySelection,
        allow_empty=True,
    )

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
def get_validation_test_set(
    test_set_id: str,
    environment: Optional[Environment] = Query(default=None),
    db: Session = Depends(get_db),
):
    repo = ValidationTestSetRepository(db)
    query_repo = ValidationQueryRepository(db)
    group_repo = ValidationQueryGroupRepository(db)
    setting_repo = ValidationSettingsRepository(db)

    entity = repo.get(test_set_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Test set not found")

    if environment is not None:
        setting = setting_repo.get_or_create(environment)
        config = _parse_json_text(entity.config_json)
        normalized_config, has_change = _normalize_test_set_config(
            config,
            test_model_default=setting.test_model_default,
            eval_model_default=setting.eval_model_default,
            repeat_in_conversation_default=setting.repeat_in_conversation_default,
            conversation_room_count_default=setting.conversation_room_count_default,
            agent_parallel_calls_default=setting.agent_parallel_calls_default,
            timeout_ms_default=setting.timeout_ms_default,
        )
        if has_change:
            entity.config_json = json.dumps(normalized_config, ensure_ascii=False)
            db.commit()

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


@router.post("/validation-test-sets/{test_set_id}/append-queries")
def append_queries_to_validation_test_set(
    test_set_id: str,
    body: ValidationTestSetAppendQueriesRequest,
    db: Session = Depends(get_db),
):
    repo = ValidationTestSetRepository(db)
    if repo.get(test_set_id) is None:
        raise HTTPException(status_code=404, detail="Test set not found")

    query_repo = ValidationQueryRepository(db)
    resolved_query_ids = _resolve_query_ids_for_request(
        query_repo,
        query_ids=body.queryIds,
        query_selection=body.querySelection,
        allow_empty=False,
    )

    added_count, skipped_count = repo.append_items(test_set_id, resolved_query_ids)
    db.commit()
    item_count = repo.count_items_by_test_set_ids([test_set_id]).get(test_set_id, 0)
    return {
        "testSetId": test_set_id,
        "requestedCount": len(resolved_query_ids),
        "addedCount": added_count,
        "skippedCount": skipped_count,
        "itemCount": item_count,
    }


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
    setting_repo = ValidationSettingsRepository(db)

    test_set = test_set_repo.get(test_set_id)
    if test_set is None:
        raise HTTPException(status_code=404, detail="Test set not found")

    setting = setting_repo.get_or_create(body.environment)
    config = _parse_json_text(test_set.config_json)
    normalized_config, has_change = _normalize_test_set_config(
        config,
        test_model_default=setting.test_model_default,
        eval_model_default=setting.eval_model_default,
        repeat_in_conversation_default=setting.repeat_in_conversation_default,
        conversation_room_count_default=setting.conversation_room_count_default,
        agent_parallel_calls_default=setting.agent_parallel_calls_default,
        timeout_ms_default=setting.timeout_ms_default,
    )
    if has_change:
        test_set.config_json = json.dumps(normalized_config, ensure_ascii=False)
        config = normalized_config

    agent_id = _normalize_agent_mode_value(
        _resolve_config_value(
            override=body.agentId,
            config=config,
            key="agentId",
            default=DEFAULT_TEST_SET_AGENT_ID,
        ),
    )
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

    run_name = (body.name or "").strip()
    if not run_name:
        run_name = f"{test_set.name} ({dt.datetime.now().strftime('%Y-%m-%d %H:%M')})"
    context = _parse_context_value(
        _resolve_config_value(
            override=body.context,
            config=config,
            key="context",
            default=None,
        )
    )
    run_options = {"source": "validation-test-set", "targetAssistant": agent_id}
    if context:
        run_options["context"] = context

    run = run_repo.create_run(
        environment=body.environment,
        name=run_name,
        agent_id=agent_id,
        test_model=test_model,
        eval_model=eval_model,
        repeat_in_conversation=repeat_in_conversation,
        conversation_room_count=conversation_room_count,
        agent_parallel_calls=agent_parallel_calls,
        timeout_ms=timeout_ms,
        options=run_options,
        test_set_id=test_set_id,
    )

    items_payload: list[dict[str, Any]] = []
    ordinal = 1
    for room_index in range(1, int(conversation_room_count) + 1):
        for repeat_index in range(1, int(repeat_in_conversation) + 1):
            for query in ordered_queries:
                items_payload.append(
                    {
                        "ordinal": ordinal,
                        "query_id": query.id,
                        "query_text_snapshot": query.query_text,
                        "expected_result_snapshot": query.expected_result,
                        "category_snapshot": query.category,
                        "conversation_room_index": room_index,
                        "repeat_index": repeat_index,
                    },
                )
                ordinal += 1

    run_repo.add_items(run.id, items_payload)
    db.commit()
    return run_repo.build_run_payload(run)
