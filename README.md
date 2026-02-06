# AX (Applicant eXperience) - AI Agent System

채용솔루션(ATS)을 위한 AI 멀티 에이전트 시스템

## 구조

```
ax/
├── ax_prompt_app.py          # Streamlit 프롬프트 관리 UI
├── prompt_api.py             # 프롬프트 관리 API 클라이언트
├── curl_parsing.py           # cURL 파싱 유틸리티
├── prompt/                   # 에이전트 프롬프트 템플릿
│   ├── nmrs_v14.0.0/         # v14.0.0 프롬프트
│   ├── nmrs_v14.1.0/         # v14.1.0 프롬프트
│   ├── resume_agent_flow/    # 이력서 에이전트 플로우
│   └── data/                 # 참조 데이터
├── ax_url_agent/             # URL 에이전트 서브시스템
├── curating_agent/           # 큐레이팅 에이전트 (GA)
├── agentic_system_development/  # 에이전트 시스템 설계 문서
├── prototype/                # 프로토타입
└── test/                     # 테스트 및 QA
    ├── agent_qa/             # 에이전트 QA 자동화
    └── langgraph_sample/     # LangGraph 샘플
```

## 주요 기능

- **오케스트레이터 워커**: 사용자 질의를 적절한 에이전트로 라우팅
- **이력서 워커**: 지원자/후보자 데이터 관리
- **채용 계획 워커**: 채용 계획 생성
- **위키 워커**: 채용 관련 지식베이스 관리
- **URL 워커**: URL 기반 네비게이션 및 데이터 추출
- **큐레이팅 에이전트**: 일일 채용 업무 추천 및 가이드

## 기술 스택

- Python 3.x
- Streamlit
- LangChain
- OpenAI / Claude API
