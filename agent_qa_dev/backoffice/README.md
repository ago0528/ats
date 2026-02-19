# AQB Backoffice

## 사내망 공유 빠른 실행

1. 백엔드 실행
```bash
cd /Users/ago0528/Desktop/files/01_work/01_planning/01_vibecoding/ats/agent_qa_dev/backoffice/backend
source .venv/bin/activate
export BACKOFFICE_VERSION=${BACKOFFICE_VERSION:-0.1.0}
export BACKOFFICE_DB_PATH=${BACKOFFICE_DB_PATH:-$(pwd)/backoffice.db}
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

2. 프론트 API 주소를 사설 IP로 설정
```bash
cd /Users/ago0528/Desktop/files/01_work/01_planning/01_vibecoding/ats/agent_qa_dev/backoffice/frontend
cp -n .env.example .env
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

## Backend Test (safe mode)
```bash
cd backoffice/backend
source .venv/bin/activate
export BACKOFFICE_DB_PATH=${BACKOFFICE_DB_PATH:-$(pwd)/backoffice_test.db}
export BACKOFFICE_ALLOW_DB_RESET=1
python -m pytest -q
```

> 백엔드 폴더에서는 `pnpm dev` 자체가 제공되지 않습니다. `pnpm` 관련 실행은 frontend 폴더로 이동해서 진행하세요.
