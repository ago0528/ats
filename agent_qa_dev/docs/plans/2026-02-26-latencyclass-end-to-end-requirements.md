# latencyClass End-to-End 반영 요구사항 (후속 작업용)

## 1. 목적
- `latencyClass(SINGLE|MULTI)`를 질의 관리부터 run 실행/평가/화면까지 일관되게 반영한다.
- 현재처럼 일부 경로(대량 업로드)에서만 입력되고 평가 입력 payload에 직접 연결되지 않는 상태를 해소한다.

## 2. 현재 이슈
- 질의 등록/수정 폼에서는 `latencyClass`를 직접 입력/수정할 수 없다.
- run item snapshot에 `latencyClass` 전용 필드가 없어 실행 시점의 분류가 명시적으로 고정되지 않는다.
- 평가 입력(`evaluation_input`)은 `expectedResult + rawPayload + peerExecutions` 중심이며 `latencyClass`가 명시 필드로 전달되지 않는다.
- 결과 탭의 `SINGLE/MULTI/UNCLASSIFIED` 표시는 LLM metric 출력에 의존하며, 사용자 지정 분류와의 추적성이 약하다.

## 3. 요구사항
### 3-1. 질의 관리(UI/API/DB)
- 질의 등록/수정 UI에 `latencyClass` 필드 추가(옵션: `SINGLE|MULTI|미지정`).
- `/queries` create/update/list 계약에 `latencyClass` 노출/저장 반영.
- CSV 대량 업로드/대량 수정 계약에 `latencyClass` 일관 반영(기존 템플릿 호환 유지).

### 3-2. run snapshot
- run 생성 시 query의 `latencyClass`를 run item snapshot으로 복사한다.
- run item 응답(`/validation-runs/{run_id}/items`)에 snapshot된 `latencyClass`를 포함한다.
- rerun/clone 시에도 snapshot이 보존되게 한다.

### 3-3. 평가 입력 payload
- `validation_evaluate_job`의 `evaluation_input_json`에 row의 snapshot `latencyClass`를 명시 포함한다.
- 프롬프트 문서(`prompt_for_scoring.txt`)에 `latencyClass` 입력 필드와 해석 규칙을 추가한다.
- 출력 스키마는 기존(`latencySingle`, `latencyMulti`) 유지하되, `latencyClass`와의 정합 규칙을 문서화한다.

### 3-4. 화면/집계
- 결과 탭과 대시보드에서 사용자 입력 `latencyClass`와 LLM 산출 점수를 함께 추적 가능하게 표시한다.
- `UNCLASSIFIED` 정의를 명확히 분리:
  - 사용자 미지정
  - LLM 산출 불일치/미산출
- 필터에 “사용자 지정 latencyClass 기준”과 “LLM 산출 기준”을 구분 제공한다.

## 4. 비범위
- 속도 점수 임계치(0~5 구간) 자체를 바꾸는 정책 변경.
- 기존 run 과거 데이터에 대한 전수 재평가(필요 시 별도 배치로 분리).

## 5. 인수 기준
- 질의 등록/수정, CSV 업로드/수정, API 응답에서 `latencyClass`를 일관 확인 가능하다.
- run item drawer에서 snapshot latencyClass를 확인 가능하다.
- 평가 입력 payload에 `latencyClass`가 포함된다.
- 결과 탭 필터에서 사용자 지정 latencyClass와 LLM 기준 분류를 각각 적용할 수 있다.
- 기존 데이터(필드 없음)도 깨지지 않고 `미지정`으로 안전 표시된다.
