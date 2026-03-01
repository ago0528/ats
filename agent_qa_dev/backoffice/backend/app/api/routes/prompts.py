from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.adapters.prompt_api_adapter import PromptApiAdapter
from app.core.db import get_db
from app.core.environment import get_env_config, to_ats_environment
from app.core.enums import Environment
from app.models.prompt_audit_log import PromptAuditLog
from app.models.prompt_snapshot import PromptSnapshot
from app.repositories.validation_eval_prompt_configs import (
    EvaluationPromptSnapshot,
    ValidationEvalPromptConfigRepository,
)

router = APIRouter(tags=["prompts"])
logger = logging.getLogger(__name__)


class PromptUpdateRequest(BaseModel):
    prompt: str


class EvalPromptUpdateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    versionLabel: str = Field(
        min_length=1,
        max_length=80,
    )


class EvalPromptActionRequest(BaseModel):
    versionLabel: str = Field(
        min_length=1,
        max_length=80,
    )


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


def _serialize_eval_prompt_snapshot(entity: EvaluationPromptSnapshot, *, updated_at, updated_by: str) -> dict:
    return {
        "promptKey": entity.prompt_key,
        "currentPrompt": entity.current_prompt,
        "previousPrompt": entity.previous_prompt,
        "currentVersionLabel": entity.current_version_label,
        "previousVersionLabel": entity.previous_version_label,
        "updatedAt": updated_at,
        "updatedBy": updated_by or "system",
    }


@router.get("/prompts/workers")
def list_workers():
    return {"workers": PromptApiAdapter.workers()}


@router.get("/prompts/evaluation/scoring")
def get_evaluation_scoring_prompt(
    x_actor: Optional[str] = Header(default="system"),
    db: Session = Depends(get_db),
):
    repo = ValidationEvalPromptConfigRepository(db)
    actor = x_actor or "system"
    entity = repo.get_or_create_scoring_prompt(actor=actor)
    db.commit()
    snapshot = repo.to_snapshot(entity)
    return _serialize_eval_prompt_snapshot(
        snapshot,
        updated_at=entity.updated_at,
        updated_by=entity.updated_by,
    )


@router.patch("/prompts/evaluation/scoring")
def update_evaluation_scoring_prompt(
    body: EvalPromptUpdateRequest,
    x_actor: Optional[str] = Header(default="system"),
    db: Session = Depends(get_db),
):
    repo = ValidationEvalPromptConfigRepository(db)
    actor = x_actor or "system"
    normalized_prompt = str(body.prompt or "").strip()
    if not normalized_prompt:
        raise HTTPException(status_code=400, detail="prompt must not be empty")
    try:
        entity = repo.update_scoring_prompt(
            prompt=normalized_prompt,
            version_label=body.versionLabel,
            actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    snapshot = repo.to_snapshot(entity)
    return _serialize_eval_prompt_snapshot(
        snapshot,
        updated_at=entity.updated_at,
        updated_by=entity.updated_by,
    )


@router.post("/prompts/evaluation/scoring/revert-previous")
def revert_evaluation_scoring_prompt_previous(
    body: EvalPromptActionRequest,
    x_actor: Optional[str] = Header(default="system"),
    db: Session = Depends(get_db),
):
    repo = ValidationEvalPromptConfigRepository(db)
    actor = x_actor or "system"
    try:
        entity = repo.revert_scoring_prompt_previous(
            version_label=body.versionLabel,
            actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    snapshot = repo.to_snapshot(entity)
    return _serialize_eval_prompt_snapshot(
        snapshot,
        updated_at=entity.updated_at,
        updated_by=entity.updated_by,
    )


@router.post("/prompts/evaluation/scoring/reset-default")
def reset_evaluation_scoring_prompt_default(
    body: EvalPromptActionRequest,
    x_actor: Optional[str] = Header(default="system"),
    db: Session = Depends(get_db),
):
    repo = ValidationEvalPromptConfigRepository(db)
    actor = x_actor or "system"
    try:
        entity = repo.reset_scoring_prompt_to_default(
            version_label=body.versionLabel,
            actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    snapshot = repo.to_snapshot(entity)
    return _serialize_eval_prompt_snapshot(
        snapshot,
        updated_at=entity.updated_at,
        updated_by=entity.updated_by,
    )


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
    except Exception:
        logger.exception(
            "Failed to fetch prompt from ATS. environment=%s worker_type=%s",
            environment.value,
            worker_type,
        )
        try:
            fallback_snapshot = _find_snapshot(db, environment, worker_type)
        except Exception:
            db.rollback()
            logger.exception(
                "Failed to load fallback prompt snapshot. environment=%s worker_type=%s",
                environment.value,
                worker_type,
            )
            fallback_snapshot = None

        if fallback_snapshot is None:
            return {
                "before": "",
                "after": "",
                "currentPrompt": "",
                "previousPrompt": "",
            }

        return {
            "before": fallback_snapshot.previous_prompt or "",
            "after": fallback_snapshot.current_prompt or "",
            "currentPrompt": fallback_snapshot.current_prompt or "",
            "previousPrompt": fallback_snapshot.previous_prompt or "",
        }

    ats_current = _resolve_ats_current(result.before, result.after)
    previous_prompt = ""
    try:
        snapshot = _upsert_snapshot_for_get(
            db=db,
            environment=environment,
            worker_type=worker_type,
            ats_current=ats_current,
            actor=actor,
        )
        _add_audit_log(db, environment, worker_type, "GET", result.before, result.after, actor)
        db.commit()
        previous_prompt = snapshot.previous_prompt or ""
    except Exception:
        db.rollback()
        logger.exception(
            "Failed to persist prompt snapshot/audit log. environment=%s worker_type=%s",
            environment.value,
            worker_type,
        )
        try:
            fallback_snapshot = _find_snapshot(db, environment, worker_type)
            if fallback_snapshot is not None:
                previous_prompt = fallback_snapshot.previous_prompt or ""
        except Exception:
            db.rollback()
            logger.exception(
                "Failed to load fallback snapshot after persistence error. environment=%s worker_type=%s",
                environment.value,
                worker_type,
            )

    return {
        "before": result.before,
        "after": result.after,
        "currentPrompt": ats_current,
        "previousPrompt": previous_prompt,
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

