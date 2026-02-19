# Backoffice 데이터 테이블 정의서 (PM Friendly)

- 최신 갱신일: 2026-02-19
- 대상: PM, PO, QA, 운영 담당자
- 스키마 기준: `backoffice/backend/app/models/*.py` + `backoffice/backend/app/main.py` startup 보정 + `backoffice/backend/backoffice.db`

## 공통 코드값

- `environment`: `dev`, `st2`, `st`, `pr`
- `run status`: `PENDING`, `RUNNING`, `DONE`, `FAILED`

## 테이블 목록

1. `generic_runs`
2. `generic_run_rows`
3. `prompt_audit_logs`
4. `prompt_snapshots`
5. `validation_query_groups`
6. `validation_queries`
7. `validation_settings`
8. `validation_test_sets`
9. `validation_test_set_items`
10. `validation_runs`
11. `validation_run_items`
12. `validation_llm_evaluations`
13. `validation_logic_evaluations`

---

## 1) `generic_runs`

### 테이블 개요

- Table name: `generic_runs`
- Business purpose: 레거시 Generic 검증 실행 단위(한 번의 실행 작업) 메타데이터를 저장
- Primary key: `id`
- Important relationships:
  - `base_run_id -> generic_runs.id` (self reference, N:1)
  - `generic_run_rows.run_id -> generic_runs.id` (1:N)
- Data lifecycle:
  - 생성: Generic 실행 생성 시
  - 수정: 실행 상태 전환(PENDING/RUNNING/DONE/FAILED), 시작/종료 시간 반영
  - 삭제/보존: 현재 soft delete 없음(운영 정책에 따라 하드 삭제 가능)

### 컬럼 정의

| Column name | Type | Nullable | Default | Description | Example value | Notes |
|---|---|---|---|---|---|---|
| `id` | `varchar(36)` | No | UUID (app) | 실행 ID | `c7b9c7d7-9a9d-4ae2-8850-4d153f7f1e21` | PK |
| `environment` | `enum` | No | 없음 | 실행 대상 환경 | `st` | 값: `dev/st2/st/pr` |
| `status` | `enum` | No | `PENDING` (app) | 실행 상태 | `RUNNING` | 값: `PENDING/RUNNING/DONE/FAILED` |
| `base_run_id` | `varchar(36)` | Yes | `NULL` | 비교 기준이 되는 이전 실행 ID | `95e64257-7f77-4dca-a37d-f9c7377c9d92` | FK(self) |
| `options_json` | `text` | No | `{}` (app) | 실행 옵션(JSON 문자열) | `{"sheet":"Sheet1"}` | JSON string |
| `created_at` | `datetime` | No | UTC now (app) | 실행 레코드 생성 시각 | `2026-02-18 11:20:31` |  |
| `started_at` | `datetime` | Yes | `NULL` | 실제 실행 시작 시각 | `2026-02-18 11:22:03` |  |
| `finished_at` | `datetime` | Yes | `NULL` | 실행 종료 시각 | `2026-02-18 11:25:48` |  |

### 인덱스/제약조건

- PK: `id`
- FK: `base_run_id -> generic_runs.id`

---

## 2) `generic_run_rows`

### 테이블 개요

- Table name: `generic_run_rows`
- Business purpose: Generic 실행 내부의 개별 질의 결과 행(응답/오류/평가 결과)을 저장
- Primary key: `id`
- Important relationships:
  - `run_id -> generic_runs.id` (N:1)
- Data lifecycle:
  - 생성: 실행 중 row 단위로 누적 생성
  - 수정: 평가/후처리 값(`llm_eval_json`, `logic_result`) 업데이트 가능
  - 삭제/보존: 상위 run 정리 시 함께 정리 가능

### 컬럼 정의

| Column name | Type | Nullable | Default | Description | Example value | Notes |
|---|---|---|---|---|---|---|
| `id` | `text` | No | UUID (app) | 실행 row ID | `bb5d41f0-f2a0-4c95-9adb-2a159cd3f73d` | PK |
| `run_id` | `varchar(36)` | No | 없음 | 소속 실행 ID | `c7b9c7d7-9a9d-4ae2-8850-4d153f7f1e21` | FK, index |
| `ordinal` | `integer` | No | 없음 | 실행 내 순번 | `12` |  |
| `query_id` | `text` | No | 없음 | 원본 입력의 질의 식별자 | `Q-012` |  |
| `query` | `text` | No | 없음 | 실제 질의 문구 | `강남구 1억 이하 전세 보여줘` |  |
| `llm_criteria` | `text` | No | `""` (app) | LLM 평가 기준 | `정확성, 근거성` |  |
| `field_path` | `text` | No | `""` (app) | 로직 검증 대상 경로 | `results[0].price` |  |
| `expected_value` | `text` | No | `""` (app) | 기대값 | `<=100000000` |  |
| `response_text` | `text` | No | `""` (app) | 에이전트 응답 텍스트 | `조건에 맞는 매물은 ...` |  |
| `response_time_sec` | `float` | Yes | `NULL` | 응답 시간(초) | `1.83` |  |
| `execution_process` | `text` | No | `""` (app) | 실행 과정 로그 요약 | `request->parse->normalize` |  |
| `error` | `text` | No | `""` (app) | 오류 메시지 | `timeout after 120000ms` |  |
| `raw_json` | `text` | No | `""` (app) | 원본 응답(JSON 문자열) | `{"response":{...}}` | JSON string |
| `logic_result` | `text` | No | `""` (app) | 로직 검증 결과 | `PASS` |  |
| `llm_eval_json` | `text` | No | `""` (app) | LLM 평가 결과(JSON 문자열) | `{"score":84}` | JSON string |
| `llm_eval_status` | `text` | No | `""` (app) | LLM 평가 상태 | `DONE` |  |

### 인덱스/제약조건

- PK: `id`
- FK: `run_id -> generic_runs.id`
- Index: `ix_generic_run_rows_run_id(run_id)`

---

## 3) `prompt_audit_logs`

### 테이블 개요

- Table name: `prompt_audit_logs`
- Business purpose: 프롬프트 변경 이력(누가, 어떤 워커 프롬프트를, 얼마나 변경했는지) 감사 로그 저장
- Primary key: `id`
- Important relationships: 별도 FK 없음
- Data lifecycle:
  - 생성: 프롬프트 수정/초기화 액션 시 append-only 생성
  - 수정: 보통 없음(감사 로그)
  - 삭제/보존: 운영/보안 정책에 따라 보존 기간 관리 필요

### 컬럼 정의

| Column name | Type | Nullable | Default | Description | Example value | Notes |
|---|---|---|---|---|---|---|
| `id` | `text` | No | UUID (app) | 감사 로그 ID | `f82494b4-b8ab-46af-8f84-a8336f95729c` | PK |
| `environment` | `enum` | No | 없음 | 변경 대상 환경 | `dev` | 값: `dev/st2/st/pr` |
| `worker_type` | `text` | No | 없음 | 워커 종류 | `ORCHESTRATOR_WORKER_V3` |  |
| `action` | `text` | No | 없음 | 수행 액션 | `UPDATE` | 예: `UPDATE`, `RESET` |
| `before_len` | `integer` | No | `0` (app) | 변경 전 프롬프트 길이 | `1240` |  |
| `after_len` | `integer` | No | `0` (app) | 변경 후 프롬프트 길이 | `1331` |  |
| `actor` | `text` | No | `system` (app) | 변경 주체 | `pm_kim` |  |
| `created_at` | `datetime` | No | UTC now (app) | 로그 생성 시각 | `2026-02-18 09:14:22` |  |

### 인덱스/제약조건

- PK: `id`

---

## 4) `prompt_snapshots`

### 테이블 개요

- Table name: `prompt_snapshots`
- Business purpose: 워커별 현재 프롬프트(ATS 조회 기준)와 직전 프롬프트 1개를 저장해 조회 시점을 안정적으로 제공
- Primary key: `id`
- Important relationships: 별도 FK 없음
- Data lifecycle:
  - 생성: 프롬프트 조회/수정/초기화에서 해당 워커 스냅샷이 없을 때 생성
  - 수정: ATS 현재값이 바뀌거나 수정/초기화 액션이 발생하면 `previous_prompt/current_prompt` 갱신
  - 삭제/보존: 운영 정책에 따라 관리(현재 soft delete 없음)

### 컬럼 정의

| Column name | Type | Nullable | Default | Description | Example value | Notes |
|---|---|---|---|---|---|---|
| `id` | `text` | No | UUID (app) | 스냅샷 ID | `1880a306-79a2-41db-95c6-f06559f03004` | PK |
| `environment` | `enum` | No | 없음 | 대상 환경 | `dev` | 값: `dev/st2/st/pr` |
| `worker_type` | `text` | No | 없음 | 워커 종류 | `RECRUIT_PLAN_WORKER_V3` | unique 제약 포함 |
| `current_prompt` | `text` | No | `""` (app) | ATS 기준 현재 프롬프트 | `You are ...` |  |
| `previous_prompt` | `text` | No | `""` (app) | 바로 직전 프롬프트 | `You are previous ...` |  |
| `actor` | `text` | No | `system` (app) | 마지막 갱신 주체 | `pm_kim` |  |
| `updated_at` | `datetime` | No | UTC now/onupdate (app) | 마지막 갱신 시각 | `2026-02-19 11:03:14` |  |

### 인덱스/제약조건

- PK: `id`
- Unique constraint: `uq_prompt_snapshots_environment_worker_type(environment, worker_type)`

---

## 5) `validation_query_groups`

### 테이블 개요

- Table name: `validation_query_groups`
- Business purpose: 질의를 묶는 상위 카테고리(도메인 그룹)와 그룹 기본 평가 기준을 관리
- Primary key: `id`
- Important relationships:
  - `validation_queries.group_id -> validation_query_groups.id` (1:N)
- Data lifecycle:
  - 생성/수정: 운영자가 그룹명, 기본 타겟 어시스턴트, 기본 평가 기준 관리
  - 삭제: 하위 query가 있으면 정합성 확인 후 진행 필요

### 컬럼 정의

| Column name | Type | Nullable | Default | Description | Example value | Notes |
|---|---|---|---|---|---|---|
| `id` | `varchar(36)` | No | UUID (app) | 질의 그룹 ID | `af247d45-2821-4879-8f2b-c6dd63ae88c6` | PK |
| `group_name` | `varchar(140)` | No | 없음 | 그룹 표시 이름 | `아파트 매매` | unique + index |
| `description` | `text` | No | `""` (app) | 그룹 설명 | `수요자 검색 시나리오 중심` |  |
| `default_target_assistant` | `text` | No | `""` (app) | 그룹 기본 대상 어시스턴트 | `real_estate_assistant` | startup 보정 컬럼 |
| `llm_eval_criteria_default_json` | `text` | No | `""` (app) | 그룹 공통 LLM 평가 기준(JSON 문자열) | `[{"name":"정확성","weight":0.4}]` | JSON string |
| `created_at` | `datetime` | No | UTC now (app) | 생성 시각 | `2026-02-10 16:11:02` |  |
| `updated_at` | `datetime` | No | UTC now/onupdate (app) | 수정 시각 | `2026-02-18 10:02:44` |  |

### 인덱스/제약조건

- PK: `id`
- Unique index: `ix_validation_query_groups_group_name(group_name)`

---

## 6) `validation_queries`

### 테이블 개요

- Table name: `validation_queries`
- Business purpose: 검증에 사용하는 질의 원본 정의(질의문/기대결과/평가기준/로직검증 기준)를 저장
- Primary key: `id`
- Important relationships:
  - `group_id -> validation_query_groups.id` (N:1)
  - `validation_test_set_items.query_id -> validation_queries.id` (1:N)
  - `validation_run_items.query_id -> validation_queries.id` (1:N, nullable)
- Data lifecycle:
  - 생성/수정: 운영자가 질의 데이터 관리 화면에서 CRUD
  - 실행 시점: run item에 snapshot으로 복제되어 이력 보존
  - 삭제: 테스트세트/이력 연관 영향 확인 필요

### 컬럼 정의

| Column name | Type | Nullable | Default | Description | Example value | Notes |
|---|---|---|---|---|---|---|
| `id` | `varchar(36)` | No | UUID (app) | 질의 ID | `db128f9a-65fd-451f-aa3b-f994f97c6f8a` | PK |
| `query_text` | `text` | No | 없음 | 실제 사용자 질의 문구 | `잠실 30평대 매매 찾아줘` |  |
| `expected_result` | `text` | No | `""` (app) | 기대 결과 설명 | `잠실/매매/30평대 매물 반환` |  |
| `category` | `varchar(40)` | No | `Happy path` (app) | 시나리오 분류 | `Edge case` | index |
| `group_id` | `varchar(36)` | No | 없음 | 소속 질의 그룹 ID | `af247d45-2821-4879-8f2b-c6dd63ae88c6` | FK, index |
| `llm_eval_criteria_json` | `text` | No | `""` (app) | 질의별 LLM 평가 기준(JSON 문자열) | `[{"metric":"정확성","weight":0.5}]` | JSON string |
| `logic_field_path` | `text` | No | `""` (app) | 로직 검증 필드 경로 | `items[0].dealType` |  |
| `logic_expected_value` | `text` | No | `""` (app) | 로직 기대값 | `SALE` |  |
| `context_json` | `text` | No | `""` (app) | 질의별 실행 컨텍스트(JSON 문자열) | `{"region":"seoul"}` | startup 보정 컬럼 |
| `target_assistant` | `text` | No | `""` (app) | 질의별 대상 어시스턴트 | `apt_sales_bot` | startup 보정 컬럼 |
| `created_by` | `varchar(120)` | No | `unknown` (app) | 작성자 | `pm_lee` |  |
| `created_at` | `datetime` | No | UTC now (app) | 생성 시각 | `2026-02-12 15:01:41` |  |
| `updated_at` | `datetime` | No | UTC now/onupdate (app) | 수정 시각 | `2026-02-18 11:10:20` |  |

### 인덱스/제약조건

- PK: `id`
- FK: `group_id -> validation_query_groups.id`
- Index: `ix_validation_queries_group_id(group_id)`
- Index: `ix_validation_queries_category(category)`

### 조회 파생 정보(비저장)

- `testSetUsage`:
  - 용도: 질의 관리 화면에서 질의별 테스트 세트 사용 현황(개수/이름 목록) 표시
  - 산출 방식: `validation_test_set_items.query_id` + `validation_test_sets.name` 조인 기반 집계
  - 저장 위치: DB 컬럼이 아닌 API 응답 파생 필드
  - 참고: DB 스키마(테이블/컬럼/관계) 변경 없음

---

## 7) `validation_settings`

### 테이블 개요

- Table name: `validation_settings`
- Business purpose: 환경별 실행 기본값(반복 수, 병렬 수, 타임아웃, 기본 모델)을 관리
- Primary key: `id`
- Important relationships: FK 없음(환경 코드 기반 설정 테이블)
- Data lifecycle:
  - 생성: 환경별 1건씩 초기 세팅
  - 수정: 운영자가 설정 화면에서 업데이트
  - 삭제: 권장하지 않음(환경 기본값 누락 위험)

### 컬럼 정의

| Column name | Type | Nullable | Default | Description | Example value | Notes |
|---|---|---|---|---|---|---|
| `id` | `varchar(36)` | No | UUID (app) | 설정 ID | `6fe2bf53-240d-4880-8125-1da616495ca6` | PK |
| `environment` | `enum` | No | 없음 | 설정 대상 환경 | `pr` | unique + index |
| `repeat_in_conversation_default` | `integer` | No | `1` (app) | 같은 방에서 반복 실행 기본 횟수 | `2` |  |
| `conversation_room_count_default` | `integer` | No | `1` (app) | 대화 방 개수 기본값 | `3` |  |
| `agent_parallel_calls_default` | `integer` | No | `3` (app) | 에이전트 병렬 호출 기본값 | `5` |  |
| `timeout_ms_default` | `integer` | No | `120000` (app) | 타임아웃 기본값(ms) | `180000` |  |
| `test_model_default` | `varchar(120)` | No | `gpt-5.2` (app) | 실행 모델 기본값 | `gpt-5.2` |  |
| `eval_model_default` | `varchar(120)` | No | `gpt-5.2` (app) | 평가 모델 기본값 | `gpt-5.2` |  |
| `pagination_page_size_limit_default` | `integer` | No | `100` (DB/app) | 페이지당 최대 조회 기본값 | `200` | startup 보정 컬럼 |
| `updated_at` | `datetime` | No | UTC now/onupdate (app) | 수정 시각 | `2026-02-18 08:55:30` |  |

### 인덱스/제약조건

- PK: `id`
- Unique index: `ix_validation_settings_environment(environment)`

---

## 8) `validation_test_sets`

### 테이블 개요

- Table name: `validation_test_sets`
- Business purpose: 실행 가능한 테스트 세트(질의 묶음 + 기본 실행 파라미터)를 저장
- Primary key: `id`
- Important relationships:
  - `validation_test_set_items.test_set_id -> validation_test_sets.id` (1:N)
  - `validation_runs.test_set_id -> validation_test_sets.id` (1:N)
- Data lifecycle:
  - 생성/수정: 운영자가 테스트 세트 관리 화면에서 관리
  - 실행: run 생성 시 참조, run item에는 snapshot으로 독립 보존

### 컬럼 정의

| Column name | Type | Nullable | Default | Description | Example value | Notes |
|---|---|---|---|---|---|---|
| `id` | `varchar(36)` | No | UUID (app) | 테스트 세트 ID | `b8da4b5e-e2ef-4ffa-b6a5-2ba9ac27c07a` | PK |
| `name` | `varchar(120)` | No | 없음 | 테스트 세트 이름 | `서울 아파트 기본 시나리오` | index |
| `description` | `text` | No | `""` (app) | 테스트 세트 설명 | `핵심 질의 30개 구성` |  |
| `config_json` | `text` | No | `{}` (app) | 테스트 세트 기본 파라미터(JSON 문자열) | `{"timeoutMs":120000,"repeat":1}` | JSON string |
| `created_at` | `datetime` | No | UTC now (app) | 생성 시각 | `2026-02-14 10:10:05` |  |
| `updated_at` | `datetime` | No | UTC now/onupdate (app) | 수정 시각 | `2026-02-18 09:31:27` |  |

### 인덱스/제약조건

- PK: `id`
- Index: `ix_validation_test_sets_name(name)`

---

## 9) `validation_test_set_items`

### 테이블 개요

- Table name: `validation_test_set_items`
- Business purpose: 테스트 세트와 질의를 연결하는 매핑 테이블(질의 순서 포함)
- Primary key: `id`
- Important relationships:
  - `test_set_id -> validation_test_sets.id` (N:1)
  - `query_id -> validation_queries.id` (N:1)
  - `validation_test_sets`와 `validation_queries`의 N:M 관계를 구성
- Data lifecycle:
  - 생성/수정: 테스트 세트 편집 시 추가/삭제/순서 변경
  - 삭제: 테스트 세트에서 질의 제외 시 제거

### 컬럼 정의

| Column name | Type | Nullable | Default | Description | Example value | Notes |
|---|---|---|---|---|---|---|
| `id` | `varchar(36)` | No | UUID (app) | 매핑 ID | `3d8f8428-809a-465d-bf57-acf0d763f6ff` | PK |
| `test_set_id` | `varchar(36)` | No | 없음 | 테스트 세트 ID | `b8da4b5e-e2ef-4ffa-b6a5-2ba9ac27c07a` | FK, index |
| `query_id` | `varchar(36)` | No | 없음 | 질의 ID | `db128f9a-65fd-451f-aa3b-f994f97c6f8a` | FK, index |
| `ordinal` | `integer` | No | `1` (app) | 테스트 세트 내 질의 순서 | `7` | index |
| `created_at` | `datetime` | No | UTC now (app) | 매핑 생성 시각 | `2026-02-14 10:11:55` |  |

### 인덱스/제약조건

- PK: `id`
- FK: `test_set_id -> validation_test_sets.id`
- FK: `query_id -> validation_queries.id`
- Unique: `uq_validation_test_set_item_test_set_query(test_set_id, query_id)`
- Index: `ix_validation_test_set_items_test_set_id(test_set_id)`
- Index: `ix_validation_test_set_items_query_id(query_id)`
- Index: `ix_validation_test_set_items_ordinal(ordinal)`

---

## 10) `validation_runs`

### 테이블 개요

- Table name: `validation_runs`
- Business purpose: 테스트 세트 실행 단위(run)의 설정/상태/시간 정보를 저장
- Primary key: `id`
- Important relationships:
  - `base_run_id -> validation_runs.id` (self reference, N:1)
  - `test_set_id -> validation_test_sets.id` (N:1)
  - `validation_run_items.run_id -> validation_runs.id` (1:N)
- Data lifecycle:
  - 생성: 실행 계획 등록 시 PENDING run 생성
  - 수정: 실행/평가/비교 과정에서 상태 및 시간 갱신
  - 삭제: 이력/분석 영향이 커서 보통 보존 권장

### 컬럼 정의

| Column name | Type | Nullable | Default | Description | Example value | Notes |
|---|---|---|---|---|---|---|
| `id` | `varchar(36)` | No | UUID (app) | 실행(run) ID | `35efe819-03de-468a-8f3a-0c5f68a9f1d0` | PK |
| `mode` | `varchar(20)` | No | `REGISTERED` (app) | 실행 모드 | `REGISTERED` |  |
| `environment` | `enum` | No | 없음 | 실행 대상 환경 | `st2` | index |
| `status` | `enum` | No | `PENDING` (app) | 실행 상태 | `DONE` | index |
| `base_run_id` | `varchar(36)` | Yes | `NULL` | 비교 기준 run ID | `f97a8927-a89a-4f95-ae6e-f3a690b9af2d` | FK(self) |
| `test_set_id` | `varchar(36)` | Yes | `NULL` | 실행에 사용한 테스트 세트 ID | `b8da4b5e-e2ef-4ffa-b6a5-2ba9ac27c07a` | FK, index |
| `agent_id` | `varchar(120)` | No | `ORCHESTRATOR_WORKER_V3` (app) | 실행 워커 ID | `ORCHESTRATOR_WORKER_V3` |  |
| `test_model` | `varchar(120)` | No | `gpt-5.2` (app) | 실행 모델 | `gpt-5.2` |  |
| `eval_model` | `varchar(120)` | No | `gpt-5.2` (app) | 평가 모델 | `gpt-5.2` |  |
| `repeat_in_conversation` | `integer` | No | `1` (app) | 동일 방 반복 횟수 | `2` |  |
| `conversation_room_count` | `integer` | No | `1` (app) | 대화 방 수 | `3` |  |
| `agent_parallel_calls` | `integer` | No | `3` (app) | 병렬 호출 수 | `4` |  |
| `timeout_ms` | `integer` | No | `120000` (app) | 실행 타임아웃(ms) | `180000` |  |
| `options_json` | `text` | No | `{}` (app) | 실행 옵션(JSON 문자열) | `{"batchSize":20}` | JSON string |
| `created_at` | `datetime` | No | UTC now (app) | run 생성 시각 | `2026-02-18 10:41:01` |  |
| `started_at` | `datetime` | Yes | `NULL` | 실행 시작 시각 | `2026-02-18 10:41:10` |  |
| `finished_at` | `datetime` | Yes | `NULL` | 실행 종료 시각 | `2026-02-18 10:44:55` |  |

### 인덱스/제약조건

- PK: `id`
- FK: `base_run_id -> validation_runs.id`
- FK: `test_set_id -> validation_test_sets.id`
- Index: `ix_validation_runs_environment(environment)`
- Index: `ix_validation_runs_status(status)`
- Index: `ix_validation_runs_test_set_id(test_set_id)`

---

## 11) `validation_run_items`

### 테이블 개요

- Table name: `validation_run_items`
- Business purpose: run 내부 개별 실행 결과(질의 snapshot, 응답, 오류, 지연시간)를 저장하는 핵심 이력 테이블
- Primary key: `id`
- Important relationships:
  - `run_id -> validation_runs.id` (N:1)
  - `query_id -> validation_queries.id` (N:1, nullable)
  - `validation_llm_evaluations.run_item_id -> validation_run_items.id` (1:1)
  - `validation_logic_evaluations.run_item_id -> validation_run_items.id` (1:1)
- Data lifecycle:
  - 생성: run 실행 시 질의/반복/방 조합별로 생성
  - 수정: 실행 결과 및 평가 결과 연결 정보 갱신
  - 보존: snapshot 중심 이력 테이블로 장기 보존 가치 높음

### 컬럼 정의

| Column name | Type | Nullable | Default | Description | Example value | Notes |
|---|---|---|---|---|---|---|
| `id` | `varchar(36)` | No | UUID (app) | run item ID | `1e8a924b-a6ac-44ec-8f57-c93ece2c53f7` | PK |
| `run_id` | `varchar(36)` | No | 없음 | 소속 run ID | `35efe819-03de-468a-8f3a-0c5f68a9f1d0` | FK, index |
| `query_id` | `varchar(36)` | Yes | `NULL` | 원본 질의 ID(연결 불가 시 null) | `db128f9a-65fd-451f-aa3b-f994f97c6f8a` | FK, index |
| `ordinal` | `integer` | No | 없음 | run 내 순번 | `41` | index |
| `query_text_snapshot` | `text` | No | 없음 | 실행 시점 질의문 스냅샷 | `잠실 30평대 매매 찾아줘` | snapshot |
| `expected_result_snapshot` | `text` | No | `""` (app) | 실행 시점 기대결과 스냅샷 | `잠실/매매/30평대` | snapshot |
| `category_snapshot` | `varchar(40)` | No | `Happy path` (app) | 실행 시점 카테고리 스냅샷 | `Edge case` | snapshot |
| `applied_criteria_json` | `text` | No | `""` (app) | 실행 적용 평가기준(JSON 문자열) | `[{"metric":"정확성"}]` | snapshot JSON |
| `logic_field_path_snapshot` | `text` | No | `""` (app) | 실행 적용 로직 경로 스냅샷 | `items[0].dealType` | snapshot |
| `logic_expected_value_snapshot` | `text` | No | `""` (app) | 실행 적용 로직 기대값 스냅샷 | `SALE` | snapshot |
| `context_json_snapshot` | `text` | No | `""` (app) | 실행 컨텍스트 스냅샷(JSON 문자열) | `{"region":"seoul"}` | startup 보정 컬럼 |
| `target_assistant_snapshot` | `text` | No | `""` (app) | 실행 대상 어시스턴트 스냅샷 | `apt_sales_bot` | startup 보정 컬럼 |
| `conversation_room_index` | `integer` | No | `1` (app) | 대화 방 번호 | `2` |  |
| `repeat_index` | `integer` | No | `1` (app) | 반복 실행 번호 | `1` |  |
| `conversation_id` | `varchar(120)` | No | `""` (app) | 대화방 식별자 | `conv_20260218_001` |  |
| `raw_response` | `text` | No | `""` (app) | 원문 응답 텍스트 | `조건에 맞는 매물 3건입니다...` |  |
| `latency_ms` | `integer` | Yes | `NULL` | 응답 지연시간(ms) | `1820` |  |
| `error` | `text` | No | `""` (app) | 실행 오류 메시지 | `HTTP 504 gateway timeout` |  |
| `raw_json` | `text` | No | `""` (app) | 원본 응답(JSON 문자열) | `{"answer":...,"debug":...}` | JSON string |
| `executed_at` | `datetime` | Yes | `NULL` | 실제 실행 시각 | `2026-02-18 10:42:37` |  |

### 인덱스/제약조건

- PK: `id`
- FK: `run_id -> validation_runs.id`
- FK: `query_id -> validation_queries.id`
- Index: `ix_validation_run_items_run_id(run_id)`
- Index: `ix_validation_run_items_query_id(query_id)`
- Index: `ix_validation_run_items_ordinal(ordinal)`

---

## 12) `validation_llm_evaluations`

### 테이블 개요

- Table name: `validation_llm_evaluations`
- Business purpose: run item에 대한 LLM 평가 결과(메트릭 점수/총점/코멘트)를 저장
- Primary key: `id`
- Important relationships:
  - `run_item_id -> validation_run_items.id` (1:1)
- Data lifecycle:
  - 생성: 평가 잡 수행 시 run item 단위 생성
  - 수정: 재평가 시 갱신 또는 재생성 전략 사용 가능
  - 보존: run 품질 분석 근거 데이터로 보존

### 컬럼 정의

| Column name | Type | Nullable | Default | Description | Example value | Notes |
|---|---|---|---|---|---|---|
| `id` | `varchar(36)` | No | UUID (app) | LLM 평가 ID | `54e0cbcf-d32d-4640-9d1e-1d1656f7473a` | PK |
| `run_item_id` | `varchar(36)` | No | 없음 | 대상 run item ID | `1e8a924b-a6ac-44ec-8f57-c93ece2c53f7` | FK, unique index |
| `eval_model` | `varchar(120)` | No | `gpt-5.2` (app) | 평가에 사용된 모델 | `gpt-5.2` |  |
| `metric_scores_json` | `text` | No | `""` (app) | 메트릭 점수(JSON 문자열) | `{"정확성":88,"근거성":81}` | JSON string |
| `total_score` | `float` | Yes | `NULL` | 총점 | `84.5` |  |
| `llm_comment` | `text` | No | `""` (app) | LLM 평가 코멘트 | `의도는 맞지만 근거 문장이 부족` |  |
| `status` | `varchar(40)` | No | `PENDING` (app) | 평가 상태 | `DONE` | index |
| `evaluated_at` | `datetime` | No | UTC now (app) | 평가 시각 | `2026-02-18 10:45:15` |  |

### 인덱스/제약조건

- PK: `id`
- FK: `run_item_id -> validation_run_items.id`
- Unique index: `ix_validation_llm_evaluations_run_item_id(run_item_id)`
- Index: `ix_validation_llm_evaluations_status(status)`

---

## 13) `validation_logic_evaluations`

### 테이블 개요

- Table name: `validation_logic_evaluations`
- Business purpose: run item에 대한 규칙/필드 기반 로직 평가 결과 저장
- Primary key: `id`
- Important relationships:
  - `run_item_id -> validation_run_items.id` (1:1)
- Data lifecycle:
  - 생성: 로직 평가 잡 수행 시 run item 단위 생성
  - 수정: 재평가 시 결과 변경 가능
  - 보존: 자동 규칙 평가 이력으로 보존

### 컬럼 정의

| Column name | Type | Nullable | Default | Description | Example value | Notes |
|---|---|---|---|---|---|---|
| `id` | `varchar(36)` | No | UUID (app) | 로직 평가 ID | `33ea03de-b887-4f68-8170-b4318a8d840a` | PK |
| `run_item_id` | `varchar(36)` | No | 없음 | 대상 run item ID | `1e8a924b-a6ac-44ec-8f57-c93ece2c53f7` | FK, unique index |
| `eval_items_json` | `text` | No | `""` (app) | 로직 평가 항목(JSON 문자열) | `[{"field":"dealType","expected":"SALE","actual":"SALE"}]` | JSON string |
| `result` | `varchar(20)` | No | `SKIPPED` (app) | 로직 평가 결과 | `PASS` | index |
| `fail_reason` | `text` | No | `""` (app) | 실패 사유 | `가격 필드 누락` |  |
| `evaluated_at` | `datetime` | No | UTC now (app) | 평가 시각 | `2026-02-18 10:45:16` |  |

### 인덱스/제약조건

- PK: `id`
- FK: `run_item_id -> validation_run_items.id`
- Unique index: `ix_validation_logic_evaluations_run_item_id(run_item_id)`
- Index: `ix_validation_logic_evaluations_result(result)`

---

## 부록: 관계 요약

- Query Group 1:N Query
- Test Set N:M Query (`validation_test_set_items` 경유)
- Test Set 1:N Run
- Run 1:N Run Item
- Run Item 1:1 LLM Evaluation
- Run Item 1:1 Logic Evaluation
- Generic Run 1:N Generic Run Row

## 부록: rename 이력 기록 규칙

- 테이블/컬럼 rename이 발생하면 해당 테이블 섹션의 Notes에 아래 형태로 남긴다.
  - `Rename history: old_name -> new_name (YYYY-MM-DD)`
