# Validation Backend Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Run 실행 결과 기반 로직/LLM 평가와 테스트세트 기준 점수 대시보드를 안정적으로 운영하고, 루트 Python 스크립트 의존을 제거해 에이전트 확장(질의 생성/리포트) 준비를 완료한다.

**Architecture:** 실행(Execute)과 평가(Evaluate), 집계(Score/Dashboard), 후속 에이전트 작업(Query Generator/Report Writer)을 분리한 파이프라인 구조로 정리한다. 루트 스크립트는 백엔드 패키지/스크립트 경로로 이관하고, API 계층은 서비스 계층 호출만 담당하도록 얇게 유지한다.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, aiohttp, pytest, React(기존 API 소비 변경 범위 확인용)

---

### Task 1: 백엔드 모듈 경계 정리(루트 의존 제거)

**Files:**
- Modify: `backoffice/backend/app/__init__.py`
- Modify: `backoffice/backend/app/core/environment.py`
- Modify: `backoffice/backend/app/services/logic_check.py`
- Modify: `backoffice/backend/app/adapters/agent_client_adapter.py`
- Modify: `backoffice/backend/app/adapters/openai_judge_adapter.py`
- Modify: `backoffice/backend/app/api/routes/generic_runs.py`
- Modify: `backoffice/backend/app/api/routes/validation_runs.py`
- Create: `backoffice/backend/app/lib/aqb_common.py`
- Create: `backoffice/backend/app/lib/aqb_runtime.py`
- Create: `backoffice/backend/app/lib/aqb_prompt_template.py`
- Create: `backoffice/backend/app/lib/aqb_agent_client.py`
- Create: `backoffice/backend/app/lib/aqb_openai_judge.py`
- (Optional compatibility shim) Modify: `/Users/ago0528/Desktop/files/01_work/01_planning/01_vibecoding/ats/agent_qa_dev/aqb_*.py`

**Step 1: 루트 의존 import 매핑표 작성**
- `rg -n "from aqb_|import aqb_" backoffice/backend/app backoffice/backend/tests`
- 결과를 기준으로 import replacement 목록 확정

**Step 2: app/lib 하위로 공용 모듈 이관**
- 루트 스크립트 중 백엔드 런타임에서 실제 참조하는 함수만 최소 이관
- API/서비스/어댑터 import를 `app.lib.*`로 전환

**Step 3: `app/__init__.py`의 repo root sys.path append 제거**
- 백엔드 패키지 단독 실행/테스트 가능 상태로 정리

**Step 4: 회귀 테스트**
- `cd backoffice/backend && BACKOFFICE_DB_PATH=./backoffice_test.db BACKOFFICE_ALLOW_DB_RESET=1 python -m pytest -q`

**Step 5: Commit**
- `git add backoffice/backend/app backoffice/backend/tests`
- `git commit -m "refactor: remove backend dependency on repo-root aqb modules"`

---

### Task 2: 실행/평가 파이프라인 상태 모델 정리

**Files:**
- Modify: `backoffice/backend/app/core/enums.py`
- Modify: `backoffice/backend/app/models/validation_run.py`
- Modify: `backoffice/backend/app/repositories/validation_runs.py`
- Modify: `backoffice/backend/app/api/routes/validation_runs.py`
- Modify: `backoffice/backend/app/jobs/validation_execute_job.py`
- Modify: `backoffice/backend/app/jobs/validation_evaluate_job.py`
- Modify: `backoffice/backend/tests/test_validation_runs_api.py`

**Step 1: 평가 상태 필드 도입**
- `validation_runs`에 평가 단계 상태(`EVAL_PENDING/RUNNING/DONE/FAILED`) 또는 동등 필드 추가
- 실행 상태와 평가 상태를 분리

**Step 2: 평가 실행 게이트 강화**
- `evaluate` API에서 최소 실행 완료 조건 검사(예: RUNNING 금지, 실행 결과 없음 금지)
- 동시 평가 중복 실행 방지

**Step 3: 잡 상태 조회 일관성 정리**
- `runner.jobs` 문자열 반환만 의존하지 않고 run 엔티티 상태를 단일 소스로 사용

**Step 4: 테스트**
- 평가 선행 조건/중복 실행/실패 상태 테스트 추가

**Step 5: Commit**
- `git commit -m "refactor: separate execute and evaluate states for validation runs"`

---

### Task 3: 점수 집계 모델(Score Snapshot) 추가

**Files:**
- Create: `backoffice/backend/app/models/validation_score_snapshot.py`
- Modify: `backoffice/backend/app/main.py`
- Modify: `backoffice/backend/app/repositories/validation_runs.py`
- Modify: `backoffice/backend/app/jobs/validation_evaluate_job.py`
- Create: `backoffice/backend/tests/test_validation_score_snapshot.py`
- Modify: `docs/architecture/data/schema.md`
- Modify: `docs/architecture/data/relations.mmd`
- Modify: `docs/architecture/data/sqlite-metrics.md`

**Step 1: 스코어 스냅샷 테이블 설계**
- 키 예시: `run_id`, `test_set_id`, `query_group_id`, `metric_scores_json`, `total_score`, `logic_pass_rate`, `evaluated_at`

**Step 2: 평가 완료 시 스냅샷 계산/업서트**
- run item + logic eval + llm eval 기준으로 집계해 저장

**Step 3: 스키마 문서 동기화**
- DB 변경 동반 문서 3종(`schema.md`, `relations.mmd`, `sqlite-metrics.md`) 업데이트

**Step 4: 테스트**
- 평가 잡 실행 후 스냅샷 생성/갱신 검증

**Step 5: Commit**
- `git commit -m "feat: add validation score snapshots for dashboard aggregation"`

---

### Task 4: 테스트세트 기준 대시보드 API 추가

**Files:**
- Modify: `backoffice/backend/app/services/validation_dashboard.py`
- Modify: `backoffice/backend/app/api/routes/validation_runs.py`
- Create: `backoffice/backend/tests/test_validation_dashboard_by_test_set.py`
- Modify: `backoffice/frontend/src/api/validation.ts`
- Modify: `backoffice/frontend/src/features/validations/AgentValidationManagementPage.tsx`
- Modify: `docs/architecture/backoffice-frontend-information-architecture.md`

**Step 1: 조회 축 정의**
- 입력 파라미터: `testSetId`(필수), `runId`(선택), `dateFrom/dateTo`(선택)
- 출력: run 요약, logic pass rate, llm metric avg, total score trend, failure patterns

**Step 2: 기존 그룹 대시보드와 분리 제공**
- `GET /validation-dashboard/test-sets/{test_set_id}` 신규 추가
- 기존 `/validation-dashboard/groups/{group_id}`는 호환 유지

**Step 3: 프론트 대시보드 조회 전환**
- 기본 축을 `groupId`에서 `testSetId` 중심으로 변경

**Step 4: 테스트**
- 동일 질의그룹이 여러 테스트세트에 걸쳐 있는 케이스에서 집계 누수 없는지 검증

**Step 5: Commit**
- `git commit -m "feat: add test-set based validation dashboard endpoints"`

---

### Task 5: 잡 실행 기반 확장 포인트(질의 생성/리포트 에이전트) 마련

**Files:**
- Create: `backoffice/backend/app/models/automation_job.py`
- Create: `backoffice/backend/app/services/agent_tasks/query_generation.py`
- Create: `backoffice/backend/app/services/agent_tasks/report_generation.py`
- Create: `backoffice/backend/app/api/routes/validation_agents.py`
- Modify: `backoffice/backend/app/main.py`
- Create: `backoffice/backend/tests/test_validation_agents_api.py`

**Step 1: 공통 job 레코드 모델 추가**
- job type / payload / status / result / error / started_at / finished_at

**Step 2: Query 생성 에이전트 엔드포인트**
- 테스트세트/그룹/실패 패턴 기반 질의 생성 요청 API

**Step 3: 리포트 생성 에이전트 엔드포인트**
- run/test-set score snapshot 기반 요약 리포트 생성 API

**Step 4: 테스트**
- 비동기 job 생성, 상태 전이, 결과 조회 API 검증

**Step 5: Commit**
- `git commit -m "feat: add agent task framework for query generation and report synthesis"`

---

### Task 6: 검증/빌드/문서 마무리

**Files:**
- Modify: `docs/architecture/project-structure.md`
- Modify: `backoffice/backend/README.md`
- Modify: `docs/troubleshooting/incidents/*` (필요 시)

**Step 1: 품질 게이트 실행**
- Frontend: `pnpm -C backoffice/frontend test`
- Frontend: `pnpm -C backoffice/frontend build`
- Backend: `cd backoffice/backend && BACKOFFICE_DB_PATH=./backoffice_test.db BACKOFFICE_ALLOW_DB_RESET=1 python -m pytest -q`

**Step 2: 문서 업데이트**
- 루트 Python 스크립트 재배치 후 구조 문서 반영
- 백엔드 실행/테스트 절차 최신화

**Step 3: 실패/이슈 기록**
- 테스트 실패나 운영 리스크 발생 시 `docs/troubleshooting/incidents/` 기록

**Step 4: Commit**
- `git commit -m "docs: align architecture and runbook after validation backend refactor"`

---

## Execution Order

1. Task 1 (경계 정리)  
2. Task 2 (상태 모델)  
3. Task 3 (점수 스냅샷)  
4. Task 4 (테스트세트 대시보드)  
5. Task 5 (에이전트 확장 포인트)  
6. Task 6 (검증/문서)

## Exit Criteria

1. 백엔드가 repo root Python 모듈 없이 실행/테스트 가능
2. Run 실행 결과 기반 로직/LLM 평가와 점수 스냅샷이 재현 가능
3. 테스트세트 기준 대시보드 API/화면이 동작
4. 질의 생성/리포트 에이전트용 job 프레임워크가 준비됨
5. 스키마/관계/운영 SQL 문서가 코드와 일치
