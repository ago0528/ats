# GenericRunPage TypeScript 컴파일 오류

## 개요
- `backoffice/frontend/src/features/generic/GenericRunPage.tsx`에서 TypeScript 컴파일 에러 6건이 발생
- 주요 증상
  - `response`가 `undefined`일 수 있다는 경고(`TS18048`)
  - `GenericRunMeta`로의 잘못된 타입 단언 경고(`TS2352`, `TS2339`)

## 재현 경로
1. 프론트엔드 타입체크 실행
2. 명령어: `pnpm -C backoffice/frontend exec tsc -b --pretty false`
3. `src/features/generic/GenericRunPage.tsx`에서 6건의 타입 오류 발생 확인

## 재현 데이터
- 파일: `backoffice/frontend/src/features/generic/GenericRunPage.tsx`
- 오류 지점
  - 239, 240 라인: `response` optional 처리 미흡
  - 496 라인대: `rows` 기반 응답 객체를 `GenericRunMeta`로 강제 단언
- 오류 코드
  - `TS18048`, `TS2352`, `TS2339`

## 원인 추정
- `getRequestErrorMessage`에서 `error.response`가 optional인데, 이후 분기에서 `response`를 확정 타입으로 좁히지 못해 안전성 검사가 실패함
- CSV 실행 생성 API 응답(`runId`, `status`, `rows`)을 `GenericRunMeta`로 직접 단언하면서 필수 필드(`totalRows`) 누락과 타입 불일치가 발생함

## 조치
- `getRequestErrorMessage`에서 `response` 존재 여부를 먼저 확인하도록 가드 추가
- `response.data`를 객체로 처리할 때 `detail` 필드를 명시적으로 안전 캐스팅해 접근
- CSV 생성 응답을 `GenericRunMeta`로 단언하지 않고, API 응답 전용 타입(`runId`, `status`, `rows`)으로 분리
- `totalRows`를 별도 계산 후 `setRun` 시점에 `GenericRunMeta` 구조로 조립
- 후속 조치(추가 2건): `backoffice/frontend/src/main.tsx`에서 `.tsx`, `.ts` 확장자를 명시한 import를 확장자 없는 경로로 수정
- 재검증: `pnpm -C backoffice/frontend exec tsc -b --pretty false` 실행 시 전체 타입 오류 0건 확인

## 후속 이슈 정리
- 추가 오류 코드: `TS5097` 2건
- 파일: `backoffice/frontend/src/main.tsx`
  - `./app/AppLayout.tsx` -> `./app/AppLayout`
  - `./theme/theme.ts` -> `./theme/theme`
- 원인: `allowImportingTsExtensions` 비활성 상태에서 TypeScript 확장자 포함 import를 사용함

## 재발 방지
- 테스트 추가 여부
  - 타입 안정성 회귀 방지를 위해 프론트엔드 CI에 `tsc -b --pretty false` 고정 실행 권장
- 배포 게이트 업데이트 여부
  - 배포 전 타입체크 실패 시 머지 차단 규칙 적용 권장
