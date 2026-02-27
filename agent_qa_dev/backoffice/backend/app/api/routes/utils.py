from __future__ import annotations

import os
import re
import httpx

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.environment import get_env_config
from app.core.enums import Environment
from app.lib.curl_parsing import parse_curl_headers


router = APIRouter(tags=["utils"])

_CURL_STATUS_TIMEOUT_SECONDS = 8.0
_AUTH_PAYLOAD = {"workerType": "ORCHESTRATOR_WORKER", "prompt": None}


class ParseCurlRequest(BaseModel):
    curlText: str


class CurlStatusRequest(BaseModel):
    bearer: str = ''
    cms: str = ''
    mrs: str = ''
    environment: Environment = Environment.DEV


class CurlStatusCheck(BaseModel):
    field: str
    label: str
    present: bool
    valid: bool
    length: int
    preview: str
    message: str


class CurlStatusResponse(BaseModel):
    checks: list[CurlStatusCheck]
    allValid: bool


def _legacy_curl_login_enabled() -> bool:
    raw_value = str(os.getenv("BACKOFFICE_ENABLE_LEGACY_CURL_LOGIN", "false")).strip().lower()
    return raw_value in {"1", "true", "yes", "on"}


def _assert_legacy_curl_login_enabled() -> None:
    if _legacy_curl_login_enabled():
        return
    raise HTTPException(status_code=404, detail="Legacy cURL login API is disabled.")


def _summarize_token(value: str) -> str:
    text = (value or '').strip()
    if not text:
        return ''
    if len(text) <= 28:
        return text
    return f'{text[:10]}...{text[-10:]}'


def _normalize_bearer(value: str) -> str:
    token = (value or "").strip()
    if token.lower().startswith("bearer "):
        return token[7:].strip()
    return token


def _check_bearer(value: str) -> tuple[bool, bool, str]:
    text = (value or "").strip()
    if not text:
        return False, False, '값이 없습니다.'
    token = _normalize_bearer(text)
    if not token:
        return True, False, 'Bearer 값이 비어 있습니다.'
    return True, True, ''


def _check_token(value: str) -> tuple[bool, bool, str]:
    text = (value or "").strip()
    if not text:
        return False, False, '값이 없습니다.'
    return True, True, ''


def _strip_quoted(value: str) -> str:
    return re.sub(r'^["\'](.*)["\']$', r'\1', value)


def _validate_tokens_with_ats(base_url: str, bearer: str, cms: str, mrs: str) -> tuple[bool, bool, str]:
    token = _normalize_bearer(bearer)
    headers = {
        "Authorization": f"Bearer {token}",
        "Cms-Access-Token": _strip_quoted((cms or "").strip()),
        "Mrs-Session": _strip_quoted((mrs or "").strip()),
        "Content-Type": "application/json",
    }

    try:
        response = httpx.put(
            f"{base_url}/api/v1/ai/prompt",
            json=_AUTH_PAYLOAD,
            headers=headers,
            timeout=_CURL_STATUS_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        return False, True, f"ATS API 연결 실패: {exc!s}"

    if 200 <= response.status_code < 300:
        return True, False, ''

    if response.status_code in {401, 403}:
        return False, False, f"ATS 인증 실패: HTTP {response.status_code}"

    return False, False, f"ATS 인증 실패: HTTP {response.status_code}"


def _build_status(field: str, label: str, present: bool, valid: bool, message: str, value: str) -> CurlStatusCheck:
    text = (value or '').strip()
    return CurlStatusCheck(
        field=field,
        label=label,
        present=present,
        valid=valid,
        length=len(text),
        preview=_summarize_token(text),
        message=message,
    )


@router.post("/utils/parse-curl")
def parse_curl(req: ParseCurlRequest):
    _assert_legacy_curl_login_enabled()
    return parse_curl_headers(req.curlText)


@router.post("/utils/curl-status", response_model=CurlStatusResponse)
def check_curl_status(req: CurlStatusRequest) -> CurlStatusResponse:
    _assert_legacy_curl_login_enabled()
    bearer_present, bearer_valid, bearer_message = _check_bearer(req.bearer)
    cms_present, cms_valid, cms_message = _check_token(req.cms)
    mrs_present, mrs_valid, mrs_message = _check_token(req.mrs)

    token_shapes_valid = bearer_valid and cms_valid and mrs_valid
    ats_valid, ats_network_error, ats_message = (False, False, '')
    if token_shapes_valid:
        cfg = get_env_config(req.environment)
        ats_valid, ats_network_error, ats_message = _validate_tokens_with_ats(
            cfg.base_url,
            req.bearer,
            req.cms,
            req.mrs,
        )

    if ats_network_error:
        raise HTTPException(status_code=503, detail=ats_message or "ATS API와 통신할 수 없습니다.")

    bearer_valid = bearer_valid and ats_valid
    cms_valid = cms_valid and ats_valid
    mrs_valid = mrs_valid and ats_valid

    if token_shapes_valid and ats_valid:
        bearer_message = cms_message = mrs_message = ''
    else:
        if token_shapes_valid:
            bearer_message = cms_message = mrs_message = ats_message or 'ATS 토큰 검증에 실패했습니다.'
        if not bearer_message:
            bearer_message = 'Bearer 토큰이 유효하지 않습니다.'
        if not cms_message:
            cms_message = 'CMS 토큰이 유효하지 않습니다.'
        if not mrs_message:
            mrs_message = 'MRS 토큰이 유효하지 않습니다.'

    checks = [
        _build_status('bearer', 'Bearer', bearer_present, bearer_valid, bearer_message, req.bearer),
        _build_status('cms', 'CMS Access Token', cms_present, cms_valid, cms_message, req.cms),
        _build_status('mrs', 'MRS Session', mrs_present, mrs_valid, mrs_message, req.mrs),
    ]

    return CurlStatusResponse(checks=checks, allValid=all(item.valid for item in checks))
