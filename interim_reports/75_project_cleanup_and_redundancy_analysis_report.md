# 프로젝트 폴더 불필요 파일 점검 및 구조 분석 보고서

작성일자: 2026년 8월 8일  
작성목적: 프로젝트 루트 및 서브 디렉토리 전수 스캔을 통한 불필요 파일, 캐시, 빈 디렉토리 식별 및 정리 방안 수립

## 1. 개요

프로젝트 저장소 전체 디렉토리를 객관적이고 과학적인 기준에 따라 스캔하였습니다.
핵심 코어 소스코드(wincc_reviewer/app), 테스트 수트(wincc_reviewer/tests), 룰 카탈로그(config) 및 프로젝트 규칙 필수 폴더(primary_data, secondary_data, intermediate_results, interim_reports, scripts)의 건전성을 확인하였으며, 정리 권장 대상을 분류하였습니다.

## 2. 점검 및 분류 결과

* 1분류: 임시 캐시 및 바이트코드 (삭제 또는 ignore 권장)
  * .pytest_cache 및 wincc_reviewer/.pytest_cache: pytest 실행 시 자동 생성되는 임시 캐시 디렉토리
  * __pycache__ 디렉토리들: 파이썬 모듈 컴파일 바이트코드
  * output/ 내 232개 임시 리포트 파일: 과거 테스트 구동 시 생성된 run timestamp 기반 중복 리포트 산출물
* 2분류: 빈 디렉토리 (Empty Directory)
  * wincc_reviewer/config: 비어있는 폴더 (실제 룰 카탈로그 및 settings.yaml은 루트의 config/ 디렉토리에 존재함)
* 3분류: 중복 위치 및 미사용 잔재 파일
  * wincc_reviewer/intermediate_results/quality_trend_db.json: 루트 intermediate_results/quality_trend_db.json과 위치 중복
* 4분류: 정당한 필수 보존 디렉토리 (프로젝트 규칙 준수)
  * primary_data: 원본 WinCC OA 샘플 8종 (원시 데이터)
  * secondary_data: 파생 데이터 및 verified_metrics (인간 검증 지표)
  * intermediate_results: 골든셋 지표 및 18종 체커 분석 데이터
  * interim_reports: 단계별 개발 메모리 보고서 (74건)
  * scripts: 분석 파이프라인 스크립트 (20개, 두 자리 숫자 규격 준수)

## 3. 조치 권고안

1. wincc_reviewer/config 빈 디렉토리 및 중복 quality_trend_db.json 정리
2. .gitignore 파일에 output/ 내 임시 run 리포트 파일 및 캐시 디렉토리 등록
3. pytest 캐시 및 파이썬 바이트코드 자동 cleanup 명령 제공

본 분석을 통해 핵심 소스코드와 보존 데이터의 안전성을 확보하면서 프로젝트 구성을 깔끔하게 유지할 수 있습니다.
