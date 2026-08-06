# Siemens WinCC OA 코드 리뷰 자동화 솔루션 (wincc_reviewer)

[![CI Test Status](https://github.com/AI_TF/wincc_reviewer/workflows/test/badge.svg)](https://github.com/AI_TF/wincc_reviewer/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Test Suite](https://img.shields.io/badge/tests-193%20passed-brightgreen.svg)](https://github.com/AI_TF/wincc_reviewer)

본 프로젝트는 산업용 SCADA 제어 스크립트(Siemens WinCC OA CTL, PNL, XML) 환경에 특화된 정적 검사 및 AI 2차 심층 검증 복합 자동화 솔루션입니다.

---

## 주요 기능 및 특장점

* **동적 엑셀 룰 파서 (`find_header_and_columns`)**: 엑셀 양식 서식 변경 시 상단 1~30행을 동적 스캔하여 열 위치 자동 인지
* **AST 및 도메인 정적 분석 체커**: 지연 함수 누락, DB 쿼리 바인딩 미준수, DP 연산 미해제, SCADA 명령 주입 위험(`CheckScadaSecurityExec`) 정밀 적발
* **git diff 기반 변경 라인 필터링 (`GitDiffFilter`)**: PR 및 커밋 변경 영역만 선별 검사하여 검사 대상을 80% 이상 압축
* **교차 파일 중복 스크립트 분석기 (`CrossFileAnalyzer`)**: 파일 간 복사 붙여넣기된 교차 파일 중복 코드(`CROSS_FILE_DUPLICATE`) 탐지
* **보안 API 키 및 소스코드 마스킹 (`log_masker`)**: 환경변수 연동 및 로그 파일 내 소스코드 민감 정보 자동 감추기
* **1문단 종합 트리아지 요약문 생성 (`ReviewSummaryGenerator`)**: 결함 통계 및 주요 룰 ID 기반 요약문 자동 작성
* **위험 수용 감사 추적 관리 (`AcceptedRiskManager`)**: `ACCEPTED_RISK` 상태 및 승인 이력 관리
* **인라인 억제 주석 (`//nolint:RULE_ID`)**: 의도된 개발 구문에 대한 인라인 주석 필터링 지원
* **CLI CI 파이프라인 제어 (`--fail-on-severity`)**: 지정 심각도 이상 결함 감지 시 exit code 1 프로세스 실패 반환 지원
* **5대 다형성 리포트 및 visual diff 차트**: JSON, HTML, CSV, Excel, PDF 통합 생성 및 이전 Run 대비 visual diff 대시보드 시각화

---

## 지원 운영체제 및 플랫폼 제약

* **지원 OS**: Windows 10 및 Windows 11 (64비트 전용)
* **제약 사유**: Siemens WinCC OA 제어 시스템 및 WinMerge CLI, pywebview 데스크톱 GUI 환경이 Windows OS 전용에 의존하므로 Windows 환경을 기본 지원합니다.

---

## 빠른 시작 가이드 (Quick Start)

### 1. 개발 환경 셋팅
```bash
# 가상환경 생성 및 활성화
python -m venv venv
.\venv\Scripts\activate

# 패키지 의존성 설치
pip install -e ".[dev]"
```

### 2. 회귀 테스트 수트 기동 (193개 전수 검증)
```bash
pytest wincc_reviewer/tests/ -v
```

### 3. CLI 검사 기동
```bash
# 기본 단일 파일/디렉토리 검사
python -m app.main --input "wincc_reviewer/tests/fixtures/ctl/broken_dp_connect.ctl"

# CI CD 파이프라인 심각도 빌드 실패 제어 실행
python -m app.main --input "wincc_reviewer/tests/fixtures/ctl/broken_dp_connect.ctl" --fail-on-severity High
```

### 4. 데스크톱 GUI 기동
```bash
python wincc_reviewer/app/ui/app.py
```

---

## 인수인계 및 관련 상세 문서 안내

* **신규 개발자 온보딩 및 백그라운드 셋팅 가이드**: [DEVELOPMENT_ONBOARDING_GUIDE.md](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/DEVELOPMENT_ONBOARDING_GUIDE.md)
* **사용자 및 운영 매뉴얼**: [USER_MANUAL.md](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/USER_MANUAL.md)
* **기술 및 아키텍처 설계서**: [02_TRD_아키텍처설계서.md](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/02_TRD_%EC%95%84%ED%82%A4%ED%85%8D%EC%B2%98%EC%84%A4%EA%B3%84%EC%84%9C.md)
* **구현 및 검증 기준서**: [06_구현기준_추적성_검증기준.md](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/06_%EA%B5%AC%ED%98%84%EA%B8%B0%EC%A4%80_%EC%B6%94%EC%A0%81%EC%84%B1_%EA%B2%80%EC%A6%9D%EA%B8%B0%EC%A4%80.md)
* **개선가이드 로드맵 문서**: [10_개선가이드_로드맵.md](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/10_%EA%B8%B0%EB%85%A5_개선가이드_로드맵.md)

---

## 라이선스

본 프로젝트는 [MIT License](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/LICENSE) 라이선스에 따라 자유롭게 사용 및 배포가 가능합니다.
