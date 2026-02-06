# ResumeGridColumnType 컬럼 타입 명세서

## 개요
지원서 그리드에서 사용되는 컬럼 타입을 정의한 Enum 클래스입니다. 각 컬럼은 필드명과 설명, 데이터 타입을 포함합니다.

## 기본 정보 컬럼

### RESUME_SN
- **필드명**: `resumeSn`
- **설명**: 지원서 식별자
- **타입**: `int`

### RESUME_DISPLAY_NO
- **필드명**: `resumeDisplayNo`
- **설명**: 수험번호
- **타입**: `string`

### NAME
- **필드명**: `name`
- **설명**: 이름
- **타입**: `string`

### AGE
- **필드명**: `age`
- **설명**: 나이
- **타입**: `int`

### GENDER_FLAG
- **필드명**: `genderFlag`
- **설명**: 성별
- **타입**: `string`
- **예시**: `M`(남자), `F`(여자)

### EMAIL
- **필드명**: `email`
- **설명**: 이메일
- **타입**: `string`

### MOBILE_NO
- **필드명**: `mobileNo`
- **설명**: 휴대번호
- **타입**: `string`

### BIRTHDAY
- **필드명**: `birthday`
- **설명**: 생년월일
- **타입**: `string` (date 형식)

## 지원 정보 컬럼

### RECRUIT_NOTICE_SN
- **필드명**: `recruitNoticeSn`
- **설명**: 공고 SN
- **타입**: `int`

### RECRUIT_NOTICE_NAME
- **필드명**: `recruitNoticeName`
- **설명**: 공고명
- **타입**: `string`

### RECRUIT_CLASS_NAME
- **필드명**: `recruitClassName`
- **설명**: 채용 구분
- **타입**: `string`

### APPLY_SECTOR
- **필드명**: `applySector`
- **설명**: 채용분야(지원분야)
- **타입**: `array`
- **구조**:
  ```json
  [
    {
      "sn": "(int)채용분야 SN",
      "name": "(string)채용분야명",
      "priority": "(int)지망 (ex.1지망, 2지망, 3지망)"
    }
  ]
  ```

### CREATE_DATETIME
- **필드명**: `createDatetime`
- **설명**: 지원서 작성일자(생성일자)
- **타입**: `string` (date-time 형식)

### SUBMIT_DATETIME
- **필드명**: `submitDatetime`
- **설명**: 지원서 제출일자
- **타입**: `string` (date-time 형식)

### RESUME_SUBMIT
- **필드명**: `resumeSubmit`
- **설명**: 지원서 제출
- **타입**: `string`

### RESUME_APPLY_COUNT
- **필드명**: `resumeApplyCount`
- **설명**: 과거지원 이력
- **타입**: `string`

### READ_STATUS
- **필드명**: `readStatus`
- **설명**: 열람여부
- **타입**: `string`

### RESUME_CREATE_CODE
- **필드명**: `resumeCreateCode`
- **설명**: 지원서 생성 타입 코드
- **타입**: `string`

### MARKING_CODE
- **필드명**: `markingCode`
- **설명**: 특이 지원자
- **타입**: `array of string`

## 학력 정보 컬럼

### FINAL_ACADEMY_CODE
- **필드명**: `finalAcademyCode`
- **설명**: 최종학력 졸업 구분
- **타입**: `string`

### FINAL_ACADEMY_SCHOOL
- **필드명**: `finalAcademySchool`
- **설명**: 최종학력 학교
- **타입**: `string`

### FINAL_ACADEMY_MAJOR
- **필드명**: `finalAcademyMajor`
- **설명**: 최종학력 전공
- **타입**: `object`
- **구조**:
  ```json
  {
    "majorName": "(string)전공명",
    "basicInfo": {
      "academyName": "(string)학교명",
      "score": "(string)성적",
      "perfectScore": "(string)성적 만점 기준"
    },
    "majorInfo": [
      {
        "majorType": "(string)전공타입",
        "majorName": "(string)전공명"
      }
    ]
  }
  ```

## 경력 정보 컬럼

### TOTAL_CAREER
- **필드명**: `totalCareer`
- **설명**: 총경력
- **타입**: `string`

### CAREER_INFO
- **필드명**: `careerInfo`
- **설명**: 경력상세
- **타입**: `array`
- **구조**:
  ```json
  [
    {
      "careerType": "(string)고용형태",
      "companyName": "(string)회사명",
      "period": "(string)경력기간"
    }
  ]
  ```

## 자격 정보 컬럼

### FOREIGN_LANGUAGE_EXAM_INFO
- **필드명**: `foreignLanguageExamInfo`
- **설명**: 어학
- **타입**: `array`
- **구조**:
  ```json
  [
    {
      "foreignExamName": "(string)어학명",
      "gradeName": "(string)등급",
      "score": "(float)성적",
      "perfectScore": "(float)성적 만점 기준"
    }
  ]
  ```

### LICENSE_INFO
- **필드명**: `licenseInfo`
- **설명**: 자격증
- **타입**: `string`

## 직무 정보 컬럼

### JOB_GROUP
- **필드명**: `jobGroup`
- **설명**: 직군
- **타입**: `string`

### JOB
- **필드명**: `job`
- **설명**: 직무
- **타입**: `string`

## 전형 정보 컬럼

### SCREENING_SN
- **필드명**: `screeningSn`
- **설명**: 전형 식별자
- **타입**: `int`

### SCREENING_NAME
- **필드명**: `screeningName`
- **설명**: 전형명
- **타입**: `string`

### SCREENING_RESULT
- **필드명**: `screeningResult`
- **설명**: 전형결과
- **타입**: `string`

### SCREENING_RESUME_INFO
- **필드명**: `screeningResumeInfo`
- **설명**: 전형 지원서 정보
- **타입**: `object`
- **구조**:
  ```json
  {
    "screeningSn": "(int)전형 지원서 SN",
    "screeningResumeSn": "(int)전형 지원서 SN",
    "screeningApplySectorSn": "(int)전형 지원 분야 SN",
    "screeningResultCodeSetSn": "(int)전형 결과 코드 셋 SN"
  }
  ```

### SCREENING_GUIDANCE
- **필드명**: `screeningGuidance`
- **설명**: 전형안내
- **타입**: `int`

### INTERVIEW_ATTENDANCE
- **필드명**: `interviewAttendance`
- **설명**: 면접참석 회신
- **타입**: `boolean`

### NEXT_SCREENING_ATTENDANCE
- **필드명**: `nextScreeningAttendance`
- **설명**: 다음전형 참석
- **타입**: `boolean`

## 평가 정보 컬럼

### FINAL_EVALUATOR
- **필드명**: `finalEvaluator`
- **설명**: 최종평가자
- **타입**: `array`
- **구조**:
  ```json
  [
    {
      "valuerSn": "(int)평가자 SN",
      "name": "(string)이름",
      "isFinalValuer": "(boolean)최종평가자 여부",
      "resultCode": "(string)평가상태코드",
      "sortOrder": "(int)순서",
      "evaluated": "(boolean)평가여부",
      "overallScore": "(float)종합평가점수"
    }
  ]
  ```

### GENERAL_EVALUATOR
- **필드명**: `generalEvaluator`
- **설명**: 일반평가자
- **타입**: `array`
- **구조**:
  ```json
  [
    {
      "valuerSn": "(int)평가자 SN",
      "name": "(string)이름",
      "isFinalValuer": "(boolean)최종평가자 여부",
      "resultCode": "(string)평가상태코드",
      "sortOrder": "(int)순서",
      "evaluated": "(boolean)평가여부",
      "overallScore": "(float)종합평가점수"
    }
  ]
  ```

### OVERALL_EVALUATION_AVERAGE
- **필드명**: `overallEvaluationAverage`
- **설명**: 종합평가평균
- **타입**: `int`

## 스크리닝 결과 컬럼

### RESUME_SCREENING_FINAL_RESULT
- **필드명**: `resumeScreeningFinalResult`
- **설명**: 스크리닝 종합 결과
- **타입**: `string`

### TALENT_SCREENING_CUTLINE
- **필드명**: `talentScreeningCutline`
- **설명**: 지원서 커트라인
- **타입**: `object`
- **구조**:
  ```json
  {
    "screeningResumeSn": "(int)전형지원서 SN",
    "cutline": "(string)커트라인(최저기준)"
  }
  ```

### TALENT_SCREENING_TOTAL_SCORE
- **필드명**: `talentScreeningTotalScore`
- **설명**: 지원서 자동심사 종합점수
- **타입**: `int`

### FIT_SCREENING_CUTLINE
- **필드명**: `fitScreeningCutline`
- **설명**: 역량 커트라인
- **타입**: `object`
- **구조**:
  ```json
  {
    "screeningResumeSn": "(int)전형지원서 SN",
    "cutline": "(string)커트라인(최저기준)"
  }
  ```

### FIT_SCREENING_RANK
- **필드명**: `fitScreeningRank`
- **설명**: 역량 등급
- **타입**: `string`
- **예시**: `A`, `A_PLUS`, `A_MINUS`

### FIT_SCREENING_TOTAL_SCORE
- **필드명**: `fitScreeningTotalScore`
- **설명**: 역량 종합점수
- **타입**: `float`

## 역량검사 결과 컬럼

### RESPONSE_RELIABILITY
- **필드명**: `responseReliability`
- **설명**: 응답 신뢰성
- **타입**: `string`

### PERFORMANCE_RANK_GRADE
- **필드명**: `performanceRankGrade`
- **설명**: 성과 예측 등급
- **타입**: `string`

### RELATION_RANK_GRADE
- **필드명**: `relationRankGrade`
- **설명**: 관계 예측 등급
- **타입**: `string`

### ADAPTATION_RANK_GRADE
- **필드명**: `adaptationRankGrade`
- **설명**: 적응 예측 등급
- **타입**: `string`

### EXAM_STATUS
- **필드명**: `examStatus`
- **설명**: 응시현황
- **타입**: `string`

## 영상면접 결과 컬럼

### VIDEO_RESPONSE_RELIABILITY
- **필드명**: `videoResponseReliability`
- **설명**: 영상 이상 확인
- **타입**: `string`

### EXTERNAL_CHARACTERISTIC_GRADE
- **필드명**: `externalCharacteristicGrade`
- **설명**: 영상면접 등급
- **타입**: `string`

### EXTERNAL_CHARACTERISTIC_SCORE
- **필드명**: `externalCharacteristicScore`
- **설명**: 영상면접 점수
- **타입**: `float`

## NCS 역량검사 결과 컬럼

### NCS_TEST_RESULT_RANK_GRADE
- **필드명**: `ncsTestResultRankGrade`
- **설명**: NCS 역검 - 핵심 종합 등급
- **타입**: `string`

### NCS_TEST_RESULT_MT_SCORE
- **필드명**: `ncsTestResultMtScore`
- **설명**: NCS 역검 - 핵심 종합 점수
- **타입**: `float`

### NCS_TEST_RESULT_RANK_TOTAL
- **필드명**: `ncsTestResultRankTotal`
- **설명**: NCS 역검 - 핵심 종합 등수(전체)
- **타입**: `int`

### NCS_TEST_RESULT_RANK_GROUP
- **필드명**: `ncsTestResultRankGroup`
- **설명**: NCS 역검 - 핵심 종합 등수(분야내)
- **타입**: `int`

### NCS_RESPONSE_RELIABILITY
- **필드명**: `ncsResponseReliability`
- **설명**: NCS 역검 - 응답 신뢰성
- **타입**: `string`

## 순위 정보 컬럼

### TOTAL_RANK_OVERALL
- **필드명**: `totalRankOverall`
- **설명**: 종합등수(전체)
- **타입**: `int`

### TOTAL_RANK_BY_GROUP
- **필드명**: `totalRankByGroup`
- **설명**: 종합등수(분야내)
- **타입**: `float`

## 합격 정보 컬럼

### FINAL_PASS_STATUS
- **필드명**: `finalPassStatus`
- **설명**: 최종 합격 여부
- **타입**: `string`

### PASS_ANNOUNCEMENT
- **필드명**: `passAnnouncement`
- **설명**: 합격자 발표
- **타입**: `int`

## 메시지 발송 컬럼

### SMS_SEND_STATUS
- **필드명**: `smsSendStatus`
- **설명**: SMS 발송 시도
- **타입**: `string`

### MAIL_SEND_STATUS
- **필드명**: `mailSendStatus`
- **설명**: 메일 발송 시도
- **타입**: `string`

## 파일 관리 컬럼

### MANAGER_UPLOAD_FILE
- **필드명**: `managerUploadFile`
- **설명**: 관리자 업로드 파일
- **타입**: `boolean`
