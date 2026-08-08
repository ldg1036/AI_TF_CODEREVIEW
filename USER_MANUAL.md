# WinCC OA Code Reviewer 사용자 매뉴얼 및 운영 가이드

> 본 매뉴얼은 WinCC OA Code Reviewer 정적 분석 및 AI 2차 코드 리뷰 도구를 사용하는 개발자, 리뷰어, 시스템 관리자를 위한 사용자 운영 가이드입니다.

## 1. 개요 및 핵심 기능

WinCC OA Code Reviewer는 SCADA 및 제어 시스템 스크립트(.ctl, .pnl, .xml)를 분석하여 안전성 위반, 메모리 누수, 무한 루프, 하드코딩 등의 결함을 자동으로 감지합니다.

* 정적 분석 룰 체커: 21개 내장 체커 및 동적 엑셀 룰 카탈로그 지원
* AST 문맥 분석: CtrlASTParser 기반 주석 및 예외처리 구문 정밀 판별로 오탐 차단
* 엑셀 스키마 린트: ExcelSchemaLinter 통한 셀 좌표 유효성 사전 검사
* AI 2차 리뷰: 로컬 LLM 폴백, AIQueueCacheManager 동시성 큐 및 TTL 캐싱 지원

## 2. 프로그램 실행 가이드

### CLI 명령어 사용법

```bash
# 기본 소스 디렉토리 검사 (HTML 및 JSON 리포트 동시 생성)
python wincc_reviewer/app/main.py --input primary_data/ --output output/

# AI 2차 리뷰 옵션 포함 구동
python wincc_reviewer/app/main.py --input primary_data/ --use-ai

# 오탐 추천 룰 카탈로그 리포트 출력
python wincc_reviewer/app/main.py --suggest-rules
```

### GUI 사용자 인터페이스 사용법

1. wincc_reviewer/app/ui/api.py 기반 웹 UI 또는 데스크톱 윈도우 실행
2. 검사 대상 폴더(primary_data 또는 사용자 코드 경로) 선택 후 리뷰 시작 클릭
3. 검사 결과 요약 카드 및 파일 트리 위반 목록 확인
4. HTML 리포트 내보내기 또는 JSON 리포트 저장 클릭

## 3. 검증 및 프로토콜 검수 가이드

* 바이브코딩 R1 R2 프로토콜 검사: python scripts/16_verify_agent_protocol.py
* 코드베이스 AST 변수 선언 검사: python scripts/23_inspect_code_variables_and_functions.py
* 전체 218개 유닛 테스트 수트 구동: python -m pytest wincc_reviewer/tests
