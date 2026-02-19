# AQB Backoffice Frontend

## Install & Run
```bash
cd /Users/ago0528/Desktop/files/01_work/01_planning/01_vibecoding/ats/agent_qa_dev/backoffice/frontend
pnpm install
pnpm dev --host 0.0.0.0 --port 5173
```

`backend/` 폴더에서 `pnpm dev`를 실행하면 `Command "dev" not found`가 발생합니다.
프론트엔드는 항상 `backoffice/frontend` 디렉터리에서 실행하거나, 상위 경로에서 다음처럼 실행하세요.
```bash
pnpm --dir backoffice/frontend dev --host 0.0.0.0 --port 5173
pnpm --dir backoffice/frontend install
```

사내 동일 네트워크에서 접속할 때는 서버 실행 PC 사설 IP를 사용합니다.

- Frontend: `http://<서버PC사설IP>:5173`

디버깅에서 `@ant-design/icons` import 에러가 나면, 로컬 node_modules가 깨진 상태일 수 있습니다.
아래 순서로 재설치하고 캐시를 정리하세요.
```bash
rm -rf node_modules
pnpm install
```

## UI notes
- PC desktop layout is implemented as **top global nav + left sidebar + main content**.
- Header includes:
  - environment selector (dev / st2 / st / pr)
  - semantic app version badge
  - cURL token parser modal (`cURL 토큰 파싱`) for parsing and auto-filling tokens

## Note
- `BACKOFFICE` API endpoint should be started with matching `/api/v1` prefix.
- 로컬 전용 예시: `http://localhost:8000/api/v1`
- 사내망 공유 예시: `http://<서버PC사설IP>:8000/api/v1`

## Build
```bash
pnpm build
```

## Env
- `VITE_API_BASE_URL` (default: `http://localhost:8000/api/v1`)
- 사내망 공유 시 `VITE_API_BASE_URL=http://<서버PC사설IP>:8000/api/v1` 로 설정
- Font: Pretendard (loaded in frontend global style)
