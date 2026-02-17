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

router = APIRouter(tags=["prompts"])


class PromptUpdateRequest(BaseModel):
    prompt: str


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
    try:
        result = adapter.get_prompt(worker_type)
    except Exception as e:
        raise HTTPException(500, str(e)) from e

    db.add(PromptAuditLog(environment=environment, worker_type=worker_type, action="GET", before_len=len(result.before or ""), after_len=len(result.after or ""), actor=x_actor or "unknown"))
    db.commit()
    return {"before": result.before, "after": result.after}


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
    try:
        result = adapter.update_prompt(worker_type, body.prompt)
    except Exception as e:
        raise HTTPException(500, str(e)) from e

    db.add(PromptAuditLog(environment=environment, worker_type=worker_type, action="UPDATE", before_len=len(result.before or ""), after_len=len(result.after or ""), actor=x_actor or "unknown"))
    db.commit()
    return {"before": result.before, "after": result.after}


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
    try:
        result = adapter.reset_prompt(worker_type)
    except Exception as e:
        raise HTTPException(500, str(e)) from e

    db.add(PromptAuditLog(environment=environment, worker_type=worker_type, action="RESET", before_len=len(result.before or ""), after_len=len(result.after or ""), actor=x_actor or "unknown"))
    db.commit()
    return {"before": result.before, "after": result.after}
