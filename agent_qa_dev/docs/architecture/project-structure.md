# Project Structure Map

- 기준 시각: 2026-02-18
- 목적: 작업 시작 전에 "어디를 수정해야 하는지" 빠르게 판단하기 위한 구조 지도

## 1) 루트 구조

```text
agent_qa_dev/
├─ AGENTS.md
├─ backoffice/
│  ├─ backend/
│  └─ frontend/
├─ docs/
│  ├─ architecture/
│  │  └─ data/
│  ├─ design-system/
│  ├─ feedback/
│  ├─ plans/
│  ├─ skills/
│  └─ troubleshooting/
├─ langfuse/
├─ ant-design/
├─ ant-design-icons/
└─ aqb_*.py
```

## 2) 웹 개발 핵심 경로

### Frontend

- 엔트리 및 앱 공통: `backoffice/frontend/src/app`
- 기능 페이지: `backoffice/frontend/src/features`
- 테스트 세트(실제 CRUD 페이지): `backoffice/frontend/src/features/test-sets`
- 공통 컴포넌트: `backoffice/frontend/src/components/common`
- 공통 유틸: `backoffice/frontend/src/shared/utils`
- API 클라이언트: `backoffice/frontend/src/api`

### Backend

- API 라우터: `backoffice/backend/app/api`
- 테스트 세트 라우터: `backoffice/backend/app/api/routes/validation_test_sets.py`
- 에이전트 잡 라우터: `backoffice/backend/app/api/routes/validation_agents.py`
- 내부 공용 라이브러리(AQB 이식): `backoffice/backend/app/lib`
- 서비스 계층: `backoffice/backend/app/services`
- 에이전트 작업 서비스: `backoffice/backend/app/services/agent_tasks`
- 저장소 계층: `backoffice/backend/app/repositories`
- 테스트 세트 저장소: `backoffice/backend/app/repositories/validation_test_sets.py`
- 배치/잡: `backoffice/backend/app/jobs`
- 운영 스크립트: `backoffice/backend/scripts`
- 테스트: `backoffice/backend/tests`

### Documentation

- 운영 규칙: `AGENTS.md`
- 프론트 정보구조: `docs/architecture/backoffice-frontend-information-architecture.md`
- 데이터 테이블 정의서: `docs/architecture/data/schema.md`
- 데이터 관계도(ERD): `docs/architecture/data/relations.mmd`
- SQLite 운영 SQL 모음: `docs/architecture/data/sqlite-metrics.md`
- 스킬 인덱스: `AGENTS.md`의 `4) @skills 인덱스 (docs/skills)` 섹션
- 장애/재발방지 기록: `docs/troubleshooting/incidents`

## 3) 유지보수 규칙

- 실제 디렉터리 구조가 변경되면 이 문서를 같은 PR에서 함께 갱신한다.
- 프론트 내비게이션/도메인 구조가 바뀌면 IA 문서도 함께 갱신한다.
- 벤더 성격 경로(`ant-design`, `ant-design-icons`, `langfuse`)는 명시 요청이 있을 때만 수정한다.
