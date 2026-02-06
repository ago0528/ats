# ToolResumeFinder 필터 가이드

## 1. ResumePeriodCondition (날짜/기간)
**역할**: 지원일 또는 제출일 기간으로 필터링  
**파라미터**:
- `periodPresetType`: ResumePeriodPresetType
  - `TODAY` (당일)
  - `ONE_WEEK` (1주일)
  - `ONE_MONTH` (1개월)
  - `THREE_MONTH` (3개월)
  - `SIX_MONTH` (6개월)
  - `ONE_YEAR` (1년)
  - `MANUAL` (직접입력, 기본값)
- `periodTypeList`: List<ResumePeriodType> - `CREATE_DATETIME`(작성일), `RESUME_SUBMIT`(제출일)
- `begin`: LocalDateTime
- `end`: LocalDateTime

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"RESUME_PERIOD","periodPresetType":"MANUAL","periodType":["RESUME_SUBMIT"],"begin":"2024-01-01T00:00:00","end":"2024-12-31T23:59:59"}]

```
**요청**: "2024년 1월부터 12월까지 지원한 지원자"

---

## 2. ResumeSubmitCondition (제출 상태)
**역할**: 지원서 제출 상태로 필터링  
**파라미터**:
- `submitType`: ResumeSubmitType - `SUBMITTED`(제출완료), `NOT_SUBMITTED`(미제출), `TEMPORARY`(임시저장)

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"RESUME_SUBMIT","submitTypes":["SUBMITTED"]}]
```
**요청**: "지원서를 제출한 지원자"

---

## 3. RecruitNoticeCondition (공고)
**역할**: 특정 공고의 지원자 필터링  
**파라미터**:
- `recruitNoticeSnList`: List<Integer>
- `recruitSectorSnList`: List<Integer> (선택)

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"RECRUIT_NOTICE","recruitNoticeSnList":[12345],"recruitSectorSnList":[100,101]}]&selectedRecruitNotices=[12345]
```
**요청**: "2024년 상반기 신입 공채 지원자"

---

## 4. ApplyChannelCondition (지원 경로)
**역할**: 지원 경로로 필터링  
**파라미터**:
- `applyChannelCodeList`: List<Integer>

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"APPLY_CHANNEL","applyChannelCodeList":[1,2,3]}]
```
**요청**: "홈페이지를 통해 지원한 지원자"

---

## 5. ResumeCreateCodeCondition (작성 방식)
**역할**: 지원서 작성 방식으로 필터링  
**파라미터**:
- `resumeCreateCodes`: List<ResumeCreateCode> - `DIRECT`(직접작성), `IMPORT`(불러오기)

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"RESUME_CREATE_CODE","resumeCreateCodes":["DIRECT"]}]
```
**요청**: "직접 작성한 지원서"

---

## 6. ResumeApplyCountCondition (과거 지원 이력)
**역할**: 과거 지원 횟수로 필터링  
**파라미터**:
- `inputValue`: Long

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"RESUME_APPLY_COUNT","inputValue":2}]
```
**요청**: "과거 2회 이상 지원한 지원자"

---

## 7. MarkingApplicantCondition (특이지원자)
**역할**: 특이지원자 표시로 필터링  
**파라미터**:
- `remarkableApplicantCodeList`: Set<ApplicantMarkingType> - `MARKED`(표시됨), `NOT_MARKED`(미표시)

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"MARKING_APPLICANT","remarkableApplicantCodeList":["MARKED"]}]
```
**요청**: "관심 지원자로 표시된 사람"

---

## 8. ReadStatusCondition (열람 상태)
**역할**: 지원서 열람 여부로 필터링  
**파라미터**:
- `viewType`: IntegrationGridViewMode
- `readStatus`: ReadStatus - `READ`(열람), `UNREAD`(미열람)

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"READ_STATUS","viewType":"RECRUIT_NOTICE","readStatus":"UNREAD"}]
```
**요청**: "아직 열람하지 않은 지원서"

---

## 9. ManagerUploadFileCondition (관리자 업로드 파일)
**역할**: 관리자 업로드 파일 유무로 필터링  
**파라미터**:
- `uploadFileTypes`: Set<ManagerUploadFileType> - `UPLOADED`(업로드됨), `NOT_UPLOADED`(미업로드)

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"MANAGER_UPLOAD_FILE","uploadFileTypes":["UPLOADED"]}]
```
**요청**: "관리자가 파일을 업로드한 지원자"

---

## 10. NationalityCondition (국적)
**역할**: 국적으로 필터링  
**파라미터**:
- `nationalityCodeList`: List<String>

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"NATIONALITY","nationalityCodes":["KR","US"]}]
```
**요청**: "한국 국적 지원자"

---

## 11. MilitaryCondition (병역)
**역할**: 병역 상태로 필터링  
**파라미터**:
- `inputValue`: Set<MilitaryStatus> - `COMPLETED`(군필), `EXEMPTED`(면제), `NOT_APPLICABLE`(해당없음)

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"MILITARY","inputValue":["COMPLETED"]}]
```
**요청**: "군필자"

---

## 12. HandicapCondition (장애 여부)
**역할**: 장애 여부로 필터링  
**파라미터**:
- `inputValue`: Boolean

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"HANDICAP","inputValue":false}]
```
**요청**: "비장애인"

---

## 13. PatriotCondition (보훈 대상)
**역할**: 보훈 대상 여부로 필터링  
**파라미터**:
- `inputValue`: Boolean

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"PATRIOT","inputValue":true}]
```
**요청**: "보훈 대상자"

---

## 14. FinalAcademyCodeCondition (최종 학력)
**역할**: 최종 학력으로 필터링  
**파라미터**:
- `finalAcademicCodeGroups`: List<FinalAcademicCodeGroup> - `MIDDLE_SCHOOL`, `HIGH_SCHOOL`, `ASSOCIATE`, `BACHELOR`, `MASTER`, `DOCTOR`, `NONE`

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"FINAL_ACADEMY_CODE","finalAcademyCodeList":["BACHELOR","MASTER"]}]
```
**요청**: "대졸 이상 학력"

---

## 15. GraduationTypeCondition (졸업 구분)
**역할**: 졸업 상태로 필터링  
**파라미터**:
- `graduationTypes`: List<GraduationType> - `GRADUATE`, `TO_GRADUATE`, `COMPLETION`, `DROP_OUT`, `LEAVE_OF_ABSENCE`, `ATTENDING`, `EQUIVALENT_EXAM`

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"GRADUATION_TYPE","graduationTypes":["GRADUATE","TO_GRADUATE"]}]
```
**요청**: "졸업 또는 졸업예정자"

---

## 16. MajorScoreCondition (학점)
**역할**: 학점으로 필터링  
**파라미터**:
- `score`: BigDecimal
- `perfectScore`: BigDecimal

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"MAJOR_SCORE","score":3.5,"perfectScore":4.5}]
```
**요청**: "학점 3.5 이상 (4.5 만점)"

---

## 17. CareerCriteriaCondition (경력 기준)
**역할**: 경력 기준으로 필터링  
**파라미터**:
- `companyRecruitCodeSnList`: List<Integer>

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"CAREER_CRITERIA","companyRecruitCodeSnList":[1,2]}]
```
**요청**: "신입 또는 경력"

---

## 18. CareerPeriodCondition (경력 기간)
**역할**: 경력 기간으로 필터링  
**파라미터**:
- `beginPeriod`: {year, month}
- `endPeriod`: {year, month}

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"CAREER_PERIOD","beginPeriod":{"year":3,"month":0},"endPeriod":{"year":5,"month":0}}]
```
**요청**: "3년 이상 5년 이하 경력자"

---

## 19. ProjectCondition (프로젝트 경험)
**역할**: 프로젝트 경험 여부로 필터링  
**파라미터**:
- `inputValue`: Boolean

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"PROJECT","inputValue":true}]
```
**요청**: "프로젝트 경험이 있는 지원자"

---

## 20. ForeignLanguageSkillCondition (외국어 능력)
**역할**: 외국어 능력으로 필터링  
**파라미터**:
- `languageCodeList`: List<String>

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"FOREIGN_LANGUAGE_SKILL","languageCodeList":["EN","JP"]}]
```
**요청**: "영어 또는 일본어 능력 보유자"

---

## 21. OverseasExperienceCondition (해외 경험)
**역할**: 해외 경험으로 필터링  
**파라미터**:
- `purposeSnList`: Set<Integer>

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"OVERSEAS_EXPERIENCE","overseasExperiencePurposeSnList":[1,2]}]
```
**요청**: "해외 경험이 있는 지원자"

---

## 22. EducationCondition (교육 이수)
**역할**: 교육 이수 여부로 필터링  
**파라미터**:
- `inputValue`: Boolean

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"EDUCATION","inputValue":true}]
```
**요청**: "교육을 이수한 지원자"

---

## 23. ActivityCondition (학내외 활동)
**역할**: 학내외 활동으로 필터링  
**파라미터**:
- `activityCategoryCodeList`: Set<Integer>

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"ACTIVITY","activityCategoryCodeList":[1,2]}]
```
**요청**: "학내외 활동 경험이 있는 지원자"

---

## 24. VolunteerCondition (봉사활동)
**역할**: 봉사활동으로 필터링  
**파라미터**:
- `codeList`: Set<Integer>

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"VOLUNTEER","volunteerActivityCodeList":[1,2]}]
```
**요청**: "봉사활동 경험이 있는 지원자"

---

## 25. ResumeScreeningFinalResultCondition (스크리닝 종합 결과)
**역할**: 스크리닝 종합 결과로 필터링  
**파라미터**:
- `inputValues`: Set<Suitability> - `SUITABLE`, `UNSUITABLE`, `NONE`

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"RESUME_SCREENING_FINAL_RESULT","suitabilities":["SUITABLE"]}]
```
**요청**: "스크리닝 적합 판정 지원자"

---

## 26. ScreeningTypeCondition (전형 유형)
**역할**: 전형 유형으로 필터링  
**파라미터**:
- `screeningType`: ScreeningTypeCode - `DOCUMENT`, `EXAM`, `INTERVIEW`, `ACC` 등

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=SCREENING&condition=[{"filterType":"SCREENING_TYPE","screeningTypes":["DOCUMENT"]}]
```
**요청**: "서류전형 지원자"

---

## 27. TalentScreeningCutlineCondition (지원서 커트라인)
**역할**: 지원서 커트라인으로 필터링  
**파라미터**:
- `cutlineList`: Set<TalentScreeningCutline> - `SUITABLE`, `UNSUITABLE`, `ANALYZING`, `FAIL`

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"TALENT_SCREENING_CUTLINE","cutlineList":["SUITABLE"]}]
```
**요청**: "지원서 커트라인 적합 지원자"

---

## 28. FitScreeningCutlineCondition (역량검사 커트라인)
**역할**: 역량검사 커트라인으로 필터링  
**파라미터**:
- `cutlineList`: Set<FitScreeningCutline> - `PASS`, `FAIL`, `EXCLUDE`, `WA`, `DO`, `ER`

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"FIT_SCREENING_CUTLINE","cutlineList":["PASS"]}]
```
**요청**: "역량검사 커트라인 통과 지원자"

---

## 29. FinalValuerCondition (최종 평가자)
**역할**: 최종 평가자로 필터링  
**파라미터**:
- `memberSnList`: List<Integer>

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=SCREENING&condition=[{"filterType":"FINAL_VALUER","memberSnList":[100,101]}]
```
**요청**: "김철수 평가자가 최종 평가한 지원자"

---

## 30. OverAllAverageScoreCondition (종합평가 평균)
**역할**: 종합평가 평균 점수로 필터링  
**파라미터**:
- `conditionType`: ConditionRangeType - `SCORE`, `PERCENTAGE`
- `begin`: Double
- `end`: Double

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=SCREENING&condition=[{"filterType":"OVER_ALL_AVERAGE_SCORE","rangeType":"SCORE","begin":80.0,"end":100.0}]
```
**요청**: "종합평가 80점 이상"

---

## 31. FinalPassApplySectorCondition (최종 합격)
**역할**: 최종 합격 여부로 필터링  
**파라미터**:
- `passTypes`: Set<PassStatus> - `FINAL_PASS`, `DECISION_PENDING`, `NOT_EVALUATED_OR_FAIL`

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=SCREENING&condition=[{"filterType":"FINAL_PASS_APPLY_SECTOR","passTypes":["FINAL_PASS"]}]
```
**요청**: "최종 합격자"

---

## 32. ScreeningResultCondition (전형 결과)
**역할**: 전형 결과로 필터링  
**파라미터**:
- `resultTypes`: List<ScreeningResultCode> - `PASS`, `SPARE_PASS`, `NOT_PASS`, `NOT_EVALUATE`

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=SCREENING&condition=[{"filterType":"SCREENING_RESULT","screeningResultCodes":["PASS"]}]
```
**요청**: "서류전형 합격자"

---

## 33. GeneralValuerCondition (일반 평가자)
**역할**: 일반 평가자로 필터링  
**파라미터**:
- `memberSnList`: Set<Integer>

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=SCREENING&condition=[{"filterType":"GENERAL_VALUER","memberSnList":[100,101]}]
```
**요청**: "김철수 평가자가 평가한 지원자"

---

## 34. NextScreeningAttendanceCondition (다음 전형 참석)
**역할**: 다음 전형 참석 여부로 필터링  
**파라미터**:
- `attendanceTypeList`: Set<AttendanceType> - `ATTENDANCE`, `ABSENCE`, `LATE`

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=SCREENING&condition=[{"filterType":"NEXT_SCREENING_ATTENDANCE","attendanceTypeList":["ATTENDANCE"]}]
```
**요청**: "다음 전형 참석 확정 지원자"

---

## 35. InterviewAttendanceCondition (면접 참석)
**역할**: 면접 참석 회신 여부로 필터링  
**파라미터**:
- `attendanceTypeList`: Set<AttendanceType>

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=SCREENING&condition=[{"filterType":"INTERVIEW_ATTENDANCE","attendanceTypeList":["ATTENDANCE"]}]
```
**요청**: "면접 참석 확정한 지원자"

---

## 36. ScreeningGuidanceCondition (전형 안내)
**역할**: 전형 안내 여부로 필터링  
**파라미터**:
- `isGuidance`: Boolean

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=SCREENING&condition=[{"filterType":"SCREENING_GUIDANCE","isGuidance":true}]
```
**요청**: "전형 안내를 받은 지원자"

---

## 37. PassAnnouncementCondition (합격 발표)
**역할**: 합격 발표 여부로 필터링  
**파라미터**:
- `isAnnounced`: Boolean

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=SCREENING&condition=[{"filterType":"PASS_ANNOUNCEMENT","isAnnounced":true}]
```
**요청**: "합격 발표된 지원자"

---

## 38. SmsSendStatusCondition (SMS 발송)
**역할**: SMS 발송 시도 여부로 필터링  
**파라미터**:
- `tried`: Boolean

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=SCREENING&condition=[{"filterType":"SMS_SEND_STATUS","tried":true}]
```
**요청**: "SMS를 발송한 지원자"

---

## 39. MailSendStatusCondition (이메일 발송)
**역할**: 이메일 발송 시도 여부로 필터링  
**파라미터**:
- `tried`: Boolean

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=SCREENING&condition=[{"filterType":"MAIL_SEND_STATUS","tried":false}]
```
**요청**: "이메일을 받지 못한 지원자"

---

## 40. ExamStatusCondition (응시 현황)
**역할**: 시험 응시 현황으로 필터링  
**파라미터**:
- `examStatusList`: Set<ExamineeStatusType> - `COMPLETED`, `NOT_STARTED`, `IN_PROGRESS`, `CONNECT_OVER` 등

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=SCREENING&condition=[{"filterType":"EXAM_STATUS","examStatusList":["COMPLETED"]}]
```
**요청**: "시험을 완료한 지원자"

---

## 41. AccTestResultRankGradeCondition (ACC 종합등급)
**역할**: ACC 역량검사 등급으로 필터링  
**파라미터**:
- `gradeList`: Set<AccRankGrade>

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=ACC&condition=[{"filterType":"ACC_TEST_RESULT_RANK_GRADE","gradeList":["A_PLUS","A"]}]
```
**요청**: "ACC 역량검사 A등급 이상"

---

## 42. AccTestResultMtScoreCondition (ACC 종합점수)
**역할**: ACC 종합점수로 필터링  
**파라미터**:
- `conditionType`: ConditionRangeType
- `begin`: Double
- `end`: Double

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=ACC&condition=[{"filterType":"ACC_TEST_RESULT_MT_SCORE","rangeType":"SCORE","begin":80.0,"end":100.0}]
```
**요청**: "ACC 점수 80점 이상"

---

## 43. AccTestResultRankTotalCondition (ACC 종합등수)
**역할**: ACC 종합등수로 필터링  
**파라미터**:
- `minRank`: Integer
- `maxRank`: Integer

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=ACC&condition=[{"filterType":"ACC_TEST_RESULT_RANK_TOTAL","minRank":1,"maxRank":10}]
```
**요청**: "ACC 종합등수 10등 이내"

---

## 44. AccTestResultRankGroupCondition (ACC 그룹 순위)
**역할**: ACC 그룹 내 순위로 필터링  
**파라미터**:
- `minRank`: Integer
- `maxRank`: Integer

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=ACC&condition=[{"filterType":"ACC_TEST_RESULT_RANK_GROUP","minRank":1,"maxRank":5}]
```
**요청**: "ACC 그룹 내 5등 이내"

---

## 45. AccTestResponseReliabilityCondition (ACC 응답 신뢰도)
**역할**: ACC 응답 신뢰도로 필터링  
**파라미터**:
- `inputValue`: ResponseReliabilityType - `TRUST`, `NON_TRUST`, `NOT_TAKEN`

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=ACC&condition=[{"filterType":"ACC_TEST_RESPONSE_RELIABILITY","inputValue":"TRUST"}]
```
**요청**: "ACC 응답 신뢰도가 높은 지원자"

---

## 46. NcsTestResultRankGradeCondition (NCS 종합등급)
**역할**: NCS 검사 등급으로 필터링  
**파라미터**:
- `gradeList`: Set<AccGradeCode>

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"NCS_TEST_RESULT_RANK_GRADE","gradeList":["S","A_PLUS"]}]
```
**요청**: "NCS S등급 또는 A+ 등급"

---

## 47. NcsTestResultMtScoreCondition (NCS 종합점수)
**역할**: NCS 종합점수로 필터링  
**파라미터**:
- `minScore`: Integer
- `maxScore`: Integer

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"NCS_TEST_RESULT_MT_SCORE","minScore":80,"maxScore":100}]
```
**요청**: "NCS 점수 80점 이상"

---

## 48. NcsTestResultRankTotalCondition (NCS 종합등수)
**역할**: NCS 종합등수로 필터링  
**파라미터**:
- `minScore`: Integer
- `maxScore`: Integer

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"NCS_TEST_RESULT_RANK_TOTAL","minScore":1,"maxScore":10}]
```
**요청**: "NCS 종합등수 10등 이내"

---

## 49. NcsTestResultRankGroupCondition (NCS 그룹 순위)
**역할**: NCS 그룹 내 순위로 필터링  
**파라미터**:
- `minScore`: Integer
- `maxScore`: Integer

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"NCS_TEST_RESULT_RANK_GROUP","minScore":1,"maxScore":5}]
```
**요청**: "NCS 그룹 내 5등 이내"

---

## 50. NcsResponseReliabilityCondition (NCS 응답 신뢰도)
**역할**: NCS 응답 신뢰도로 필터링  
**파라미터**:
- `inputValue`: ResponseReliabilityType

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=RECRUIT_NOTICE&condition=[{"filterType":"NCS_RESPONSE_RELIABILITY","inputValue":"TRUST"}]
```
**요청**: "NCS 응답 신뢰도가 높은 지원자"

---

## 51. ResumeScreeningCondition (전형 검색)
**역할**: 특정 전형의 지원자 필터링  
**파라미터**:
- `screeningSnList`: List<Integer>

**URL 예시**:
```
/agent/integrated-grid/applicant?viewMode=SCREENING&condition=[{"filterType":"SCREENING","screeningSnList":[1001]}]
```
**요청**: "1차 면접 전형 지원자"  
**제약**: RecruitPlanCondition + ScreeningTypeCondition 필요

---

## ViewMode 자동 결정 규칙
1. `SCREENING_ONLY` 카테고리 → `viewMode=SCREENING`
2. `ACC_ONLY` 카테고리 → `viewMode=ACC`
3. `SCREENING_COMMON` 카테고리 → `viewMode=SCREENING`
4. 기본값 → `viewMode=RECRUIT_NOTICE`

## 제약사항
1. **로그인 필수**: MRS CMS Access Token 필요
2. **필터 중복 금지**: 동일한 filterType은 한 번만 사용 가능
3. **의존성**: 일부 필터는 다른 필터와 함께 사용 필요
