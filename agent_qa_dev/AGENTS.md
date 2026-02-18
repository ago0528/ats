# AGENTS.md

> 웹 개발 운영 규칙 엔트리포인트 (Source of Truth)

이 파일이 프로젝트 운영 규칙의 기준 문서다.

## 1) 빠른 구조 확인

- 전체 구조: `docs/architecture/project-structure.md`
- 프론트 IA: `docs/architecture/backoffice-frontend-information-architecture.md`
- 스킬 인덱스: `AGENTS.md`의 `4) @skills 인덱스 (docs/skills)` 섹션

구조가 실제 코드와 다르면 먼저 위 문서를 갱신한 뒤 개발을 진행한다.

## 2) 웹 개발 기본 원칙

- 페이지(`features/*/*Page.tsx`)는 조합/오케스트레이션 역할만 담당한다.
- 비즈니스 로직은 `hooks/`, UI 블록은 `components/`로 분리한다.
- 공통 유틸은 `backoffice/frontend/src/shared/utils`를 우선 재사용한다.
- 공통 UI 패턴은 `backoffice/frontend/src/components/common`을 우선 재사용한다.
- 상태 관리는 기본적으로 `useState/useEffect + custom hooks`를 유지한다.
- 리팩토링 시 UI/동작/문구를 임의 변경하지 않는다.
- 백엔드 API 계약(엔드포인트, 요청/응답 시그니처)을 프론트에서 임의 변경하지 않는다.
- `.js` 레거시는 명시 요청 없이는 수정하지 않고 `.ts/.tsx` 기준으로 작업한다.
- 구조 변경 시 관련 문서(`docs/architecture/*`, `docs/troubleshooting/*`)를 함께 갱신한다.

## 3) 작업 대상 경로

- 프론트엔드: `backoffice/frontend`
- 백엔드: `backoffice/backend`
- 문서: `docs`

아래 경로는 벤더/외부 소스 성격이 강하므로 명시 요청 없이는 수정하지 않는다.

- `ant-design`
- `ant-design-icons`
- `langfuse`

## 4) @skills 인덱스 (docs/skills)

문서/설계/구현 전, 작업 목적에 맞는 스킬을 `docs/skills/*/SKILL.md`에서 먼저 선택해 사용한다.

사용 가능한 스킬 목록:

- `docs/skills/aqb-scoring/SKILL.md`
- `docs/skills/backoffice-backend-api/SKILL.md`
- `docs/skills/backoffice-frontend-antd/SKILL.md`
- `docs/skills/backoffice-quality-review/SKILL.md`
- `docs/skills/brainstorming/SKILL.md`
- `docs/skills/dispatching-parallel-agents/SKILL.md`
- `docs/skills/executing-plans/SKILL.md`
- `docs/skills/finishing-a-development-branch/SKILL.md`
- `docs/skills/receiving-code-review/SKILL.md`
- `docs/skills/requesting-code-review/SKILL.md`
- `docs/skills/subagent-driven-development/SKILL.md`
- `docs/skills/systematic-debugging/SKILL.md`
- `docs/skills/test-driven-development/SKILL.md`
- `docs/skills/using-git-worktrees/SKILL.md`
- `docs/skills/using-superpowers/SKILL.md`
- `docs/skills/verification-before-completion/SKILL.md`
- `docs/skills/writing-plans/SKILL.md`
- `docs/skills/writing-skills/SKILL.md`
- `docs/skills/worktree-merge-release/SKILL.md`

선택 규칙:

- 작업 시작 전 관련 스킬의 체크리스트를 먼저 읽는다.
- 여러 스킬이 겹치면 구현 스킬 1개 + 검증 스킬 1개를 우선 조합한다.
- 코드/구조가 변경되면 스킬 결과물(문서/테스트/리뷰 메모)까지 함께 반영한다.

## 5) 최소 품질 게이트

프론트엔드 변경 시 아래 명령을 통과해야 한다.

- `pnpm -C backoffice/frontend test`
- `pnpm -C backoffice/frontend build`

백엔드 로직 변경 시 관련 테스트를 반드시 실행하고, 실패 시 원인/조치 내용을 `docs/troubleshooting/incidents/`에 남긴다.
