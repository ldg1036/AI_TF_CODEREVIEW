# WinCC OA 코드 리뷰 자동화 도구 (AI TF CODEREVIEW)

[![CI Test Status](https://github.com/AI_TF/wincc_reviewer/workflows/test/badge.svg)](https://github.com/AI_TF/wincc_reviewer/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)

본 프로젝트는 산업용 SCADA 제어 스크립트(Siemens WinCC OA CTL, PNL, XML) 환경에 특화된 정적 검사 및 AI 2차 심층 검증 복합 자동화 솔루션입니다.

## 주요 특징

* **동적 엑셀 헤더 탐지 파서**: 엑셀 양식 변경 시 1~30행을 동적 스캔하여 열 위치를 자동 탐지
* **AST 및 도메인 정적 분석 체커 6종**: 지연 함수 누락, DB 쿼리 바인딩 위반, DP 연산 쌍 미준수, SCADA 명령 주입 위험 정밀 검출
* **git diff 변경 라인 스캔 모듈**: PR 및 커밋 변경 영역 라인만 선별 검사 기능 지원
* **교차 파일 분석기**: 파일 간 복사 붙여넣기 중복 코드 블록 탐지
* **보안 API 키 및 로그 마스킹**: 환경변수 연동 및 소스코드 민감 정보 자동 마스킹
* **1문단 종합 가이드 요약문 자동 생성**: 검출된 결함의 1문단 요약문 작성
* **오탐 수용 및 감사 추적 이력 관리**: ACCEPTED_RISK 상태 및 승인 이력 관리
* **5대 다형성 리포트 출력**: JSON, HTML, CSV, Excel, PDF 종합 결과 내보내기 지원

## 플랫폼 지원 및 제약 사항

* **지원 운영체제**: Windows 10 및 Windows 11 (64비트 전용)
* **제약 사유**: Siemens WinCC OA 시스템 및 WinMerge, pywebview 데스크톱 환경이 Windows OS에 의존적이므로 Windows 환경을 기본 지원합니다.

## 빠른 시작 가이드

### 1) 의존성 설치
```bash
pip install -e ".[dev]"
```

### 2) 회귀 테스트 수트 실행
```bash
pytest wincc_reviewer/tests/ -v
```

### 3) CLI 분석 기동
```bash
python -m app.main --input-path "c:/path/to/script.ctl"
```

### 4) 데스크톱 GUI 실행
```bash
python wincc_reviewer/app/ui/app.py
```

## 상세 설정 및 개발 가이드
상세 세부 설정 및 파이프라인 아키텍처는 [USER_MANUAL.md](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/USER_MANUAL.md) 및 [02_TRD_아키텍처설계서.md](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/02_TRD_%EC%95%84%ED%82%A4%ED%85%8D%EC%B2%98%EC%84%A4%EA%B3%84%EC%84%9C.md) 문서를 참고하십시오.
