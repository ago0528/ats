# Validation Runs API 계약 (run 목록 조회)

본 문서는 `검증 이력` 화면에서 사용하는 `GET /validation-runs` 조회 API의 파라미터/응답 계약을 정리한다.

## 1) Endpoint

- Method: `GET`
- Path: `/api/v1/validation-runs`
- Auth: 현재 구현 기준 별도 인증 미요구 (백오피스 내부 라우팅에서 처리)
- Response: `200`

## 2) Query Parameters

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `environment` | `string` | N | - | 실행 환경 필터 (`dev` \| `st2` \| `st` \| `pr`) |
| `testSetId` | `string` | N | - | 테스트 세트 ID로 필터. 빈값이 아닌 특정 ID를 전달 |
| `status` | `string` | N | - | 실행 상태 필터 (`PENDING` \| `RUNNING` \| `DONE` \| `FAILED`) |
| `evaluationStatus` | `string` | N | - | 평가 상태 파생 필터. 아래 값 허용 (한글/영문 모두) |
| `offset` | `integer` | N | `0` | 시작 offset |
| `limit` | `integer` | N | `50` | 페이지 크기 |

### `testSetId` 특이 동작

- `__NULL__`, `null` : `testSetId IS NULL` 조회
- 그 외 문자열: 동일 값의 test set ID만 조회
- 미지정: 전체 조회

### `status` 및 `evaluationStatus` 규칙

- `status`: `ValidationRun.status` 직접 비교 필터입니다.
- `evaluationStatus`: run 자체 상태 기반이 아닌, 실행/평가 진행 파생값을 기준으로 필터링합니다.
  - 허용 값(한글): `평가대기`, `평가중`, `평가완료`
  - 허용 값(영문): `PENDING`, `RUNNING`, `DONE` (내부 변환 후 동일 처리)
- 동작 요약
  - `평가완료`: `run.status == DONE` 이고 LLM 평가 완료 조건 만족
  - `평가중`: `run.status == DONE` 이고 LLM 평가가 진행 중으로 판단될 때
  - `평가대기`: 위 두 경우가 아니고, 실행이 완료되지 않았거나 LLM 평가가 시작 전인 경우

## 3) Response

`200` 응답:

```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Run 2026-02-20 ...",
      "environment": "dev",
      "status": "DONE",
      "evalStatus": "DONE",
      "baseRunId": null,
      "testSetId": "uuid",
      "agentId": "ORCHESTRATOR_WORKER_V3",
      "testModel": "gpt-4o",
      "evalModel": "gpt-4o-mini",
      "repeatInConversation": 1,
      "conversationRoomCount": 1,
      "agentParallelCalls": 2,
      "timeoutMs": 10000,
      "options": {},
      "createdAt": "2026-02-20T10:00:00",
      "startedAt": "2026-02-20T10:00:01",
      "finishedAt": "2026-02-20T10:00:10",
      "evalStartedAt": "2026-02-20T10:00:11",
      "evalFinishedAt": "2026-02-20T10:00:13",
      "averageResponseTimeSec": 1.234,
      "scoreSummary": {
        "totalItems": 10,
        "executedItems": 10,
        "errorItems": 0,
        "logicPassItems": 9,
        "logicPassRate": 90,
        "llmDoneItems": 8,
        "llmMetricAverages": {},
        "llmTotalScoreAvg": 4.11
      },
      "totalItems": 10,
      "doneItems": 10,
      "errorItems": 0,
      "llmDoneItems": 8
    }
  ],
  "total": 1
}
```

## 4) 정렬/기타

- 정렬: `createdAt DESC` (최신순)
- `GET /validation-runs`는 `offset`/`limit` 적용한 부분 집합을 반환
- 응답은 프런트/백엔드에서 필드 추가 가능성이 있는 공통 객체 형태를 유지

