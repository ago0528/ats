# Backoffice 데이터 정의 문서 (PM Friendly)

- 대상 독자: PM, PO, QA, 운영 담당자
- 목적: "어떤 데이터가 왜 저장되는지"를 기술 용어 최소화로 이해하고, 운영/분석에 바로 활용할 수 있게 정리
- 기준 시스템: `backoffice/backend` (SQLite + SQLAlchemy)

## 문서 구성

- `docs/architecture/data/schema.md`: 테이블/컬럼 메인 정의서
- `docs/architecture/data/relations.mmd`: Mermaid ERD(관계도)
- `docs/architecture/data/sqlite-metrics.md`: 복붙용 SQLite 조회 SQL 모음
- `docs/architecture/data/data_dictionary.csv`: 스프레드시트용 컬럼 목록(선택 산출물)

## 문서 사용법

1. 비즈니스 관점에서 먼저 `schema.md`의 "Business purpose"를 본다.
2. 화면/기능 간 데이터 흐름은 `relations.mmd`를 본다.
3. 실제 운영 수치 확인은 `sqlite-metrics.md`의 SQL을 복붙해서 실행한다.
4. 상세 필터링/정렬은 `sqlite-metrics.md` 쿼리의 파라미터만 바꿔 재사용한다.

## 업데이트 규칙 (요약)

- DB 스키마(테이블/컬럼/관계/제약) 변경 시, 같은 작업 단위에서 이 폴더 문서를 반드시 함께 갱신한다.
- 변경 시 최소 갱신 대상:
  - `schema.md`
  - `relations.mmd`
- 테이블명/컬럼명 변경(rename)이 있으면 `schema.md` Notes에 "이전 명칭 -> 새 명칭"을 남긴다.
- 자세한 절차는 스킬 `docs/skills/db-schema-doc-updater/SKILL.md`를 따른다.

## 용어 간단 정의

- Table: 같은 성격의 데이터를 저장하는 "엑셀 시트" 단위
- Column: 테이블 안 각 데이터 항목(열)
- PK (Primary Key): 각 행을 고유하게 식별하는 대표 키
- FK (Foreign Key): 다른 테이블 PK를 참조하는 연결 키
- Nullable: 비어 있어도 되는지 여부
- Default: 값을 안 넣었을 때 자동으로 들어가는 기본값
- Index: 검색 속도를 높이기 위한 보조 구조
- Unique: 중복 저장을 금지하는 제약
- Enum: 허용 값이 제한된 상태/코드 집합

## 데이터 정확성 기준

이 문서는 아래 순서로 사실을 맞춘다.

1. `backoffice/backend/app/models/*.py` (모델 정의)
2. `backoffice/backend/app/main.py`의 startup 스키마 보정 로직
3. 실제 SQLite 스키마(`backoffice/backend/backoffice.db`)
