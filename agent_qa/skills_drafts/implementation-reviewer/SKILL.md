---
name: implementation-reviewer
description: Use this skill to verify whether implementation matches requirements, detect regressions, and prepare release-readiness checks. Trigger for review requests, QA validation, and pre-release confidence checks.
---

# Implementation Reviewer

## Goal
구현 결과가 요구사항을 충족하는지 검증하고, 회귀/리스크를 식별해 릴리즈 신뢰도를 높인다.

## When to use
- "요구사항 반영 확인", "리뷰", "검증" 요청
- 수정 후 회귀 위험이 있는 변경
- 배포 전 점검이 필요한 상황

## Workflow
1. 요구사항 문서를 기준선으로 잠근다.
2. 구현 변경점을 파일/행 단위로 매핑한다.
3. `충족/부분충족/미충족` 판정표를 만든다.
4. 기능 리스크와 데이터 리스크를 분리한다.
5. 테스트 공백을 우선순위로 제시한다.
6. 재현 가능한 검증 가이드를 만든다.

## Output format
- `Findings (Severity 순)`
- `Requirement Coverage Matrix`
- `Residual Risks`
- `Test Gaps`
- `Validation Guide`

## Guardrails
- 요약보다 결함/리스크를 먼저 제시한다.
- 판정 근거는 파일 경로와 함께 남긴다.
- 추정은 추정으로 명시한다.
- 테스트 미실행이면 명확히 고지한다.

## Checklist
- [ ] 요구사항 대비 누락 항목이 없는가?
- [ ] 리스크가 우선순위화됐는가?
- [ ] 검증 절차가 재현 가능한가?
- [ ] 배포 전 필수 확인 항목이 정리됐는가?
