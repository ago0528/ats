---
name: H.채용 solution scoring guide (v2)
description: Single-prompt scoring guide for validation runs
updatedDate: 26-02-26
---

# 채용에이전트 지표별 점수화 방식(v2)

## 핵심 원칙
- 평가는 단일 프롬프트 1회 호출로 수행한다.
- 입력은 `기대결과(expected_result) + rawPayload + peerExecutions`만 사용한다.
- 별도 규칙 파싱(`@check`, accuracyChecks) 절차는 사용하지 않는다.

## 출력 지표
- `intent`
- `accuracy`
- `consistency`
- `latencySingle`
- `latencyMulti`
- `stability`

## consistency 규칙
- 동일 query_id 실행이 2건 이상일 때만 점수를 사용한다.
- 그룹 내 row는 동일 consistency 값을 가진다.
- 단건 query_id는 consistency = `null`.

## total_score 규칙
- 포함: intent, accuracy, stability
- 조건부 포함: consistency(존재 시)
- 제외: latencySingle, latencyMulti

## 에러 처리
- strict schema 위반/파싱 실패 시 `DONE_WITH_LLM_ERROR`
- 해당 row 실패와 무관하게 다른 row 평가는 계속 진행
