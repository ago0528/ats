## 문서 개요

- `C:\Users\ago0528\cursor_work\recruit_solution\src\ats\ax\test\agent_qa\backoffice_app_v2.py`를 개선하기 위해 피드백을 모아둔 문서

## UI/UX 피드백

### 설정 패널

1. 사용자는 설정 패널의 'ATS cURL 붙여넣기' 기능을 통해 'ATS_BEARER_TOKEN, ATS_CMS_TOKEN, ATS_MRS_SESSION'을 인증할 수 있다.

- 사용자가 API에서 cURL을 복사한 후 붙여넣을 수 있는 input이 있고, '인증' 버튼을 클릭하면 TOKEN이 자동으로 입력되고 토큰 상태가 체크된다.
- Parsing 로직은 `C:\Users\ago0528\cursor_work\recruit_solution\src\ats\ax\test\agent_qa\curl_parsing.py`을 참고한다.

2. 세션이 살아있는지 체크하는 버튼이 있어야 한다.

3. OpenAI 평가 영역에선 LLM 병렬수, 응답 최대 길이(평가 입력)만 수정할 수 있다. 그 외 나머지(OPENAI_API_KEY~Cached Input $)는 숨김 처리한다.

### 메인 컨테이너 > 지원자 에이전트 탭

1. 실행 버튼 실행 전, `send_query`의 payload 세부값을 설정할 수 있게 한다.

- 정확히는 `"context": {}`를 추가할 것인지 묻는 것이다.
- conversationId와 userMessage는 지금 값을 유지하되, 사용자가 원하면 context의 내용을 입력할 수 있게 해야 한다. 이 입력은 버튼을 실행하기 윗 단계에서 알 수 있어야 하고, Default는 context 입력이 없는 것이다.
- 이 내용은 `backoffice_app_v2.py`의 689~692 Lines를 참고한다.

2. 진행률을 알 수 있다.

- 총 몇 개를 질의를 수행해야 하고, 몇 개 질의를 수행했는지, 얼마나 기다렸고, 예상 완료 시간도 알 수 있으면 좋겠다.

3. 결과 테이블의 답을 기다리는 중에는 이 기다리는 중이란 게 명확하게 인지되면 좋겠다. (예: 스켈레톤, 실시간으로 채워지는 값)

4. 세션 만료를 고려하여 질문 10개 단위로 결과가 자동 저장된다.

5. 사용자는 LLM이 동일 채팅방에서 몇 번이나 채팅을 호출할지 정할 수 있다.

- 현재는 2회 고정이며, 이후엔 Default 1회 고정, 최대 4번까지로 설정할 수 있으면 좋겠다.

### 메인 컨테이너 > 신규 탭

1. '공통' 탭을 추가한다. (적절한 이름을 제안해라.)

- 이 탭의 목표는 질의 CSV를 간소화하는데 있다.
- 사용자가 입력한 CSV 중 '질의, LLM 평가기준'이란 컬럼만 필수값으로 두고, 이 둘을 통해 subscribe API 응답(SSE)에서 텍스트를 추출하는 걸 목표한다.
- 이땐 'CHAT' Event 뿐 아니라, 'CHAT_EXECUTION_PROCESS' Event의 응답도 가져와야 한다.
- CHAT_EXECUTION_PROCESS의 데이터 샘플: `{"replyTargetChatId":4329,"messageSummary":"이동 준비가 완료됐어요.","message":"선택한 채용 ‘(가온) 2026년 공채 (플로우)’의 채용 현황(대시보드)에서 상시 채용 성과를 확인할 수 있어요."}`

2. 이 탭에선 CSV를 업로드해서 질의를 할 수도 있고, 직접 입력해서 질의할 수도 있어야 한다.

E.o.D
