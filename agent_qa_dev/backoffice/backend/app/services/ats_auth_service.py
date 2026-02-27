from __future__ import annotations

import base64
import datetime as dt
import json
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import requests
from requests import Session
from requests.exceptions import HTTPError, RequestException

from app.core.enums import Environment

try:
    from Crypto.Cipher import PKCS1_v1_5
    from Crypto.PublicKey import RSA
except Exception:  # pragma: no cover - optional dependency import guard
    PKCS1_v1_5 = None
    RSA = None

UTC = dt.timezone.utc
AUTH_SESSION_COOKIE_NAME = "backoffice_auth_session"
AGENT_REFRESH_THRESHOLD = dt.timedelta(minutes=10)
CMS_REFRESH_THRESHOLD = dt.timedelta(hours=12)
AUTH_SESSION_TTL = dt.timedelta(days=14)
LOCAL_DEV_BYPASS_TOKEN_TTL = dt.timedelta(days=30)


class AtsAuthError(RuntimeError):
    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthSessionNotFoundError(AtsAuthError):
    def __init__(self) -> None:
        super().__init__("인증 세션이 없습니다.", status_code=401)


class AuthEnvironmentNotFoundError(AtsAuthError):
    def __init__(self, environment: Environment) -> None:
        super().__init__(f"{environment.value} 환경 로그인 세션이 없습니다.", status_code=401)


def _utc_now() -> dt.datetime:
    return dt.datetime.now(tz=UTC)


def _to_utc(dt_value: Optional[dt.datetime]) -> Optional[dt.datetime]:
    if dt_value is None:
        return None
    if dt_value.tzinfo is None:
        return dt_value.replace(tzinfo=UTC)
    return dt_value.astimezone(UTC)


def _parse_iso_datetime(value: Any) -> Optional[dt.datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return _to_utc(parsed)


def _decode_jwt_exp(token: str) -> Optional[dt.datetime]:
    encoded = str(token or "").strip()
    if not encoded:
        return None
    parts = encoded.split(".")
    if len(parts) < 2:
        return None
    payload = parts[1]
    padding = "=" * ((4 - len(payload) % 4) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload + padding)
        data = json.loads(decoded.decode("utf-8"))
    except Exception:
        return None
    exp = data.get("exp")
    if isinstance(exp, (int, float)):
        return dt.datetime.fromtimestamp(float(exp), tz=UTC)
    return None


def _resolve_token_expiration(*candidates: Any) -> Optional[dt.datetime]:
    for value in candidates:
        parsed = _parse_iso_datetime(value)
        if parsed is not None:
            return parsed
        if isinstance(value, str):
            jwt_exp = _decode_jwt_exp(value)
            if jwt_exp is not None:
                return jwt_exp
    return None


def _json_or_raise(response: requests.Response, *, default_message: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception as exc:
        raise AtsAuthError(default_message, status_code=response.status_code) from exc
    if not isinstance(payload, dict):
        raise AtsAuthError(default_message, status_code=response.status_code)
    return payload


def _safe_request(
    request_fn,
    *,
    error_message: str,
    timeout_seconds: float = 10.0,
) -> requests.Response:
    try:
        response = request_fn(timeout=timeout_seconds)
        response.raise_for_status()
        return response
    except HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        raise AtsAuthError(f"{error_message} (HTTP {status_code})", status_code=status_code) from exc
    except RequestException as exc:
        raise AtsAuthError(f"{error_message}: {exc}", status_code=503) from exc


@dataclass
class AuthTokenBundle:
    agent_access_token: str
    cms_access_token: str
    mrs_session: str
    acc_auth_token: str
    agent_expires_at: Optional[dt.datetime]
    cms_expires_at: Optional[dt.datetime]
    refreshed_at: dt.datetime = field(default_factory=_utc_now)

    def should_refresh(self, now: Optional[dt.datetime] = None) -> bool:
        current = now or _utc_now()
        agent_expiration = _to_utc(self.agent_expires_at)
        cms_expiration = _to_utc(self.cms_expires_at)
        if agent_expiration is None or cms_expiration is None:
            return True
        if agent_expiration <= current + AGENT_REFRESH_THRESHOLD:
            return True
        if cms_expiration <= current + CMS_REFRESH_THRESHOLD:
            return True
        return False

    def response_payload(self, *, environment: Environment, user_id: str) -> dict[str, Any]:
        candidates = [value for value in (self.agent_expires_at, self.cms_expires_at) if value is not None]
        expires_at = min(candidates).isoformat() if candidates else None
        return {
            "authenticated": True,
            "environment": environment.value,
            "userId": user_id,
            "runtimeSecrets": {
                "bearer": self.agent_access_token,
                "cms": self.cms_access_token,
                "mrs": self.mrs_session,
            },
            "optionalTokens": {
                "accAuthToken": self.acc_auth_token,
            },
            "expiresAt": expires_at,
            "agentAccessTokenExpiresAt": self.agent_expires_at.isoformat() if self.agent_expires_at else None,
            "cmsAccessTokenExpiresAt": self.cms_expires_at.isoformat() if self.cms_expires_at else None,
            "refreshedAt": self.refreshed_at.isoformat(),
        }


@dataclass
class AuthCredential:
    user_id: str
    password: str


@dataclass
class AuthEnvironmentSession:
    environment: Environment
    cms_base_url: str
    user_id: str
    credential: Optional[AuthCredential]
    tokens: AuthTokenBundle
    cookies: dict[str, str]
    is_local_dev_bypass: bool = False
    updated_at: dt.datetime = field(default_factory=_utc_now)


@dataclass
class AuthSession:
    session_id: str
    environments: dict[Environment, AuthEnvironmentSession] = field(default_factory=dict)
    created_at: dt.datetime = field(default_factory=_utc_now)
    updated_at: dt.datetime = field(default_factory=_utc_now)


class AtsAuthSessionStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, AuthSession] = {}

    def create_session_id(self) -> str:
        return uuid.uuid4().hex

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def login(
        self,
        *,
        session_id: str,
        environment: Environment,
        cms_base_url: str,
        user_id: str,
        password: str,
    ) -> dict[str, Any]:
        normalized_user_id = str(user_id or "").strip()
        normalized_password = str(password or "").strip()
        if not normalized_user_id or not normalized_password:
            raise AtsAuthError("아이디/비밀번호를 입력해 주세요.", status_code=400)

        tokens, cookies = self._perform_full_login(
            cms_base_url=cms_base_url,
            user_id=normalized_user_id,
            password=normalized_password,
        )

        with self._lock:
            self._cleanup_locked()
            auth_session = self._sessions.get(session_id)
            if auth_session is None:
                auth_session = AuthSession(session_id=session_id)
                self._sessions[session_id] = auth_session
            auth_session.environments[environment] = AuthEnvironmentSession(
                environment=environment,
                cms_base_url=cms_base_url,
                user_id=normalized_user_id,
                credential=AuthCredential(user_id=normalized_user_id, password=normalized_password),
                tokens=tokens,
                cookies=cookies,
            )
            auth_session.updated_at = _utc_now()
            return tokens.response_payload(environment=environment, user_id=normalized_user_id)

    def login_local_dev_bypass(
        self,
        *,
        session_id: str,
        environment: Environment,
        user_id: str,
        bearer_token: str,
        cms_access_token: str,
        mrs_session: str,
        acc_auth_token: str = "",
    ) -> dict[str, Any]:
        normalized_user_id = str(user_id or "").strip() or "local-dev-bypass"
        normalized_bearer = str(bearer_token or "").strip()
        normalized_cms = str(cms_access_token or "").strip()
        normalized_mrs = str(mrs_session or "").strip()
        normalized_acc_auth = str(acc_auth_token or "").strip()
        if not normalized_bearer or not normalized_cms or not normalized_mrs:
            raise AtsAuthError("로컬 개발 백도어 세션 토큰 값이 올바르지 않습니다.", status_code=400)

        now = _utc_now()
        expires_at = now + LOCAL_DEV_BYPASS_TOKEN_TTL
        tokens = AuthTokenBundle(
            agent_access_token=normalized_bearer,
            cms_access_token=normalized_cms,
            mrs_session=normalized_mrs,
            acc_auth_token=normalized_acc_auth,
            agent_expires_at=expires_at,
            cms_expires_at=expires_at,
            refreshed_at=now,
        )

        with self._lock:
            self._cleanup_locked()
            auth_session = self._sessions.get(session_id)
            if auth_session is None:
                auth_session = AuthSession(session_id=session_id)
                self._sessions[session_id] = auth_session
            auth_session.environments[environment] = AuthEnvironmentSession(
                environment=environment,
                cms_base_url="",
                user_id=normalized_user_id,
                credential=None,
                tokens=tokens,
                cookies={},
                is_local_dev_bypass=True,
            )
            auth_session.updated_at = now
            return tokens.response_payload(
                environment=environment,
                user_id=normalized_user_id,
            )

    def get_session(
        self,
        *,
        session_id: str,
        environment: Environment,
        auto_refresh: bool = True,
    ) -> dict[str, Any]:
        with self._lock:
            self._cleanup_locked()
            auth_session = self._sessions.get(session_id)
            if auth_session is None:
                raise AuthSessionNotFoundError()
            env_session = auth_session.environments.get(environment)
            if env_session is None:
                raise AuthEnvironmentNotFoundError(environment)

        if (
            auto_refresh
            and not env_session.is_local_dev_bypass
            and env_session.tokens.should_refresh()
        ):
            env_session = self._refresh_environment_session(
                session_id=session_id,
                environment=environment,
                fallback_relogin=True,
            )

        with self._lock:
            auth_session = self._sessions.get(session_id)
            if auth_session is None:
                raise AuthSessionNotFoundError()
            latest = auth_session.environments.get(environment)
            if latest is None:
                raise AuthEnvironmentNotFoundError(environment)
            auth_session.updated_at = _utc_now()
            return latest.tokens.response_payload(
                environment=environment,
                user_id=latest.user_id,
            )

    def refresh(
        self,
        *,
        session_id: str,
        environment: Environment,
    ) -> dict[str, Any]:
        with self._lock:
            auth_session = self._sessions.get(session_id)
            if auth_session is None:
                raise AuthSessionNotFoundError()
            env_session = auth_session.environments.get(environment)
            if env_session is None:
                raise AuthEnvironmentNotFoundError(environment)
            if env_session.is_local_dev_bypass:
                now = _utc_now()
                env_session.tokens.refreshed_at = now
                env_session.updated_at = now
                auth_session.updated_at = now
                return env_session.tokens.response_payload(
                    environment=environment,
                    user_id=env_session.user_id,
                )

        env_session = self._refresh_environment_session(
            session_id=session_id,
            environment=environment,
            fallback_relogin=True,
        )
        with self._lock:
            auth_session = self._sessions.get(session_id)
            if auth_session is None:
                raise AuthSessionNotFoundError()
            auth_session.updated_at = _utc_now()
        return env_session.tokens.response_payload(
            environment=environment,
            user_id=env_session.user_id,
        )

    def _refresh_environment_session(
        self,
        *,
        session_id: str,
        environment: Environment,
        fallback_relogin: bool,
    ) -> AuthEnvironmentSession:
        with self._lock:
            auth_session = self._sessions.get(session_id)
            if auth_session is None:
                raise AuthSessionNotFoundError()
            env_session = auth_session.environments.get(environment)
            if env_session is None:
                raise AuthEnvironmentNotFoundError(environment)

        try:
            tokens, cookies = self._refresh_tokens(
                cms_base_url=env_session.cms_base_url,
                cookies=env_session.cookies,
            )
        except AtsAuthError as exc:
            should_relogin = (
                fallback_relogin
                and env_session.credential is not None
                and exc.status_code in {401, 403}
            )
            if not should_relogin:
                raise
            if env_session.credential is None:
                raise AtsAuthError("재로그인 자격증명이 없습니다.", status_code=401) from exc
            tokens, cookies = self._perform_full_login(
                cms_base_url=env_session.cms_base_url,
                user_id=env_session.credential.user_id,
                password=env_session.credential.password,
            )

        with self._lock:
            auth_session = self._sessions.get(session_id)
            if auth_session is None:
                raise AuthSessionNotFoundError()
            latest = auth_session.environments.get(environment)
            if latest is None:
                raise AuthEnvironmentNotFoundError(environment)
            latest.tokens = tokens
            latest.cookies = cookies
            latest.updated_at = _utc_now()
            auth_session.updated_at = _utc_now()
            return latest

    def _cleanup_locked(self) -> None:
        threshold = _utc_now() - AUTH_SESSION_TTL
        stale_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if session.updated_at < threshold
        ]
        for session_id in stale_ids:
            self._sessions.pop(session_id, None)

    def _perform_full_login(
        self,
        *,
        cms_base_url: str,
        user_id: str,
        password: str,
    ) -> tuple[AuthTokenBundle, dict[str, str]]:
        with requests.Session() as session:
            encrypted_password = self._encrypt_password(session=session, cms_base_url=cms_base_url, password=password)
            self._login(session=session, cms_base_url=cms_base_url, user_id=user_id, encrypted_password=encrypted_password)
            retention = self._issue_retention_token(session=session, cms_base_url=cms_base_url)
            cms = self._issue_cms_token(session=session, cms_base_url=cms_base_url)
            tokens = self._build_tokens(retention=retention, cms=cms)
            return tokens, session.cookies.get_dict()

    def _refresh_tokens(
        self,
        *,
        cms_base_url: str,
        cookies: dict[str, str],
    ) -> tuple[AuthTokenBundle, dict[str, str]]:
        with requests.Session() as session:
            if cookies:
                session.cookies.update(cookies)
            retention = self._issue_retention_token(session=session, cms_base_url=cms_base_url)
            cms = self._issue_cms_token(session=session, cms_base_url=cms_base_url)
            tokens = self._build_tokens(retention=retention, cms=cms)
            return tokens, session.cookies.get_dict()

    def _encrypt_password(
        self,
        *,
        session: Session,
        cms_base_url: str,
        password: str,
    ) -> str:
        response = _safe_request(
            lambda timeout: session.get(f"{cms_base_url}/mrs2/cus/rsa/get-public-key-spec", timeout=timeout),
            error_message="RSA 공개키 조회 실패",
        )
        if RSA is None or PKCS1_v1_5 is None:
            raise AtsAuthError("pycryptodome 의존성이 설치되지 않았습니다.", status_code=500)
        payload = _json_or_raise(response, default_message="RSA 공개키 응답 파싱 실패")
        modulus = payload.get("modulus")
        exponent = payload.get("exponent")
        if not modulus or not exponent:
            raise AtsAuthError("RSA 공개키 응답에 modulus/exponent가 없습니다.", status_code=response.status_code)
        try:
            rsa_key = RSA.construct((int(str(modulus), 16), int(str(exponent), 16)))
            cipher = PKCS1_v1_5.new(rsa_key)
            return cipher.encrypt(str(password).encode("utf-8")).hex()
        except Exception as exc:
            raise AtsAuthError("비밀번호 RSA 암호화 실패") from exc

    def _login(
        self,
        *,
        session: Session,
        cms_base_url: str,
        user_id: str,
        encrypted_password: str,
    ) -> None:
        response = _safe_request(
            lambda timeout: session.post(
                f"{cms_base_url}/cus/loginDo",
                data={
                    "authType": "MANAGER",
                    "id": user_id,
                    "password": encrypted_password,
                    "saveTF": "on",
                },
                timeout=timeout,
            ),
            error_message="CMS 로그인 실패",
        )
        payload = _json_or_raise(response, default_message="CMS 로그인 응답 파싱 실패")
        if not payload.get("successYn"):
            raise AtsAuthError("CMS 로그인 실패: 아이디/비밀번호를 확인해 주세요.", status_code=401)

    def _issue_retention_token(
        self,
        *,
        session: Session,
        cms_base_url: str,
    ) -> dict[str, Any]:
        response = _safe_request(
            lambda timeout: session.get(
                f"{cms_base_url}/mrs2/manager/screening/retention/v1/token/issue",
                timeout=timeout,
            ),
            error_message="Retention 토큰 발급 실패",
        )
        payload = _json_or_raise(response, default_message="Retention 토큰 응답 파싱 실패")
        if not payload.get("accessToken") or not payload.get("mrsSession"):
            raise AtsAuthError("Retention 토큰 응답이 올바르지 않습니다.", status_code=response.status_code)
        return payload

    def _issue_cms_token(
        self,
        *,
        session: Session,
        cms_base_url: str,
    ) -> dict[str, Any]:
        response = _safe_request(
            lambda timeout: session.post(
                f"{cms_base_url}/cus/selectProduct",
                timeout=timeout,
            ),
            error_message="CMS Access 토큰 발급 실패",
        )
        payload = _json_or_raise(response, default_message="CMS Access 토큰 응답 파싱 실패")
        if not payload.get("accessToken"):
            raise AtsAuthError("CMS Access 토큰 응답이 올바르지 않습니다.", status_code=response.status_code)
        return payload

    def _build_tokens(
        self,
        *,
        retention: dict[str, Any],
        cms: dict[str, Any],
    ) -> AuthTokenBundle:
        agent_access_token = str(retention.get("accessToken", "")).strip()
        cms_access_token = str(cms.get("accessToken", "")).strip()
        mrs_session = str(retention.get("mrsSession", "")).strip()
        acc_auth_token = str(cms.get("accAuthToken", "")).strip()
        if not agent_access_token or not cms_access_token or not mrs_session:
            raise AtsAuthError("토큰 발급 결과에 필수 값이 누락됐습니다.")
        return AuthTokenBundle(
            agent_access_token=agent_access_token,
            cms_access_token=cms_access_token,
            mrs_session=mrs_session,
            acc_auth_token=acc_auth_token,
            agent_expires_at=_resolve_token_expiration(
                retention.get("accessTokenExpirationAt"),
                agent_access_token,
            ),
            cms_expires_at=_resolve_token_expiration(
                cms.get("accessTokenExpirationAt"),
                cms_access_token,
            ),
        )


auth_session_store = AtsAuthSessionStore()
