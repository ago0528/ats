# 검증 평가 정책 (LLM as a judge)

작성일: 2026-02-21  
최종 개정: 2026-02-21  
버전: v0.2  
적용 범위: 에이전트 검증(`validation_runs`) 파이프라인

## 1) 평가 개요

- 각 응답(run item)은 **실행 결과 + 규칙(Logic) + LLM 평가**를 결합해 최종 품질을 판단한다.
- 현재는 `평가 실행`에서 run-level 집계는 `validation_score_snapshots`를 기준으로 계산한다.
- `run.mode`는 UI 실행 타입(REGISTERED/AD_HOC)와 구분되는 개념이며, 이력 노출/집계에는 DB의 `run.mode`를 사용하지 않는다.

## 2) 단계별 판정 규칙

### 2.1 실행/Raw 단계

- 실행 오류(`error`)가 있으면 품질 판단은 실패 케이스로 먼저 분류한다.
- `responseTime`은 `latency_ms` 또는 `responseTimeSec`로 저장한다.

### 2.2 Logic 단계

- 로직 조건(`logicEvaluation.result`)이 존재하면 우선 적용한다.
- `FAIL`이면 최종 판단은 실패로 고정한다.
- `PASS/SKIPPED`는 다음 단계로 진행한다.

### 2.3 LLM as a judge

- LLM 평가는 아래 필수 요소를 기준으로 JSON 응답을 요구한다.
  - `metric_scores`: `{ metricName: score(1~5) }`
  - `total_score`: 1~5 실수
  - `comment`: 근거/판정 설명
  - `passed`(권장): true/false
- LLM 출력이 비정상(JSON 파싱 실패, 범위 초과)이면 해당 run item은 평가 실패로 기록하고 진행을 막지 않는다.
- `passed`가 비어있거나 파싱되지 않으면 `total_score`로 PASS/FAIL을 보정한다.

## 3) 병합 정책

- 실행오류 존재: 최종 실패
- `logicEvaluation.result === FAIL`: 최종 실패
- 그 외: LLM 판단 우선 사용
  - `passed`가 있으면 이를 최종 판정 근거로 사용
  - `passed` 부재 시 `total_score`가 정책 임계치보다 낮으면 실패로 판단
- 기본 임계치: `total_score < 3.0` 이면 실패
- `logicEvaluation.result`가 `FAIL`일 때는 LLM 판정과 무관하게 최종 실패
- `logicEvaluation.result`가 `FAIL`이면 LLM 평가는 `SKIPPED_LOGIC_FAIL` 또는 상태 메시지로 분기 처리 가능.
- `passed=true`/`false`와 `total_score`는 동시에 기록되어 집계 신뢰성을 높인다.

최종 점수 산출은 다음과 같이 제안합니다.

- `LLM 판단 점수`:
  - `passed=true`: `5.0`
  - `passed=false`: `1.0`
  - `passed` 미지정: `total_score` 그대로 반영
- `항목 pass/fail`:
  - `logicEvaluation.result == FAIL`: fail(hard-fail)
  - 그 외: `passed=true` 또는 (`passed` 미지정 + `total_score >= 3.0`)

## 4) 이력 상세에 노출할 집계 KPI 제안

다음 항목을 우선 노출한다.

- `평균 응답시간(초)` = 전체 실행 응답 시간 평균(`responseTimeSec`)
- `응답시간 P50(초)` = 응답시간 분포 50% 분위수
- `응답시간 P95(초)` = 응답시간 분포 95% 분위수
- `LLM PASS율` = `llmEvaluation.status === DONE` + (`passed=true` 또는 `total_score >= 3.0`) 비율
- `LLM 평가율` = `llmEvaluation.status === DONE` 비율
- `LLM 평균 점수` = `llmEvaluation.totalScore`의 DONE 건 평균
- `Logic PASS율` = `logicEvaluation.result === PASS` 비율

## 5) 추적/변경 관리

- 기준 변경 시 문서 버전/시행일을 이력 메모에 남긴다.
- 정책 변경이 반영되면 프롬프트/파서/집계 산식과 점검 항목을 함께 갱신한다.
