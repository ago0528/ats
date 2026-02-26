"""
ATS CMS 인증 모듈

MRS(Midas Recruiting System) CMS에 로그인하여
ATS LLM API 호출에 필요한 인증 토큰 3종을 자동 발급한다.

사용 예시:
    from ats_auth import authenticate, build_headers

    tokens = authenticate()
    headers = build_headers(tokens)
    # headers를 사용해 ATS API 호출
"""

import requests
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5

DEFAULT_BASE_URL = "https://qa-jobda02-cms-recruiter-co-kr.midasweb.net"


# ──────────────────────────────────────────────
#  내부 함수
# ──────────────────────────────────────────────

def _encrypt_password(session, base_url, password):
    """서버에서 RSA 공개키를 받아 비밀번호를 암호화한다."""
    res = session.get(f"{base_url}/mrs2/cus/rsa/get-public-key-spec")
    data = res.json()
    pub_key = RSA.construct((int(data["modulus"], 16), int(data["exponent"], 16)))
    cipher = PKCS1_v1_5.new(pub_key)
    return cipher.encrypt(password.encode("utf-8")).hex()


def _login(session, base_url, user_id, enc_password):
    """POST /cus/loginDo — 세션 쿠키를 획득한다."""
    res = session.post(
        f"{base_url}/cus/loginDo",
        data={
            "authType": "MANAGER",
            "id": user_id,
            "password": enc_password,
            "saveTF": "on",
        },
    )
    body = res.json()
    if not body.get("successYn"):
        raise RuntimeError(f"로그인 실패: {body}")
    return body


def _issue_retention_token(session, base_url):
    """GET /mrs2/manager/screening/retention/v1/token/issue
    → agentAccessToken(=Authorization) + mrsSession 반환."""
    res = session.get(
        f"{base_url}/mrs2/manager/screening/retention/v1/token/issue"
    )
    if res.status_code != 200:
        raise RuntimeError(f"Retention 토큰 발급 실패 (HTTP {res.status_code})")
    data = res.json()
    return {
        "agent_access_token": data["accessToken"],
        "mrs_session": data["mrsSession"],
    }


def _issue_cms_token(session, base_url):
    """POST /cus/selectProduct
    → accessToken(=Cms-Access-Token) + accAuthToken 반환."""
    res = session.post(f"{base_url}/cus/selectProduct")
    if res.status_code != 200:
        raise RuntimeError(f"CMS 토큰 발급 실패 (HTTP {res.status_code})")
    data = res.json()
    if not data.get("accessToken"):
        raise RuntimeError(f"accessToken 누락: {list(data.keys())}")
    return {
        "cms_access_token": data["accessToken"],
        "acc_auth_token": data.get("accAuthToken", ""),
    }


# ──────────────────────────────────────────────
#  공개 API
# ──────────────────────────────────────────────

def authenticate(user_id, password, base_url=DEFAULT_BASE_URL):
    """
    전체 인증 플로우를 실행하고 토큰 dict를 반환한다.

    Returns:
        {
            "agent_access_token": str,   # Authorization 헤더 (Bearer 접두사 없이)
            "cms_access_token":   str,   # Cms-Access-Token 헤더
            "mrs_session":        str,   # Mrs-Session 헤더
            "acc_auth_token":     str,   # accAuthToken 헤더
        }
    """
    s = requests.Session()

    enc_pw = _encrypt_password(s, base_url, password)
    _login(s, base_url, user_id, enc_pw)
    retention = _issue_retention_token(s, base_url)
    cms = _issue_cms_token(s, base_url)

    return {
        "agent_access_token": retention["agent_access_token"],
        "cms_access_token": cms["cms_access_token"],
        "mrs_session": retention["mrs_session"],
        "acc_auth_token": cms["acc_auth_token"],
    }


def build_headers(tokens):
    """
    authenticate()가 반환한 dict로 ATS API 요청 헤더를 조립한다.

    Returns:
        dict — requests 호출 시 headers= 파라미터에 바로 사용 가능
    """
    return {
        "Authorization": f"Bearer {tokens['agent_access_token']}",
        "Cms-Access-Token": tokens["cms_access_token"],
        "Mrs-Session": tokens["mrs_session"],
        "accAuthToken": tokens.get("acc_auth_token", ""),
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
    }


# ──────────────────────────────────────────────
#  직접 실행 시 동작 확인
# ──────────────────────────────────────────────

if __name__ == "__main__":
    USER_ID = "ago0528"
    PASSWORD = "mid@sit0901!"

    tokens = authenticate(USER_ID, PASSWORD)

    print("인증 완료")
    print()
    print(f"  Authorization    : Bearer {tokens['agent_access_token'][:50]}...")
    print(f"  Cms-Access-Token : {tokens['cms_access_token'][:50]}...")
    print(f"  Mrs-Session      : {tokens['mrs_session']}")
    print(f"  accAuthToken     : {tokens['acc_auth_token'][:50]}...")
    print()

    headers = build_headers(tokens)
    print(f"  build_headers() 키: {list(headers.keys())}")
