# AX (Applicant eXperience) - AI Agent System

채용솔루션(ATS)을 위한 AI 멀티 에이전트 시스템

## 구조

```
ats/
├── agent_qa/                    # 에이전트 QA 및 백오피스 (AQB v1.0)
│   ├── aqb_v1.0.0.py            # Streamlit 검증 백오피스 앱 (진입점)
│   ├── aqb_agent_client.py      # 지원자 관리 에이전트 API 클라이언트
│   ├── aqb_bulk_runner.py       # 벌크 호출·OpenAI 평가 러너
│   ├── aqb_common_utils.py      # CSV 템플릿·로직 검사 등 공통 유틸
│   ├── aqb_openai_judge.py      # ChatGPT 기반 자동 평가(JSON)
│   ├── aqb_prompt_template.py   # 평가 프롬프트 템플릿·환경 프리셋
│   ├── aqb_runtime_utils.py     # 비동기 실행·Excel 내보내기
│   ├── aqb_url_tester.py        # URL Agent(이동/버튼) 벌크 테스트
│   ├── bulktest_agent_v3.py     # 에이전트 벌크 테스트 (구)
│   ├── prompt_api.py            # 프롬프트 관리 API 클라이언트
│   ├── curl_parsing.py          # cURL 파싱 유틸리티
│   ├── query/                   # 에이전트 질의 CSV
│   ├── 준비물/                  # 검증 규칙·도구 문서
│   ├── 지원자 관리 에이전트 첫 벌크 테스트_260202/
│   └── legacy/                  # 이전 버전 앱·문서 (backoffice_app_v3.x 등)
├── curating_agent/              # 큐레이팅 에이전트
│   ├── prototype/               # 프로토타입 (super_agent_260115)
│   └── reivew_260127/           # 리뷰 문서·데이터
├── prompt/                      # 에이전트 프롬프트 템플릿
│   ├── nmrs_v14.0.0/            # v14.0.0 (오케스트레이터, 시나리오 등)
│   └── nmrs_v14.1.0/            # v14.1.0 (URL·위키 워커 등)
├── docs/                        # 프로젝트 문서
└── 99_legacy/                   # 레거시 코드
    └── ax_url_agent/            # URL 에이전트 (구버전)
```

## 주요 기능

- **오케스트레이터**: 사용자 질의를 적절한 에이전트로 라우팅
- **지원자 관리 에이전트**: 지원자/후보자 데이터 관리
- **플랜 생성 에이전트**: 채용 계획 생성
- **위키 에이전트**: 채용 관련 지식베이스 관리
- **이동 에이전트**: URL 워커라고도 불리며, URL 기반 네비게이션 및 데이터 추출
- **큐레이팅 에이전트**: 일일 채용 업무 추천 및 가이드

## 기술 스택

- Python 3.x
- Streamlit
- LangChain
- OpenAI / Claude API

## 실행 방법 (에이전트 QA 백오피스)

에이전트 검증 백오피스(AQB v1.0) 실행:

```bash
cd agent_qa
streamlit run aqb_v1.0.0.py
```

`.env`에 `ATS_BEARER_TOKEN`, `ATS_CMS_TOKEN`, `OPENAI_API_KEY` 등이 설정되어 있어야 합니다. `agent_qa/.env.example` 참고.

## 문서

- [파이썬 가상환경 설치 가이드](docs/파이썬_가상환경_설치_가이드.md)
- [배포 준비 체크리스트](docs/배포_준비_체크리스트.md)