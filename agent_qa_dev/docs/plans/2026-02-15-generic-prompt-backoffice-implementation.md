# Generic Bulk Test + Prompt Management Backoffice Implementation Plan

> For Claude: REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

## Goal
`aqb_v1.2.0.py`의 Generic + Prompt 기능을 API/동작 기준으로 독립 백오피스에 이관.

## Scope
- In scope: Generic run create/execute/evaluate/rows/compare/export, Prompt worker get/update/reset
- Out of scope: Applicant, URL, Quality 탭

## Environment Rules
- UI scope: `dev`, `st2`, `st`, `pr`
- ATS mapping: `dev->DV`, `st2->QA`, `st->ST`, `pr->PR`
- same-environment compare only

## Runtime Secret Rules
- bearer/cms/mrs/openaiKey는 API 요청 범위 내 메모리에서만 사용
- DB 저장 금지

## Status
- v0.1: Backoffice skeleton + core API + frontend pages implemented.
- v0.2(피드백 1135 반영): 템플릿 다운로드/단일 질의, 병렬 실행/평가 복원, 메뉴 라벨 정리, 프롬프트 모달형 관리 화면 반영.
- Blocker: 프론트 의존성(pnpm registry 접근) 네트워크 이슈로 테스트/빌드 실행 대기 중.
