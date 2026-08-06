# 🛡️ Siemens WinCC OA Code Reviewer

p[![CI Test Status](https://github.com/ldg1036/AI_TF_CODEREVIEW/workflows/test/badge.svg)](https://github.com/ldg1036/AI_TF_CODEREVIEW/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Test Suite](https://img.shields.io/badge/tests-193%20passed-brightgreen.svg)](https://github.com/ldg1036/AI_TF_CODEREVIEW)

> **Siemens WinCC OA 정적 검사 엔진 및 AI 심층 검증 통합 데스크톱 코드리뷰 솔루션**

---

## 📌 Overview

**WinCC OA Code Reviewer**는 산업용 SCADA 제어 시스템 스크립트(Siemens WinCC OA CTL, PNL, XML)에 특화된 자동화 코드 리뷰 시스템입니다. 엑셀 룰 카탈로그와 정적 AST 파서, AI 심층 검증을 결합하여 스크립트 결함과 보안 위험을 1초 만에 적발합니다.

---

## ✨ Key Features

* **⚡ 동적 엑셀 헤더 탐지 파서 (`find_header_and_columns`)**: 서식이 변경되어도 상단 1~30행을 동적 스캔하여 열 위치 자동 탐지
* **🛡️ SCADA 전용 보안 체커 (`CheckScadaSecurityExec`)**: `system()`, `popen()`, `exec()` 등 외부 프로세스 명령 주입 결함 `CRITICAL` 적발
* **🎯 git diff 기반 변경 라인 검사 (`GitDiffFilter`)**: 커밋 변경 라인만 선별 검사하여 리뷰 대상 80% 이상 압축
* **🧩 교차 파일 중복 분석기 (`CrossFileAnalyzer`)**: 여러 패널 스크립트 간 복사 붙여넣기된 교차 파일 중복 코드(`CROSS_FILE_DUPLICATE`) 탐지
* **🔒 API 키 및 소스코드 마스킹 (`log_masker`)**: 환경변수 연동 및 소스코드 스니펫 무단 노출 방지 마스킹
* **📝 1문단 종합 결함 요약 (`ReviewSummaryGenerator`)**: 결함 통계 기반 핵심 리스크 및 가이드 1문단 자동 요약
* **🏷️ 위반 억제 주석 (`//nolint:RULE_ID`)**: 소스코드 인라인 주석을 통한 명시적 예외 처리 지원
* **📈 릴리스 품질 트렌드 및 visual diff 차트**: 이전 Run 대비 결함 변화율(New, Fixed, Persistent) 프로그레스 바 대시보드 시각화

---

## 🏗️ System Architecture

```
┌───────────────────────────────────────────────────────────┐
│                    GUI / CLI Interface                    │
└─────────────────────────────┬─────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────┐
│                 Pipeline Orchestrator                     │
└─────┬───────────────┬───────────────┬───────────────┬─────┘
      │               │               │               │
┌─────▼─────┐   ┌─────▼─────┐   ┌─────▼─────┐   ┌─────▼─────┐
│ CTL/PNL/  │   │  Excel    │   │ AI Provider│   │   Report  │
│ XML Parser│   │ RuleEngine│   │ (Gemini/  │   │  Builder  │
│(Confidence│   │(//nolint) │   │ Local AI) │   │(HTML/Excel│
│ Warning)  │   │           │   │           │   │ /PDF/CSV) │
└───────────┘   └───────────┘   └───────────┘   └───────────┘
```

---

## 🚀 Quick Start

### Prerequisites
* **Operating System**: Windows 10 또는 Windows 11 (64bit 전용)
* **Python Runtime**: Python 3.12 이상

### Installation

```bash
git clone https://github.com/ldg1036/AI_TF_CODEREVIEW.git
cd AI_TF_CODEREVIEW

python -m venv venv
.\venv\Scripts\activate

pip install -e ".[dev]"
```

### Usage

#### 💻 Graphical Interface (GUI) 기동
```bash
python wincc_reviewer/app/ui/app.py
```

#### ⚡ Command Line Interface (CLI) 기동
```bash
# 기본 분석 기동
python -m app.main --input "wincc_reviewer/tests/fixtures/ctl/broken_dp_connect.ctl"

# CI CD 파이프라인 심각도 빌드 실패 처리 기동
python -m app.main --input "wincc_reviewer/tests/fixtures/ctl/broken_dp_connect.ctl" --fail-on-severity High
```

---

## 📊 Verification & Test Metrics

| 검증 항목 | 검증 결과 지표 | 비고 |
|---|---|---|
| 전체 유닛 테스트 수트 | **193 passed (100%)** | `pytest wincc_reviewer/tests/ -v` |
| 정적 검사 Precision 지표 | **100.0%** | `scripts/03_precision_recall_evaluator.py` |
| 정적 검사 Recall 지표 | **100.0%** | `intermediate_results/precision_recall_metrics.csv` |
| F1 Score 실측 지표 | **100.0%** | 픽스처 데이터 수트 실측 |

---

## ⚙️ Environment Variables

| 환경변수명 | 필수 여부 | 설명 |
|---|---|---|
| `WINCC_AI_API_KEY` | 선택 | 사내 Gemini AI 프로바이더 접근 토큰 |
| `LOCAL_AI_API_KEY` | 선택 | 사내 로컬 LLM 서버 인증 키 |

---

## 📚 Documentation Links

* 📘 **신규 개발자 온보딩 가이드**: [DEVELOPMENT_ONBOARDING_GUIDE.md](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/DEVELOPMENT_ONBOARDING_GUIDE.md)
* 📕 **사용자 및 운영 매뉴얼**: [USER_MANUAL.md](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/USER_MANUAL.md)
* 📗 **기술 및 아키텍처 설계서**: [02_TRD_아키텍처설계서.md](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/02_TRD_%EC%95%84%ED%82%A4%ED%85%8D%EC%B2%98%EC%84%A4%EA%B3%84%EC%84%9C.md)
* 📙 **구현 및 검증 기준서**: [06_구현기준_추적성_검증기준.md](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/06_%EA%B5%AC%ED%98%84%EA%B8%B0%EC%A4%80_%EC%B6%94%EC%A0%81%EC%84%B1_%EA%B2%80%EC%A6%9D%EA%B8%B0%EC%A4%80.md)

---

## 📄 License

This project is licensed under the [MIT License](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/LICENSE).
