## 문서 개요

- `C:\Users\ago0528\cursor_work\recruit_solution\src\ats\ax\test\agent_qa\backoffice_app_v2.py`를 개선하기 위해 피드백을 모아둔 문서

## 피드백

### 메인 컨테이너 > 지원자 에이전트 탭

1. 진행, 경과 시간이 너무 보기 힘들다.

- 큰 글시로 하나씩 내려오니 보기 힘든 것 같다.
- 각 데이터가 업데이트 되는 형태면 될 것 같다.
- 진행 1/19 였다면, 하나가 완료됐을 때 이게 2/19로 업데이트되는 형태로 말이다.
- 예상 남은 시간을 개선해서, 총 경과 시간 값을 추가하면 좋겠다. -> 총 경과 시간(예상 남은 시간), 값은 13.7초(약 247초 남음) 표기

2. 'Context 사용'뿐 아니라, "targetAssistant":"RECRUIT_PLAN_ASSISTANT"도 입력할 수 있는 곳이 들어가야 한다.

- 이 구조를 참고하자 -> payload = {"conversationId": conversation_id, "context": {"recruitPlanId": 968},"targetAssistant":"RECRUIT_PLAN_ASSISTANT","userMessage": message} #'실행 에이전트' 케이스 (v14.2.x 구조)
- 참고로 이건 '범용 테스트' 탭에도 있어야 한다.

### 공통

1. 현재는 범용 테스트, URL 에이전트 테스트 탭이 어떤 조건을 만족해야만 보이는 것 같다. 바로 보이게 개선하자.

2. 범용 테스트 탭을 맨 왼쪽으로 이동시킨다.

3. URL Agent (이동) 테스트 탭 제목을 변경한다. -> TO-BE: 이동 에이전트 검증

E.o.D
