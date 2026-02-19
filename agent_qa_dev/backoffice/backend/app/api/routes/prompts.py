from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.adapters.prompt_api_adapter import PromptApiAdapter
from app.core.db import get_db
from app.core.environment import get_env_config, to_ats_environment
from app.core.enums import Environment
from app.models.prompt_audit_log import PromptAuditLog
from app.models.prompt_snapshot import PromptSnapshot

router = APIRouter(tags=["prompts"])


class PromptUpdateRequest(BaseModel):
    prompt: str


def _add_audit_log(
    db: Session,
    environment: Environment,
    worker_type: str,
    action: str,
    before: Optional[str],
    after: Optional[str],
    actor: str,
) -> None:
    db.add(
        PromptAuditLog(
            environment=environment,
            worker_type=worker_type,
            action=action,
            before_len=len(before or ""),
            after_len=len(after or ""),
            actor=actor,
        )
    )


def _resolve_ats_current(before: Optional[str], after: Optional[str]) -> str:
    return after or before or ""


def _find_snapshot(db: Session, environment: Environment, worker_type: str) -> Optional[PromptSnapshot]:
    return (
        db.query(PromptSnapshot)
        .filter(
            PromptSnapshot.environment == environment,
            PromptSnapshot.worker_type == worker_type,
        )
        .one_or_none()
    )


def _upsert_snapshot_for_get(
    db: Session,
    environment: Environment,
    worker_type: str,
    ats_current: str,
    actor: str,
) -> PromptSnapshot:
    snapshot = _find_snapshot(db, environment, worker_type)
    if snapshot is None:
        snapshot = PromptSnapshot(
            environment=environment,
            worker_type=worker_type,
            current_prompt=ats_current,
            previous_prompt="",
            actor=actor,
        )
        db.add(snapshot)
        return snapshot

    if ats_current != snapshot.current_prompt:
        snapshot.previous_prompt = snapshot.current_prompt or ""
        snapshot.current_prompt = ats_current
        snapshot.actor = actor

    return snapshot


def _upsert_snapshot_for_mutation(
    db: Session,
    environment: Environment,
    worker_type: str,
    ats_current: str,
    prompt_before: str,
    actor: str,
) -> PromptSnapshot:
    snapshot = _find_snapshot(db, environment, worker_type)
    if snapshot is None:
        snapshot = PromptSnapshot(
            environment=environment,
            worker_type=worker_type,
            current_prompt=ats_current,
            previous_prompt=prompt_before,
            actor=actor,
        )
        db.add(snapshot)
        return snapshot

    snapshot.previous_prompt = prompt_before or snapshot.current_prompt or ""
    snapshot.current_prompt = ats_current
    snapshot.actor = actor
    return snapshot


@router.get("/prompts/workers")
def list_workers():
    return {"workers": PromptApiAdapter.workers()}


@router.get("/prompts/{environment}/{worker_type}")
def get_prompt(
    environment: Environment,
    worker_type: str,
    bearer: Optional[str] = Header(default=None),
    cms: Optional[str] = Header(default=None),
    mrs: Optional[str] = Header(default=None),
    x_actor: Optional[str] = Header(default="unknown"),
    db: Session = Depends(get_db),
):
    cfg = get_env_config(environment)
    adapter = PromptApiAdapter(cfg.base_url, to_ats_environment(environment), bearer, cms, mrs)
    actor = x_actor or "unknown"
    try:
        result = adapter.get_prompt(worker_type)
    except Exception as e:
        raise HTTPException(500, str(e)) from e

    ats_current = _resolve_ats_current(result.before, result.after)
    snapshot = _upsert_snapshot_for_get(
        db=db,
        environment=environment,
        worker_type=worker_type,
        ats_current=ats_current,
        actor=actor,
    )
    _add_audit_log(db, environment, worker_type, "GET", result.before, result.after, actor)
    db.commit()
    return {
        "before": result.before,
        "after": result.after,
        "currentPrompt": ats_current,
        "previousPrompt": snapshot.previous_prompt or "",
    }


@router.put("/prompts/{environment}/{worker_type}")
def update_prompt(
    environment: Environment,
    worker_type: str,
    body: PromptUpdateRequest,
    bearer: Optional[str] = Header(default=None),
    cms: Optional[str] = Header(default=None),
    mrs: Optional[str] = Header(default=None),
    x_actor: Optional[str] = Header(default="unknown"),
    db: Session = Depends(get_db),
):
    cfg = get_env_config(environment)
    adapter = PromptApiAdapter(cfg.base_url, to_ats_environment(environment), bearer, cms, mrs)
    actor = x_actor or "unknown"
    try:
        result = adapter.update_prompt(worker_type, body.prompt)
    except Exception as e:
        raise HTTPException(500, str(e)) from e

    ats_current = _resolve_ats_current(result.before, result.after)
    snapshot = _upsert_snapshot_for_mutation(
        db=db,
        environment=environment,
        worker_type=worker_type,
        ats_current=ats_current,
        prompt_before=result.before or "",
        actor=actor,
    )
    _add_audit_log(db, environment, worker_type, "UPDATE", result.before, result.after, actor)
    db.commit()
    return {
        "before": result.before,
        "after": result.after,
        "currentPrompt": ats_current,
        "previousPrompt": snapshot.previous_prompt or "",
    }


@router.put("/prompts/{environment}/{worker_type}/reset")
def reset_prompt(
    environment: Environment,
    worker_type: str,
    bearer: Optional[str] = Header(default=None),
    cms: Optional[str] = Header(default=None),
    mrs: Optional[str] = Header(default=None),
    x_actor: Optional[str] = Header(default="unknown"),
    db: Session = Depends(get_db),
):
    cfg = get_env_config(environment)
    adapter = PromptApiAdapter(cfg.base_url, to_ats_environment(environment), bearer, cms, mrs)
    actor = x_actor or "unknown"
    try:
        result = adapter.reset_prompt(worker_type)
    except Exception as e:
        raise HTTPException(500, str(e)) from e

    ats_current = _resolve_ats_current(result.before, result.after)
    snapshot = _upsert_snapshot_for_mutation(
        db=db,
        environment=environment,
        worker_type=worker_type,
        ats_current=ats_current,
        prompt_before=result.before or "",
        actor=actor,
    )
    _add_audit_log(db, environment, worker_type, "RESET", result.before, result.after, actor)
    db.commit()
    return {
        "before": result.before,
        "after": result.after,
        "currentPrompt": ats_current,
        "previousPrompt": snapshot.previous_prompt or "",
    }
