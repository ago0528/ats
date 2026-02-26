# ATS CMS 인증 API 가이드

ATS(채용솔루션) LLM API를 호출하려면 4개의 인증 헤더가 필요하다.  
이 문서는 해당 헤더 값을 자동으로 발급받는 플로우를 설명한다.

---

## 빠른 사용법

```python
from ats_auth import authenticate, build_headers

tokens = authenticate(user_id="ago0528", password="비밀번호")
headers = build_headers(tokens)

# 이후 ATS API 호출 시 headers= 에 전달
requests.post("https://api-llm.ats.kr-st2-midasin.com/api/v2/ai/orchestrator/query",
              headers=headers, json=payload)
```

---

## 인증 플로우 (4단계)

```
┌───────────────────────────────────────────────────────────────┐
│  CMS 도메인: qa-jobda02-cms-recruiter-co-kr.midasweb.net      │
│                                                               │
│  [1] GET  /mrs2/cus/rsa/get-public-key-spec                  │
│       → RSA 공개키(modulus, exponent) 수신                     │
│       → 비밀번호를 PKCS1_v1_5로 암호화                          │
│                                                               │
│  [2] POST /cus/loginDo                                        │
│       → 세션 쿠키(SESSION_mrs) 획득                            │
│                                                               │
│  [3] GET  /mrs2/manager/screening/retention/v1/token/issue    │
│       → agent_access_token (HS256 JWT) + mrs_session          │
│                                                               │
│  [4] POST /cus/selectProduct                                  │
│       → cms_access_token (RS256 JWT) + acc_auth_token         │
└───────────────────────────────────────────────────────────────┘
```

---

## 각 API 상세

### [1] RSA 공개키 조회

| 항목   | 값                                            |
| ------ | --------------------------------------------- |
| Method | `GET`                                         |
| URL    | `{base_url}/mrs2/cus/rsa/get-public-key-spec` |
| 인증   | 없음                                          |

**Response (JSON)**

```json
{
  "modulus": "a1c303...(hex, 매 요청마다 변경)",
  "exponent": "10001"
}
```

**처리**: modulus/exponent를 hex→int로 변환, RSA 공개키 구성 후 `PKCS1_v1_5`로 비밀번호 암호화 → hex 문자열.

---

### [2] 로그인

| 항목         | 값                                  |
| ------------ | ----------------------------------- |
| Method       | `POST`                              |
| URL          | `{base_url}/cus/loginDo`            |
| Content-Type | `application/x-www-form-urlencoded` |
| 인증         | 없음                                |

**Request Body (form)**
| 파라미터 | 값 | 설명 |
|---------|---|------|
| authType | `MANAGER` | 고정값 |
| id | 사용자 ID | |
| password | [1]에서 암호화한 hex | |
| saveTF | `on` | 자동 로그인 |

**Response (JSON)**

```json
{
  "successYn": true,
  "returnURL": "/agent/home"
}
```

**핵심**: 성공 시 `SESSION_mrs` 쿠키가 세팅된다. 이후 [3], [4]는 이 세션 쿠키로 인증한다.

---

### [3] Retention 토큰 발급

| 항목   | 값                                                           |
| ------ | ------------------------------------------------------------ |
| Method | `GET`                                                        |
| URL    | `{base_url}/mrs2/manager/screening/retention/v1/token/issue` |
| 인증   | 세션 쿠키 (자동, [2]에서 획득)                               |

**Response (JSON)**

```json
{
  "accessToken": "eyJ0eXAiOiJKV1Q...(HS256 JWT)",
  "accessTokenExpirationAt": "2026-02-26T22:34:30...",
  "refreshToken": "eyJ0eXAiOiJKV1Q...",
  "refreshTokenExpirationAt": "2026-03-05T20:34:30...",
  "mrsSession": "ZGE0MjcyM2It..."
}
```

| 응답 필드     | 용도                     | 헤더 이름                    |
| ------------- | ------------------------ | ---------------------------- |
| `accessToken` | HS256 JWT, 약 2시간 유효 | `Authorization: Bearer {값}` |
| `mrsSession`  | Base64 세션 ID           | `Mrs-Session`                |

---

### [4] CMS Access Token 발급

| 항목   | 값                                         |
| ------ | ------------------------------------------ |
| Method | `POST` (GET 아님 — GET은 HTML 페이지 반환) |
| URL    | `{base_url}/cus/selectProduct`             |
| 인증   | 세션 쿠키 (자동, [2]에서 획득)             |

**Response (JSON)**

```json
{
  "accessToken": "eyJhbGciOiJSUzI1NiJ9...(RS256 JWT)",
  "accAuthToken": "eyJhbGciOiJIUzI1NiJ9...",
  "serviceList": [...],
  "successYn": true,
  ...
}
```

| 응답 필드      | 용도                   | 헤더 이름          |
| -------------- | ---------------------- | ------------------ |
| `accessToken`  | RS256 JWT, 약 7일 유효 | `Cms-Access-Token` |
| `accAuthToken` | Account Center 토큰    | `accAuthToken`     |

---

## 최종 ATS API 요청 헤더

```
Authorization:    Bearer {agent_access_token}    ← [3] accessToken
Cms-Access-Token: {cms_access_token}             ← [4] accessToken
Mrs-Session:      {mrs_session}                  ← [3] mrsSession
accAuthToken:     {acc_auth_token}               ← [4] accAuthToken
Content-Type:     application/json
```

---

## 토큰 유효 기간

| 토큰               | 알고리즘 | 유효 기간 | 갱신 방법         |
| ------------------ | -------- | --------- | ----------------- |
| agent_access_token | HS256    | ~2시간    | [3] 재호출        |
| cms_access_token   | RS256    | ~7일      | [4] 재호출        |
| mrs_session        | —        | 세션 의존 | 로그인부터 재수행 |

---

## 환경 설정

```bash
cd ats_auth
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python ats_auth.py          # 동작 확인
```

## 의존성

- `requests` — HTTP 클라이언트
- `pycryptodome` — RSA 암호화 (`Crypto.PublicKey.RSA`, `Crypto.Cipher.PKCS1_v1_5`)
