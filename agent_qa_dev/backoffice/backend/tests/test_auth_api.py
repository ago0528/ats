from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient

from app.main import app
from app.services.ats_auth_service import (
    AUTH_SESSION_COOKIE_NAME,
    AtsAuthError,
    AuthTokenBundle,
    auth_session_store,
)


def _build_token_bundle(
    *,
    agent: str = "agent-token",
    cms: str = "cms-token",
    mrs: str = "mrs-session",
    acc: str = "acc-token",
    agent_minutes: int = 120,
    cms_hours: int = 24,
) -> AuthTokenBundle:
    now = dt.datetime.now(dt.timezone.utc)
    return AuthTokenBundle(
        agent_access_token=agent,
        cms_access_token=cms,
        mrs_session=mrs,
        acc_auth_token=acc,
        agent_expires_at=now + dt.timedelta(minutes=agent_minutes),
        cms_expires_at=now + dt.timedelta(hours=cms_hours),
    )


def _extract_auth_cookie(client: TestClient) -> str:
    cookie = client.cookies.get(AUTH_SESSION_COOKIE_NAME)
    assert cookie is not None
    return str(cookie)


def test_auth_login_returns_runtime_tokens_and_cookie(monkeypatch):
    client = TestClient(app)

    def _fake_full_login(**_kwargs):
        return _build_token_bundle(), {"SESSION_mrs": "cookie-session"}

    monkeypatch.setattr(auth_session_store, "_perform_full_login", _fake_full_login)
    auth_session_store._sessions.clear()

    response = client.post(
        "/api/v1/auth/login",
        json={"environment": "dev", "userId": "ago0528", "password": "pw"},
    )

    assert response.status_code == 200
    assert response.json()["authenticated"] is True
    assert response.json()["runtimeSecrets"]["bearer"] == "agent-token"
    assert response.json()["runtimeSecrets"]["cms"] == "cms-token"
    assert response.json()["runtimeSecrets"]["mrs"] == "mrs-session"
    assert response.json()["optionalTokens"]["accAuthToken"] == "acc-token"
    assert AUTH_SESSION_COOKIE_NAME in response.headers.get("set-cookie", "")
    assert _extract_auth_cookie(client)


def test_auth_session_skips_refresh_when_not_near_expiry(monkeypatch):
    client = TestClient(app)
    auth_session_store._sessions.clear()

    def _fake_full_login(**_kwargs):
        return _build_token_bundle(agent="stable-agent", cms="stable-cms", mrs="stable-mrs"), {"SESSION_mrs": "cookie-session"}

    monkeypatch.setattr(auth_session_store, "_perform_full_login", _fake_full_login)
    login = client.post(
        "/api/v1/auth/login",
        json={"environment": "dev", "userId": "ago0528", "password": "pw"},
    )
    assert login.status_code == 200

    def _should_not_refresh(**_kwargs):
        raise AssertionError("refresh should not be called when token is still valid")

    monkeypatch.setattr(auth_session_store, "_refresh_environment_session", _should_not_refresh)

    session_response = client.get("/api/v1/auth/session", params={"environment": "dev"})
    assert session_response.status_code == 200
    assert session_response.json()["runtimeSecrets"]["bearer"] == "stable-agent"


def test_auth_session_refreshes_when_threshold_reached(monkeypatch):
    client = TestClient(app)
    auth_session_store._sessions.clear()

    def _fake_full_login(**_kwargs):
        return _build_token_bundle(agent="about-to-expire", cms="cms-old", mrs="mrs-old", agent_minutes=2), {"SESSION_mrs": "cookie-session"}

    monkeypatch.setattr(auth_session_store, "_perform_full_login", _fake_full_login)
    login = client.post(
        "/api/v1/auth/login",
        json={"environment": "dev", "userId": "ago0528", "password": "pw"},
    )
    assert login.status_code == 200
    session_id = _extract_auth_cookie(client)

    called = {"value": False}

    def _fake_refresh_environment_session(**_kwargs):
        called["value"] = True
        auth_session = auth_session_store._sessions[session_id]
        env_session = auth_session.environments[next(iter(auth_session.environments.keys()))]
        env_session.tokens = _build_token_bundle(
            agent="refreshed-agent",
            cms="refreshed-cms",
            mrs="refreshed-mrs",
            agent_minutes=180,
            cms_hours=48,
        )
        return env_session

    monkeypatch.setattr(auth_session_store, "_refresh_environment_session", _fake_refresh_environment_session)

    session_response = client.get("/api/v1/auth/session", params={"environment": "dev"})
    assert session_response.status_code == 200
    assert called["value"] is True
    assert session_response.json()["runtimeSecrets"]["bearer"] == "refreshed-agent"


def test_auth_refresh_falls_back_to_relogin_on_401(monkeypatch):
    client = TestClient(app)
    auth_session_store._sessions.clear()

    def _initial_login(**_kwargs):
        return _build_token_bundle(agent="initial-agent", cms="initial-cms", mrs="initial-mrs"), {"SESSION_mrs": "cookie-initial"}

    monkeypatch.setattr(auth_session_store, "_perform_full_login", _initial_login)
    login = client.post(
        "/api/v1/auth/login",
        json={"environment": "dev", "userId": "ago0528", "password": "pw"},
    )
    assert login.status_code == 200

    monkeypatch.setattr(
        auth_session_store,
        "_refresh_tokens",
        lambda **_kwargs: (_ for _ in ()).throw(AtsAuthError("expired", status_code=401)),
    )

    def _fallback_login(**_kwargs):
        return _build_token_bundle(agent="fallback-agent", cms="fallback-cms", mrs="fallback-mrs"), {"SESSION_mrs": "cookie-fallback"}

    monkeypatch.setattr(auth_session_store, "_perform_full_login", _fallback_login)

    refresh = client.post("/api/v1/auth/refresh", json={"environment": "dev"})
    assert refresh.status_code == 200
    assert refresh.json()["runtimeSecrets"]["bearer"] == "fallback-agent"


def test_auth_logout_clears_cookie_and_blocks_session(monkeypatch):
    client = TestClient(app)
    auth_session_store._sessions.clear()
    monkeypatch.setattr(
        auth_session_store,
        "_perform_full_login",
        lambda **_kwargs: (_build_token_bundle(), {"SESSION_mrs": "cookie-session"}),
    )

    login = client.post(
        "/api/v1/auth/login",
        json={"environment": "dev", "userId": "ago0528", "password": "pw"},
    )
    assert login.status_code == 200
    assert _extract_auth_cookie(client)

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    assert logout.json()["ok"] is True
    assert client.cookies.get(AUTH_SESSION_COOKIE_NAME) is None

    session_response = client.get("/api/v1/auth/session", params={"environment": "dev"})
    assert session_response.status_code == 401


def test_local_dev_backdoor_login_creates_authenticated_session(monkeypatch):
    client = TestClient(app)
    auth_session_store._sessions.clear()

    monkeypatch.setenv("BACKOFFICE_ENABLE_LOCAL_DEV_BACKDOOR_LOGIN", "true")
    monkeypatch.setenv("BACKOFFICE_LOCAL_DEV_BACKDOOR_KEY", "local-only-key")
    monkeypatch.setenv("BACKOFFICE_LOCAL_DEV_BACKDOOR_BEARER", "local-bearer")
    monkeypatch.setenv("BACKOFFICE_LOCAL_DEV_BACKDOOR_CMS", "local-cms")
    monkeypatch.setenv("BACKOFFICE_LOCAL_DEV_BACKDOOR_MRS", "local-mrs")

    response = client.post(
        "/api/v1/auth/local-dev-bypass",
        json={"environment": "dev", "backdoorKey": "local-only-key"},
        headers={
            "host": "localhost:8000",
            "origin": "http://localhost:5173",
            "referer": "http://localhost:5173/login",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["runtimeSecrets"] == {
        "bearer": "local-bearer",
        "cms": "local-cms",
        "mrs": "local-mrs",
    }
    assert AUTH_SESSION_COOKIE_NAME in response.headers.get("set-cookie", "")

    refresh_response = client.post("/api/v1/auth/refresh", json={"environment": "dev"})
    assert refresh_response.status_code == 200
    assert refresh_response.json()["runtimeSecrets"]["bearer"] == "local-bearer"


def test_local_dev_backdoor_login_rejects_non_local_host(monkeypatch):
    client = TestClient(app)
    auth_session_store._sessions.clear()

    monkeypatch.setenv("BACKOFFICE_ENABLE_LOCAL_DEV_BACKDOOR_LOGIN", "true")
    monkeypatch.setenv("BACKOFFICE_LOCAL_DEV_BACKDOOR_KEY", "local-only-key")

    response = client.post(
        "/api/v1/auth/local-dev-bypass",
        json={"environment": "dev", "backdoorKey": "local-only-key"},
        headers={"host": "qa-jobda.internal:8000"},
    )
    assert response.status_code == 403


def test_local_dev_backdoor_login_rejects_invalid_key(monkeypatch):
    client = TestClient(app)
    auth_session_store._sessions.clear()

    monkeypatch.setenv("BACKOFFICE_ENABLE_LOCAL_DEV_BACKDOOR_LOGIN", "true")
    monkeypatch.setenv("BACKOFFICE_LOCAL_DEV_BACKDOOR_KEY", "local-only-key")

    response = client.post(
        "/api/v1/auth/local-dev-bypass",
        json={"environment": "dev", "backdoorKey": "wrong-key"},
        headers={"host": "localhost:8000"},
    )
    assert response.status_code == 401
