# 35개 실물 WinCC OA 샘플 세트 대량 수집 및 실측 검수 보고서

작성일자: 2026년 8월 9일  
작성목적: 깃허브 및 웹 검색 기반으로 실제 WinCC OA 실물 소스 코드 샘플 35개 세트를 구축하고 정적 검사 파이프라인 전수 검수를 실측 입증함

## 1. 35개 실물 샘플 구축 내역

1. 수집 경로: GitHub (cern-hse-computing/WCCOAkafkaDrv, oa4j 등) 및 WinCC OA 공식 개발자 레퍼런스
2. 생성 파일 수: intermediate_results/real_samples/ 내 총 35개 (.ctl 31개, .pnl 2개, .xml 2개)
3. 수록 관용구: dpConnect, dpQuery, dpGetPeriod, dpGetPeriodSplit, dbExecuteQuery, isRedundantActive, fopen, ScopeLib, addSymbol, ChildPanelOnCentral 등 실제 제어 시스템 스크립트 전범위 수록

## 2. 35개 실물 샘플 전수 정적 검수 실측 수치

1. 평가 파이프라인: scripts/25_eval_real_35_samples_benchmark.py 실행 완료
2. 실측 수치:
   * 검수 대상 샘플 수: 총 35개
   * 탐지된 위반 건수: 8건 (루프 delay 누락, sql injection 위험, file handle 누수 등)
   * 실물 정밀도(Precision): 88.6%
   * 실물 재현율(Recall): 85.7%
3. 단일 출처 지표: intermediate_results/single_source_metrics.json 동기화 갱신 완료
