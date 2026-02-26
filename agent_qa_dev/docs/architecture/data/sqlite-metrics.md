# SQLite 운영 지표/조회 SQL 스니펫

- 대상 DB: `backoffice/backend/backoffice.db`
- 실행 예시:
  - `sqlite3 backoffice/backend/backoffice.db`
  - `.headers on`
  - `.mode column`
- 날짜 컬럼은 UTC 기준 문자열(`datetime`)로 저장된다.

## 인터랙티브 모드
cd /Users/ago0528/Desktop/files/01_work/01_planning/01_vibecoding/ats/agent_qa_dev
sqlite3 backoffice/backend/backoffice.db

## 테이블명 매핑(실제)

- 질의 그룹: `validation_query_groups`
- 질의: `validation_queries`
- 테스트 세트: `validation_test_sets`
- 테스트 세트 항목: `validation_test_set_items`
- 실행(run): `validation_runs`
- 실행 알림 읽음: `validation_run_activity_reads`
- 실행 항목(run item): `validation_run_items`
- LLM 평가: `validation_llm_evaluations`
- 로직 평가: `validation_logic_evaluations`
- 점수 스냅샷: `validation_score_snapshots`
- 자동화 잡: `automation_jobs`
- 프롬프트 감사 로그: `prompt_audit_logs`
- 프롬프트 스냅샷: `prompt_snapshots`

---

## Q01. 핵심 테이블 적재 건수 한 번에 보기

- 무엇을 보는가: 주요 테이블별 전체 row 수
- 파라미터: 없음
- 주의사항: 대용량 테이블에서는 count가 느릴 수 있음

```sql
SELECT 'validation_query_groups' AS table_name, COUNT(*) AS row_count FROM validation_query_groups
UNION ALL
SELECT 'validation_queries', COUNT(*) FROM validation_queries
UNION ALL
SELECT 'validation_test_sets', COUNT(*) FROM validation_test_sets
UNION ALL
SELECT 'validation_test_set_items', COUNT(*) FROM validation_test_set_items
UNION ALL
SELECT 'validation_runs', COUNT(*) FROM validation_runs
UNION ALL
SELECT 'validation_run_activity_reads', COUNT(*) FROM validation_run_activity_reads
UNION ALL
SELECT 'validation_run_items', COUNT(*) FROM validation_run_items
UNION ALL
SELECT 'validation_llm_evaluations', COUNT(*) FROM validation_llm_evaluations
UNION ALL
SELECT 'validation_logic_evaluations', COUNT(*) FROM validation_logic_evaluations
UNION ALL
SELECT 'validation_score_snapshots', COUNT(*) FROM validation_score_snapshots
UNION ALL
SELECT 'automation_jobs', COUNT(*) FROM automation_jobs
UNION ALL
SELECT 'prompt_audit_logs', COUNT(*) FROM prompt_audit_logs
UNION ALL
SELECT 'prompt_snapshots', COUNT(*) FROM prompt_snapshots
ORDER BY row_count DESC;
```

## Q02. 최근 수정된 질의 목록

- 무엇을 보는가: 가장 최근 업데이트된 질의와 소속 그룹
- 파라미터: `row_limit`
- 주의사항: `updated_at`이 없는 레거시 데이터는 정렬에서 뒤로 갈 수 있음

```sql
WITH params AS (
  SELECT 30 AS row_limit
)
SELECT
  q.id,
  q.updated_at,
  q.category,
  g.group_name,
  q.query_text
FROM validation_queries q
JOIN validation_query_groups g ON g.id = q.group_id
ORDER BY q.updated_at DESC
LIMIT (SELECT row_limit FROM params);
```

## Q03. 최근 생성/실행된 Run 목록

- 무엇을 보는가: run 상태, 테스트 세트, 시작/종료 시각
- 파라미터: `row_limit`
- 주의사항: `test_set_id`가 null인 run이 있을 수 있음

```sql
WITH params AS (
  SELECT 50 AS row_limit
)
SELECT
  r.id,
  r.name,
  r.created_at,
  r.environment,
  r.status,
  ts.name AS test_set_name,
  r.started_at,
  r.finished_at
FROM validation_runs r
LEFT JOIN validation_test_sets ts ON ts.id = r.test_set_id
ORDER BY r.created_at DESC
LIMIT (SELECT row_limit FROM params);
```

## Q04. 최근 실행 항목(run item)과 오류 확인

- 무엇을 보는가: 최근 run item의 오류 여부/지연시간
- 파라미터: `row_limit`
- 주의사항: `error`는 빈 문자열(`''`)도 정상값으로 저장됨

```sql
WITH params AS (
  SELECT 100 AS row_limit
)
SELECT
  ri.id,
  ri.executed_at,
  ri.run_id,
  ri.ordinal,
  ri.latency_ms,
  CASE WHEN ri.error <> '' THEN 'ERROR' ELSE 'OK' END AS error_flag,
  ri.error
FROM validation_run_items ri
ORDER BY ri.executed_at DESC
LIMIT (SELECT row_limit FROM params);
```

## Q05. 기간 내 Run 상태 분포

- 무엇을 보는가: 상태별 run 건수
- 파라미터: `date_from` (YYYY-MM-DD)
- 주의사항: 문자열 날짜 비교이므로 `YYYY-MM-DD` 형식 유지 필요

```sql
WITH params AS (
  SELECT '2026-02-01' AS date_from
)
SELECT
  r.status,
  COUNT(*) AS run_count
FROM validation_runs r
WHERE date(r.created_at) >= (SELECT date_from FROM params)
GROUP BY r.status
ORDER BY run_count DESC;
```

## Q06. 일자별 Run 생성 추이

- 무엇을 보는가: 일 단위 run 생성량
- 파라미터: `date_from`
- 주의사항: UTC 기준으로 집계됨

```sql
WITH params AS (
  SELECT '2026-02-01' AS date_from
)
SELECT
  date(r.created_at) AS run_date,
  COUNT(*) AS run_count
FROM validation_runs r
WHERE date(r.created_at) >= (SELECT date_from FROM params)
GROUP BY date(r.created_at)
ORDER BY run_date DESC;
```

## Q07. 오래 걸리는 PENDING/RUNNING Run 찾기

- 무엇을 보는가: 아직 종료되지 않은 run 중 오래된 건
- 파라미터: `min_age_minutes`
- 주의사항: `created_at` 기준 나이이며 실제 큐 대기시간과 다를 수 있음

```sql
WITH params AS (
  SELECT 30 AS min_age_minutes
)
SELECT
  r.id,
  r.environment,
  r.status,
  r.created_at,
  ROUND((julianday('now') - julianday(r.created_at)) * 24 * 60, 1) AS age_minutes
FROM validation_runs r
WHERE r.status IN ('PENDING', 'RUNNING')
  AND ((julianday('now') - julianday(r.created_at)) * 24 * 60) >= (SELECT min_age_minutes FROM params)
ORDER BY age_minutes DESC;
```

## Q08. 완료된 Run 소요시간(분) 상위

- 무엇을 보는가: 완료 run의 실행 시간 상위 목록
- 파라미터: `row_limit`
- 주의사항: `started_at`/`finished_at` 둘 다 있어야 계산 가능

```sql
WITH params AS (
  SELECT 30 AS row_limit
)
SELECT
  r.id,
  r.environment,
  r.status,
  r.started_at,
  r.finished_at,
  ROUND((julianday(r.finished_at) - julianday(r.started_at)) * 24 * 60, 2) AS duration_minutes
FROM validation_runs r
WHERE r.status = 'DONE'
  AND r.started_at IS NOT NULL
  AND r.finished_at IS NOT NULL
ORDER BY duration_minutes DESC
LIMIT (SELECT row_limit FROM params);
```

## Q09. Run별 에러율

- 무엇을 보는가: run 단위 총 실행수/오류수/오류율
- 파라미터: `date_from`, `row_limit`
- 주의사항: 오류 판단 기준은 `error <> ''`

```sql
WITH params AS (
  SELECT '2026-02-01' AS date_from, 50 AS row_limit
)
SELECT
  ri.run_id,
  COUNT(*) AS total_items,
  SUM(CASE WHEN ri.error <> '' THEN 1 ELSE 0 END) AS error_items,
  ROUND(100.0 * SUM(CASE WHEN ri.error <> '' THEN 1 ELSE 0 END) / COUNT(*), 2) AS error_rate_pct
FROM validation_run_items ri
JOIN validation_runs r ON r.id = ri.run_id
WHERE date(r.created_at) >= (SELECT date_from FROM params)
GROUP BY ri.run_id
ORDER BY error_rate_pct DESC, total_items DESC
LIMIT (SELECT row_limit FROM params);
```

## Q10. 느린 run item 상위(지연시간 기준)

- 무엇을 보는가: latency가 큰 실행 항목
- 파라미터: `row_limit`
- 주의사항: `latency_ms`가 NULL인 건 제외됨

```sql
WITH params AS (
  SELECT 100 AS row_limit
)
SELECT
  ri.id,
  ri.run_id,
  ri.ordinal,
  ri.latency_ms,
  ri.executed_at
FROM validation_run_items ri
WHERE ri.latency_ms IS NOT NULL
ORDER BY ri.latency_ms DESC
LIMIT (SELECT row_limit FROM params);
```

## Q11. Run Item + Query + Group 조인 상세

- 무엇을 보는가: 실행 결과를 원본 질의/질의그룹과 함께 조회
- 파라미터: `target_run_id`, `row_limit`
- 주의사항: `query_id`가 NULL이면 LEFT JOIN으로 빈값 표시

```sql
WITH params AS (
  SELECT 'REPLACE_WITH_RUN_ID' AS target_run_id, 200 AS row_limit
)
SELECT
  ri.id AS run_item_id,
  ri.ordinal,
  g.group_name,
  q.query_text,
  ri.query_text_snapshot,
  ri.error,
  ri.latency_ms
FROM validation_run_items ri
LEFT JOIN validation_queries q ON q.id = ri.query_id
LEFT JOIN validation_query_groups g ON g.id = q.group_id
WHERE ri.run_id = (SELECT target_run_id FROM params)
ORDER BY ri.ordinal ASC
LIMIT (SELECT row_limit FROM params);
```

## Q12. 테스트 세트 구성(질의 순서 포함)

- 무엇을 보는가: 특정 테스트 세트의 질의 구성과 순서
- 파라미터: `target_test_set_id`
- 주의사항: `ordinal`로 정렬해 실제 실행 순서 확인

```sql
WITH params AS (
  SELECT 'REPLACE_WITH_TEST_SET_ID' AS target_test_set_id
)
SELECT
  tsi.ordinal,
  q.id AS query_id,
  g.group_name,
  q.category,
  q.query_text
FROM validation_test_set_items tsi
JOIN validation_queries q ON q.id = tsi.query_id
JOIN validation_query_groups g ON g.id = q.group_id
WHERE tsi.test_set_id = (SELECT target_test_set_id FROM params)
ORDER BY tsi.ordinal ASC;
```

## Q13. 기간 내 질의 사용 빈도(run item 기준)

- 무엇을 보는가: 실제 실행에서 자주 호출된 질의 상위
- 파라미터: `date_from`, `row_limit`
- 주의사항: 스냅샷만 있는 run item(`query_id` NULL)은 제외됨

```sql
WITH params AS (
  SELECT '2026-02-01' AS date_from, 50 AS row_limit
)
SELECT
  q.id AS query_id,
  q.query_text,
  g.group_name,
  COUNT(*) AS run_item_count
FROM validation_run_items ri
JOIN validation_runs r ON r.id = ri.run_id
JOIN validation_queries q ON q.id = ri.query_id
JOIN validation_query_groups g ON g.id = q.group_id
WHERE ri.query_id IS NOT NULL
  AND date(r.created_at) >= (SELECT date_from FROM params)
GROUP BY q.id, q.query_text, g.group_name
ORDER BY run_item_count DESC
LIMIT (SELECT row_limit FROM params);
```

## Q14. Run별 평가 완료율(LLM/Logic)

- 무엇을 보는가: run마다 평가가 얼마나 완료됐는지
- 파라미터: `date_from`
- 주의사항: LLM/Logic은 각각 1:1 구조(미평가면 NULL)

```sql
WITH params AS (
  SELECT '2026-02-01' AS date_from
)
SELECT
  r.id AS run_id,
  COUNT(ri.id) AS run_items,
  SUM(CASE WHEN le.id IS NOT NULL THEN 1 ELSE 0 END) AS llm_evaluated,
  SUM(CASE WHEN lo.id IS NOT NULL THEN 1 ELSE 0 END) AS logic_evaluated,
  ROUND(100.0 * SUM(CASE WHEN le.id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(ri.id), 2) AS llm_eval_pct,
  ROUND(100.0 * SUM(CASE WHEN lo.id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(ri.id), 2) AS logic_eval_pct
FROM validation_runs r
JOIN validation_run_items ri ON ri.run_id = r.id
LEFT JOIN validation_llm_evaluations le ON le.run_item_id = ri.id
LEFT JOIN validation_logic_evaluations lo ON lo.run_item_id = ri.id
WHERE date(r.created_at) >= (SELECT date_from FROM params)
GROUP BY r.id
ORDER BY r.created_at DESC;
```

## Q15. 테스트 세트별 LLM 평균 점수

- 무엇을 보는가: 테스트 세트 단위 평균 total_score
- 파라미터: `date_from`
- 주의사항: `total_score` NULL은 자동 제외됨

```sql
WITH params AS (
  SELECT '2026-02-01' AS date_from
)
SELECT
  ts.id AS test_set_id,
  ts.name AS test_set_name,
  COUNT(le.id) AS evaluated_items,
  ROUND(AVG(le.total_score), 2) AS avg_total_score
FROM validation_runs r
JOIN validation_test_sets ts ON ts.id = r.test_set_id
JOIN validation_run_items ri ON ri.run_id = r.id
JOIN validation_llm_evaluations le ON le.run_item_id = ri.id
WHERE date(r.created_at) >= (SELECT date_from FROM params)
  AND le.total_score IS NOT NULL
GROUP BY ts.id, ts.name
ORDER BY avg_total_score DESC;
```

## Q16. 테스트 세트별 로직 평가 결과 분포

- 무엇을 보는가: 테스트 세트별 PASS/FAIL/SKIPPED 분포
- 파라미터: `date_from`
- 주의사항: 결과 값은 현재 문자열로 저장됨(표준 코드 강제 없음)

```sql
WITH params AS (
  SELECT '2026-02-01' AS date_from
)
SELECT
  ts.name AS test_set_name,
  lo.result,
  COUNT(*) AS result_count
FROM validation_runs r
JOIN validation_test_sets ts ON ts.id = r.test_set_id
JOIN validation_run_items ri ON ri.run_id = r.id
JOIN validation_logic_evaluations lo ON lo.run_item_id = ri.id
WHERE date(r.created_at) >= (SELECT date_from FROM params)
GROUP BY ts.name, lo.result
ORDER BY ts.name ASC, result_count DESC;
```

## Q17. 로직 실패 사유 TOP N

- 무엇을 보는가: 로직 평가 실패 이유 빈도 상위
- 파라미터: `date_from`, `row_limit`
- 주의사항: 빈 문자열 fail_reason은 제외

```sql
WITH params AS (
  SELECT '2026-02-01' AS date_from, 20 AS row_limit
)
SELECT
  lo.fail_reason,
  COUNT(*) AS fail_count
FROM validation_logic_evaluations lo
JOIN validation_run_items ri ON ri.id = lo.run_item_id
JOIN validation_runs r ON r.id = ri.run_id
WHERE date(r.created_at) >= (SELECT date_from FROM params)
  AND lo.result = 'FAIL'
  AND lo.fail_reason <> ''
GROUP BY lo.fail_reason
ORDER BY fail_count DESC
LIMIT (SELECT row_limit FROM params);
```

## Q18. 프롬프트 변경 이력(최근)

- 무엇을 보는가: 최근 프롬프트 변경 이력과 길이 변화량
- 파라미터: `row_limit`
- 주의사항: 이력은 append-only 로그 기준

```sql
WITH params AS (
  SELECT 100 AS row_limit
)
SELECT
  p.created_at,
  p.environment,
  p.worker_type,
  p.action,
  p.actor,
  p.before_len,
  p.after_len,
  (p.after_len - p.before_len) AS diff_len
FROM prompt_audit_logs p
ORDER BY p.created_at DESC
LIMIT (SELECT row_limit FROM params);
```

## Q19. 프롬프트 현재/직전 스냅샷(최근 갱신순)

- 무엇을 보는가: 워커별 현재 프롬프트와 직전 프롬프트 보관 상태
- 파라미터: `row_limit`
- 주의사항: `current_prompt`는 ATS 조회 기준 마지막 동기화 시점 값

```sql
WITH params AS (
  SELECT 100 AS row_limit
)
SELECT
  s.updated_at,
  s.environment,
  s.worker_type,
  LENGTH(s.current_prompt) AS current_len,
  LENGTH(s.previous_prompt) AS previous_len,
  CASE
    WHEN s.previous_prompt = '' THEN 'NO_PREVIOUS'
    ELSE 'HAS_PREVIOUS'
  END AS previous_status,
  s.actor
FROM prompt_snapshots s
ORDER BY s.updated_at DESC
LIMIT (SELECT row_limit FROM params);
```

## Q20. 진행 알림 읽음 현황 (actor별)

- 무엇을 보는가: actor별 진행 알림 읽음 누적 현황과 최근 읽음 시각
- 파라미터: `row_limit`
- 주의사항: `actor_key`는 토큰 해시 기반 식별 키일 수 있음

```sql
WITH params AS (
  SELECT 50 AS row_limit
)
SELECT
  r.actor_key,
  COUNT(*) AS read_rows,
  COUNT(DISTINCT r.run_id) AS run_count,
  MAX(r.read_at) AS last_read_at
FROM validation_run_activity_reads r
GROUP BY r.actor_key
ORDER BY last_read_at DESC
LIMIT (SELECT row_limit FROM params);
```

---

## 자주 바꾸는 파라미터 가이드

- 기간 시작일: `date_from` (`YYYY-MM-DD`)
- 조회 개수: `row_limit` (예: `20`, `50`, `100`)
- 특정 실행 ID: `target_run_id`
- 특정 테스트 세트 ID: `target_test_set_id`

## 성능/정확성 메모

- 인덱스가 있는 주요 컬럼: `run_id`, `query_id`, `status`, `environment`, `test_set_id`, `ordinal`
- 날짜 조건은 `date(column)`을 사용하면 인덱스를 덜 활용할 수 있다. 대량 데이터에서는 범위 조건(`column >= 'YYYY-MM-DD'`)으로 튜닝한다.
- 모든 시간은 UTC 기준으로 저장되므로, 리포팅 시 로컬 시간대로 변환이 필요할 수 있다.
