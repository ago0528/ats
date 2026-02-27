# Backoffice Design System (Ant Design + Custom Theme)

## 0. Goal

Build an internal backoffice UI to run and validate agent performance via internal Agent APIs. The UI must be **predictable, dense, and fast**: an **Admin/Dashboard App Shell** with clear global context, robust state handling, and drilldowns from metrics to evidence (runs → cases → traces/logs).

---

## 1. Layout: App Shell Pattern

### 1.1 Structure

- **GNB (Top Global Navigation)**: persistent header for global context and utilities.
- **LNB (Left Navigation Sidebar)**: primary IA for feature modules.
- **Main Content Area**: dashboards, tables, drilldowns, and detail pages.

### 1.2 Fixed Dimensions (Desktop first)

- **GNB height**: `56px`
- **LNB width**: `240px`
- **LNB collapsed width**: `72px`
- **Content padding**: `24px`
- **Card radius**: `12px` (consistent across surfaces)
- **Page max width**: optional `1440px` container; otherwise fluid with comfortable padding.

### 1.3 Sticky / Scroll Rules

- GNB is **sticky** at top.
- Global filters (time range, env, agent/model) are **sticky** beneath the GNB on pages that use them.
- Prefer **single primary scroll container** (main content panel). Avoid nested scrolls unless necessary (e.g., log viewer).

### 1.4 Responsive

- Desktop-first. Provide breakpoints for:
    - `≥ 1200px`: default layout
    - `768–1199px`: allow LNB collapse by default
    - `< 768px`: optional (if supported) convert LNB into a Drawer.

---

## 2. Typography (Pretendard)

### 2.1 Font stack

Use Pretendard as the primary font:

- `Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif`

### 2.2 Type scale (recommended)

Define a minimal, consistent scale:

- **H1**: 24px / 32px, weight 700
- **H2**: 20px / 28px, weight 700
- **H3**: 16px / 24px, weight 600
- **Body**: 14px / 22px, weight 400
- **Small**: 12px / 18px, weight 400
- **Code/Logs**: 12–13px / 18px, monospace fallback

### 2.3 Numeric display

For KPI cards and tabular metrics:

- Use **tabular numerals** where supported (consistent digit width).
- Standardize units and formatting (see Data Presentation).

---

## 3. Color System (Custom Ant Design Theme)

### 3.1 Principles

- Ant Design base tokens are used; colors are customized.
- Provide clear tokens for **Primary**, **Status**, **Neutrals**, **Surface**, **Text**, **Border**.

### 3.2 Required color tokens

Define at minimum:

**Brand / Primary**

- `colorPrimary`
- `colorPrimaryHover`
- `colorPrimaryActive`

**Status**

- `colorSuccess`
- `colorWarning`
- `colorError`
- `colorInfo`

**Neutrals**

- `gray-50 ... gray-900` (or Ant tokens)
- `colorText`
- `colorTextSecondary`
- `colorTextTertiary`
- `colorTextDisabled`

**Surfaces / Borders**

- `colorBgLayout` (page background)
- `colorBgContainer` (cards/panels)
- `colorBorder`
- `colorBorderSecondary`

### 3.3 Dark mode

- If not supported: explicitly state **“Light theme only”**.
- If supported later: ensure tokens are defined for both modes (do not ad-hoc style).

---

## 4. Spacing, Sizing, and Elevation

### 4.1 Spacing scale (4px base)

Only use these spacing values:

- `4, 8, 12, 16, 24, 32, 48`

### 4.2 Corners

- Default radius: `12px` for cards
- Buttons/inputs: align with Ant defaults, but keep consistent.

### 4.3 Shadows

- Use a small set of elevations:
    - `elevation-0`: no shadow (default)
    - `elevation-1`: subtle shadow for floating panels
    - `elevation-2`: modals/popovers

---

## 5. Components: Usage Rules (Ant Design)

### 5.1 Buttons

- Use **Primary** for the single dominant action on a view (e.g., “Run evaluation”).
- Use **Default** for secondary actions.
- Use **Text/Link** for tertiary actions.
- Avoid multiple primary buttons in one container.

### 5.2 Forms

- Labels: consistent placement (recommended: top-aligned labels).
- Validation:
    - inline error message under the field
    - do not rely on color alone; include icon/message.
- Required indicator and help text style must be consistent.

### 5.3 Tables

- Must support:
    - sorting (where applicable)
    - pagination
    - empty state
    - row click → detail drilldown
- Define density:
    - default row height; optionally compact mode for power users.

### 5.4 Cards / Panels

- Standard structure:
    - Header: title + optional actions (right)
    - Body: content
    - Footer: optional, for secondary actions or “View details”
- Keep card titles short; use subtitles for context.

### 5.5 Modal / Drawer

- Modals for confirmation and small forms.
- Drawers for detail inspection (trace/log) when it helps keep context.
- Button order: **Cancel** (left) then **Confirm** (right).
- Modal 공통 규칙은 [Modal Standardization](./modal-standardization.md) 참조.

### 5.6 Icons

- Use Ant Design Icons.
- Sizes: 16px default, 20px for emphasis, 24px for large controls.
- Keep icon meaning consistent across the app.

---

## 6. State Design (Reliability UX)

### 6.1 Loading

- Prefer **skeletons** for dashboards and lists to avoid layout shift.
- Use spinners only for local components (small areas).

### 6.2 Empty

Every empty state must include:

- why it’s empty (common reasons)
- the next action (change time range, switch env, run a sample, etc.)

### 6.3 Error

Errors must include:

- what failed (API name or module)
- retry action
- requestId / traceId (for debugging internal APIs)
- partial failure is acceptable: do not blank the entire page if one widget fails.

### 6.4 Disabled

Use disabled states with:

- tooltip explaining why disabled (when non-obvious)
- consistent contrast and cursor behavior.

---

## 7. Data Presentation (Agent Evaluation Console)

### 7.1 Global filters (first-class)

On evaluation dashboards and run pages, provide:

- **Time range** (default: last 24h)
- **Environment** (prod/staging/dev)
- **Agent / Model**
- Optional: dataset/scenario, version, user/team

Filter state must be **shareable via URL**.

### 7.2 KPI Card template

KPI cards should include:

- value + unit
- time range label
- delta vs previous period (optional but recommended)
- click → drilldown list (cases/runs)

### 7.3 Drilldown model (non-negotiable)

- Dashboard metrics → **Run list** → **Run detail**
- Run detail → **Case list** (sortable/filterable)
- Case detail → **Trace / tool calls / logs / timings / tokens / cost**

### 7.4 Formatting standards

- Latency: show ms under 1s, seconds above 1s (consistent rounding)
- Cost: consistent currency and decimals
- Scores: fixed decimal precision (e.g., 2dp)
- Dates: show in the user’s timezone; display timezone label in tooltips.

### 7.5 Logs / Traces viewer

- Use monospace for logs.
- Provide copy-to-clipboard.
- Provide collapsible sections for tool calls and payloads.
- Highlight errors and warnings by status token, not custom colors.

---

## 8. Navigation & Information Architecture

### 8.1 LNB grouping (recommended)

- **Runs / Evaluations**
- **Tracing / Sessions**
- **Datasets**
- **Prompts**
- **Scores / Judges**
- **Users / Access**
- **Settings**

### 8.2 GNB contents (recommended)

- workspace/project selector
- global search (runId/traceId/caseId)
- user menu
- quick actions (optional)

---

## 9. Accessibility & i18n

- Maintain sufficient contrast for text and controls.
- Keyboard navigability: focus rings must be visible.
- Korean UI text tends to be longer; avoid fixed-width truncation for primary buttons/labels when possible.
- Use consistent truncation with tooltips for long identifiers (runId, traceId).

---

## 10. Implementation Notes (for agents)

- Use Ant Design components; avoid bespoke components unless required.
- Do not hardcode colors; use theme tokens.
- Ensure filter state is synchronized with URL query params.
- Prefer composition over customization: keep overrides minimal and systematic.

## 11. v0.2 백오피스 적용 규칙

### 11.1 핵심 UI 정책
- 보라 계열(Primary `#7B5CF2`)은 유지하고, 라이트 테마 기준으로만 배포.
- 데스크톱 우선 App Shell:
  - GNB(56px), LNB(240px), 메인 패딩(24px), 컨테이너 max 1440px.
- 동일 용어 표준화:
  - `Generic` → `에이전트 검증`
  - `Prompt Management` → `프롬프트 관리`

### 11.2 실행 플로우 UX
- 2단계 방식은 상단의 Steps로 항상 노출: 생성 → 1단계 실행 → 2단계 LLM 평가.
- 상태 의존적으로 버튼 비활성화를 유지하고, `tooltip`으로 즉시 이유 안내.
- 핵심 실행 버튼 집합(생성/1단계/2단계)은 동일 액션 블록으로 배치.
- 토큰 미입력/실행 오류/대상 미생성은 Alert + Empty state에서 즉시 안내.
- 템플릿 다운로드, 업로드, 단일 질의, 실행 시작은 하나의 카드/폼 흐름으로 정렬.
- 결과 화면은 실행 상태(KPI)와 데이터 그리드를 분리해 스크롤을 안정화.

### 11.3 표/목록 규칙
- 정렬 가능한 핵심 컬럼 유지: Query ID, 질의, 응답, 로직 결과, LLM 상태, 오류.
- 긴 텍스트는 말줄임+툴팁 + 모노스페이스 사용으로 가독성 보장.
- 오류 행은 배경색 강조.
- 행 확장(Expansion)으로 실행 프로세스/raw JSON/LLM 검증 조건을 오프로드.
- 핵심 지표는 카드 기반 KPI로 상단 배치(총 질의, PASS/FAIL, LLM 완료, 오류).
- 검색/필터는 행 패널에 통합: 키워드 검색, 로직 상태 필터, 오류 전용 토글.

### 11.4 프롬프트 관리 규칙
- Worker 목록은 표 형태로 제공.
- 조회/수정은 모달 + Tabs로 분리.
- 조회와 수정 화면의 변경 전/후 텍스트를 동시에 확인 가능.
- 수정은 별도 입력 단계 없이 바로 편집 가능한 상태에서 저장.

### 11.5 토큰 운영 규칙
- ATS 토큰(`Bearer`, `cms-access-token`, `mrs-session`)은 공식 로그인(`/login`) 후 자동 발급/자동 갱신을 기본으로 사용.
- 헤더에서는 사용자에게 `세션 상태`, `수동 새로고침`, `로그아웃`만 노출한다.
- 레거시 cURL 파싱은 fallback 전용이며 기본 비활성:
  - 프론트: `VITE_ENABLE_LEGACY_CURL_LOGIN=true`
  - 백엔드: `BACKOFFICE_ENABLE_LEGACY_CURL_LOGIN=true`
  - 두 플래그가 모두 켜져야 사용 가능
- OpenAI Key는 `에이전트 검증`에서만 2단계 평가 입력으로 허용.

### 11.6 상태/오류 규칙
- API 실패/재시도 권장 메시지는 경고(Alert)로 즉시 노출.
- 행이 빈 경우에는 "어떤 액션을 수행하면 데이터가 생기는지"를 텍스트로 안내.
- 오류 행은 색상 + 메시지 노출 + 개별 상세 패널을 통해 재발행 원인 확인 가능.

### 11.7 UI/UX 품질 체크리스트 (v0.2)
- [ ] 용어 정합: 메뉴/버튼/상태 문구가 `에이전트 검증`, `프롬프트 관리`, `검증 실행 생성`으로 통일.
- [ ] 토큰 UX: ATS 토큰은 공식 로그인 + 자동 갱신 루프를 기본으로 사용.
- [ ] fallback UX: cURL fallback은 feature flag 2종이 켜졌을 때만 노출.
- [ ] 플로우 가시성: 생성-1단계-2단계 Steps가 항상 보임.
- [ ] 데이터 탐색성: 검색/필터/확장 상세가 가능.
- [ ] 에러 안전성: 토큰 미입력/대상 미생성/실행 실패 시 즉시 안내.
- [ ] 배포 규정: AGENTS.md 배치 게이트 테스트를 통과 후 배포.

## 12. 적용 요약 (Reference Mapping)

### 화면별 매핑
- Generic
  - `AppLayout` 상단 헤더: 환경/버전/공식 로그인 세션 상태(필요 시 cURL fallback)
  - `GenericRunPage` 상단: 실행 상태 카드, 2단계 Step 바, 실행 옵션, 템플릿/실행 버튼
  - `RunTable`: 테이블 + 행 확장 상세 + 오류 하이라이트 + 컬럼 정렬
- Prompt
  - Worker 목록 테이블 + 모달 조회/수정 탭 + 길이 차이 확인

### 컬러 규칙 유지
- Primary: `#7B5CF2`
- 배경: `#f4f6fb`
- 경계/구분: `#edf1f7`, `#e5e8ef`
- 에러 하이라이트: `#fff2f0`
