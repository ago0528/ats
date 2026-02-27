# AQB Backoffice

## 사내망 공유 빠른 실행

1. 백엔드 실행

```bash
cd /Users/ago0528/Desktop/files/01_work/01_planning/01_vibecoding/ats/agent_qa_dev/backoffice/backend
source .venv/bin/activate
export BACKOFFICE_VERSION=${BACKOFFICE_VERSION:-0.1.0}
export BACKOFFICE_DB_PATH=${BACKOFFICE_DB_PATH:-$(pwd)/backoffice.db}
# 필요 시 현재 프론트 origin 명시(예: http://10.11.3.52:5173)
# export BACKOFFICE_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://10.11.3.52:5173
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

2. 프론트 API 주소를 사설 IP로 설정

```bash
cd /Users/ago0528/Desktop/files/01_work/01_planning/01_vibecoding/ats/agent_qa_dev/backoffice/frontend
cp -n .env
```

`VITE_API_BASE_URL`을 아래처럼 수정:

```bash
VITE_API_BASE_URL=http://<서버PC사설IP>:8000/api/v1
```

3. 프론트 실행

```bash
cd /Users/ago0528/Desktop/files/01_work/01_planning/01_vibecoding/ats/agent_qa_dev/backoffice
pnpm dev --host 0.0.0.0 --port 5173
```

4. 같은 사내망 사용자의 접속 주소

- Frontend: `http://<서버PC사설IP>:5173`
- Backend API: `http://<서버PC사설IP>:8000`
- Swagger: `http://<서버PC사설IP>:8000/docs`

## 포트 의미

- `5173`: 프론트엔드(Vite dev server) 접속 포트
- `8000`: 백엔드(FastAPI) API 포트
- 프론트 화면은 `5173`으로 열고, 데이터 요청은 `8000`으로 보냅니다.

## Frontend Dev Server

```bash
cd /Users/ago0528/Desktop/files/01_work/01_planning/01_vibecoding/ats/agent_qa_dev/backoffice
pnpm dev --host 0.0.0.0 --port 5173
```

또는

```bash
pnpm --dir frontend dev --host 0.0.0.0 --port 5173
```

사내 동일 네트워크에서 프론트에 접속하려면 서버 실행 PC의 사설 IP로 접근합니다.

- Frontend: `http://<서버PC사설IP>:5173`

로컬 PC에서만 접근하려면 `--host 127.0.0.1`로 실행하세요.

## Backend

```bash
cd backoffice/backend
source .venv/bin/activate
export BACKOFFICE_VERSION=${BACKOFFICE_VERSION:-0.1.0}
export BACKOFFICE_DB_PATH=${BACKOFFICE_DB_PATH:-$(pwd)/backoffice.db}
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

사내 동일 네트워크에서 접속하려면 서버 실행 PC의 사설 IP로 접근합니다.

- API: `http://<서버PC사설IP>:8000`
- Swagger: `http://<서버PC사설IP>:8000/docs`

프론트를 사내망에서 함께 사용할 때는 `backoffice/frontend/.env`에서
`VITE_API_BASE_URL`을 `http://<서버PC사설IP>:8000/api/v1`로 맞춰야 합니다.

로컬 PC에서만 접근하려면 `--host 127.0.0.1`로 실행하세요.

### 로컬 개발 백도어키 로그인 (선택)

로컬 UI 점검 시 ATS 계정 로그인 없이 접근하려면 백엔드에 아래 환경변수를 추가합니다.

```bash
export BACKOFFICE_ENABLE_LOCAL_DEV_BACKDOOR_LOGIN=true
export BACKOFFICE_LOCAL_DEV_BACKDOOR_KEY=<원하는_백도어키>
```

선택 값(미설정 시 기본 placeholder 사용):

```bash
export BACKOFFICE_LOCAL_DEV_BACKDOOR_USER_ID=local-dev-bypass
export BACKOFFICE_LOCAL_DEV_BACKDOOR_BEARER=<bearer>
export BACKOFFICE_LOCAL_DEV_BACKDOOR_CMS=<cms>
export BACKOFFICE_LOCAL_DEV_BACKDOOR_MRS=<mrs>
export BACKOFFICE_LOCAL_DEV_BACKDOOR_ACC_AUTH_TOKEN=<accAuthToken>
```

주의:

- `/api/v1/auth/local-dev-bypass`는 `localhost/127.0.0.1/::1` 요청에서만 허용됩니다.
- 배포/공유 환경에서는 반드시 `BACKOFFICE_ENABLE_LOCAL_DEV_BACKDOOR_LOGIN=false`로 유지하세요.

## Backend Test (safe mode)

```bash
cd backoffice/backend
source .venv/bin/activate
export BACKOFFICE_DB_PATH=${BACKOFFICE_DB_PATH:-$(pwd)/backoffice_test.db}
export BACKOFFICE_ALLOW_DB_RESET=1
python -m pytest -q
```

## Backend Test (offline / internal mirror)

```bash
cd backoffice/backend

# 오프라인 wheelhouse
export BACKOFFICE_WHEELHOUSE=/path/to/wheelhouse
./scripts/run_tests_offline.sh

# 또는 사내 미러
export BACKOFFICE_PIP_INDEX_URL=https://<internal-pypi>/simple
./scripts/run_tests_offline.sh
```

> 백엔드 폴더에서는 `pnpm dev` 자체가 제공되지 않습니다. `pnpm` 관련 실행은 frontend 폴더로 이동해서 진행하세요.
