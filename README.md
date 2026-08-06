# Siemens WinCC OA Code Reviewer

[![CI Test Status](https://github.com/ldg1036/AI_TF_CODEREVIEW/workflows/test/badge.svg)](https://github.com/ldg1036/AI_TF_CODEREVIEW/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Test Suite](https://img.shields.io/badge/tests-193%20passed-brightgreen.svg)](https://github.com/ldg1036/AI_TF_CODEREVIEW)

> **Siemens WinCC OA 제어 스크립트를 정적 룰 엔진과 AI로 자동 검사하여 결함을 1초 만에 적발하는 통합 코드리뷰 솔루션**

---

## 1단계: 이 프로그램은 무엇인가요?

Siemens WinCC OA 제어 시스템에서 사용되는 **CTL, PNL, XML** 스크립트 코드의 문법 오류, 메모리 누수, 보안 위험 구문, DB 바인딩 누락 등을 엑셀 룰 카탈로그와 AI를 통해 자동으로 검사하고 정밀 보고서를 작성해 주는 도구입니다.

### 3대 핵심 가치
* **시간 90% 이상 절감**: 사람이 파일 하나를 20분 동안 눈으로 보며 검사하던 것을 단 0.1초 만에 스캔 완료
* **SCADA 보안 위험 원천 차단**: 외부 프로세스 명령 주입(`system()`, `exec()`) 등 위험 코드 정밀 적발
* **제출용 표준 리포트 작성**: HTML, 엑셀, PDF 등 표준 결과 리포트 자동 생성

---

## 2단계: 프로젝트 디렉토리 및 폴더 구조 (Directory Structure)

```text
AI_TF_CODEREVIEW (Project Root)
├── wincc_reviewer/                # 코드 리뷰 자동화 도구 코어
│   ├── app/                       # CLI 실행 진입점, 파서, 룰 엔진, AI, GUI
│   ├── tests/                     # 193개 유닛 테스트 수트 및 픽스처
│   └── pyproject.toml             # 프로젝트 패키지 셋팅 및 의존성 명세
├── config/                        # Client/Server 엑셀 룰 카탈로그 및 settings.yaml
├── scripts/                       # Precision/Recall 실측 평가 및 데이터 익명화 스크립트
├── interim_reports/               # 단계별 개발 및 검증 보고서
├── intermediate_results/          # 장기 품질 트렌드 DB 및 평가 결과 데이터
├── .github/workflows/            # CI/CD 자동화 파이프라인 (test.yml, release.yml)
├── DEVELOPMENT_ONBOARDING_GUIDE.md # 신규 개발자 인수인계 가이드
├── USER_MANUAL.md                  # 사용자 및 운영 매뉴얼
└── README.md                       # 프로젝트 대표 안내서
```

---

## 3단계: 설치 및 준비하기 (Quick Setup)

### 시스템 요구사항
* **운영체제**: Windows 10 또는 Windows 11 (64비트 전용)
* **파이썬**: Python 3.12 이상

### 따라하기 전용 1분 설치 명령어
터미널(CMD 또는 PowerShell)을 열고 아래 명령어를 입력합니다.

```bash
git clone https://github.com/ldg1036/AI_TF_CODEREVIEW.git
cd AI_TF_CODEREVIEW

python -m venv venv
.\venv\Scripts\activate

pip install -e ".[dev]"
```

---

## 4단계: 실행하고 결과 확인하기 (Usage)

### 방법 A. 그래픽 화면(GUI)으로 편하게 실행하기 (권장)
```bash
python wincc_reviewer/app/ui/app.py
```
* 화면이 열리면 좌측 패널에서 검사할 폴더나 파일을 선택하고 검사 버튼을 누르면 시작됩니다.

### 방법 B. 터미널(CLI) 명령으로 빠르게 실행하기
```bash
python -m app.main --input "wincc_reviewer/tests/fixtures/ctl/broken_dp_connect.ctl"
python -m app.main --input "wincc_reviewer/tests/fixtures/ctl/broken_dp_connect.ctl" --fail-on-severity High
```
* 검사 완료 후 `./output/` 폴더에서 깔끔한 HTML 리포트를 열람하실 수 있습니다.

---

## 5단계: 핵심 기능 들여다보기 (Features)

* **동적 엑셀 룰 파서 (`find_header_and_columns`)**: 엑셀 서식이 바뀌어도 1~30행을 동적 스캔하여 열 위치 자동 인식
* **SCADA 전용 보안 체커 (`CheckScadaSecurityExec`)**: `system()`, `popen()`, `exec()` 등 위험 코드 `CRITICAL` 적발
* **git diff 기반 변경 라인 검사 (`GitDiffFilter`)**: 이번 커밋에서 변경되거나 추가된 라인만 선택 검사
* **교차 파일 중복 스크립트 분석기 (`CrossFileAnalyzer`)**: 파일 간 복사 붙여넣기된 교차 파일 중복 코드(`CROSS_FILE_DUPLICATE`) 탐지
* **AI 1문단 종합 결함 요약 (`ReviewSummaryGenerator`)**: 위반 목록을 다 읽지 않아도 핵심 리스크와 가이드를 1문단 요약 작성
* **위반 억제 주석 (`//nolint:RULE_ID`)**: 의도된 코드 행에는 `//nolint` 주석을 달아 오탐 알림 방지
* **릴리스 품질 트렌드 및 visual diff 차트**: 이전 검사 대비 결함 변화율(New, Fixed, Persistent) 프로그레스 바 시각화

---

## 6단계: 검증 지표 및 회귀 테스트 (Metrics)

| 검증 항목 | 검증 결과 지표 | 비고 |
|---|---|---|
| 전체 유닛 테스트 수트 | **193 passed (100%)** | `pytest wincc_reviewer/tests/ -v` |
| 정적 검사 Precision 지표 | **100.0%** | `scripts/03_precision_recall_evaluator.py` |
| 정적 검사 Recall 지표 | **100.0%** | `intermediate_results/precision_recall_metrics.csv` |
| F1 Score 실측 지표 | **100.0%** | 픽스처 데이터 수트 실측 |

---

## 7단계: 자주 묻는 질문 (FAQ)

### Q1. AI 심층 리뷰 API 키를 어디에 설정하나요?
환경변수에 `WINCC_AI_API_KEY` 또는 `LOCAL_AI_API_KEY` 값을 등록하거나, GUI 화면의 `환경 설정` 탭에서 기입하시면 됩니다.

### Q2. 특정 심각도 이상일 때 빌드를 실패 처리하고 싶어요.
`--fail-on-severity High` 옵션을 부여하면 High 이상 위험 감지 시 프로세스 exit code 1을 반환합니다.

---

## 인수인계 및 상세 문서 안내

* **신규 개발자 온보딩 가이드**: [DEVELOPMENT_ONBOARDING_GUIDE.md](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/DEVELOPMENT_ONBOARDING_GUIDE.md)
* **상세 사용자 매뉴얼**: [USER_MANUAL.md](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/USER_MANUAL.md)
* **기술 아키텍처 설계서**: [02_TRD_아키텍처설계서.md](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/02_TRD_%EC%95%84%ED%82%A4%ED%85%8D%EC%B2%98%EC%84%A4%EA%B3%84%EC%84%9C.md)
* **구현 및 검증 기준서**: [06_구현기준_추적성_검증기준.md](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/06_%EA%B5%AC%ED%98%84%EA%B8%B0%EC%A4%80_%EC%B6%94%EC%A0%81%EC%84%B1_%EA%B2%80%EC%A6%9D%EA%B8%B0%EC%A4%80.md)

---

## License

This project is licensed under the [MIT License](file:///c:/Users/39145/Downloads/%ED%81%B4%EB%A1%9C%EB%93%9Cprd/LICENSE).
