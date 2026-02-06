제공해주신 `tool-resume-finder-guide(1209).md` 파일은 **채용 시스템(ATS)에서 지원자를 검색/필터링하기 위한 51가지 조건(Filter)**을 정의하고 있습니다.

이 툴들은 `prompt_resume_worker_qa.md` 에 정의된 AI 에이전트가 사용자의 자연어 질문(예: "서울대 출신 합격자 보여줘")을 **실제 API 호출 가능한 URL 파라미터(JSON 형태)**로 변환하는 데 사용됩니다.

이해를 돕기 위해 51개의 필터를 **기능별로 4가지 카테고리**로 분류하여 도표로 정리해 드립니다.

---

### 1. 기본 정보 및 접수 현황 (Basic & Status)
지원 시기, 공고 정보, 제출 상태 등 지원서의 가장 기초적인 메타데이터를 필터링합니다.

| ID | 필터 타입 (FilterType) | 역할 | 주요 파라미터 | 예시 요청 |
|:---:|:---:|:---|:---|:---|
| 1 | `RESUME_PERIOD` | 기간(지원일/제출일) | `periodPresetType`, `begin`, `end` | "작년 하반기 지원자" |
| 2 | `RESUME_SUBMIT` | 제출 상태 | `submitType` (제출/미제출/임시) | "제출 완료한 사람" |
| 3 | `RECRUIT_NOTICE` | 채용 공고 | `recruitNoticeSnList` | "2024년 공채 지원자" |
| 4 | `APPLY_CHANNEL` | 지원 경로 | `applyChannelCodeList` | "잡코리아로 지원한 사람" |
| 5 | `RESUME_CREATE_CODE` | 작성 방식 | `resumeCreateCodes` (직접/불러오기) | "직접 작성한 지원서" |
| 6 | `RESUME_APPLY_COUNT` | 재지원 횟수 | `inputValue` (횟수) | "3회 이상 지원한 사람" |
| 7 | `MARKING_APPLICANT` | 관심 지원자 마킹 | `remarkableApplicantCodeList` | "관심 지원자로 표시됨" |
| 8 | `READ_STATUS` | 열람 여부 | `readStatus` (열람/미열람) | "안 읽은 지원서" |
| 9 | `MANAGER_UPLOAD_FILE` | 관리자 파일 업로드 | `uploadFileTypes` | "관리자 파일 있는 사람" |

### 2. 지원자 인적사항 및 스펙 (Applicant Specs)
지원자의 학력, 경력, 자격, 병역 등 이력서 상의 구체적인 스펙을 필터링합니다.

| ID | 필터 타입 (FilterType) | 역할 | 주요 파라미터 | 예시 요청 |
|:---:|:---:|:---|:---|:---|
| 10 | `NATIONALITY` | 국적 | `nationalityCodeList` | "외국인 지원자" |
| 11 | `MILITARY` | 병역 | `inputValue` (군필/면제 등) | "군필자만" |
| 12 | `HANDICAP` | 장애 여부 | `inputValue` (Boolean) | "장애인 우대" |
| 13 | `PATRIOT` | 보훈 대상 | `inputValue` (Boolean) | "보훈 대상자" |
| 14 | `FINAL_ACADEMY_CODE` | 최종 학력 | `finalAcademyCodeList` (대졸 등) | "석사 이상" |
| 15 | `GRADUATION_TYPE` | 졸업 상태 | `graduationTypes` (졸업/예정 등) | "졸업 예정자" |
| 16 | `MAJOR_SCORE` | 학점 | `score`, `perfectScore` | "3.5/4.5 이상" |
| 17 | `CAREER_CRITERIA` | 신입/경력 구분 | `companyRecruitCodeSnList` | "경력직 지원자" |
| 18 | `CAREER_PERIOD` | 경력 기간 | `beginPeriod`, `endPeriod` | "3년~5년차" |
| 19 | `PROJECT` | 프로젝트 경험 | `inputValue` (Boolean) | "프로젝트 경험 있음" |
| 20 | `FOREIGN_LANGUAGE_SKILL`| 외국어 능력 | `languageCodeList` | "영어 가능자" |
| 21 | `OVERSEAS_EXPERIENCE` | 해외 경험 | `purposeSnList` | "해외 연수 경험" |
| 22 | `EDUCATION` | 교육 이수 | `inputValue` (Boolean) | "직무 교육 이수자" |
| 23 | `ACTIVITY` | 대외 활동 | `activityCategoryCodeList` | "공모전 수상자" |
| 24 | `VOLUNTEER` | 봉사 활동 | `codeList` | "봉사활동 경험" |

### 3. 전형 진행 및 결과 (Process & Result)
서류, 면접 등 전형 단계별 합불 여부, 참석 여부, 커트라인 등을 필터링합니다.

| ID | 필터 타입 (FilterType) | 역할 | 주요 파라미터 | 예시 요청 |
|:---:|:---:|:---|:---|:---|
| 25 | `RESUME_SCREENING_FINAL_RESULT` | 스크리닝 종합 결과 | `inputValues` (적합/부적합) | "스크리닝 통과자" |
| 26 | `SCREENING_TYPE` | 전형 단계 | `screeningType` (서류/면접) | "1차 면접 대상자" |
| 27 | `TALENT_SCREENING_CUTLINE` | 지원서 커트라인 | `cutlineList` | "커트라인 합격" |
| 28 | `FIT_SCREENING_CUTLINE` | 역량검사 커트라인 | `cutlineList` | "역검 Pass" |
| 31 | `FINAL_PASS_APPLY_SECTOR` | 최종 합격 | `passTypes` | "최종 합격자" |
| 32 | `SCREENING_RESULT` | 단계별 결과 | `resultTypes` (합격/불합격) | "서류 탈락자" |
| 34 | `NEXT_SCREENING_ATTENDANCE` | 다음 전형 참석 | `attendanceTypeList` | "참석 확정자" |
| 35 | `INTERVIEW_ATTENDANCE` | 면접 참석 | `attendanceTypeList` | "면접 불참자" |
| 36 | `SCREENING_GUIDANCE` | 안내 발송 여부 | `isGuidance` | "안내 받은 사람" |
| 37 | `PASS_ANNOUNCEMENT` | 합격 발표 여부 | `isAnnounced` | "발표 난 사람" |
| 38 | `SMS_SEND_STATUS` | SMS 발송 | `tried` | "문자 보낸 사람" |
| 39 | `MAIL_SEND_STATUS` | 메일 발송 | `tried` | "메일 발송 실패" |
| 51 | `SCREENING` | 특정 전형 검색 | `screeningSnList` | "임원 면접 지원자" |

### 4. 평가 점수 및 검사 데이터 (Evaluation & Test Data)
평가자 정보, 종합 점수, 그리고 ACC/NCS와 같은 특정 검사 데이터를 필터링합니다.

| ID | 필터 타입 (FilterType) | 역할 | 주요 파라미터 | 예시 요청 |
|:---:|:---:|:---|:---|:---|
| 29 | `FINAL_VALUER` | 최종 평가자 | `memberSnList` | "김팀장이 평가함" |
| 30 | `OVER_ALL_AVERAGE_SCORE`| 종합 평균 점수 | `rangeType`, `begin`, `end` | "평균 90점 이상" |
| 33 | `GENERAL_VALUER` | 일반 평가자 | `memberSnList` | "이대리가 평가함" |
| 40 | `EXAM_STATUS` | 시험 응시 현황 | `examStatusList` | "시험 완료자" |
| 41~45| `ACC_TEST_...` | ACC 역량검사 | 등급, 점수, 등수, 신뢰도 등 | "ACC A등급 이상" |
| 46~50| `NCS_TEST_...` | NCS 검사 | 등급, 점수, 등수, 신뢰도 등 | "NCS 상위 10%" |

---

### 💡 URL 생성 구조 요약

AI Agent는 위 툴을 조합하여 아래와 같은 형태의 URL 파라미터를 생성합니다.

```json
[
  {
    "filterType": "RESUME_PERIOD",
    "periodPresetType": "MANUAL",
    "begin": "...", 
    "end": "..."
  },
  {
    "filterType": "FINAL_ACADEMY_CODE",
    "finalAcademyCodeList": ["BACHELOR"] 
  }
]
```

**특징:**
1.  **조합 가능:** 여러 필터 객체를 리스트 `[]` 안에 담아 AND 조건으로 처리합니다.
2.  **ViewMode:** 필터 성격에 따라 `RECRUIT_NOTICE`(기본), `SCREENING`(전형), `ACC`(역검) 중 하나를 선택합니다.
3.  **제약사항:** 동일한 `filterType`은 한 번만 사용 가능합니다.

이 정리를 바탕으로 코드를 분석하거나 구현하시면 도움이 될 것입니다. 추가적인 상세 설명이 필요하면 말씀해 주세요.