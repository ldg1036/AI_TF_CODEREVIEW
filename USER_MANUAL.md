# WinCC OA Code Reviewer 사용자 매뉴얼 및 운영 가이드

> 본 매뉴얼은 WinCC OA Code Reviewer 정적 분석 및 AI 코드 리뷰 도구를 사용하는 비개발자 현업 사용자, 개발자, 시스템 관리자를 위한 종합 매뉴얼입니다.

## 1. 개요 및 핵심 기능

WinCC OA Code Reviewer는 SCADA 및 제어 시스템 스크립트(.ctl, .pnl, .xml)를 분석하여 안전성 위반, 메모리 누수, 무한 루프, 하드코딩 등의 결함을 자동으로 감지합니다.

* 정적 분석 룰 체커: 33개 내장 체커 및 동적 엑셀 룰 카탈로그 지원
* AST 문맥 분석: TreeSitterASTParser 기반 주석 및 예외처리 스코프 정밀 판별로 오탐 차단
* 엑셀 스키마 린트: ExcelSchemaLinter 통한 셀 좌표 유효성 사전 검사
* AI 2차 리뷰: 로컬 LLM 폴백, AIQueueCacheManager 동시성 큐 및 TTL 캐싱 지원
* 비개발자 원클릭 환경: setup.bat, run_gui.bat, run_check.bat 지원

## 2. 비개발자용 원클릭 실행 방법

1. setup.bat : 최초 1회 더블클릭하여 파이썬 및 가상환경(.venv), 패키지 자동 설치
2. run_gui.bat : 데스크톱 화면 형태로 프로그램을 띄워서 사용
3. run_check.bat : 검사할 폴더를 아이콘 위로 마우스 끌어다 놓기 (드래그 앤 드롭)
4. 결과 확인 : output 폴더 내 생성된 HTML 보고서 파일을 더블클릭하여 확인

## 3. 개발자용 CLI 명령어 사용법

```bash
# 기본 소스 디렉토리 검사 (HTML 및 JSON 리포트 동시 생성)
python wincc_reviewer/app/main.py --input primary_data/ --output output/

# AI 2차 리뷰 옵션 포함 구동
python wincc_reviewer/app/main.py --input primary_data/ --use-ai

# 오탐 추천 룰 카탈로그 리포트 출력
python wincc_reviewer/app/main.py --suggest-rules
```

## 4. 자주 묻는 질문 및 트러블슈팅

* python 명령어를 찾을 수 없다는 오류: Python 설치 시 Add python.exe to PATH 체크를 누르고 재설치합니다.
* 스마트스크린 경고: 추가 정보 클릭 후 실행을 누릅니다.
* 프록시 및 사내망 설치 오류: 사내 IT 담당자에게 문의하여 프록시 환경변수를 설정합니다.

## 5. 온보딩 및 검증 프로토콜

* 바이브코딩 R1 R2 프로토콜 검사: python scripts/16_verify_agent_protocol.py
* 코드베이스 AST 변수 선언 검사: python scripts/23_inspect_code_variables_and_functions.py
* 전체 239개 유닛 테스트 수트 구동: python -m pytest wincc_reviewer/tests
