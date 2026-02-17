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
python -m pytest -q
```

## Notes
- Runtime secrets(bearer/cms/mrs/openaiKey)는 DB에 저장하지 않습니다.
- DB 기본 경로는 `backoffice/backend/backoffice.db`입니다.
- 화면/알림에는 `/api/v1/version`으로 조회한 앱 버전(기본 `0.1.0`)이 표시됩니다.
