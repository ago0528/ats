### 채용 관리

- [기존 채용 불러오기](/agent/flow/create?copy={planId}): 이전 채용을 복제하여 새로 시작. "채용 복사", "기존 거 가져오기", "이전 채용 복제"
- [설정중 채용 수정](/agent/flow/process/{planId}): 작성 중이던 채용 이어서 편집. "임시저장 채용", "이어서 수정", "작성 중인 채용"
- [공채 채용 생성](/agent/flow/create?template=DEFAULT_TEMPLATE): 신규 공개채용 시작. "공채 만들기", "새 채용 생성", "공개 채용 시작"
- [수시/상시 채용 생성](/agent/flow/create?operationType=CONDITION_BASED&template=DEFAULT_TEMPLATE): 수시 또는 상시 채용 시작. "수시채용 만들기", "상시채용 생성", "경력직 채용"
- [맞춤 인재 채용 설계](/agent/plan/gate): 인재상 정의부터 시작하는 채용 계획 수립. "우리 회사에 맞는 인재", "채용 전략 설계", "처음부터 채용 기획", "인재상 기반 채용"
- [채용 현황 확인](/agent/flow/process/{planId}/dashboard): 지원 현황, 전형별 인원, 통계 확인. "대시보드", "채용 진행상황", "현황 보기"

### 메시지 관리

- [메시지 현황](/agent/mrs/communication/message): 발송된 문자/이메일 이력 확인. "보낸 메시지", "발송 내역", "메시지 히스토리"
- [메시지 템플릿](/agent/mrs/communication/message-template): 채용 안내 메시지 양식 관리. "메시지 양식", "템플릿 만들기", "문자 템플릿", "이메일 템플릿"

### 채용 설정

- [채용 코드](/agent/mrs/setting/recruit-code): 지원서 선택항목 코드값 관리. "코드 설정", "선택값 관리", "드롭다운 항목"
- [동의서](/agent/mrs/setting/agreement): 채용을 위한 각종 동의서 관리. "개인정보 동의", "정보수집 동의서", "동의서 등록"
- [지원서 템플릿](/agent/mrs/setting/resume-template): 지원서 양식 등록 및 관리. "지원서 양식", "이력서 폼", "지원서 폼 만들기"
- [스크리닝](/agent/mrs/setting/resume-screening): 지원서 자동 필터링 조건 설정. "자동 스크리닝", "필터 기준", "자격요건 자동 체크", "서류 자동 분류"
- [평가 척도](/agent/mrs/setting/scale): 면접 등 평가에 사용할 척도 관리. "평가 기준", "점수 척도", "등급 설정"

### 플로우 포커스 - 기본 정보

- [공고명](/agent/flow/process/{planId}?dataKey=RECRUIT_NOTICE_NAME): 채용공고 제목 수정. "공고 제목", "채용 타이틀", "공고명 변경"
- [채용 형태](/agent/flow/process/{planId}?dataKey=RECRUIT_TYPE): 일반/상시/추천/비공개 등 형태 설정. "채용 타입", "공개 여부", "비공개 채용"
- [채용 구분](/agent/flow/process/{planId}?dataKey=RECRUIT_CLASS): 공채/수시/상시 구분 설정. "채용 분류", "공채 수시 구분"
- [접수 기간](/agent/flow/process/{planId}?dataKey=RECEIVE_PERIOD): 지원 접수 시작일~종료일 설정. "지원 기간", "접수 일정", "모집 기간"
- [제출 마감](/agent/flow/process/{planId}?dataKey=SUBMISSION_CLOSING_DATETIME): 지원서 제출 마감일시 설정. "마감일", "마감 시간", "데드라인"
- [지원서 설정](/agent/flow/process/{planId}?dataKey=APPLICATION_SETTING): 공고에 사용할 지원서 템플릿 선택. "지원서 양식 선택", "어떤 지원서 쓸지"
- [지원자 동의서](/agent/flow/process/{planId}?dataKey=PERSONAL_INFORMATION_COLLECTION): 지원 시 개인정보 동의서 설정. "개인정보 수집", "동의서 연결"
- [지원자 서약서](/agent/flow/process/{planId}?dataKey=RESUME_SUBMIT_OATH): 지원서 제출 시 서약서 설정. "서약서", "제출 서약"
- [본인 인증](/agent/flow/process/{planId}?dataKey=RECRUIT_REAL_NAME_CHECK): 지원 시 본인인증 필수 여부. "실명 인증", "본인확인", "인증 필수"

### 플로우 포커스 - 채용 분야

- [복수 지원 설정](/agent/flow/process/{planId}?dataKey=MULTIPLE_APPLY_SETTING): 여러 직무 동시 지원 허용 설정. "복수 지원", "다중 지원", "여러 분야 지원"
- [중복 지원 차단](/agent/flow/process/{planId}?dataKey=RECRUIT_DUPLICATE_APPLY_CRITERIA): 동일인 중복 지원 차단 설정. "중복 방지", "재지원 차단", "동일인 체크"
- [채용 분야 설정](/agent/flow/process/{planId}?dataKey=RECRUIT_SECTOR_LIST): 모집 직무/분야 등록 관리. "직무 추가", "모집 분야", "채용 직군"

### 플로우 포커스 - 공고 정보

- [게시 설정](/agent/flow/process/{planId}?dataKey=RECRUIT_NOTICE_POST_SETTING): 공고 게시/비게시 설정. "공고 올리기", "게시 여부", "공고 노출"
- [지원서 작성 버튼 제공](/agent/flow/process/{planId}?dataKey=RECRUIT_NOTICE_WRITE_BUTTON_STATE): '지원서 작성' 버튼 표시 설정. "지원 버튼", "작성 버튼 숨기기"
- [지원서 접수현황 알림](/agent/flow/process/{planId}?dataKey=RESUME_CONFIRM_NOTIFY_METHOD): 지원서 접수 시 관리자/지원자 알림 설정. "접수 알림", "지원 알림", "노티 설정"
- [채용사이트 공고 설정](/agent/flow/process/{planId}?dataKey=RECRUIT_NOTICE_CONTENTS): 채용사이트 공고 내용 편집. "공고 내용", "공고문 수정", "채용 상세"
- [오픈그래프](/agent/flow/process/{planId}?dataKey=RECRUIT_OPEN_GRAPH): 공고 페이지 썸네일/제목 설정. "공유 미리보기", "SNS 썸네일", "링크 미리보기"

### 플로우 포커스 - 전형 공통

- [전형명](/agent/flow/process/{planId}?dataKey=SCREENING_NAME): 전형 이름 수정. "전형 이름", "단계명 변경"
- [온라인 평가기간](/agent/flow/process/{planId}?dataKey=SCREENING_EVALUATION_PERIOD): 평가 진행 기간 설정. "평가 기간", "평가 일정"
- [평가점수 입력 방식](/agent/flow/process/{planId}?dataKey=EVALUATION_SCORE_INPUT_METHOD): 점수 입력 방식 설정. "점수 입력", "평가 방식"
- [평가자 세부 설정](/agent/flow/process/{planId}?dataKey=SCREENING_VALUER_SETTING): 평가자 배정 방식, 결과 공개 설정. "평가자 설정", "평가자 권한"
- [전형대상 및 평가자 배정](/agent/flow/process/{planId}?dataKey=SCREENING_VALUER_ASSIGNMENT): 전형 대상자(지원자)와 평가자 배정. "평가자 배정", "누가 평가할지"
- [합격자 결정 기준](/agent/flow/process/{planId}?dataKey=PASS_DECISION_CRITERIA_SETTING): 합격 기준 설정. "합격 기준", "커트라인", "통과 조건"
- [최종 평가척도](/agent/flow/process/{planId}?dataKey=SCREENING_RESULT_CODE_MAPPING_SETTING): 최종 평가 척도 설정. "최종 점수", "결과 척도"
- [지원서 인쇄 허용](/agent/flow/process/{planId}?dataKey=PRINT_PDF_OPEN_TYPE_SETTING): 지원서 PDF 인쇄 허용 여부. "인쇄 허용", "PDF 다운로드", "출력 설정"
- [지원서 블라인드](/agent/flow/process/{planId}?dataKey=RESUME_BLIND_SETTING): 블라인드 채용용 개인정보 가리기. "블라인드 채용", "블라인드 설정", "이름 가리기", "익명 처리", "편견 없는 채용"

### 플로우 포커스 - 서류 전형

- [요약 리포트](/agent/flow/process/{planId}?dataKey=SUMMARY_REPORT_SETTING): 서류전형 요약 리포트 화면 설정. "서류 리포트", "요약 화면", "서류 결과 보기"

### 플로우 포커스 - 역량검사 전형

- [검사 설정 선택](/agent/flow/process/{planId}?dataKey=ACC_SCREENING_CMS_TEST_SETTING_SN): 역량검사 설정 확인/수정. "역검 설정", "검사 종류"
- [정보 제공 동의서](/agent/flow/process/{planId}?dataKey=ACC_SCREENING_CMS_AGREEMENT_LETTER_SN): 역량검사 동의서 설정. "역검 동의서", "검사 동의"
- [JOBDA 결과 불러오기](/agent/flow/process/{planId}?dataKey=ACC_SCREENING_RESULT_IMPORT_ALLOW): 잡다 기존 결과 불러오기 허용. "잡다 연동", "JOBDA 결과", "기존 역검 결과"
- [본인 인증(역검)](/agent/flow/process/{planId}?dataKey=ACC_SCREENING_VERIFICATION_SETTING): 역량검사 시 본인인증 여부 설정. "역검 본인인증", "검사 인증"
- [접속 허용 횟수](/agent/flow/process/{planId}?dataKey=ACC_SCREENING_CONNECT_LIMIT_SETTING): 역량검사 접속 제한 횟수 설정. "접속 제한", "재접속 횟수"
- [채용 사이트 세부 설정(역검)](/agent/flow/process/{planId}?dataKey=ACC_SCREENING_APPLICANT_SITE_SETTING): 역량검사 채용사이트 설정. "역검 사이트 설정"
- [응시자 사이트 세부 설정](/agent/flow/process/{planId}?dataKey=ACC_SCREENING_EXAMINEE_SITE_SETTING): 응시자용 사이트 설정. "응시자 화면", "수험자 사이트"
- [역량검사 타입](/agent/flow/process/{planId}?dataKey=ACC_SCREENING_COMPETENCY_ASSESSMENT_TYPE): 역량검사 종류 설정. "역검 타입", "역검 종류"
- [응시자 세부 설정](/agent/flow/process/{planId}?dataKey=ACC_SCREENING_EXAMINEE_SETTING): 응시자 관련 세부 설정. "응시자 설정", "수험자 옵션"
- [결과 가중치 종류](/agent/flow/process/{planId}?dataKey=ACC_SCREENING_RESULT_WEIGHT_TYPE): 역량검사 결과 가중치 종류 설정. "가중치 설정", "점수 반영 비율"
- [대표 구성원](/agent/flow/process/{planId}?dataKey=ACC_SCREENING_REPRESENTATIVE_MEMBER_SETTING): 직군 대표 구성원 비교 콘텐츠 설정. "대표 구성원 비교", "직군 대표"
- [유사 구성원](/agent/flow/process/{planId}?dataKey=ACC_SCREENING_SIMILAR_MEMBER_SETTING): 유사 구성원 비교 콘텐츠 설정. "유사 인재", "비슷한 구성원"
- [결과 콘텐츠](/agent/flow/process/{planId}?dataKey=ACC_SCREENING_RESULT_CONTENTS): 역량검사 결과 화면 콘텐츠 설정. "결과 화면", "역검 결과 내용"
- [관심 역량](/agent/flow/process/{planId}?dataKey=ACC_SCREENING_INTEREST_COMPETENCY_SETTING): 관심 역량 콘텐츠 설정. "관심 역량", "주요 역량"
- [AI 콘텐츠](/agent/flow/process/{planId}?dataKey=ACC_SCREENING_AI_CONTENTS_SETTING): AI 면접 가이드 등 AI 콘텐츠 설정. "AI 가이드", "AI 면접", "AI 분석"

### 플로우 포커스 - 면접 전형

- [전형유형(면접)](/agent/flow/process/{planId}?dataKey=INTERVIEW_SCREENING_TYPE): 대면/화상 등 면접 유형 설정. "면접 타입", "대면 면접", "화상 면접", "비대면"
- [전형기간(면접)](/agent/flow/process/{planId}?dataKey=INTERVIEW_SCREENING_COORDINATION_SCREENING_PERIOD): 면접 전형 기간 설정. "면접 일정", "면접 기간"
- [일정조율 바로가기](/agent/flow/process/{planId}?dataKey=INTERVIEW_SCREENING_COORDINATION_VALUER_ASSIGNMENT): 면접 일정조율 기능. "일정 조율", "면접 스케줄", "시간 조정"
- [면접비 지급여부](/agent/flow/process/{planId}?dataKey=INTERVIEW_SCREENING_INTERVIEW_PAY_SETTING): 면접비 지급 여부 설정. "면접비", "교통비 지급", "면접 수당"
- [수험표 사용여부](/agent/flow/process/{planId}?dataKey=INTERVIEW_SCREENING_IDENTIFICATION_SETTING): 수험표 발급 여부 설정. "수험표", "면접 티켓"
- [면접확인서 사용 여부](/agent/flow/process/{planId}?dataKey=INTERVIEW_SCREENING_INTERVIEW_CONFIRMATION_SETTING): 면접확인서 발급 여부 설정. "면접 확인서", "참석 확인"
- [평가자 배정(면접)](/agent/flow/process/{planId}?dataKey=INTERVIEW_SCREENING_VALUER_ASSIGNMENT): 면접관 배정. "면접관 배정", "누가 면접할지", "면접 평가자"
