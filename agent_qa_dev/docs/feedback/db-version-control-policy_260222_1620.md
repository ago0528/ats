# DB 버전 관리 정책 (검토용)

> 작성 시점: 2026-02-22
> 목적: 백오피스 백엔드의 SQLite 파일(`backoffice.db`, `backoffice_test.db`)을 Git에서 어떻게 관리할지 결정 근거 정리

## 1) 현재 요청 반영(즉시 반영분)

- 이번 커밋에서는 요청에 따라 DB 변경분(`agent_qa_dev/backoffice/backend/backoffice.db`, `agent_qa_dev/backoffice/backend/backoffice_test.db`)을 함께 커밋합니다.
- 단, DB 파일은 협업에서 추적 기준이 되기 어렵기 때문에 장기적으로는 레포에서 분리하는 방안을 별도로 검토합니다.

## 2) 왜 DB 파일을 보통 추적하지 않는가

- 실행/테스트마다 파일 변경이 많고, 내용이 환경마다 달라 재현성 감소
- Git 이력에서 "데이터 스냅샷"이 늘어남
- 충돌/병합 시 실제 코드 변경보다 우선순위가 높아져 작업 흐름이 흔들릴 수 있음

## 3) 장기 추천 운영안

1. `git rm --cached`로 `backoffice/backend/*.db` 추적 해제
2. `.gitignore`에 `agent_qa_dev/backoffice/backend/*.db` 패턴 추가
3. DB 경로는 `BACKOFFICE_DB_PATH` 환경변수로 관리
4. 팀 문서에 "개발 DB는 로컬 경로 고정" 규칙 및 초기화 절차 정의

예시:

```bash
export BACKOFFICE_DB_PATH=$HOME/.ats/backoffice_dev.db
export BACKOFFICE_DB_PATH=$HOME/.ats/backoffice_test.db  # 테스트 실행 시
```

## 4) 참고 기준

- 실행 상태 보호: `agent_qa_dev/backoffice/backend/app/core/db.py`의 `is_test_db_path` 규칙( suffix `*_test` )과 `assert_safe_db_reset`는 테스트 DB 보호를 위한 가드 역할 유지
- 원격에서 DB 파일이 삭제되어도, 로컬 경로 고정 정책만 지키면 앱 동작에는 영향이 없음

## 5) 다음 액션(권장)

- 기존 커밋에 포함된 DB는 이번 이슈 대응용으로 보존
- 추가 변경부터는 장기 운영안(추적 해제 + ignore)으로 전환 여부를 PR에서 확정 후 적용
