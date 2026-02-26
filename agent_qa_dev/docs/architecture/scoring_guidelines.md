## 단일 프롬프트 기반 평가 운영 기준 (v2)

### 1) 평가 입력
- 단일 프롬프트 입력은 `expected_result + rawPayload + peerExecutions`를 사용한다.
- 규칙 파싱(`@check`, `accuracyChecks`, extractor fallback) 기반의 별도 정확성 엔진은 사용하지 않는다.

### 2) 출력 스키마
- `docs/evaluating/prompt_for_scoring_output_schema.json`을 단일 기준 스키마로 사용한다.
- metricScores 키는 아래 6개로 고정한다.
  - `intent`, `accuracy`, `consistency`, `latencySingle`, `latencyMulti`, `stability`

### 3) consistency 확정 규칙
- 동일 `query_id` 실행이 2건 이상인 경우에만 consistency 값을 사용한다.
- 동일 `query_id` 그룹의 모든 row는 동일 consistency 값을 저장한다.
- 그룹 크기 1건이면 consistency는 `null`이다.

### 4) total_score 산식
- `intent`, `accuracy`, `stability`는 항상 포함한다.
- `consistency`가 존재하면 함께 포함해 산술 평균을 계산한다.
- `latencySingle`, `latencyMulti`는 KPI 저장/표시용이며 total_score에는 포함하지 않는다.

### 5) 오류 처리
- OpenAI 응답이 strict schema를 만족하지 않으면 해당 row를 `DONE_WITH_LLM_ERROR`로 기록한다.
- 일부 row 실패가 발생해도 run 전체 평가는 계속 진행한다.

### 6) UI/계약 표기
- consistency가 null이면 화면에는 `집계 없음`으로 표시한다.
- 공개 API 계약에서는 `llmEvalCriteria`, `appliedCriteria`를 노출하지 않는다.
