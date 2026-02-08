# 지원자 관리 에이전트 검증 백오피스

## 1) 설치
```bash
pip install -r requirements.txt
```

## 2) .env 준비
같은 폴더에 `.env` 파일을 만들고 아래 값을 채우세요.

- `ATS_BEARER_TOKEN`
- `ATS_CMS_TOKEN`
- `ATS_MRS_SESSION`
- `OPENAI_API_KEY` (평가 수행 시 필요)
- `OPENAI_MODEL` (기본: gpt-5.2)

`.env.example` 참고.

## 3) 실행
### (A) 통합 백오피스
```bash
streamlit run backoffice_app.py
```

### (B) URL Agent 단독 도구
```bash
streamlit run bulktest_url_agent_updated.py
```

## 4) CSV 포맷 (지원자 에이전트)
기본 템플릿 컬럼:
- ID
- 질의
- 기대 필터/열

나머지 컬럼(1차/2차 답변 등)은 도구가 자동으로 생성/채웁니다.

## 5) CSV 포맷 (URL Agent)
권장 헤더:
- ID
- 질의
- 기대URL

`기대URL`은 부분 문자열 또는 `/정규식/` 형태를 지원합니다.
