# 검증 평가 정책 (LLM-only)

작성일: 2026-02-21  
최종 개정: 2026-02-28  
버전: v0.3  
적용 범위: 에이전트 검증(`validation_runs`) 파이프라인

## 1) 평가 개요

- 각 run item은 **실행 결과 + LLM 평가**만으로 품질을 판단한다.
- Query/Run item의 Logic 평가(`logicEvaluation`)는 더 이상 사용하지 않는다.
- `run.mode`는 UI 실행 타입(REGISTERED/AD_HOC)과 별개이며, 이력 노출/집계에는 DB `run.mode`를 사용하지 않는다.

## 2) 단계별 판정 규칙

### 2.1 실행/Raw 단계

- 실행 오류(`error`)가 있으면 해당 항목은 실패 케이스로 분류한다.
- `responseTime`은 `latency_ms` 또는 `responseTimeSec`으로 저장한다.

### 2.2 LLM as a judge

- LLM 평가는 아래 요소를 기준으로 JSON 응답을 생성한다.
  - `metric_scores`: `{ metricName: score(1~5) }`
  - `total_score`: 1~5 실수
  - `comment`: 근거/판정 설명
  - `passed`(권장): true/false
- LLM 출력이 비정상(JSON 파싱 실패, 범위 초과)이면 해당 항목은 평가 실패로 기록하되 전체 파이프라인은 계속 진행한다.
- `passed`가 비어있거나 파싱되지 않으면 `total_score`로 PASS/FAIL을 보정한다.

## 3) 최종 판정 병합 규칙

- 실행 오류 존재: 최종 실패
- 그 외: LLM 판단 결과를 사용
  - `passed`가 있으면 이를 최종 판정 근거로 사용
  - `passed`가 없으면 `total_score` 임계치로 판단
- 기본 임계치: `total_score < 3.0` 이면 실패

## 4) KPI/대시보드 기준

- 노출 KPI:
  - 평균 응답시간(초)
  - 응답시간 P50/P95
  - LLM 평가율 (`llmEvaluation.status === DONE`)
  - LLM 평균 점수 (`llmEvaluation.totalScore` 평균)
- 제거 KPI:
  - `Logic PASS율`
  - `logicPassItems`, `logicPassRate`

## 5) 실패 패턴 집계 기준

- `failurePatterns`는 **오류(error) 발생 항목만 실패**로 집계한다.
- Logic FAIL 또는 Logic 관련 상태값은 실패 집계 기준에서 제외한다.

## 6) 단계적 제거 원칙

- DB 물리 구조는 이번 릴리즈에서 삭제하지 않는다.
  - `validation_logic_evaluations` 테이블
  - `validation_score_snapshots.logic_*` 컬럼
  - `validation_queries/validation_run_items`의 logic/context/target 관련 컬럼
- 위 항목은 **DB 잔존(미사용)** 상태로 유지하며, 후속 마이그레이션에서 물리 삭제를 검토한다.
