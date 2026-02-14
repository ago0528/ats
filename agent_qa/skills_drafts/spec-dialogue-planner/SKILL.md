---
name: spec-dialogue-planner
description: Use this skill when the user wants to refine ideas through conversation and turn ambiguous requests into executable specifications. Trigger for planning, requirement clarification, policy definition, and decision logging.
---

# Spec Dialogue Planner

## Goal
대화 기반으로 모호한 요구를 실행 가능한 명세로 구체화한다.

## When to use
- "일단 논의부터", "요건부터 정리" 같은 요청
- 정책/규칙/평가 기준을 먼저 확정해야 할 때
- 구현 전에 의사결정 로그가 필요한 때

## Workflow
1. 목표/성공기준/제약을 3줄로 정리한다.
2. 미결 쟁점을 목록화하고 우선순위를 매긴다.
3. 질문은 한 번에 1~3개로 제한해 합의를 만든다.
4. 각 합의사항을 `결정됨/미결/가정`으로 분류한다.
5. 최종 명세를 버전 단위로 정리한다.
6. 구현자가 바로 작업 가능한 체크리스트로 변환한다.

## Output format
- `Scope`
- `Decisions`
- `Open Questions`
- `Assumptions`
- `Spec vX.Y.Z`
- `Implementation Checklist`

## Guardrails
- 합의되지 않은 내용은 구현 사실처럼 단정하지 않는다.
- 상대가 확인하기 쉬운 짧은 문장과 표를 우선한다.
- 정책 변경 시 이전 결정과 변경 사유를 함께 남긴다.
- 상대가 혼란스러워하면 옵션 수를 줄여 재질문한다.

## Checklist
- [ ] 성공 기준이 수치/행동으로 정의됐는가?
- [ ] 미결 이슈가 분리됐는가?
- [ ] 명세가 구현 가능 수준인가?
- [ ] 변경 이력이 추적 가능한가?
