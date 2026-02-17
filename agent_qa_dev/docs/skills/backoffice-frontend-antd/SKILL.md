---
name: backoffice-frontend-antd
description: Use when implementing the backoffice frontend in this project with Ant Design, especially tables/forms/wizards and the purple theme.
---

# Backoffice Frontend (Ant Design)

## Overview
이 스킬은 채용 에이전트 검증 백오피스의 프론트엔드를 Ant Design으로 구현할 때 사용하는 기준이다.

## When to Use
- 백오피스 UI를 신규로 구성하거나 주요 화면을 추가해야 할 때
- CSV 업로드, 실행 현황, 결과 테이블, 스코어링 요약을 화면으로 만들 때
- Ant Design 테마를 보라색 계열로 고정해야 할 때

## Theme Rules
- Primary 컬러는 보라색 계열을 사용한다.
- 기본 토큰 값 예시: primary #7B5CF2, info #8A7CFF, success #52C41A, warning #FAAD14, error #FF4D4F
- ConfigProvider로 전역 테마를 적용한다.

## Page Structure
- Runs 목록: 실행 상태 중심의 리스트와 필터
- Run 상세: 좌측 요약, 우측 결과 테이블
- 평가 탭: OpenAI 평가 결과와 파생 컬럼 표시
- 스코어 탭: AQB 점수, 플래그, 요약 리포트
- URL 테스트 탭: URL Agent 결과와 실패 사유

## Component Checklist
- CSV 업로드 컴포넌트는 업로드 즉시 스키마 검증 결과를 표시한다.
- 결과 테이블은 큰 데이터 대비 페이지네이션 또는 가상 스크롤을 지원한다.
- 실행 상태는 태그와 타임라인으로 시각화한다.
- 에러 메시지는 원인과 재시도 버튼을 함께 노출한다.

## Data Display Rules
- 응답 시간은 초 단위로 표기하고 소수 2자리까지 표시한다.
- 응답 상태는 PASS, FAIL, ERROR로 통일한다.
- 결과 테이블에는 최소 컬럼으로 run_id, query_id, query_text, 응답 요약, 점수를 포함한다.

## UX Guardrails
- 토큰/키 입력 필드는 마스킹하고 저장하지 않는다.
- 장시간 작업은 진행률 표시와 중단 버튼을 제공한다.
- 다운로드 버튼은 항상 최종 결과 시트로 내보내도록 한다.
