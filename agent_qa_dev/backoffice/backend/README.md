# AQB Backoffice Backend

## Setup (venv)
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install fastapi uvicorn sqlalchemy pydantic python-multipart aiohttp httpx pandas openpyxl pytest
```

### Optional: version override (SemVer)
```bash
export BACKOFFICE_VERSION=0.2.0
```

## Run
```bash
source .venv/bin/activate
export BACKOFFICE_VERSION=${BACKOFFICE_VERSION:-0.1.0}
export BACKOFFICE_DB_PATH=${BACKOFFICE_DB_PATH:-$(pwd)/backoffice.db}
python -m uvicorn app.main:app --reload --port 8000
```

프론트엔드 개발 서버를 실행하려면 backend 디렉터리에서 `pnpm dev`를 실행하지 마세요.
`backoffice/frontend` 폴더에서 다음을 실행하세요.
```bash
cd ../frontend
pnpm dev
```
또는
```bash
pnpm --dir ../frontend dev
```

## Test
```bash
source .venv/bin/activate
export BACKOFFICE_DB_PATH=${BACKOFFICE_DB_PATH:-$(pwd)/backoffice_test.db}
export BACKOFFICE_ALLOW_DB_RESET=1
python -m pytest -q
```

## Safe DB reset (test DB only)
```bash
source .venv/bin/activate
export BACKOFFICE_DB_PATH=${BACKOFFICE_DB_PATH:-$(pwd)/backoffice_test.db}
python scripts/reset_db.py --allow-db-reset
```

## Notes
- Runtime secrets(bearer/cms/mrs/openaiKey)는 DB에 저장하지 않습니다.
- DB 기본 경로는 `backoffice/backend/backoffice.db`입니다.
- 백엔드를 직접 실행할 때는 `BACKOFFICE_DB_PATH`를 절대경로로 고정하는 것을 권장합니다.
- 테스트/리셋은 `*_test` DB에서만 허용되며, 리셋 시 `BACKOFFICE_ALLOW_DB_RESET=1` 또는 `--allow-db-reset` 명시가 필요합니다.
- 화면/알림에는 `/api/v1/version`으로 조회한 앱 버전(기본 `0.1.0`)이 표시됩니다.
