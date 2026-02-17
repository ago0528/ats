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
python -m uvicorn app.main:app --reload --port 8000
```

> 백엔드 폴더에서는 `pnpm dev` 자체가 제공되지 않습니다. `pnpm` 관련 실행은 frontend 폴더로 이동해서 진행하세요.
