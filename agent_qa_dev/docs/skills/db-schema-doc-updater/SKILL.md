---
name: db-schema-doc-updater
description: Use when database schema changes in this repo (tables/columns/keys/relations/indexes) to keep PM-friendly data documentation in sync under docs/architecture/data.
---

# DB Schema Doc Updater

## Overview

이 스킬은 백엔드 DB 스키마 변경 시, PM도 이해 가능한 데이터 정의 문서를 항상 최신 상태로 유지하기 위한 작업 절차다.

## When to Use

다음 변경이 하나라도 있으면 반드시 사용한다.

- `backoffice/backend/app/models/*.py` 변경
- `backoffice/backend/app/main.py`의 startup 스키마 보정 로직 변경 (`PRAGMA`, `ALTER TABLE`, `create_all` 관련)
- DB 스키마 산출물 변경 (`*.sql`, `*.dbml`, migration/DDL 성격 파일)
- 테이블/컬럼/인덱스/관계/nullable/default/enum 값 변경

## Required Outputs

스키마 변경 작업에는 아래 문서 갱신이 포함되어야 한다.

1. `docs/architecture/data/schema.md`
2. `docs/architecture/data/relations.mmd`
3. `docs/architecture/data/sqlite-metrics.md` (테이블/컬럼명이 바뀐 경우 필수)
4. 필요 시 `docs/architecture/data/data_dictionary.csv` 재생성

## Source of Truth Priority

문서 사실값은 아래 우선순위로 확인한다.

1. SQLAlchemy 모델: `backoffice/backend/app/models/*.py`
2. 런타임 스키마 보정: `backoffice/backend/app/main.py`
3. 실제 SQLite 스키마: `backoffice/backend/backoffice.db` (`.schema`, `PRAGMA table_info`)

값이 다르면 이유를 확인한 뒤 문서 Notes에 차이를 명시한다.

## Workflow

1. Detect
- 변경 파일에서 스키마 영향 범위를 식별한다.
- 영향 유형을 분류한다: `ADD`, `DROP`, `RENAME`, `TYPE/NULL/DEFAULT`, `FK/INDEX`.

2. Reconstruct
- 최신 테이블/컬럼/관계를 재구성한다.
- enum 값, nullable, default, PK/FK/unique/index를 표로 정리한다.

3. Update PM Docs
- `schema.md`: 테이블 목적 + 컬럼 정의 + 예시값 + 제약조건을 PM 친화 문장으로 갱신
- `relations.mmd`: 실제 FK 기준으로 관계도 갱신
- `sqlite-metrics.md`: 변경된 테이블/컬럼명 반영, 깨진 쿼리 수정

4. Optional Export
- 스프레드시트 협업 필요 시 `data_dictionary.csv`를 재생성한다.

5. Emit Change Summary
- PR/커밋 메시지에 붙일 수 있는 변경 요약을 생성한다.

## Writing Rules

- 개발자 약어 남발 금지, PM이 이해 가능한 목적/예시 중심 설명
- 관계/키/nullable/default는 정확성 최우선
- JSON 문자열 컬럼은 "JSON string"임을 명시
- rename이 있으면 Notes에 반드시 기록
  - 형식: `Rename history: old_name -> new_name (YYYY-MM-DD)`

## Guardrails

- DB 변경인데 `docs/architecture/data/*` 변경이 없으면 작업 미완료로 간주한다.
- 문서와 코드가 충돌하면 문서를 코드/실스키마에 맞춰 먼저 수정한다.

## Output Template (for PR body)

아래 형식으로 요약을 남긴다.

- Schema changes
  - Added: `table.column`, `table` ...
  - Removed: `table.column`, `table` ...
  - Updated: `type/null/default/index/fk` ...
  - Renamed: `old -> new`
- Docs updated
  - `docs/architecture/data/schema.md`
  - `docs/architecture/data/relations.mmd`
  - `docs/architecture/data/sqlite-metrics.md`
  - `docs/architecture/data/data_dictionary.csv` (if regenerated)

## Completion Checklist

- [ ] 스키마 영향 범위 식별 완료
- [ ] `schema.md` 반영 완료
- [ ] `relations.mmd` 반영 완료
- [ ] `sqlite-metrics.md` 검증 완료
- [ ] (선택) `data_dictionary.csv` 재생성 완료
- [ ] 변경 요약(ADD/DROP/UPDATE/RENAME) 작성 완료
