# 질의 실행 동작 미동작

## 개요
- 백오피스 에이전트 검증 메뉴에서 CSV 업로드 후 `1단계 질의 실행` 버튼이 반응하지 않거나 결과가 즉시 반영되지 않는 증상

## 재현 경로
1. cURL 토큰 파싱으로 `bearer`, `cms`, `mrs`를 채운다.
2. `Generic`(에이전트 검증) 메뉴에서 CSV 업로드 후 `검증 실행 생성` 실행
3. `1단계 질의 실행` 버튼 클릭

## 재현 데이터
- 환경: `dev`
- 업로드 질의 예시: `[{\"질의\":\"테스트\"}]`

## 원인 추정
- 실행 버튼 disabled 조건(`runId`/상태) 또는 실행 API 호출 및 폴링 경로 불일치 가능성

## 조치
- `backoffice/frontend/src/features/generic/GenericRunPage.tsx`의 실행/평가 흐름 재점검
- API 스펙(`POST /generic-runs/{runId}/execute`) 호출 시 런타임 토큰 주입 여부 확인
- 결과 조회/상태 폴링 경로 보강 및 실패 시 사용자 메시지 표시

## 재발 방지
- 백엔드/프론트 단위 테스트로 `execute` 트리거 및 결과 폴링 경로 고정
- `playwright` e2e 흐름으로 실행 버튼 동작 자동 검증
