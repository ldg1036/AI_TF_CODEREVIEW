# AI 프로바이더 13개 이슈 수용 및 아키텍처 개편 계획 보고서

작성일자: 2026년 8월 8일  
작성목적: 2026년 8월 7일자 AI 프로바이더 개선 계획(문서 10번)의 13개 이슈 수용 및 세부 실행 방안 정리

## 1. 개요

로컬 AI(OpenWebUI/Gemma/Qwen) 연동 및 2차 심층 AI 리뷰 점검 과정에서 발견된 13개 이슈를 계층별로 분류하고, 프롬프트 통제, 가짜 fallback 제거, 중복 AI 호출 방지, 뱃지 모순 해소, 스니펫 컨텍스트 확장을 포함하는 종합 실행 계획을 작성하였습니다.

## 2. 주요 개선 과제 및 실행 계획

* 1단계: 프롬프트 제어 및 생성 파라미터 표준화
  * local_provider.py: 도메인 우선순위, 8가지 규칙 및 판정(위반/문제없음) 형식 적용, max_tokens 500 및 temperature 전달
  * gemini_provider.py: generationConfig(temperature 0.2, maxOutputTokens 500) 추가 및 모델명 정합화
* 2단계: 가짜 fallback 제거 및 실효성 확보
  * gemini_provider.py: API 키 미설정 또는 호출 실패 시 하드코딩 템플릿 반환 제거 및 is_success=False 정정
* 3단계: AI 중복 호출 및 뱃지 모순 아키텍처 개편
  * pipeline.py: 위반 1건당 2회 AI 호출 낭비 제거 (1차 RAG 보강 호출로 단일화)
  * false_positive_filter.py: 2차 중복 호출 코드 제거, 1차 AI 판정 결과와 정규식 분석 결과를 통합하여 confidence_score 계산
  * html_report_builder.py: AI 판정 내용과 뱃지 표기 문구 간의 모순 해소
* 4단계: 스니펫 컨텍스트 확장 및 문서 정합성 확보
  * rule_engine.py: 단일 라인 스니펫 대신 위반 라인 기준 앞뒤 10줄 윈도우 슬라이싱 캡처 구현 (할루시네이션 방지)
  * 01_PRD.md: DEC 01 항목 지원 WinCC OA 버전 3.17부터 3.20까지 확정 반영

## 3. 향후 추진 일정

수립된 구현 계획서(implementation_plan.md)에 따라 단계별로 리팩터링 및 단위 테스트(pytest 193건 + 신규 테스트)를 이행하여 신뢰도와 속도를 동시에 달성할 예정입니다.
