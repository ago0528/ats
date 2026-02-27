from __future__ import annotations

import os
import secrets
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from app.core.environment import get_env_config
from app.core.enums import Environment
from app.services.ats_auth_service import (
    AUTH_SESSION_COOKIE_NAME,
    AtsAuthError,
    auth_session_store,
)

router = APIRouter(tags=["auth"])

COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 14
LOCAL_DEV_BYPASS_DEFAULT_USER_ID = "local-dev-bypass"
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "testclient"}


def _is_truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _cookie_secure_enabled() -> bool:
    raw_value = os.getenv("BACKOFFICE_COOKIE_SECURE", "")
    if raw_value:
        return _is_truthy(raw_value)
    return False


def _set_auth_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=AUTH_SESSION_COOKIE_NAME,
        value=session_id,
        max_age=COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=_cookie_secure_enabled(),
        samesite="lax",
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=AUTH_SESSION_COOKIE_NAME,
        path="/",
        samesite="lax",
    )


def _resolve_session_id(request: Request) -> str:
    session_id = str(request.cookies.get(AUTH_SESSION_COOKIE_NAME, "")).strip()
    if not session_id:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return session_id


def _raise_auth_http_error(error: AtsAuthError) -> None:
    status_code = int(error.status_code or 500)
    raise HTTPException(status_code=status_code, detail=str(error)) from error


def _normalize_hostname(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if "://" in text:
        return str(urlparse(text).hostname or "").strip().lower()
    if text.startswith("[") and "]" in text:
        return text[1 : text.index("]")]
    if ":" in text:
        return text.split(":", 1)[0]
    return text


def _is_local_request(request: Request) -> bool:
    client_host = _normalize_hostname(request.client.host if request.client else "")
    host_header = _normalize_hostname(request.headers.get("host", ""))
    origin_host = _normalize_hostname(request.headers.get("origin", ""))
    referer_host = _normalize_hostname(request.headers.get("referer", ""))
    candidates = [host for host in (client_host, host_header, origin_host, referer_host) if host]
    if not candidates:
        return False
    return all(host in _LOCAL_HOSTS for host in candidates)


def _local_dev_backdoor_enabled() -> bool:
    return _is_truthy(os.getenv("BACKOFFICE_ENABLE_LOCAL_DEV_BACKDOOR_LOGIN", "false"))


def _resolve_local_dev_token(name: str, fallback: str) -> str:
    value = str(os.getenv(name, "")).strip()
    return value or fallback


class AuthLoginRequest(BaseModel):
    environment: Environment
    userId: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AuthRefreshRequest(BaseModel):
    environment: Environment


class AuthLocalDevBackdoorRequest(BaseModel):
    environment: Environment
    backdoorKey: str = Field(min_length=1)


@router.post("/auth/login")
def login(body: AuthLoginRequest, request: Request, response: Response):
    session_id = str(request.cookies.get(AUTH_SESSION_COOKIE_NAME, "")).strip()
    if not session_id:
        session_id = auth_session_store.create_session_id()
    config = get_env_config(body.environment)
    try:
        payload = auth_session_store.login(
            session_id=session_id,
            environment=body.environment,
            cms_base_url=config.cms_base_url,
            user_id=body.userId,
            password=body.password,
        )
    except AtsAuthError as error:
        _raise_auth_http_error(error)
    _set_auth_cookie(response, session_id)
    return payload


@router.get("/auth/session")
def get_session(
    request: Request,
    response: Response,
    environment: Environment = Query(...),
):
    session_id = _resolve_session_id(request)
    try:
        payload = auth_session_store.get_session(
            session_id=session_id,
            environment=environment,
            auto_refresh=True,
        )
    except AtsAuthError as error:
        _raise_auth_http_error(error)
    _set_auth_cookie(response, session_id)
    return payload


@router.post("/auth/refresh")
def refresh_session(body: AuthRefreshRequest, request: Request, response: Response):
    session_id = _resolve_session_id(request)
    try:
        payload = auth_session_store.refresh(
            session_id=session_id,
            environment=body.environment,
        )
    except AtsAuthError as error:
        _raise_auth_http_error(error)
    _set_auth_cookie(response, session_id)
    return payload


@router.post("/auth/local-dev-bypass")
def local_dev_backdoor_login(
    body: AuthLocalDevBackdoorRequest,
    request: Request,
    response: Response,
):
    if not _local_dev_backdoor_enabled():
        raise HTTPException(status_code=404, detail="로컬 개발 백도어 로그인 기능이 비활성화되어 있습니다.")
    if not _is_local_request(request):
        raise HTTPException(status_code=403, detail="로컬 개발 백도어 로그인은 localhost에서만 사용할 수 있습니다.")

    expected_key = str(os.getenv("BACKOFFICE_LOCAL_DEV_BACKDOOR_KEY", "")).strip()
    if not expected_key:
        raise HTTPException(status_code=503, detail="BACKOFFICE_LOCAL_DEV_BACKDOOR_KEY 설정이 필요합니다.")
    provided_key = str(body.backdoorKey or "").strip()
    if not provided_key or not secrets.compare_digest(provided_key, expected_key):
        raise HTTPException(status_code=401, detail="백도어키가 올바르지 않습니다.")

    session_id = str(request.cookies.get(AUTH_SESSION_COOKIE_NAME, "")).strip()
    if not session_id:
        session_id = auth_session_store.create_session_id()
    user_id = str(
        os.getenv(
            "BACKOFFICE_LOCAL_DEV_BACKDOOR_USER_ID",
            LOCAL_DEV_BYPASS_DEFAULT_USER_ID,
        )
        or LOCAL_DEV_BYPASS_DEFAULT_USER_ID
    ).strip() or LOCAL_DEV_BYPASS_DEFAULT_USER_ID

    try:
        payload = auth_session_store.login_local_dev_bypass(
            session_id=session_id,
            environment=body.environment,
            user_id=user_id,
            bearer_token=_resolve_local_dev_token(
                "BACKOFFICE_LOCAL_DEV_BACKDOOR_BEARER",
                "local-dev-backdoor-bearer",
            ),
            cms_access_token=_resolve_local_dev_token(
                "BACKOFFICE_LOCAL_DEV_BACKDOOR_CMS",
                "local-dev-backdoor-cms",
            ),
            mrs_session=_resolve_local_dev_token(
                "BACKOFFICE_LOCAL_DEV_BACKDOOR_MRS",
                "local-dev-backdoor-mrs",
            ),
            acc_auth_token=_resolve_local_dev_token(
                "BACKOFFICE_LOCAL_DEV_BACKDOOR_ACC_AUTH_TOKEN",
                "",
            ),
        )
    except AtsAuthError as error:
        _raise_auth_http_error(error)

    _set_auth_cookie(response, session_id)
    return payload


@router.post("/auth/logout")
def logout(request: Request, response: Response):
    session_id = str(request.cookies.get(AUTH_SESSION_COOKIE_NAME, "")).strip()
    if session_id:
        auth_session_store.clear_session(session_id)
    _clear_auth_cookie(response)
    return {"ok": True}
