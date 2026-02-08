# ResumeWorkerV3 사용 가능한 Tool 목록

## 개요
ResumeWorkerV3는 채용 데이터(지원서/지원자)를 조회·집계하여 인사담당자가 원하는 수치/비교 결과를 제공하는 AI 워커입니다.

---

## 1. ToolResumeFinderV3 (지원자 검색 도구)

### 1.1 지원자 관리 화면 URL 생성
- **Tool Name**: `RESUME_CONFIRM_URL`
- **설명**: 지원자 관리 화면으로 이동할 수 있는 URL을 생성
- **파라미터**:
  - `columnList`: 지원자 데이터 검색 필드(컬럼)
  - `conditionList`: 지원자 데이터 검색 조건

### 1.2 지원자 검색
- **Tool Name**: `RESUME_FINDER`
- **설명**: 검색 조건으로 필터링된 지원자 수를 검색
- **파라미터**:
  - `columnList`: 지원자 데이터 검색 필드(컬럼)
  - `conditionList`: 지원자 데이터 검색 조건
- **반환**: 지원자 수 또는 오류 메시지

### 1.3 검색 조건 문서 추출
- **Tool Name**: `RESUME_CONDITION_DOCUMENT`
- **설명**: 검색 조건을 생성하기 위한 JSON 명세(문서)를 추출 (지원자 검색 전 필수 호출)
- **파라미터**:
  - `filterTypeList`: 검색 조건 유형 목록
- **반환**: 조건별 JSON 스키마 및 사용 가능한 Tool 안내

### 1.4 채용플랜 목록 조회
- **Tool Name**: `RESUME_FINDER_RECRUIT_PLAN_LIST`
- **설명**: 채용플랜의 공고 목록을 조회
- **파라미터**:
  - `searchKeyword`: 채용플랜명 검색어 (선택)
- **반환**: 채용플랜 목록 (최대 100개)

### 1.5 공고 목록 조회
- **Tool Name**: `RESUME_FINDER_RECRUIT_NOTICE_LIST`
- **설명**: 공고 목록을 조회
- **파라미터**:
  - `searchKeyword`: 검색어 (선택)
- **반환**: 공고 목록

### 1.6 채용분야 목록 조회
- **Tool Name**: `RESUME_FINDER_RECRUIT_SECTOR_LIST`
- **설명**: 공고의 채용분야 목록을 조회
- **파라미터**:
  - `searchKeyword`: 검색어 (선택)
  - `recruitNoticeSn`: 공고 식별자 (필수)
- **반환**: 채용분야 목록

### 1.7 지원 경로 목록 조회
- **Tool Name**: `RESUME_FINDER_APPLY_CHANNEL_LIST`
- **설명**: 지원 경로 목록을 조회
- **파라미터**: 없음
- **반환**: 지원 경로 목록

### 1.8 국적 검색 조건 생성
- **Tool Name**: `RESUME_FINDER_NATIONALITY_CONDITION`
- **설명**: 국적에 대한 검색 조건을 생성
- **파라미터**:
  - `nationalityNameList`: 국적 이름 목록 (선택)
- **반환**: NationalityCondition 또는 국적 목록

### 1.9 경력 기준 검색 조건 생성
- **Tool Name**: `RESUME_FINDER_CAREER_CRITERIA_CONDITION`
- **설명**: 경력 기준에 대한 검색 조건을 생성
- **파라미터**:
  - `careerCriteriaNameList`: 경력 기준 이름 목록 (선택)
- **반환**: CareerCriteriaCondition 또는 경력 기준 목록

### 1.10 외국어 활용 능력 검색 조건 생성
- **Tool Name**: `RESUME_FINDER_FOREIGN_LANGUAGE_SKILL_CONDITION`
- **설명**: 외국어 활용 능력에 대한 검색 조건을 생성
- **파라미터**:
  - `languageNameList`: 외국어 이름 목록 (선택)
- **반환**: ForeignLanguageSkillCondition 또는 외국어 목록

### 1.11 해외 경험 검색 조건 생성
- **Tool Name**: `RESUME_FINDER_OVERSEAS_EXPERIENCE_CONDITION`
- **설명**: 해외 경험에 대한 검색 조건을 생성
- **파라미터**:
  - `purposeNameList`: 해외 경험 목적 이름 목록 (선택)
- **반환**: OverseasExperienceCondition 또는 해외 경험 목록

### 1.12 학내외 활동 검색 조건 생성
- **Tool Name**: `RESUME_FINDER_ACTIVITY_CONDITION`
- **설명**: 학내외 활동에 대한 검색 조건을 생성
- **파라미터**:
  - `activityNameList`: 활동 이름 목록 (선택)
- **반환**: ActivityCondition 또는 학내외 활동 목록

### 1.13 봉사활동 검색 조건 생성
- **Tool Name**: `RESUME_FINDER_VOLUNTEER_CONDITION`
- **설명**: 봉사활동에 대한 검색 조건을 생성
- **파라미터**:
  - `volunteerNameList`: 봉사활동 이름 목록 (선택)
- **반환**: VolunteerCondition 또는 봉사활동 목록

### 1.14 최종 평가자 검색 조건 생성
- **Tool Name**: `RESUME_FINDER_FINAL_VALUER_CONDITION`
- **설명**: 최종 평가자명으로 검색하여 최종 평가자 검색 조건을 생성
- **파라미터**:
  - `memberName`: 최종 평가자명 검색어 (선택)
- **반환**: FinalValuerCondition

### 1.15 전형 검색 조건 생성
- **Tool Name**: `RESUME_FINDER_SCREENING_CONDITION`
- **설명**: 전형명으로 검색하여 전형 검색 조건을 생성 (채용플랜과 전형유형 필터 필요)
- **파라미터**:
  - `recruitPlanIdList`: 채용플랜 식별자 목록
  - `screeningType`: 전형 유형
  - `screeningName`: 전형명
- **반환**: ResumeScreeningCondition

### 1.16 일반 평가자 검색 조건 생성
- **Tool Name**: `RESUME_FINDER_GENERAL_VALUER_CONDITION`
- **설명**: 일반 평가자명으로 검색하여 일반 평가자 검색 조건을 생성
- **파라미터**:
  - `memberName`: 일반 평가자명 검색어 (선택)
- **반환**: GeneralValuerCondition

### 1.17 고등학교 데이터 검색
- **Tool Name**: `RESUME_FINDER_HIGH_SCHOOL_LIST`
- **설명**: 고등학교 데이터를 검색
- **파라미터**:
  - `keyword`: 고등학교명 검색어 (contains)
- **반환**: 고등학교 목록

### 1.18 대학교 데이터 검색
- **Tool Name**: `RESUME_FINDER_COLLEGE_LIST`
- **설명**: 대학교 데이터를 검색
- **파라미터**:
  - `keyword`: 대학교명 검색어
- **반환**: 대학교 목록

### 1.19 대학교 전공 데이터 검색
- **Tool Name**: `RESUME_FINDER_COLLEGE_MAJOR_LIST`
- **설명**: 대학교 전공 데이터를 검색
- **파라미터**:
  - `keyword`: 대학교 전공명 검색어 (contains)
- **반환**: 대학교 전공 목록

### 1.20 대학원 데이터 검색
- **Tool Name**: `RESUME_FINDER_GRADUATE_SCHOOL_LIST`
- **설명**: 대학원 데이터를 검색
- **파라미터**:
  - `keyword`: 대학원명 검색어 (contains)
- **반환**: 대학원 목록

### 1.21 대학원 전공 데이터 검색
- **Tool Name**: `RESUME_FINDER_GRADUATE_SCHOOL_MAJOR_LIST`
- **설명**: 대학원 전공 데이터를 검색
- **파라미터**:
  - `keyword`: 대학원 전공명 검색어 (contains)
- **반환**: 대학원 전공 목록

### 1.22 자격증 데이터 검색
- **Tool Name**: `RESUME_FINDER_LICENSE_LIST`
- **설명**: 자격증 데이터를 검색
- **파라미터**:
  - `keyword`: 자격증명 검색어 (contains)
- **반환**: 자격증 목록

### 1.23 외국어 시험 데이터 검색
- **Tool Name**: `RESUME_FINDER_FOREIGN_EXAM_LIST`
- **설명**: 외국어 시험 데이터를 검색
- **파라미터**:
  - `keyword`: 외국어 시험명 검색어 (contains)
- **반환**: 외국어 시험 목록

---

## 2. ToolAssistantExecutionProcess (실행 과정 알림 도구)

### 2.1 실행 과정 알림
- **Tool Name**: `ASSISTANT_EXECUTION_PROGRESS_NOTIFY`
- **설명**: 실행 과정/내역을 유저에게 제공
- **파라미터**:
  - `conversationId`: 대화 맥락 유지를 위한 ID
  - `notifyMessageSummary`: 진행 사항 안내 메시지(요약)
  - `notifyMessage`: 진행 사항 안내 메시지
- **동작**: Redis Pub/Sub을 통해 SSE 이벤트 발행

---

## 3. ToolResumeAnalysisCodeV3 (지원자 데이터 분석 코드 실행 도구)

### 3.1 지원자 데이터 분석 코드 실행
- **Tool Name**: `RESUME_ANALYSIS_CODE_RUNNER`
- **설명**: Code 실행 방식으로 지원자 데이터 통계/분석을 실행
- **파라미터**:
  - `conversationId`: 대화 맥락 유지를 위한 ID
  - `command`: 해야할 작업 내용 (1차 필터링 내용 제외)
  - `conditionList`: 지원자 데이터 검색 조건 (1차 필터링)
- **동작**:
  1. ResumeAnalysisCodeCreateWorkerV3를 호출하여 분석 코드 생성
  2. 지원자 수 확인 (최대 제한: ANALYSIS_DATA_MAX_LIMIT)
  3. AWS Lambda를 통해 분석 코드 실행
  4. 분석 결과 반환
- **제한사항**: 분석 대상 지원자 수가 제한을 초과하면 실패

---

## 4. ToolResumeCommonDataSearchWorkerV3Call (공통 데이터 검색 워커 호출 도구)

### 4.1 공통 데이터 검색
- **Tool Name**: `RESUME_COMMON_DATA_SEARCH`
- **설명**: 공통 데이터를 전체 기준으로 검색 (문맥 검색 방식)
- **대상 데이터**: 고등학교, 대학교, 대학원, 자격증, 외국어 시험
- **파라미터**:
  - `conversationId`: 대화 맥락 유지를 위한 ID
  - `command`: 공통 데이터 검색 AI 에이전트가 작업할 내용
- **동작**: ResumeCommonDataSearchWorkerV3를 호출하여 문맥 기반 검색 수행
