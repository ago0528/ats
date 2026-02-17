---
name: aqb-scoring
description: Use when implementing AQB scoring rules, rubric evaluation, or score summaries for this project.
---

# AQB Scoring

## Overview
이 스킬은 AQB v1.2.0 기준의 점수 산출과 요약 리포트를 구현할 때 사용한다.

## When to Use
- 점수 계산 로직을 구현하거나 수정해야 할 때
- 스코어 요약 리포트를 백엔드 또는 프론트에 표시해야 할 때

## Metric Rules
- 모든 지표는 0~5점 범위다.
- 지표: 의도 충족, 일관성, 정확성, 응답 속도, 안정성
- 종합 점수: semantic*0.2 + consistency*0.1 + accuracy*0.3 + speed*0.2 + stability*0.2
- TTFT는 PASS/FAIL만 기록하고 종합 점수에는 반영하지 않는다.

## Manual Review Flags
- 의도 충족 <= 2
- 정확성 <= 2
- 안정성 <= 2
- 종합 점수 <= 2.5
- 응답 중 하나라도 에러 또는 빈 응답

## Speed Scoring
- 단일 도구 호출 기준: 5<=5s, 4:5~8s, 3:8~10s, 2:10~15s, 1:15~20s, 0:>20s
- 복수 도구 호출 기준: 지원자 관리 5<=20s, 4:20~30s, 3:30~40s, 2:40~50s, 1:50~60s, 0:>60s
- 복수 도구 호출 기준(그 외): 5<=10s, 4:10~15s, 3:15~20s, 2:20~30s, 1:30~45s, 0:>45s

## Consistency Scoring
- 기본 3회 호출 결과를 기준으로 한다.
- 3회 모두 숫자+결론 일치 시 5점
- 3회 결론 일치, 숫자 허용오차(기본 ±1%) 내는 4점
- 3회 중 2회 숫자+결론 일치 3점
- 3회 중 2회 결론만 일치 2점
- 결론 유사하나 숫자 매번 다름 1점
- 모두 상이 또는 평가 불가 0점

## Accuracy Scoring
- 실행/이동 에이전트는 datakey 매칭 정확도로 평가한다.
- 지원자 관리 질의는 필터 정확성과 수치 정확도를 함께 본다.
