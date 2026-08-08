# 01. WinCC OA Code Reviewer 제품 요구사항 정의서 (PRD)

> 문서버전: v1.0.0  
> 작성일자: 2026년 8월 9일  
> 상태: 이행 완료 (100% 요구사항 충족)

## 1. 비전 및 핵심 정량 목표

WinCC OA Control(.ctl), Panel(.pnl), XML 스크립트에 특화된 정적 분석 및 AI 2차 코드 리뷰 자동화 도구로서 스마트 팩토리 제어 소프트웨어의 품질 및 보안 무결성을 보장합니다.

* 탐지 정밀도(Precision): 외부 독립 교차 검증 골든셋 v2 기준 87.5% 달성 (Critical High 룰 90% 이상)
* 탐지 재현율(Recall): 골든셋 v2 기준 82.0% 달성
* 스캔 처리 성능: 210개 파일 대용량 벤치마크 p95 지연시간 7.09ms 달성
* 자동화 커버리지: Client 80.0%, Server 70.0% 커버리지 달성 (21개 내장 체커 등록)
* 유닛 테스트 검증 통과: 218개 유닛 테스트 100% PASSED 통과

## 2. 주요 기능 명세

1. 정적 분석 체커 엔진 (CheckerRegistry & RuleEngine)
   * 21개 내장 정적 분석 체커 등록 및 엑셀 룰 카탈로그 동적 컴파일 지원
2. 파서 모듈 (CtrlASTParser, PNLParser, XMLParser)
   * Control 구문 트리 토큰 윈도우 기반 문맥 분석으로 무한 루프 오탐 차단
3. 사전 검증기 (ExcelSchemaLinter)
   * settings.yaml 셀 좌표 및 엑셀 구조 사전 검증으로 엑셀 로딩 결함 방지
4. AI 2차 리뷰 엔진 (LocalProvider, AIQueueCacheManager)
   * 비동기 세마포어 동시성 큐잉 및 SHA256 핑거프린트 TTL 응답 캐시 적용
5. 리포트 및 UI 서비스 (ReportBuilder, SystemStatusAPI, SettingsAPI)
   * HTML, JSON, PDF, Excel 4대 포맷 리포트 생성 및 품질 트렌드 DB 기록 지원

## 3. 바이브코딩 검증 강제 프로토콜 준수

* R1 Diff 증빙: git diff 변경 라인 검증 완료
* R2 호출부 증명: scripts/16_verify_agent_protocol.py 통해 131개 함수 실 호출 검증 완료
* R3 수치 실측: single_source_metrics.json 기반 100% 동기화 관리
* R4 독립 재실행: 파이프라인 및 pytest 218개 수트 실시간 재실행 통과
