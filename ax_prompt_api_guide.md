## Worker type

- ORCHESTRATOR_WORKER("하위 에이전트 실행 판단 AI 에이전트"),
- SCENARIO_WORKER("시나리오(Scenario) AI 에이전트"),
- SCENARIO_SCRIPT_WORKER("대본(Scenario Script) 진행 AI 에이전트"),
- RESUME_WORKER("지원자 관리 AI 에이전트"),
- RECRUIT_PLAN_CREATE_WORKER("채용 플랜 생성 AI 에이전트"),
- RECRUIT_WIKI_WORKER("채용 위키 AI 에이전트"),

## Request URL

### URL

- DV: https://api-llm.ats.kr-dv-midasin.com/{path}
- PR: (not yet)

### Sample

- DV: https://api-llm.ats.kr-dv-midasin.com/api/v1/ai/orchestrator/chat-room?limit=30
- PR: (not yet)

## API

### 1. 프롬프트 수정/조회

- Path : PUT /api/v1/ai/prompt
- Body

```json
{
  "workerType": "에이전트 Worker 타입(ex. ORCHESTRATOR_WORKER)",
  "prompt": "변경할 프롬프트(null이면 현재 프롬프트 조회 가능)"
}
```

- Response

```json
{
  "before": "변경전 프롬프트",
  "after": "변경후 프롬프트"
}
```

- Next. “이제 프롬프트가 완벽하다. 코드로 백업을 남겨두겠다.” → 구상에게 전달

### 2. 프롬프트 초기화 (코드에 남겨둔 System Prompt로 초기화 됨)

- Path : PUT /api/v1/ai/prompt/reset
- Body

```json
{
  "workerType": "에이전트 Worker 타입(ex. ORCHESTRATOR_WORKER)"
}
```

- Response

```json
{
  "before": "변경전 프롬프트",
  "after": "변경후 프롬프트"
}
```

### 3. Worker를 특정해서 질문하기 (프롬프트 테스트)

- Path : POST /api/v1/ai/prompt/worker/test
- Header (배포 환경의 API 요청 정보에서 추출)

```txt
Authorization : Retention 토큰 (ex. Bearer eyJ0eXAiOiJKV1QiLCJ~~~~)
Mrs-Session : Mrs 세션 (ex. ZTNhYWVjMmItNGZkMC00NDBm~~~~)
Cms-Access-Token : Mrs-Cms 토큰 (ex. eyJ0eXAiOiJKV1QiLCJ~~~~)
```

- Body

```json
{
  "workerType": "에이전트 Worker 타입(ex. ORCHESTRATOR_WORKER)",
  "conversationId": "대화 맥락 유지를 위한 ID(처음 대화 시작 시 null, 대화 이어갈 시에 Response의 conversationId 사용)",
  "userMessage": "질문"
}
```

- Response

```json
{
  "conversationId": "대화 맥락 유지를 위한 ID(같은 대화방에서 다음 질문 시 사용)",
  "answer": "에이전트 Worker 답변(Worker마다 형태가 다름)"
}
```
