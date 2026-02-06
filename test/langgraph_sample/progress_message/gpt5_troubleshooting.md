# GPT-5 모델 문제 해결 가이드

GPT-5 모델 사용 시 발생할 수 있는 문제와 해결 방법을 정리했습니다.

## Temperature 오류 해결

### 문제

```
Error code: 400 - {'error': {'message': "Unsupported value: 'temperature' does not support 0.7 with this model. Only the default (1) value is supported."
```

### 원인

[OpenAI 커뮤니티 포스트](https://community.openai.com/t/gpt-5-models-temperature/1337957)에 따르면, **GPT-5는 reasoning 모델이므로 `temperature`, `top_p`, `presence_penalty`, `frequency_penalty` 파라미터를 지원하지 않습니다.**

### 해결 방법

GPT-5 API 호출 시 이러한 파라미터를 **완전히 제거**해야 합니다.

#### 방법 1: `temperature=None` 설정 (권장)

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="gpt-5-mini-2025-08-07",
    temperature=None  # GPT-5는 None으로 설정해야 합니다
)
```

이 방법은 API 요청에 temperature 파라미터를 포함하지 않습니다.

#### 방법 2: `default_headers` 사용

만약 방법 1이 작동하지 않는다면:

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="gpt-5-mini-2025-08-07",
    temperature=None,
    model_kwargs={}  # 빈 딕셔너리로 추가 파라미터 제거
)
```

#### 방법 3: 직접 OpenAI 클라이언트 사용

LangChain이 자동으로 파라미터를 추가하는 것을 피하려면:

```python
from openai import OpenAI

client = OpenAI()

response = client.chat.completions.create(
    model="gpt-5-mini-2025-08-07",
    messages=[
        {"role": "user", "content": "Hello!"}
    ]
    # temperature 파라미터를 명시적으로 제외
)
```

#### 방법 4: LangChain 최신 버전 확인

```bash
pip install --upgrade langchain-openai
```

최신 버전에서는 GPT-5 지원이 개선되었을 수 있습니다.

## 다른 파라미터 제한

GPT-5 모델은 다음 파라미터들도 제한적으로 지원합니다:

| 파라미터            | GPT-4       | GPT-5       | 설정 방법          |
| ------------------- | ----------- | ----------- | ------------------ |
| `temperature`       | 0-2         | 기본값(1)만 | `temperature=None` |
| `max_tokens`        | 사용자 지정 | 제한적      | `max_tokens=None`  |
| `top_p`             | 0-1         | 제한적      | 명시하지 않음      |
| `frequency_penalty` | 0-2         | 제한적      | 명시하지 않음      |
| `presence_penalty`  | 0-2         | 제한적      | 명시하지 않음      |

### GPT-5 권장 초기화 설정

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="gpt-5-mini-2025-08-07",
    temperature=None,  # 필수
    max_tokens=None,   # 필수
    # 다른 파라미터는 명시하지 않음
)
```

## GPT-5 모델 목록

현재 사용 가능한 GPT-5 모델들:

| 모델명                  | 설명           | 추천 용도           |
| ----------------------- | -------------- | ------------------- |
| `gpt-5-mini`            | 균형잡힌 성능  | 일반적인 작업       |
| `gpt-5-nano`            | 빠르고 저렴    | 간단한 작업, 테스트 |
| `gpt-5`                 | 최고 성능      | 복잡한 추론 작업    |
| `gpt-5-mini-2025-08-07` | 특정 날짜 버전 | 버전 고정 필요 시   |

## Reasoning 기능 (GPT-5 전용)

GPT-5는 새로운 reasoning 기능을 지원합니다:

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="gpt-5-mini",
    temperature=None,
    reasoning={
        "effort": "medium",  # 'low', 'medium', 'high'
        "summary": "auto"    # 'detailed', 'auto', None
    }
)
```

Reasoning 출력 확인:

```python
response = llm.invoke("복잡한 수학 문제")

# Reasoning 내용 확인
for block in response.content_blocks:
    if block["type"] == "reasoning":
        print("Reasoning:", block["reasoning"])

# 최종 답변
print("Answer:", response.text)
```

## 일반적인 문제들

### 1. 빈 응답이 나오는 경우

```python
# 해결: max_tokens를 충분히 설정
llm = ChatOpenAI(
    model="gpt-5-mini",
    temperature=None,
    max_tokens=None  # 또는 충분히 큰 값
)
```

### 2. API 키 오류

```bash
# PowerShell
$env:OPENAI_API_KEY="your-api-key"

# Linux/Mac
export OPENAI_API_KEY="your-api-key"
```

### 3. 모델을 찾을 수 없는 경우

```
Error: The model `gpt-5-mini` does not exist
```

해결:

- API 키가 GPT-5 접근 권한을 가지고 있는지 확인
- 모델명 철자 확인
- OpenAI 대시보드에서 사용 가능한 모델 확인

## 참고 자료

- [LangChain OpenAI 문서](https://docs.langchain.com/oss/python/integrations/chat/openai)
- [OpenAI API 문서](https://platform.openai.com/docs)
- [GPT-5 가이드](https://platform.openai.com/docs/guides)

## 문의

문제가 계속되면:

1. LangChain 버전 확인: `pip show langchain-openai`
2. OpenAI Python SDK 버전 확인: `pip show openai`
3. 최신 버전으로 업그레이드: `pip install --upgrade langchain-openai openai`
