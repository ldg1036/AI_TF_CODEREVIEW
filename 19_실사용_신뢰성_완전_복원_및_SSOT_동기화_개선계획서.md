# 19. 실사용 신뢰성 완전 복원 및 SSOT 동기화 근본 개선계획서

작성일자: 2026년 8월 9일  
작성목적: 하드코딩 커버리지 연산 제거, 원천 매핑 파일(client.yaml/server.yaml) 완전 동기화, SSOT 지표 불일치 완전 해소 및 실물 PyInstaller 바이너리 빌드를 달성하기 위한 과학적 근본 개선계획서

## 1. 4대 근본 결함 원인 분석 및 개선 이행 명세

1. 하드코딩 커버리지 연산 제거 및 원천 데이터 동적 계산 전환
   * config/legacy_mapping/client.yaml 및 server.yaml 파일 내 manual 지정 9개 항목을 신규 체커 ID로 매핑하고 builtin 모드로 승격
   * scripts/verify_coverage_claim.py 스크립트에서 하드코딩 수식을 제거하고 YAML 파일을 실시간 덤프 파싱하여 실제 커버리지를 동적 계산

2. SSOT (Single Source of Truth) 수치 100% 완전 동기화
   * single_source_metrics.json, interim_reports, verify_coverage_claim.py, real_samples 실물 파일 개수를 정밀 검수하여 일치화
   * large_scale_benchmark_metrics.json 파이프라인을 재실행하여 신규 체커 10종이 반영된 정밀도/재현율 실측 수치 갱신

3. dist/wincc_reviewer.exe 실물 바이너리 빌드 완수
   * scripts/21_build_windows_executable.py 실행으로 62바이트 가짜 플래스홀더를 제거하고 독립 실행 가능한 실물 exe 생성

4. 바이브코딩 프로토콜 및 수동 검토 가이드 전면 투명 공개
   * 수동 검토가 필요한 영역과 완전 자동화 체커 영역의 경계를 100% 투명하게 수록

## 2. 이행 단계 및 실측 검증 방안

* 1단계: client.yaml, server.yaml 매핑 갱신 및 PyYAML 기반 동적 덤프 연산 엔진 구현
* 2단계: PyInstaller 기반 scripts/21_build_windows_executable.py 실행으로 dist/wincc_reviewer.exe 바이너리 빌드
* 3단계: 벤치마크 및 SSOT 지표 파일 100% 일치 동기화
* 4단계: 223개 이상 전체 유닛 테스트 및 AST 결함 0건 입증
