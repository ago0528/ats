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
pnpm --dir backoffice/frontend install
pnpm --dir backoffice/frontend dev --host 0.0.0.0 --port 5173
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
  - 공식 로그인 세션 상태 뱃지/수동 새로고침 버튼/로그아웃 버튼
  - (옵션) 레거시 cURL token parser (`VITE_ENABLE_LEGACY_CURL_LOGIN=true`일 때만 노출)
- 로그인 페이지는 카드 패딩/입력 높이/모바일 간격을 표준화한 레이아웃을 사용합니다.
- (옵션) 로컬 개발 백도어키 로그인 섹션 (`VITE_ENABLE_LOCAL_DEV_BACKDOOR_LOGIN=true` + localhost 접속일 때만 노출)

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
- `VITE_ENABLE_LEGACY_CURL_LOGIN` (default: `false`)
  - `true`일 때에만 cURL 파싱 fallback UI를 노출
- `VITE_ENABLE_LOCAL_DEV_BACKDOOR_LOGIN` (default: `false`)
  - `true`일 때 `/login` 하단에 백도어키 입력 UI를 노출
  - 프론트는 `localhost/127.0.0.1/::1` 접속에서만 해당 UI를 표시
- Font: Pretendard (loaded in frontend global style)

## Troubleshooting

- 로그인 직후 `/login`으로 다시 돌아오면 백엔드 CORS/Cookie 설정을 확인하세요.
  - `BACKOFFICE_ALLOWED_ORIGINS`에 현재 프론트 origin(`http://localhost:5173`, `http://10.x.x.x:5173` 등)이 포함되어야 합니다.
  - `BACKOFFICE_ALLOWED_ORIGINS`를 비우면 백엔드가 `localhost/127.0.0.1` + 서버의 사설 IP(`:5173/:4173`)를 자동 허용합니다.
  - `BACKOFFICE_COOKIE_SECURE=true`인 경우 HTTPS 환경에서만 쿠키가 저장됩니다.
- 자동 갱신이 실패하면 헤더의 `세션 새로고침`으로 즉시 재시도할 수 있습니다.
- 백도어키 버튼이 안 보이면 아래를 점검하세요.
  - 프론트 `.env`의 `VITE_ENABLE_LOCAL_DEV_BACKDOOR_LOGIN=true`
  - 현재 접속 호스트가 `localhost`, `127.0.0.1`, `::1` 중 하나인지 확인
