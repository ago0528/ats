# LangGraph Agent Flow 사용 가이드

## 빠른 시작

### GPT-5 사용 (권장)

```bash
python agent_flow_gpt5_direct.py
```

✅ **성공적으로 테스트 완료** (터미널 로그 315-459번 라인 참조)

### GPT-4 사용 (안정)

```bash
python agent_flow_simple.py
# 또는
python agent_flow_prototype.py
```

## 파일 비교

| 파일 | 모델 | 특징 | 추천 |
|------|------|------|------|
| `agent_flow_gpt5_direct.py` | gpt-5-mini-2025-08-07 | OpenAI Client 직접 사용, temperature 문제 해결 | ⭐ GPT-5 사용 시 |
| `agent_flow_simple.py` | gpt-4o-mini | 간단하고 안정적 | ⭐ 안정성 우선 |
| `agent_flow_prototype.py` | gpt-4o-mini | LangChain 완전 통합 | 학습 및 확장용 |

## 실행 결과 예시

### agent_flow_gpt5_direct.py 성공 사례

```
🚀 Agent Flow 시작 (GPT-5-mini via Direct OpenAI Client)
============================================================

📦 Event: ['agent']
📊 [5%] PLANNING: PRD 작성 시작
   💬 병원 상세 페이지 간호등급 정보 표시 PRD 초안 작성 시작

📊 [20%] RESEARCH: 과거 대화 검토 결과 보고
   💬 관련 대화 3건 확인

📊 [35%] WRITING: PRD 초안 작성 시작
   💬 병원 상세 페이지에 간호등급 정보 표시 관련 PRD 초안 작성 시작

============================================================
✅ Agent Flow 완료
============================================================

💡 최종 답변:
[전체 PRD 문서 생성됨 - 11개 섹션, 상세한 요구사항 포함]
```

## 환경 설정

### 1. API 키 설정

**PowerShell:**
```powershell
$env:OPENAI_API_KEY="your-api-key-here"
```

**또는 .env 파일:**
```
OPENAI_API_KEY=your-api-key-here
```

### 2. 패키지 설치

```bash
pip install langgraph langchain-openai langchain-core python-dotenv openai
```

## GPT-5 사용 시 주의사항

GPT-5는 reasoning 모델로 다음 파라미터를 지원하지 않습니다:
- `temperature`
- `top_p`
- `presence_penalty`
- `frequency_penalty`

**해결 방법:**
- ✅ `agent_flow_gpt5_direct.py` 사용 (OpenAI Client 직접 호출)
- ❌ `ChatOpenAI` 클래스 직접 사용 (자동으로 temperature 추가)

참고: [OpenAI Community - GPT-5 Temperature Issue](https://community.openai.com/t/gpt-5-models-temperature/1337957)

## 문제 해결

### Temperature 오류

```
Error: 'temperature' does not support 0.7 with this model
```

**해결:** `agent_flow_gpt5_direct.py` 사용

### Method object is not a mapping

```
Error: 'method' object is not a mapping
```

**해결:** `agent_flow_prototype.py` 또는 `agent_flow_simple.py` 사용 (GPT-4)

### 모델을 찾을 수 없음

```
Error: The model does not exist
```

**해결:** 
1. API 키에 GPT-5 접근 권한이 있는지 확인
2. 모델명 확인: `gpt-5-mini-2025-08-07`
3. 또는 GPT-4 버전 사용

## 커스터마이징

### 새로운 도구 추가

```python
@tool
def my_custom_tool(param: str) -> str:
    """도구 설명"""
    return "결과"

# tools 리스트에 추가
tools = [report_progress, search_conversations, read_document, my_custom_tool]
```

### System Prompt 수정

`run_agent_with_progress` 함수의 `system_prompt` 변수 수정

### 다른 쿼리 실행

```python
run_agent_with_progress("원하는 질문을 입력하세요")
```

## 성능 비교

| 항목 | GPT-5 | GPT-4 |
|------|-------|-------|
| 속도 | 빠름 | 중간 |
| 추론 능력 | 우수 | 좋음 |
| 안정성 | 새로운 모델 | 검증됨 |
| 파라미터 제어 | 제한적 | 완전 지원 |
| 비용 | 저렴 | 중간 |

## 추가 리소스

- [LangGraph 문서](https://langchain-ai.github.io/langgraph/)
- [OpenAI Platform](https://platform.openai.com/docs)
- [GPT-5 문제 해결 가이드](./gpt5_troubleshooting.md)
- [README](./README.md)

## 지원

문제가 발생하면:
1. `gpt5_troubleshooting.md` 참조
2. 터미널 오류 메시지 확인
3. 다른 파일 버전 시도 (GPT-5 ↔ GPT-4)

