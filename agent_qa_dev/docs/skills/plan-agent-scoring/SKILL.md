---
name: plan-agent-scoring
description: Use when scoring 실행 에이전트(plan_agent) raw CSV results and generating a 0~5 markdown score report.
---

# 실행 에이전트 Scoring Skill

## 목표
`plan_agent_*.csv` raw 결과를 받아 회차별/세트별 성능을 0~5 척도로 산출한다.

- 의도 충족
- 정확성
- 일관성
- 응답 속도(단일 도구)
- 안정성

**총 가중치 합산은 산출하지 않는다.**

---

## 적용 범위
- 대상: 실행 에이전트(`plan_agent`)
- 입력: `docs/test-result/plan_agent_*.csv`
- 전제: 동일 Query ID가 최소 2회차(예: `1/1`, `2/1`) 실행됨
- 출력: 마크다운 리포트(회차별·세트별 지표 + 인사이트)

---

## 1) 입력 데이터 규격
필수 컬럼

- `Run ID`
- `Item ID`
- `Query ID`
- `질의`
- `기대결과`
- `카테고리`
- `방/반복`
- `오류`
- `LLM 상태`
- `LLM 점수`
- `LLM 코멘트`
- `Raw JSON`

`Raw JSON`은 문자열 JSON.

### Raw JSON 핵심 필드
- `assistantMessage`
- `dataUIList[*].uiValue`
- `responseTimeSec`
- `error`
- `executionProcesses`, `worker` (보조)

---

## 2) 체크리스트 기반 점수 규칙

`기대결과(F)`와 `Raw JSON`을 비교해 문항 점수를 부여한다.

### 2-1. 체크 항목 파싱 (F)
각 행의 `기대결과` 문자열에서 다음을 추출한다.

- `assistantMessage` 키워드(예: `"합격자 결정 기준"`)
- `formType`(예: `SELECT`, `ACTION`)
- `multiSelectAllowYn`(true/false)
- `actionType`
- `value.dataKey`
- `value.buttonKey`

### 2-2. Raw 판정
- `error` 존재 OR `Raw JSON` 파싱 실패 → 즉시 0점
- `assistantMessage`와 `dataUIList`가 모두 비어있음 → 0점
- 그 외: 각 체크 항목 pass/fail 계산

### 2-3. 0~5 변환(의도 충족·정확성 공통)

`pass_ratio = pass_count / check_count`

- 1.00 → 5
- 0.75 ~ <1.00 → 4
- 0.50 ~ <0.75 → 3
- 0.25 ~ <0.50 → 2
- 0.01 ~ <0.25 → 1
- 0.00 → 0

정확성은 의도 충족과 동일 체크셋/변환식을 사용한다.

### 2-4. 안정성
- 점수 1~5: **5**
- 점수 0: **0**

### 2-5. 일관성
같은 `Query ID`의 `1/1`/`2/1` 점수를 비교한다.

- both-pass: 둘 다 3점 이상
- both-fail: 둘 다 0~2점
- 불일치: 위 조건 외

`일관성 = 5 × (both-pass + both-fail) / QueryID_개수`

### 2-6. 응답 속도
`plan_agent`는 단일 도구 기반이므로 단일 루브릭만 사용한다.

- <=5초: 5
- 5~8초: 4
- 8~10초: 3
- 10~15초: 2
- 15~20초: 1
- >20초: 0

점수는 평균 `responseTimeSec`의 구간 변환값이다.

---

## 3) 집계 규칙

- 문항 점수는 회차별 평균으로 집계
- 세트 점수는 회차별 점수 평균
- 안정성은 정규화된 평균(문항점수 5/0 기준)
- 일관성은 `Query ID` 쌍 비교 규칙 적용

---

## 4) 출력 템플릿(마크다운)

```markdown
# 실행 에이전트 스코어링 리포트
- 데이터: <파일명>
- 총 항목: <N>
- 실행: 1/1, 2/1

## 산출 기준
- 의도/정확성: F 기대조건 + R 체크패스율 0~5 매핑
- 안정성: error/empty 0점
- 일관성: same-pass/fail(3점이상/미만) 기준
- 속도: 단일 루브릭(responseTimeSec)

## 지표별 점수
1) 의도 충족 — 1/1: x.xx, 2/1: x.xx, 세트: x.xx
2) 정확성 — 1/1: x.xx, 2/1: x.xx, 세트: x.xx
3) 일관성 — x.xx
4) 응답 속도 (단일) — 1/1: <sec>초 / <pt>, 2/1: <sec>초 / <pt>, 세트: <sec>초 / <pt>
5) 안정성 — x.xx

## 분포/첨언
- 0~5 점수 분포
- 속도 분포
- 안정성 실패(에러) 패턴
- 정성 인사이트 Top 패턴
```

---

## 5) LLM 평가 프롬프트(복붙)

```text
너는 실행 에이전트(plan_agent) 평가자다.
1) 각 행을 Query ID와 방/반복(1/1,2/1)로 매핑한다.
2) Raw JSON에서 assistantMessage, dataUIList[*].uiValue, responseTimeSec, error를 파싱한다.
3) 기대결과(F)에서 formType/actionType/dataKey/buttonKey/multiSelectAllowYn/assistant 키워드를 체크리스트로 추출한다.
4) error 또는 assistantMessage+dataUIList 모두 비어있으면 0점.
5) 각 체크리스트 pass 비율로 0~5 점수화:
   - 1.00:5, 0.75~<1:4, 0.5~<0.75:3, 0.25~<0.5:2, 0~<0.25:1, 0:0
6) 의도 충족/정확성 모두 동일 산식 적용.
7) 응답 속도는 단일 루브릭(<=5, <=8, <=10, <=15, <=20, >20)으로 점수화.
8) Query ID 쌍으로 일관성 계산(3점 이상 = pass, 0~2 = fail).
9) 1/1, 2/1, 세트로 출력하고 총 가중치 합계는 계산하지 않는다.
10) 안정성은 0점이 실패, 그 외 정상으로 처리.
```

---

## 6) 체크리스트(운영)
- [ ] Query ID-방/반복 매핑이 깨지지 않았는지 확인
- [ ] LLM 점수 미기록 시 F+R 휴리스틱이 일관되게 적용되는지 확인
- [ ] 0/1/2점 구간의 오탐이 과도한지 패턴 분석
- [ ] 속도 분포(특히 2~3점) 상위 패턴 추적
- [ ] 안정성 실패가 1% 이상이면 수집/파싱 경로 점검
