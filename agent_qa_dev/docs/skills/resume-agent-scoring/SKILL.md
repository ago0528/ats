---
name: resume-agent-scoring
description: Use when scoring 지원자 관리 에이전트 raw CSVs (Track 1/2/3) and generating a per-round, per-track markdown report.
---

# 지원자 관리 에이전트 Scoring Skill

## 목표
지원자 관리 에이전트(`resume_agent_*.csv`) 결과를 받아 다음 지표를 산출한다.
- 의도 충족
- 일관성
- 정확성
- 응답 속도(Track 1/2: 단일, Track 3: 복수)
- 안정성

**총 가중치 합산은 계산하지 않는다.**

---

## 적용 범위
- 대상: 지원자 관리 에이전트
- 데이터: `docs/test-result/resume_agent_*.csv`
- 전제: 동일 질문 세트를 최소 2회 실행(예: `1/1`, `2/1`)
- Track 정의
  - **Track 1**: 단일 필터 전수 테스트
  - **Track 2**: 열 기반 집계(성별/나이/등급 등)
  - **Track 3**: 복합 시나리오(최적화/분석형)

---

## 1) 입력 데이터 규격
필수 컬럼

- `Run ID`
- `Item ID`
- `Query ID`
- `Track`
- `질의`
- `기대결과`
- `카테고리`
- `방/반복`
- `응답`
- `오류`
- `LLM 상태`
- `LLM 점수`
- `LLM 코멘트`
- `Raw JSON`

`Raw JSON`은 문자열 JSON.

### Raw JSON 핵심 필드
- `assistantMessage`
- `dataUIList`
- `responseTimeSec`
- `error`

---

## 2) 라벨링 규칙(LLM 점수가 비어있을 때 사용)
`assistantMessage` 유무 + `dataUIList` 유무 + 오류/타임아웃 + 보완 질문 문구를 조합해 1문항 상태를 정의한다.

- `ok`
  - `오류` 또는 `raw.error` 없음
  - `assistantMessage` 존재 또는 `dataUIList` 존재
  - 보완 문구(선택/알려주기/주시면)가 없음
- `partial`
  - 응답은 있으나 사용자의 추가 입력/선택을 요구
  - 키워드 포함: `선택`, `선택해 주세요`, `알려주`, `주시면`, `원하시면`, `확인해 주세요`
- `error`
  - `오류` 또는 `raw.error` 비어있지 않음
- `empty`
  - `assistantMessage`와 `dataUIList`가 모두 비어있음

상태 우선순위: `error` > `empty` > `partial` > `ok`

---

## 3) 문항 점수 규칙

### 3-1. 의도 충족
- ok = 5
- partial = 4
- error/empty = 0

### 3-2. 정확성
- 기본적으로 의도 충족 점수와 동일 적용
  - ok = 5
  - partial = 4
  - error/empty = 0

### 3-3. 안정성
- ok/partial = 5
- error/empty = 0

### 3-4. 일관성
동일 `Query ID`의 회차 쌍(A/B)을 비교한다.

- pass/pass: 둘 다 ok 또는 partial
- fail/fail: 둘 다 error 또는 empty
- mismatch: 위 외

일관성 점수 = `5 × (both-pass + both-fail) / 대상 질의 수`

### 3-5. 응답 속도

Track 1,2는 단일 도구 루브릭, Track 3은 복수 도구 루브릭을 사용한다.

- 단일 루브릭(Track 1/2)
  - <=5초:5
  - 5~8초:4
  - 8~10초:3
  - 10~15초:2
  - 15~20초:1
  - >20초:0
- 복수 루브릭(Track 3)
  - <=20초:5
  - 20~30초:4
  - 30~40초:3
  - 40~50초:2
  - 50~60초:1
  - >60초:0

> 점수는 `평균 초`의 단순 정규화가 아니라 규칙 구간 매핑값이다.

---

## 4) 집계 규칙

### 4-1. 회차 집계
- 각 지표는 회차별 문항 평균으로 계산한다.
- 안정성은 정상(5) 비율 × 5
- 일관성은 동일 Query ID 쌍 계산

### 4-2. 세트 집계
- 회차별 결과를 평균하여 세트 산출.
- 정성/속도 모두 “평균 점수” 기준으로 제시.
- Track별도 별도 집계 가능.

### 4-3. 권장 표시 항목
- `전체 문항 수`, `Track 1/2/3` 개수
- 각 Track의 `평균 초(sec)` + `점수`
- Track3는 `복수 도구 속도`
- 점수 분포(Score bucket) 출력 권장

---

## 5) 최종 리포트 템플릿

```markdown
# 지원자 관리 에이전트 스코어링 요약
- 데이터: <파일명>
- 총 문항: <N>
- 회차: <1/1,2/1...>
- Track 분포: Track 1=<n>, Track 2=<n>, Track 3=<n>

## 1) 산출 기준
- 라벨링 규칙: LLM 점수 미기록 시 ok/partial/error/empty 휴리스틱
- 일관성: 동일 Query ID 회차쌍 기준
- 속도: Track 1/2 단일, Track 3 복수 루브릭

## 2) 지표별 점수
### 1. 의도 충족
- 1/2회차 + 세트 점수

### 2. 일관성
- Track별(가능 시) 둘 다 pass / 둘 다 fail / 차이

### 3. 정확성
- 1/2회차 + Track별 점수

### 4. 응답 속도
#### 1/2회차/세트(초+점수)
| 구분 | Track 1(초) | Track 1(점수) | Track 2(초) | Track 2(점수) | Track 3(초) | Track 3(점수) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1회차 |  |  |  |  |  |  |

#### 점수 분포
- Track1+2 분포 (단일)
- Track3 분포 (복수)

### 5. 안정성
- Track별/세트 안정성

## 3) 정성 인사이트
- 실패 질의 Top pattern
- Track별 취약영역
- 반복 재현 필요 질문
```

---

## 6) LLM 평가 프롬프트(복붙)

```text
너는 지원자 관리 에이전트 평가자다.

[규칙]
1) CSV의 각 행을 `Query ID`-`방/반복`로 매핑한다.
2) Raw JSON을 파싱하고 assistantMessage, dataUIList, responseTimeSec, error를 추출한다.
3) 오류/타임아웃이면 status=error
4) error/empty이 아니고 텍스트에 '선택/주시면/알려주/확인해 주세요' 등이 있으면 partial, 아니면 ok
5) 의도=ok/partial/error/empty를 5/4/0/0로 치환
6) 정확성은 의도와 동일치로 임시 산정
7) 안정성은 ok/partial=5, error/empty=0
8) 일관성은 동일 Query ID를 회차 간 비교, both-pass + both-fail 기준으로 계산
9) 속도는 Track별 룰 적용:
   - Track1/2: 단일 루브릭
   - Track3: 복수 루브릭
10) 회차별 후 세트로 집계. 총 가중치 합산은 하지 않는다.

[출력]
- 지표별 회차 점수, 세트 점수
- Track별 평균 초(sec) + 점수
- 점수 분포표(트랙별)
- 일관성 표(둘 다 pass/둘 다 fail/차이)
- 안정성 리스크 Top pattern
```

---

## 7) 운영 체크리스트
- [ ] Track 1/2/3 분포가 의도대로 매칭되었는지
- [ ] Raw JSON 파싱 실패율이 이상치인지
- [ ] LLM 정량 점수 존재 시 사용했는지, 미존재 시 휴리스틱 사용 사유 기록
- [ ] 일관성 쿼리 쌍 개수를 회차별로 확인
- [ ] Track3에서 60초 이상 구간이 누적되는지 확인
