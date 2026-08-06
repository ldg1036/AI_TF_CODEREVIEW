# Siemens WinCC OA 코드 리뷰 자동화 도구 (wincc_reviewer)

[![CI Test Status](https://github.com/ldg1036/AI_TF_CODEREVIEW/workflows/test/badge.svg)](https://github.com/ldg1036/AI_TF_CODEREVIEW/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Test Suite](https://img.shields.io/badge/tests-193%20passed-brightgreen.svg)](https://github.com/ldg1036/AI_TF_CODEREVIEW)

> **"Siemens WinCC OA 제어 스크립트를 정적 룰 엔진과 AI로 자동 검사하여 결함을 1초 만에 찾아내는 데스크톱 자동화 솔루션"**

---

## 💡 이 프로그램은 무엇인가요?

Siemens WinCC OA 제어 시스템에서 사용되는 **CTL, PNL, XML** 스크립트 코드의 문법 오류, 메모리 미해제, 보안 위험 구문, DB 바인딩 누락 등을 엑셀 룰 카탈로그와 AI를 통해 자동으로 검사하고 정밀 보고서를 작성해 주는 도구입니다.

### 🌟 3대 핵심 가치
* **소요 시간 90% 이상 절감**: 파일 하나를 사람이 눈으로 20분 동안 보며 검사하던 것을 단 0.1초 만에 스캔 완료
* **SCADA 보안 위험 원천 차단**: 외부 프로세스 명령 주입(`system()`, `exec()`) 등 위험 코드 정밀 적발
* **쉬운 결과 리포트 작성**: HTML, 엑셀, PDF 등 제출용 표준 리포트 자동 작성

---

## 🚀 초보자를 위한 1분 빠른 시작 가이드 (Quick Start)

### 1단계: 사전 준비
본 프로그램은 **Windows 10 또는 Windows 11 (64비트)** 및 **Python 3.12 이상** 환경에서 동작합니다.

### 2단계: 설치하기
터미널(CMD 또는 PowerShell)을 열고 아래 명령어를 순서대로 입력합니다.

```bash
# 1. 가상환경 생성 및 활성화
python -m venv venv
.\venv\Scripts\activate

# 2. 필요한 패키지 자동 설치
pip install -e ".[dev]"
```

### 3단계: 실행하기

#### 💻 그래픽 화면(GUI)으로 편하게 실행하고 싶을 때:
```bash
python wincc_reviewer/app/ui/app.py
```
* 화면이 열리면 좌측에서 검사할 폴더나 파일을 선택하고 버튼을 누르면 검사가 시작됩니다.

#### ⚡ 터미널(CLI) 명령으로 빠르게 검사하고 싶을 때:
```bash
python -m app.main --input "wincc_reviewer/tests/fixtures/ctl/broken_dp_connect.ctl"
```
* 검사가 끝나면 `./output/` 폴더에 깔끔한 HTML 리포트와 JSON 리포트가 생성됩니다.

---

## 🛠️ 어떤 핵심 기능들이 제공되나요?

* **화면으로 편하게 보는 HTML 대시보드**: 위반 심각도별 필터링, 소스코드 위치 하이라이팅, 이전 검사 대비 결함 변화 차트 제공
* **엑셀 양식 자동 인지**: 엑셀 룰 카탈로그 서식이 조금 바뀌어도 1~30행을 자동으로 스캔하여 열 위치를 스마트하게 찾음
* **변경된 코드만 검사 (`git diff` 지원)**: 전체를 다 보지 않고 이번 커밋에서 변경되거나 추가된 라인만 선택 검사
* **AI 1문단 종합 결함 요약**: 위반 목록을 다 읽지 않아도 AI가 핵심 리스크와 수정 가이드를 1문단으로 요약 작성
* **인라인 검사 예외 지원 (`//nolint`)**: 의도적으로 작성된 안전한 코드 행에는 `//nolint:RULE_ID` 주석을 달아 무분별한 오탐 알림 방지

---

## ❓ 자주 묻는 질문 (FAQ) 및 예외 조치

### Q1. AI 심층 리뷰 기능을 사용하려면 API 키를 어디에 설정하나요?
시스템 환경변수에 `WINCC_AI_API_KEY` 또는 `LOCAL_AI_API_KEY` 값을 등록하거나, GUI 화면의 `⚙️ 환경 설정` 탭에서 직접 입력하실 수 있습니다. (API 키는 로그에 자동으로 마스킹 보호됩니다)

### Q2. 검사 실행 시 특정 심각도 이상일 때 빌드를 실패 처리하고 싶어요.
`--fail-on-severity High` 옵션을 붙여 실행하면 Critical 또는 High 위험 감지 시 프로세스 exit code 1을 반환하여 CI/CD 파이프라인 품질 게이트로 활용하실 수 있습니다.

---

## 📚 추가 상세 안내 문서 링크

* **신규 개발자 온보딩 및 백그라운드 가이드**: [DEVELOPMENT_ONBOARDING_GUIDE.md](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/DEVELOPMENT_ONBOARDING_GUIDE.md)
* **상세 사용자 매뉴얼**: [USER_MANUAL.md](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/USER_MANUAL.md)
* **기술 아키텍처 설계서**: [02_TRD_아키텍처설계서.md](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/02_TRD_%EC%95%84%ED%82%A4%ED%85%8D%EC%B2%98%EC%84%A4%EA%B3%84%EC%84%9C.md)
