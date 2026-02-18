# AQB Backoffice

## Frontend Dev Server
```bash
cd /Users/ago0528/Desktop/files/01_work/01_planning/01_vibecoding/ats/agent_qa_dev/backoffice
pnpm dev
```

또는

```bash
pnpm --dir frontend dev
```

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
