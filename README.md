# WinCC OA Code Reviewer

> 스마트 팩토리 및 SCADA 시스템을 위한 고성능 정적 분석 및 AI 코드 리뷰 자동화 도구

[![CI Status](https://github.com/ldg1036/AI_TF_CODEREVIEW/workflows/test/badge.svg)](https://github.com/ldg1036/AI_TF_CODEREVIEW/actions)
[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://python.org)
[![Test Suite](https://img.shields.io/badge/tests-237%20passed-brightgreen.svg)](file:///c:/Users/39145/Downloads/클로드prd/intermediate_results/single_source_metrics.json)
[![Precision](https://img.shields.io/badge/precision-99.2%25-green.svg)](file:///c:/Users/39145/Downloads/클로드prd/intermediate_results/single_source_metrics.json)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](file:///c:/Users/39145/Downloads/클로드prd/LICENSE)

---

## 💡 프로젝트 소개 (What & Why)

WinCC OA Code Reviewer는 시멘스 WinCC OA(Open Architecture) 산업용 제어 시스템의 CTRL 스크립트(.ctl), 패널 UI 스크립트(.pnl), XML 설정 파일에서 발생할 수 있는 결함을 자동으로 정적 검사하고 Tree sitter AST 스코프 파싱 및 AI 리뷰를 수행하는 도구입니다.

### 이 도구가 해결하는 문제
* 제어 시스템 다운 원인 차단: 무한 루프, delay 미비, 메모리 누수 사전 감지
* 데이터베이스 및 SCADA 안전성 확보: 동적 SQL 결합, dpConnect 미해제 경고
* 정밀 정적 분석 및 오탐 최소화: TreeSitterASTParser 도입으로 99.2% 실측 정밀도 확보
* 코드 리뷰 자동화: 33개 내장 룰 체커와 엑셀 룰 카탈로그를 기반으로 리포트 자동 생성

---

## 💻 실행 필수 요구사항 (System Prerequisites)

프로그램을 정상 구동하고 빌드하기 위한 필수 환경 조건입니다.

1. 권장 운영체제: Windows 10 또는 Windows 11 (WinCC OA 개발 및 실행 환경)
2. 필수 파이썬 버전: Python 3.10 이상 3.12 이하 (Python 3.12.x 권장)
3. 핵심 의존성 라이브러리: PyYAML, openpyxl, pytest, pytest cov, ruff, mypy, tree sitter
4. 선택 필수사항 (AI 2차 리뷰 구동 시):
   * 로컬 LLM 서버 (Ollama 또는 vLLM, Qwen2.5 Coder 권장) VRAM 8GB 이상
   * 또는 사내 Gemini API 키 설정 (`settings.yaml` 파일 연동)

---

## 📂 프로젝트 폴더 및 소스 구조 (Project Structure)

```text
c:\Users\39145\Downloads\클로드prd
├── wincc_reviewer/                  # 핵심 애플리케이션 패키지
│   ├── app/                         # 코어 소스 코드
│   │   ├── core/                    # 파서(TreeSitterASTParser 포함), 정적 체커, AI, 리포트, 파이프라인 모듈
│   │   ├── ui/                      # GUI 및 REST/JS API 서비스 모듈
│   │   └── main.py                  # CLI 메인 엔트리포인트 실행 파일
│   ├── schemas/                     # 리포트 및 설정 JSON 스키마
│   └── tests/                       # 237개 유닛 테스트 수트 및 테스트 픽스처
├── config/                          # 엑셀 룰 카탈로그 및 환경 설정 파일
│   ├── settings.yaml                # 시스템 전역 설정
│   ├── rules_catalog.xlsx           # 동적 룰 정의 엑셀 파일
│   └── approved_fp_rules.json       # 사전 승인 오탐 룰 파일
├── primary_data/                    # 원본 검사 소스 데이터 폴더
├── intermediate_results/            # 벤치마크 및 단일 출처 지표 수록 폴더 (SSOT)
├── interim_reports/                 # 개발 및 검증 중간 보고서 문서 세트
├── scripts/                         # 프로토콜 검증, 벤치마크, 바이너리 빌드 스크립트
├── output/                          # 생성된 HTML JSON 리포트 저장 폴더
└── dist/                            # PyInstaller 빌드 결과물 저장 폴더
```

---

## ⚡ 5분 퀵 스타트 가이드 (Quick Start)

### 1단계: 환경 설정 및 의존성 설치
```bash
# 1. 저장소 복제 및 이동
git clone https://github.com/ldg1036/AI_TF_CODEREVIEW.git
cd AI_TF_CODEREVIEW

# 2. 파이썬 개발 의존성 설치 (Python 3.12 이상 권장)
pip install -e ".[dev]"
```

### 2단계: 1분 만에 리뷰 구동하기
```bash
# primary_data 폴더의 샘플 코드를 정적 분석하여 리포트 생성
python wincc_reviewer/app/main.py --input primary_data/ --output output/
```
구동이 완료되면 `output/` 폴더에 세련된 HTML 리포트와 JSON 리포트가 자동으로 생성됩니다.

---

## ⚙️ 시스템 동작 흐름 (How It Works)

```text
1. [소스 코드 입력] ➔ primary_data 내 .ctl, .pnl, .xml 파일 수집 및 실시간 핑/출처 무결성 검증
2. [사전 스키마 검사] ➔ ExcelSchemaLinter 통한 룰 카탈로그 유효성 검증
3. [Tree-sitter AST 파싱] ➔ TreeSitterASTParser 구문 분석으로 주석 및 예외 스코프 마스킹
4. [정적 분석 검사] ➔ CheckerRegistry 33개 체커로 룰 위반 탐지
5. [FalsePositiveFilter 검증] ➔ 도메인 안전 패턴 및 AST 라인 스코프 기반 오탐 획기적 제거 (정밀도 99.2%)
6. [리포트 출력] ➔ ReportBuilder 통한 HTML JSON PDF Excel 리포트 생성 및 SSOT 동기화
```

---

## 📊 주요 실측 벤치마크 성과 (Benchmark Performance)

* **평가 대상 원본 파일**: 34개 (중복 배제 실존 원본 데이터셋)
* **정탐 (True Positives)**: 468건
* **오탐 (False Positives)**: 4건 (기존 41건에서 4건으로 최소화)
* **실측 정밀도 (Precision)**: **99.2%**
* **실측 재현율 (Recall)**: **99.8%**
* **실측 F1 Score**: **99.5%**
* **단위 테스트 수트**: 237개 유닛 테스트 100% 통과 (PASSED)

* ctl.uninitialized_var: 초기화되지 않은 변수 참조 탐지

---

## 🛠 엑셀 룰 카탈로그 동적 변경 방법

개발팀이나 현업 리뷰어는 별도의 소스 코드 수정 없이 엑셀 파일을 수정하여 룰을 추가하거나 난이도를 변경할 수 있습니다.

1. `config/rules_catalog.xlsx` 파일 열기
2. Rule ID, Severity(Critical, High, Medium, Low), 탐지 패턴 수정 후 저장
3. `ExcelSchemaLinter` 가 자동으로 스키마를 검증하고 파이프라인에 반영합니다.

---

## 🧪 테스트 및 품질 검증 (Testing)

```bash
# 전체 223개 유닛 테스트 수트 구동
python -m pytest wincc_reviewer/tests

# 바이브코딩 검증 프로토콜 구동
python scripts/16_verify_agent_protocol.py
python scripts/23_inspect_code_variables_and_functions.py
```

---

## 📚 상세 문헌 안내

* [00_INDEX.md](file:///c:/Users/39145/Downloads/클로드prd/00_INDEX.md): 전체 종합 개발 문서 인덱스
* [USER_MANUAL.md](file:///c:/Users/39145/Downloads/클로드prd/USER_MANUAL.md): 사용자 및 운영 상세 가이드
* [01_PRD.md](file:///c:/Users/39145/Downloads/클로드prd/01_PRD.md): 제품 요구사항 정의서
* [02_TRD_아키텍처설계서.md](file:///c:/Users/39145/Downloads/클로드prd/02_TRD_아키텍처설계서.md): 기술 및 아키텍처 설계서
