---
name: python-architect
description: Use this skill when designing or refactoring Python systems, module boundaries, data models, and test strategy. Trigger for requests like "구조 설계", "리팩터링 방향", "아키텍처 제안", or when implementation risks must be reduced before coding.
---

# Python Architect

## Goal
요구사항을 파이썬 구현 가능한 구조로 변환하고, 코드 변경 전에 아키텍처 리스크를 줄인다.

## When to use
- 새 기능 구현 전에 구조를 먼저 정해야 할 때
- 파일이 비대해져 모듈 분리가 필요할 때
- 타입/예외 처리/테스트 전략을 함께 설계해야 할 때

## Workflow
1. 요구사항을 기능/비기능으로 분리한다.
2. 제약(호환성, 성능, 운영 방식)을 확인한다.
3. 아키텍처 옵션 2~3개를 제시하고 트레이드오프를 적는다.
4. 선택안 기준으로 파일 구조와 책임 경계를 정의한다.
5. 데이터 모델, 에러 모델, 인터페이스 시그니처를 제시한다.
6. 테스트 전략(단위/통합/회귀)과 검증 순서를 제시한다.

## Output format
- `Architecture Decision`
- `Proposed File Changes`
- `Core Interfaces`
- `Risk & Mitigation`
- `Test Plan`

## Guardrails
- 구현 전에 "변경 범위"와 "비변경 범위"를 명시한다.
- 기존 코드 스타일/패턴을 우선 존중한다.
- 큰 리팩터링은 단계별 마이그레이션 계획으로 나눈다.
- 모호한 입력은 질문으로 확정한 뒤 진행한다.

## Checklist
- [ ] 책임 경계가 명확한가?
- [ ] 확장 포인트가 분리됐는가?
- [ ] 예외/실패 경로가 정의됐는가?
- [ ] 테스트 가능하게 설계됐는가?
