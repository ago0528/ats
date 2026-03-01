## 단일 프롬프트 기반 평가 운영 기준 (v1)

### 1) 평가 입력
- 단일 프롬프트 입력은 `queryText + expectedResult + rawPayload + peerExecutions + error + responseTimeSec + latencyMs + rawPayloadParseOk`를 사용한다.
- 규칙 파싱(`@check`, `accuracyChecks`, extractor fallback) 기반의 별도 정확성 엔진은 사용하지 않는다.
- `expectedResult`는 JSON 객체(예: `{"formType":"ACTION","actionType":"...","dataKey":"...","buttonKey":"..."}`) 형태를 권장하며, LLM이 rawPayload 산출물과 직접 비교한다.

### 2) 프롬프트/스키마 소스
- 평가 프롬프트는 DB `validation_eval_prompt_configs`의 `prompt_key=validation_scoring` current 값을 사용한다.
- 기본 템플릿은 `backoffice/backend/app/evaluation/validation_scoring_default_prompt.md`이다.
- 출력 스키마는 `backoffice/backend/app/evaluation/validation_scoring_output_schema.json`을 사용한다.
- metricScores 키는 아래 6개로 고정한다.
  - `intent`, `accuracy`, `consistency`, `latencySingle`, `latencyMulti`, `stability`

### 3) 점수 산정 원칙 (LLM-only)
- 6개 지표 점수는 모두 LLM 출력값을 그대로 저장한다.
- 서버는 점수 보정/보완/동기화(예: consistency 강제 공유, stability fallback)를 수행하지 않는다.
- consistency를 포함한 모든 지표는 item 단위 평가 결과를 그대로 기록한다.

### 4) total_score 산식
- `intent`, `accuracy`, `stability`는 항상 포함한다.
- `consistency`가 존재하면 함께 포함해 산술 평균을 계산한다.
- `latencySingle`, `latencyMulti`는 KPI 저장/표시용이며 total_score에는 포함하지 않는다.

### 5) 오류 처리
- OpenAI 응답이 strict schema를 만족하지 않으면 해당 row를 `DONE_WITH_LLM_ERROR`로 기록한다.
- 일부 row 실패가 발생해도 run 전체 평가는 계속 진행한다.
- 평가 Job 시작 시점의 프롬프트/버전 라벨을 스냅샷으로 고정하고, 해당 Job 전체 item에 동일 `prompt_version`을 저장한다.

### 6) UI/계약 표기
- consistency가 null이면 화면에는 `집계 없음`으로 표시한다.
- 공개 API 계약에서는 `llmEvalCriteria`, `appliedCriteria`를 노출하지 않는다.
