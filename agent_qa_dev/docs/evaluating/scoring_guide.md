---
name: H.채용 solution's agent scroing guide.
description: Use when evaluating H.채용 solution's agent response evaluating and generating markdown score reports.
updatedDate: 26-02-25
---

# 채용에이전트 지표별 점수화 방식(루브릭)

## 개요

### 채용에이전트 지표별 정의

| **지표명**               | **평가 기준**                                                | **평가 대상**                                                                |
| ------------------------ | ------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| **의도 충족**            | 사용자 의도에 맞는 에이전트의 커뮤니케이션(답변 메시지) 품질 | assistantMessage                                                             |
| **정확성**               | (기대 결과 대비) 기능 수행의 정합성                          | dataUIList, setting, filterType, 집계 값                                     |
| **일관성**               | 동일 질문 반복 실행 시, 의도와 산출물의 재현성               | assistantMessage 의도 일치율 + dataUIList 핵심 데이터 일치율 (5:5 비율 결합) |
| **응답 속도(기본)**      | 도구 단일 호출 시 에이전트 응답 시간                         | responseTimeSec, latency_ms(혹은 latencyClass=SINGLE)                        |
| **응답 속도(다중 도구)** | 도구 다중 호출 시 에이전트 응답 시간                         | responseTimeSec, latency_ms(혹은 latencyClass=MULTI)                         |
| **안정성**               | 서비스가 에러 발생 정도                                      | item.error, raw JSON 파싱 성공 여부, assistantMessage/dataUIList 존재 여부   |

## 지표별 점수화 방식

### 의도 충족 (intent_verdict)

| intent_verdict        | 점수 | 기준                                                     |
| --------------------- | ---- | -------------------------------------------------------- |
| PERFECT               | 5    | 동사/대상/범위 모두 일치, 메시지 즉시 이해                |
| GOOD                  | 4    | 핵심 일치, 표현이 다소 모호                               |
| PARTIAL               | 3    | 핵심은 인지되나 대상/범위가 애매                          |
| WEAK                  | 2    | 핵심 의도 일부만 반영, 오해 가능성 큼                     |
| RELATED_BUT_WRONG     | 1    | 관련 도메인은 맞지만 목적 불일치                          |
| FAILED                | 0    | 무관/무응답/실패                                          |

### 정확성 (pass ratio)

| 조건                                              | 점수 | 기준                                                          |
| ------------------------------------------------- | ---- | ------------------------------------------------------------- |
| 실행 오류/타임아웃/JSON 파싱 실패                  | 0    | 산출물을 신뢰할 수 없음                                       |
| 체크 없음(accuracyChecks 없음 + expected_result @check 없음) | 0    | 평가 불가                                                     |
| ratio = 1.0                                       | 5    | 모든 체크 통과                                                |
| ratio >= 0.75                                     | 4    | 대부분 체크 통과                                              |
| ratio >= 0.5                                      | 3    | 절반 이상 체크 통과                                           |
| ratio >= 0.25                                     | 2    | 일부 체크 통과                                                |
| 0 < ratio < 0.25                                  | 1    | 극소수 체크만 통과                                            |
| ratio = 0                                         | 0    | 모든 체크 실패                                                |

### 일관성 (반복 실행 재현성)

| 항목              | 값/정의                                                                                   |
| ----------------- | ----------------------------------------------------------------------------------------- |
| 평가 조건         | 동일 Query ID 반복 실행 N >= 2 (N < 2면 consistency = 0)                                  |
| ratioA            | assistantMessage의 `intent_label` mode 비율 (`ratioA = count(label==mode)/N`)             |
| intent_label      | ADD, UPDATE, DELETE, VIEW, MOVE, CLARIFY, ERROR, OTHER                                    |
| ratioB            | dataUIList 핵심 signature mode 비율 (`ratioB = count(signature==mode)/N`)                 |
| signature(핵심 키) | formType, actionType, planId, value.nodeId(존재 시), value.nodeType(존재 시), setting, filterType |
| 빈 dataUIList      | signature = EMPTY                                                                          |
| 점수 산출         | `consistency = ((ratioA + ratioB) / 2) * 5` (0~5 clamp)                                   |

### 응답 속도(기본) — 단일 도구 호출(SINGLE) 구간 점수

| 점수 | latencySec 기준               |
| ---- | ----------------------------- |
| 5    | latencySec <= 5               |
| 4    | 5 < latencySec <= 8           |
| 3    | 8 < latencySec <= 10          |
| 2    | 10 < latencySec <= 15         |
| 1    | 15 < latencySec <= 20         |
| 0    | latencySec > 20 또는 누락     |

### 응답 속도(다중 도구) — 멀티 도구 호출(MULTI) 구간 점수

| 점수 | latencySec 기준               |
| ---- | ----------------------------- |
| 5    | latencySec <= 20              |
| 4    | 20 < latencySec <= 30         |
| 3    | 30 < latencySec <= 40         |
| 2    | 40 < latencySec <= 50         |
| 1    | 50 < latencySec <= 60         |
| 0    | latencySec > 60 또는 누락     |

### 안정성 — 에러/파싱/응답 존재 기반(0 또는 5)

| 점수 | 기준                                  |
| ---- | ------------------------------------- |
| 5    | 에러 없음 + 파싱 성공 + 응답 존재      |
| 0    | 에러/타임아웃/파싱 실패/응답 부재      |

## 종합 점수(선택)

| 항목               | 가중치 | 근거                               |
| ------------------ | ------ | ---------------------------------- |
| 의도 충족 (1번)    | 20%    | 에이전트의 핵심 역할               |
| 일관성 (2번)       | 10%    | 신뢰도 지표이나 정확성과 일부 중복 |
| 정확성 (3번)       | 30%    | 가장 직접적인 품질 지표            |
| 응답 속도 (4, 5번) | 20%    | 사용자 체감에 직접 영향            |
| 안정성 (6번)       | 20%    | 서비스 운영의 기본 전제            |
