# 02. WinCC OA Code Reviewer 기술 및 아키텍처 설계서 (TRD)

> 문서버전: v1.0.0  
> 작성일자: 2026년 8월 9일  
> 상태: 이행 완료

## 1. 시스템 컴포넌트 아키텍처

본 시스템은 크게 5개의 코어 서브시스템으로 구성되어 구동됩니다.

1. 정적 분석 및 파서 레이어
   * CtrlASTParser: Control 스크립트 구문 트리 토큰 윈도우 문맥 파서
   * PNLParser: Panel XML 및 텍스트 폼 UI 스크립트 파서
   * XMLParser: SCADA 설정 XML 파서
   * CheckerRegistry: 21개 내장 정적 체커 동적 레지스트리

2. 룰 카탈로그 및 사전 검증 레이어
   * ExcelSchemaLinter: settings.yaml 셀 좌표 사전 린팅 및 엑셀 헤더 유효성 검사
   * RuleEngine: 정규식, AST, 엑셀 룰 동적 파이프라인 컴파일러
   * RuleOptimizer: 오탐 이력 학습 및 approved_fp_rules.json 사전 승인 검증

3. AI 2차 리뷰 및 동시성 관리 레이어
   * LocalProvider: 로컬 LLM(Ollama, vLLM) 및 외부 AI 폴백 프로바이더
   * AIQueueCacheManager: asyncio.Semaphore(5) 동시성 큐잉 및 SHA256 TTL 응답 캐시

4. 리포트 및 트렌드 DB 레이어
   * ReportBuilder: HTML, JSON, PDF, Excel 4대 포맷 생성기
   * QualityTrendDB: 누적 정적분석 지표 SQLite DB 기록

5. 테스트 및 바이브코딩 프로토콜 레이어
   * 16_verify_agent_protocol.py: R1 Diff 및 R2 131개 함수 호출부 검증
   * 23_inspect_code_variables_and_functions.py: 89개 파이썬 파일 AST 무결성 검수
   * test_suite: 218개 유닛 테스트 100% PASSED 통과

## 2. 데이터 흐름 및 파이프라인 제어

```text
[입력 코드(.ctl/.pnl/.xml)] 
   ➔ [ExcelSchemaLinter 린트] ➔ [CtrlASTParser 파싱] 
   ➔ [CheckerRegistry 정적 분석] ➔ [AIQueueCacheManager AI 리뷰] 
   ➔ [ReportBuilder 출력]
```
