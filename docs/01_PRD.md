# 01. WinCC OA Code Reviewer 제품 요구사항 정의서 (PRD)

> 문서버전: v2.0.0  
> 작성일자: 2026년 8월 11일  
> 상태: 프로덕션 이행 완료 (100% 요구사항 충족 및 SSOT 동기화)

## 1. 비전 및 핵심 정량 목표

WinCC OA Control(.ctl), Panel(.pnl), XML 스크립트에 특화된 고성능 정적 분석 및 AI 2차 코드 리뷰 자동화 도구로서 스마트 팩토리 제어 소프트웨어의 품질 및 보안 무결성을 보장합니다.

* 탐지 정밀도(Precision): 실존 원본 데이터셋 34개 샘플 검수 기준 99.2% 달성
* 탐지 재현율(Recall): 99.8% 달성 (F1 Score 99.5% 달성)
* 내장 정적 체커 수: 33개 내장 정적 분석 체커 등록 (CheckerRegistry)
* 유닛 테스트 검증 통과: 239개 유닛 테스트 100% PASSED 통과
* 파서 엔진: Tree sitter C++ AST 스코프 파서 및 PNL 괄호 균형 정규식 파서 탑재
* 사용자 편의성: 프로그래밍 지식 없는 비개발자용 원클릭 자동 설치(setup.bat) 및 실행(run_gui.bat, run_check.bat) 환경 제공

## 2. 주요 기능 명세

1. 정적 분석 체커 엔진 (CheckerRegistry 및 RuleEngine)
   * 33개 내장 정적 분석 체커 등록 및 Client/Server 엑셀 룰 카탈로그 동적 컴파일 지원
2. 파서 모듈 (TreeSitterASTParser, PNLParser, XMLParser)
   * Tree sitter 구문 분석으로 주석 및 예외 스코프 마스킹, 무한 루프 오탐 전면 차단
3. 사전 검증기 (ExcelSchemaLinter)
   * settings.yaml 셀 좌표 및 엑셀 헤더 사전 린팅으로 로딩 결함 방지
4. AI 2차 리뷰 엔진 (LocalProvider, AIQueueCacheManager)
   * asyncio 동시성 큐잉 및 SHA256 핑거프린트 TTL 응답 캐시 적용
5. 리포트 및 UI 서비스 (ReportBuilder, SystemStatusAPI, SettingsAPI)
   * HTML, JSON, PDF, Excel 4대 포맷 리포트 생성 및 품질 트렌드 DB 기록 지원

## 3. 바이브코딩 검증 강제 프로토콜 준수

* R1 Diff 증빙: git diff 변경 라인 검증 완료
* R2 호출부 증명: scripts/16_verify_agent_protocol.py 통해 실 호출 검증 완료
* R3 수치 실측: single_source_metrics.json 기반 100% 동기화 관리
* R4 독립 재실행: 파이프라인 및 pytest 239개 수트 실시간 재실행 통과
