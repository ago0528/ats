# Validation Runs API 계약 (run 목록 조회)

본 문서는 `질문 결과` 화면에서 사용하는 `GET /validation-runs` 조회 API의 파라미터/응답 계약을 정리한다.

## 1) Endpoint

- Method: `GET`
- Path: `/api/v1/validation-runs`
- Auth: 현재 구현 기준 별도 인증 미요구 (백오피스 내부 라우팅에서 처리)
- Response: `200`

## 2) Query Parameters

| 파라미터           | 타입      | 필수 | 기본값 | 설명                                                          |
| ------------------ | --------- | ---- | ------ | ------------------------------------------------------------- |
| `environment`      | `string`  | N    | -      | 실행 환경 필터 (`dev` \| `st2` \| `st` \| `pr`)               |
| `testSetId`        | `string`  | N    | -      | 테스트 세트 ID로 필터. 빈값이 아닌 특정 ID를 전달             |
| `status`           | `string`  | N    | -      | 실행 상태 필터 (`PENDING` \| `RUNNING` \| `DONE` \| `FAILED`) |
| `evaluationStatus` | `string`  | N    | -      | 평가 상태 파생 필터. 아래 값 허용 (한글/영문 모두)            |
| `offset`           | `integer` | N    | `0`    | 시작 offset                                                   |
| `limit`            | `integer` | N    | `50`   | 페이지 크기                                                   |

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
      "agentId": "ORCHESTRATOR_ASSISTANT",
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
      "evalCancelRequested": false,
      "evalCancelRequestedAt": null,
      "averageResponseTimeSec": 1.234,
      "scoreSummary": {
        "totalItems": 10,
        "executedItems": 10,
        "errorItems": 0,
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

### 실행 파라미터 의미 (2026-02 기준)

- `conversationRoomCount`: 실행 room 배치 개수. 배치는 순차 처리된다. (`room1` 완료 후 `room2`)
- `agentParallelCalls`: 각 room 배치 내부에서 질의를 동시에 처리하는 워커 수
- `repeatInConversation`: 동일 room 배치 내 반복 횟수
- `conversationId`(run item): 항목 단위로 저장되는 대화 식별자이며, 같은 room 내에서 동일 ID를 보장하지 않는다

---

## 5) 부분 실행/부분 평가 API (`itemIds`)

워크벤치의 질의별 `재실행`/`재평가` 동작을 위한 계약이다. `itemIds`는 같은 run 안의 `validation_run_items.id` 목록을 의미한다.

### 5-1) 부분 실행

- Method: `POST`
- Path: `/api/v1/validation-runs/{run_id}/execute`
- Body:
  - 공통: `bearer`, `cms`, `mrs`
  - 선택: `itemIds?: string[]`

동작:
- `itemIds` 미지정: 기존과 동일하게 전체 실행 (`run.status == PENDING` 필요)
- `itemIds` 지정:
  - 대상 item 유효성 검증 (모두 해당 run 소속이어야 함)
  - 대상 item 실행 결과/평가 결과 스냅샷 초기화 후 부분 실행
  - `run.status == RUNNING` 또는 `run.eval_status == RUNNING`이면 `409`
  - 단, `run.status == RUNNING` 이지만 고착(stale)으로 판단되면 자동 복구 후 부분 실행을 허용
    - stale 기준: `max(300초, timeoutMs*3)` 동안 실행 시각 진행이 없음
    - 복구 시 run status는 `FAILED`로 정리된 뒤 요청된 `itemIds` 부분 실행을 시작

### 5-2) 부분 평가

- Method: `POST`
- Path: `/api/v1/validation-runs/{run_id}/evaluate`
- Body:
  - 선택: `openaiModel`, `maxChars`, `maxParallel`
  - 선택: `itemIds?: string[]`

동작:
- `itemIds` 미지정: 기존과 동일한 전체 평가
- `run.eval_status == RUNNING`이면 active 평가 job 존재 여부를 확인하고, active job이 없으면 stale로 간주해 `PENDING`으로 자동 복구 후 평가를 시작
- `itemIds` 지정:
  - 대상 item 유효성 검증 (모두 해당 run 소속이어야 함)
  - 대상 item에 실행 결과가 있어야 함 (`executedAt`/`error`/`rawResponse` 중 하나)
  - 대상 item의 `expected_result_snapshot` 누락 시 `409 expected_result_missing`
  - 평가 완료 후 run 전체 스냅샷을 재집계

---

### 5-3) 평가 중단 요청

- Method: `POST`
- Path: `/api/v1/validation-runs/{run_id}/evaluate/cancel`

동작:
- `run.eval_status != RUNNING`이면 `409` (`Evaluation is not running`)
- active 평가 job이 있으면 취소 요청 플래그를 기록하고 `CANCEL_REQUESTED` 반환
- 이미 취소 요청된 상태에서 active job이 남아 있으면 `ALREADY_REQUESTED` 반환
- active job이 없는 RUNNING은 stale로 간주해 `PENDING`으로 복구하고 `RECOVERED_STALE` 반환

Response:

```json
{
  "ok": true,
  "action": "CANCEL_REQUESTED",
  "evalStatus": "RUNNING",
  "evalCancelRequested": true
}
```

`action` 값:
- `CANCEL_REQUESTED`
- `ALREADY_REQUESTED`
- `RECOVERED_STALE`

## 6) 기대결과 일괄 업데이트 API

질문 결과 상세에서 Run Item 스냅샷(`expected_result_snapshot`)을 대량 수정하기 위한 계약이다.

### 6-1) 템플릿 다운로드

- Method: `GET`
- Path: `/api/v1/validation-runs/{run_id}/expected-results/template.csv`
- Response: CSV
- 컬럼:
  - `Item ID`
  - `Query ID`
  - `방/반복`
  - `질의`
  - `기존 기대결과`
  - `기대결과`

### 6-2) Preview

- Method: `POST`
- Path: `/api/v1/validation-runs/{run_id}/expected-results/bulk-update/preview`
- Content-Type: `multipart/form-data`
- Body: `file` (`.csv`, `.xlsx`, `.xls`)

#### 식별/수정 컬럼 후보

- Item ID: `Item ID`, `itemId`, `runItemId`, `run_item_id`, `item_id`
- 기대결과: `기대결과`, `기대 결과`, `expectedResult`, `expected_result`, `expected`

#### Response

```json
{
  "totalRows": 120,
  "validRows": 118,
  "plannedUpdateCount": 40,
  "unchangedCount": 60,
  "invalidRows": [2, 17],
  "missingItemIdRows": [2],
  "duplicateItemIdRows": [17],
  "unmappedItemRows": [44],
  "previewRows": [
    { "rowNo": 1, "itemId": "uuid", "status": "planned-update", "changedFields": ["expectedResult"] }
  ],
  "remainingMissingExpectedCountAfterApply": 3
}
```

상태값:
- `planned-update`
- `unchanged`
- `missing-item-id`
- `duplicate-item-id`
- `unmapped-item-id`

### 6-3) Apply

- Method: `POST`
- Path: `/api/v1/validation-runs/{run_id}/expected-results/bulk-update`
- Content-Type: `multipart/form-data`
- Body: `file`

#### 실행 제약

- `run.status == RUNNING` 이면 `409`
- `run.eval_status == RUNNING` 이면 `409`

#### Response

```json
{
  "requestedRowCount": 120,
  "updatedCount": 40,
  "unchangedCount": 60,
  "skippedMissingItemIdCount": 1,
  "skippedDuplicateItemIdCount": 1,
  "skippedUnmappedCount": 1,
  "evalReset": true,
  "remainingMissingExpectedCount": 3
}
```

#### 부가 동작

- `updatedCount > 0`이면 평가 결과 자동 초기화:
  - `validation_llm_evaluations` (해당 run item 전부) 삭제
  - `validation_score_snapshots` (해당 run) 삭제
  - run `eval_status = PENDING`, `eval_started_at/eval_finished_at = NULL`
- `validation_logic_evaluations`는 DB에 물리적으로 남아 있으나, 현재 파이프라인에서는 생성/갱신하지 않는다(미사용 상태 유지).

---

## 7) GNB 진행 알림 API

검증 화면을 벗어나 있어도 현재 실행/평가 중인 Run을 GNB에서 확인하기 위한 계약이다.

### 7-1) 진행 중 Run 조회

- Method: `GET`
- Path: `/api/v1/validation-run-activity`
- Query:
  - `environment` (required): `dev | st2 | st | pr`
  - `actorKey` (required): 읽음 상태 식별 키
  - `limit` (optional, default `20`, max `100`)
- 활성 Run 기준:
  - `status == RUNNING`
  - 또는 `status == DONE && evalStatus == RUNNING`

#### Response

```json
{
  "items": [
    {
      "runId": "uuid",
      "runName": "실행중 Run",
      "testSetId": "uuid",
      "status": "RUNNING",
      "evalStatus": "PENDING",
      "totalItems": 30,
      "doneItems": 12,
      "errorItems": 1,
      "llmDoneItems": 0,
      "createdAt": "2026-02-25T10:00:00",
      "startedAt": "2026-02-25T10:00:10",
      "evalStartedAt": null,
      "isRead": false
    }
  ],
  "unreadCount": 1
}
```

오류:
- `actorKey` 누락/공백: `400`

### 7-2) 읽음 처리

- Method: `POST`
- Path: `/api/v1/validation-run-activity/read`
- Body:
  - 개별 읽음:
    - `{ "environment":"dev", "actorKey":"...", "runIds":["run-id-1"] }`
  - 전체 읽음(현재 활성 Run 대상):
    - `{ "environment":"dev", "actorKey":"...", "markAll": true }`

#### Response

```json
{
  "updatedCount": 2
}
```

오류:
- `actorKey` 누락/공백: `400`
- `markAll=false` 이고 `runIds`가 비어 있거나 해당 환경(`environment`)에서 유효한 run ID가 없음: `400`
