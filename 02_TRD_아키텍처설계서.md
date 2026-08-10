# 02. WinCC OA Code Reviewer 기술 및 아키텍처 설계서 (TRD)

> 문서버전: v2.0.0  
> 작성일자: 2026년 8월 11일  
> 상태: 프로덕션 이행 완료 (Tree sitter AST 및 33개 체커 파이프라인 구축)

## 1. 시스템 컴포넌트 아키텍처

본 시스템은 크게 5개의 코어 서브시스템으로 구성되어 구동됩니다.

1. 정적 분석 및 파서 레이어
   * TreeSitterASTParser: Tree sitter C++ AST 구문 분석으로 주석 및 스코프 마스킹
   * DFAEngine: 제어 흐름 분석 기반 상태 전이 체커
   * PNLParser: Panel XML 및 텍스트 폼 UI 스크립트 파서
   * XMLParser: SCADA 설정 XML 파서
   * CheckerRegistry: 33개 내장 정적 체커 동적 레지스트리

2. 룰 카탈로그 및 사전 검증 레이어
   * ExcelSchemaLinter: settings.yaml 셀 좌표 사전 린팅 및 엑셀 헤더 유효성 검사
   * RuleEngine: 정규식, AST, 엑셀 룰 동적 파이프라인 컴파일러
   * RuleOptimizer: 오탐 이력 학습 및 approved_fp_rules.json 사전 승인 검증

3. AI 2차 리뷰 및 동시성 관리 레이어
   * LocalProvider: 로컬 LLM(Ollama, vLLM) 및 사내 API 폴백 프로바이더
   * AIQueueCacheManager: asyncio 세마포어 동시성 큐잉 및 SHA256 TTL 응답 캐시

4. 리포트 및 트렌드 DB 레이어
   * ReportBuilder: HTML, JSON, PDF, Excel 4대 포맷 생성기
   * QualityTrendDB: 누적 정적분석 지표 SQLite DB 기록

5. 실행 및 배포 자동화 레이어
   * setup.bat: 파이썬 검증, 가상환경(.venv) 생성, 의존성 설치 자동화
   * run_gui.bat: 데스크톱 화면 형태의 검사 프로그램 구동
   * run_check.bat: 폴더/파일 마우스 드래그 앤 드롭 검사 스크립트

## 2. 데이터 흐름 및 파이프라인 제어

```text
[입력 소스 코드(.ctl/.pnl/.xml)] 
   ➔ [ExcelSchemaLinter 린트 검증] 
   ➔ [TreeSitterASTParser AST 구문 파싱] 
   ➔ [CheckerRegistry 33개 정적 체커 분석] 
   ➔ [AIQueueCacheManager AI 2차 리뷰] 
   ➔ [ReportBuilder 4대 리포트 생성 및 저장]
```
