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
- 컴포넌트를 새로 만들 때는 우선 `backoffice/frontend/src/components/common` 및 기존 `features` 내 지역 공통 컴포넌트에 해당 기능이 있는지 먼저 확인해 재사용한다.
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
스킬 인덱스는 `docs/skills` 실디렉터리와 동기화한다. (파일 추가/삭제 시 이 섹션도 함께 갱신)

### 4-1) 평가·리포트 생성 스킬

- `docs/skills/url-agent-move-scoring/SKILL.md`: 이동 에이전트 raw CSV(`url_agent_*.csv`)를 반복 실행 기준으로 평가하고 마크다운 리포트를 생성한다.
- `docs/skills/resume-agent-scoring/SKILL.md`: 지원자 관리 에이전트 raw CSV(Track 1/2/3)를 라운드/트랙 단위로 집계해 마크다운 리포트를 생성한다.
- `docs/skills/plan-agent-scoring/SKILL.md`: 실행 에이전트 raw CSV(`plan_agent_*.csv`)를 0~5 점수 규칙으로 재채점해 마크다운 리포트를 생성한다.

### 4-2) 백오피스 구현 스킬

- `docs/skills/backoffice-backend-api/SKILL.md`
- `docs/skills/backoffice-frontend-antd/SKILL.md`
- `docs/skills/systematic-debugging/SKILL.md`
- `docs/skills/test-driven-development/SKILL.md`
- `docs/skills/db-schema-doc-updater/SKILL.md`

### 4-3) 품질·리뷰·실행 스킬

- `docs/skills/brainstorming/SKILL.md`
- `docs/skills/writing-plans/SKILL.md`
- `docs/skills/executing-plans/SKILL.md`
- `docs/skills/subagent-driven-development/SKILL.md`
- `docs/skills/dispatching-parallel-agents/SKILL.md`
- `docs/skills/requesting-code-review/SKILL.md`
- `docs/skills/receiving-code-review/SKILL.md`
- `docs/skills/backoffice-quality-review/SKILL.md`
- `docs/skills/verification-before-completion/SKILL.md`

### 4-4) 브랜치·릴리즈 스킬

- `docs/skills/using-git-worktrees/SKILL.md`
- `docs/skills/sync-main-branch/SKILL.md`
- `docs/skills/worktree-merge-release/SKILL.md`
- `docs/skills/finishing-a-development-branch/SKILL.md`

### 4-5) 메타 스킬

- `docs/skills/writing-skills/SKILL.md`

### 4-6) 검증 이력 운영 가이드

- 기대결과 일괄 수정(다운로드→수정→업로드) 계약: `docs/architecture/validation-runs-api-contract.md`의 `5) 기대결과 일괄 업데이트 API`
- 스코어링 운영 기준: `docs/architecture/scoring_guidelines.md`

선택 규칙:

- 작업 시작 전 관련 스킬의 체크리스트를 먼저 읽는다.
- 여러 스킬이 겹치면 구현 스킬 1개 + 검증 스킬 1개를 우선 조합한다.
- 코드/구조가 변경되면 스킬 결과물(문서/테스트/리뷰 메모)까지 함께 반영한다.

## 5) 최소 품질 게이트

프론트엔드 변경 시 아래 명령을 통과해야 한다.

- `pnpm -C backoffice/frontend test`
- `pnpm -C backoffice/frontend build`

백엔드 로직 변경 시 관련 테스트를 반드시 실행하고, 실패 시 원인/조치 내용을 `docs/troubleshooting/incidents/`에 남긴다.

백엔드 테스트/초기화 데이터 보호 규칙:

- 테스트 실행 시 DB는 반드시 `*_test` suffix 경로만 사용한다. (예: `BACKOFFICE_DB_PATH=./backoffice_test.db`)
- `drop_all`, `truncate`, reset 스크립트 같은 파괴적 초기화는 `BACKOFFICE_ALLOW_DB_RESET=1` 또는 동등한 명시 플래그가 없으면 실행하지 않는다.
- 관리/운영 데이터 DB(`*_test`가 아닌 경로)는 어떤 테스트/초기화 작업에서도 대상으로 사용하지 않는다.

## 6) DB 스키마 문서화 가드레일

- DB/스키마 변경 PR에는 반드시 `docs/skills/db-schema-doc-updater/SKILL.md`를 실행한다.
- DB 변경(테이블/컬럼/관계/인덱스/제약) 커밋/PR에는 `architecture/data/*` 문서(저장소 기준 `docs/architecture/data/*`) 변경이 반드시 동반되어야 한다.
- 위 동반 변경이 없으면 리뷰에서 실패로 간주한다.

리뷰 체크리스트(스키마 변경 PR 필수):

- [ ] `schema.md`가 최신 스키마 사실(PK/FK/nullable/default/index/enum)을 반영했는가
- [ ] `relations.mmd`가 최신 관계를 반영했는가
- [ ] `sqlite-metrics.md` 쿼리가 실제 테이블/컬럼명과 일치하는가
