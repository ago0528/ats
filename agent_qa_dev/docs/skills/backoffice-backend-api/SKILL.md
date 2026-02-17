---
name: backoffice-backend-api
description: Use when implementing backend APIs, async jobs, and integrations for the AQB backoffice in this project.
---

# Backoffice Backend API

## Overview
이 스킬은 AQB 백오피스의 백엔드 API, 비동기 작업, ATS 및 OpenAI 연동을 구현할 때의 기준이다.

## When to Use
- CSV 업로드 기반 실행(run) 파이프라인을 만들 때
- ATS 오케스트레이터 호출을 백엔드로 옮길 때
- OpenAI 평가 및 AQB 스코어링 작업을 비동기로 수행해야 할 때

## Core Flow
- Run 생성 시 상태는 PENDING으로 시작한다.
- 작업 시작 시 RUNNING, 완료 시 DONE, 실패 시 FAILED로 변경한다.
- 긴 작업은 워커에서 수행하고 API는 상태 조회만 제공한다.

## API Responsibilities
- CSV 업로드, 검증, 파싱
- ATS 호출 실행과 결과 저장
- OpenAI 평가 실행과 파생 컬럼 생성
- AQB 스코어링 계산
- Excel 다운로드용 데이터 묶음 생성

## Integration Rules
- ATS 호출은 `aqb_agent_client.py` 로직을 기준으로 구현한다.
- 버튼 URL 파싱과 필터 추출은 기존 함수 로직을 이식한다.
- OpenAI 평가는 `aqb_openai_judge.py` 프롬프트/후처리를 참고한다.

## Data Model Hints
- Run: id, env, status, started_at, finished_at, options
- Query: id, run_id, query_text, expected_filters, meta
- Response: id, query_id, ordinal, assistant_message, data_ui, guide_list, response_time_sec, error
- JudgeResult: query_id, eval_json, derived_fields
- Score: query_id, metric_scores, weighted_total, flags

## Storage Rules
- 토큰과 키는 DB에 저장하지 않는다.
- 업로드 파일은 원본과 파생본을 분리 저장한다.
- 결과 저장은 row 단위로 증분 업데이트 가능하게 설계한다.

## Error Handling
- 외부 API 오류는 원문과 축약 메시지를 모두 기록한다.
- 재시도 정책은 ATS와 OpenAI에 분리 적용한다.
- 실패 상태에서 재실행이 가능하도록 idempotent 키를 둔다.
