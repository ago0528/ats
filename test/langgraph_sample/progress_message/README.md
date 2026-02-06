# LangGraph Agent Flow 프로토타입

OpenAI GPT 모델을 사용한 LangGraph 기반 Agent Flow 구현입니다.

## 파일 선택 가이드

| 파일                        | 모델        | 용도                              | 상태    |
| --------------------------- | ----------- | --------------------------------- | ------- |
| `agent_flow_gpt5_direct.py` | GPT-5-mini  | GPT-5 사용 (Direct OpenAI Client) | ✅ 권장 |
| `agent_flow_simple.py`      | GPT-4o-mini | 안정적인 GPT-4 사용               | ✅ 권장 |
| `agent_flow_prototype.py`   | GPT-4o-mini | LangChain 완전 사용               | ✅ 안정 |

## 주요 기능

- OpenAI GPT-5 모델 지원 (gpt-5-mini, gpt-5-nano)
- 실시간 진행 상황 보고 (report_progress tool)
- 과거 대화 검색 및 문서 읽기
- 상태 관리 및 도구 실행 추적
- 스트리밍 지원

## 설치

필수 패키지를 설치했습니다:

```bash
pip install langgraph langchain-openai langchain-core python-dotenv
```

## 환경 설정

### OpenAI API 키 설정

**PowerShell에서:**

```powershell
$env:OPENAI_API_KEY="your-api-key-here"
```

**또는 .env 파일 생성:**

프로젝트 루트에 `.env` 파일을 만들고 다음 내용을 추가했습니다:

```
OPENAI_API_KEY=your-api-key-here
```

## 모델 설정

`agent_flow_prototype.py` 파일 상단에서 모델을 설정할 수 있습니다:

```python
# GPT-5 모델 선택
GPT5_MODEL_NAME = "gpt-5-mini"  # 또는 "gpt-5-nano", "gpt-5"

# Reasoning 설정 (선택사항)
REASONING_CONFIG = {
    "effort": "medium",  # 'low', 'medium', 'high'
    "summary": "auto"    # 'detailed', 'auto', None
}
```

### 사용 가능한 GPT-5 모델

| 모델명       | 특징                        |
| ------------ | --------------------------- |
| `gpt-5-mini` | 균형잡힌 성능과 비용 (권장) |
| `gpt-5-nano` | 빠르고 비용 효율적          |
| `gpt-5`      | 최고 성능                   |

## 실행

```bash
python src/ats/ax/test/langgraph_sample/agent_flow_prototype.py
```

### 실행 결과 예시

```
🤖 사용 모델: gpt-5-mini
📚 LangGraph Agent Flow 프로토타입

============================================================
🚀 Agent Flow 시작
============================================================

📊 [10%] PLANNING: 작업 계획 수립
   💬 PRD 작성을 위한 5단계 작업 계획 수립 중

📊 [30%] EXECUTING: 과거 대화 검색
   💬 병원 상세 페이지 관련 대화 검색 중

...
```

## GPT-5 모델 주의사항

GPT-5 모델은 GPT-4와 다음과 같은 차이가 있습니다:

1. **제한된 파라미터 지원**

   - `temperature`: 기본값(1)만 지원
   - `max_tokens`: 일부 제약 존재
   - 기본 설정으로 사용하는 것을 권장했습니다

2. **새로운 기능**

   - `reasoning` 파라미터 지원
   - 향상된 추론 능력

3. **초기화 방식**

   ```python
   # GPT-5 권장 방식 (중요: temperature=None 필수)
   llm = ChatOpenAI(
       model="gpt-5-mini",
       temperature=None  # GPT-5는 기본값만 지원하므로 None으로 설정
   )

   # Reasoning 사용 시
   llm = ChatOpenAI(
       model="gpt-5-mini",
       temperature=None,
       reasoning={"effort": "medium", "summary": "auto"}
   )
   ```

## 코드 구조

```
agent_flow_prototype.py
├── 설정 (Configuration)
│   ├── GPT5_MODEL_NAME
│   └── REASONING_CONFIG
├── State 정의
│   └── AgentState (messages, progress_log)
├── Tools 정의
│   ├── report_progress
│   ├── search_conversations
│   └── read_document
├── Nodes 정의
│   ├── agent_node (LLM 호출)
│   └── tool_node (도구 실행)
├── Graph 구성
│   ├── should_continue (라우팅)
│   └── create_agent_graph
└── 실행 로직
    └── run_agent_with_progress
```

## 커스터마이징

### 새로운 도구 추가

```python
@tool
def my_custom_tool(param: str) -> str:
    """도구 설명"""
    # 구현
    return "결과"

# agent_node와 tool_node의 tools 리스트에 추가
tools = [report_progress, search_conversations, read_document, my_custom_tool]
```

### System Prompt 수정

`run_agent_with_progress` 함수의 `system_prompt` 변수를 수정했습니다.

## 문제 해결

### API 키 오류

```
❌ 실행 중 오류 발생: Could not resolve authentication method
```

→ `OPENAI_API_KEY` 환경변수를 확인해주세요.

### Temperature 오류

```
Error: 'temperature' does not support 0.0 with this model
```

→ GPT-5는 temperature 파라미터를 지원하지 않습니다. 코드에서 제거되었습니다.

### 빈 응답

GPT-5 reasoning 모델에서 빈 응답이 나오는 경우, `max_tokens`를 `None`으로 설정하거나 증가시켜주세요.

## 참고 문서

- [LangChain OpenAI Chat 문서](https://docs.langchain.com/oss/python/integrations/chat/openai)
- [OpenAI GPT-5 API 문서](https://platform.openai.com/docs)
- [LangGraph 문서](https://langchain-ai.github.io/langgraph/)
