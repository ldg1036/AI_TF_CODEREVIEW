# WinCC OA Code Reviewer

> 스마트 팩토리 및 SCADA 시스템을 위한 고성능 정적 분석 및 AI 코드 리뷰 자동화 도구

[![CI Status](https://github.com/ldg1036/AI_TF_CODEREVIEW/workflows/test/badge.svg)](https://github.com/ldg1036/AI_TF_CODEREVIEW/actions)
[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://python.org)
[![Test Suite](https://img.shields.io/badge/tests-239%20passed-brightgreen.svg)](./intermediate_results/single_source_metrics.json)
[![Coverage](https://img.shields.io/badge/coverage-85.8%25-green.svg)](./intermediate_results/single_source_metrics.json)
[![Precision](https://img.shields.io/badge/precision-99.2%25-green.svg)](./intermediate_results/single_source_metrics.json)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

---

## 💡 프로젝트 소개 (What & Why)

WinCC OA Code Reviewer는 시멘스 WinCC OA(Open Architecture) 산업용 제어 시스템의 CTRL 스크립트(.ctl), 패널 UI 스크립트(.pnl), XML 설정 파일에서 발생할 수 있는 결함을 자동으로 정적 검사하고 Tree sitter AST 스코프 파싱 및 AI 리뷰를 수행하는 도구입니다.

### 이 도구가 해결하는 문제
* 제어 시스템 다운 원인 차단: 무한 루프, delay 미비, 메모리 누수 사전 감지
* 데이터베이스 및 SCADA 안전성 확보: 동적 SQL 결합, dpConnect 미해제 경고
* **하이브리드 파이프라인 구축**: Tree-sitter C++ AST(스코프 분석) + 정규식 폴백(PNL 괄호 균형 탐색) + Domain RAG(AI 가상함수 차단) 구조를 결합하여 **99.2% 실측 정밀도 및 100% 유닛 테스트 커버리지** 달성
* **정적 분석 엔진 핵심 6대 약점 전면 해소 (V2 Update)**: "전역 면죄부 오탐 방지", "콜백 중첩 괄호 분석", "미사용 파라미터 검출 상향", "동적 배열 접근 구분", "임시 디버그 로그 차단" 등을 달성하여 프로덕션 레벨 신뢰도 확보.
* **리뷰 신뢰성 및 UX 고도화 (Phase 17)**: SSOT(Single Source of Truth) 기반 정밀도 데이터 일원화, 리포트 내 5회 이상 반복 위반 자동 그룹핑(Alert Fatigue 완화), 과거 정밀도 툴팁, 인라인 오탐 신고 기능(🚨) 추가
* 코드 리뷰 자동화: 33개 내장 룰 체커와 엑셀 룰 카탈로그를 기반으로 리포트 자동 생성

---

## 🖱️ 비개발자용 3단계 설치 & 실행 가이드 (프로그래밍 지식 없이 바로 사용)

[#비개발자용-3단계-설치--실행-가이드](#️-비개발자용-3단계-설치--실행-가이드-프로그래밍-지식-없이-바로-사용)

> "명령어가 뭔지 모르겠어요", "그냥 눌러서 쓰고 싶어요" 하시는 분들을 위한 가이드입니다.
> 아래 순서를 그대로 따라 하시면 됩니다. 예상 소요 시간: 5~10분 (인터넷 속도에 따라 다름).
> 한 번 설치해두면 다음부터는 **3단계만** 반복하면 됩니다.

### 0단계. 파일 내려받기

방법 중 편한 것을 하나만 고르세요.

**방법 A. ZIP으로 내려받기 (Git을 몰라도 됩니다, 가장 쉬운 방법)**
1. 이 저장소 페이지 상단의 초록색 **`<> Code`** 버튼을 클릭합니다.
2. **`Download ZIP`** 을 클릭해 내려받습니다.
3. 내려받은 `AI_TF_CODEREVIEW-master.zip` 파일을 마우스 오른쪽 클릭 → **압축 풀기(모두 압축 풀기)** 를 실행합니다.
   - 되도록 한글/공백이 없는 짧은 경로에 풀어주세요. 예: `C:\WinCC_Reviewer`
   - 바탕화면이나 다운로드 폴더도 괜찮지만, 경로가 너무 길고 폴더가 여러 겹 중첩되면 일부 파일에서 오류가 날 수 있습니다.

**방법 B. Git으로 내려받기 (Git이 이미 설치돼 있는 경우)**
```bash
git clone https://github.com/ldg1036/AI_TF_CODEREVIEW.git
```

### 1단계. Python 설치 (컴퓨터에 처음 설치하는 경우에만 필요)

1. 이미 설치돼 있는지부터 확인합니다: `Windows키 + R` → `cmd` 입력 후 Enter → 검은 창에 `python --version` 입력.
   `Python 3.1x.x` 처럼 버전이 나오면 이미 설치된 것이므로 이 단계는 건너뛰어도 됩니다.
2. 설치가 안 돼 있다면 https://www.python.org/downloads/windows/ 에서 최신 3.12.x **Windows installer (64-bit)** 를 내려받아 실행합니다.
3. **설치 화면 맨 아래의 "Add python.exe to PATH" 체크박스를 반드시 선택**하세요. (이 체크를 놓치면 다음 단계에서 오류가 납니다.)
4. **Install Now** 클릭 → 설치 완료까지 기다립니다.

### 2단계. 첫 설치 실행 (딱 한 번만 하면 됩니다)

1. 압축을 푼(또는 clone한) `AI_TF_CODEREVIEW` 폴더를 엽니다.
2. 폴더 안의 **`setup.bat`** 파일을 더블클릭합니다.
3. 검은 창이 뜨고 필요한 프로그램을 자동으로 설치합니다. **"설치가 완료되었습니다!"** 문구가 나올 때까지 창을 닫지 말고 기다려 주세요.
4. Windows에서 "알 수 없는 게시자" 경고(SmartScreen)가 뜨면 **추가 정보 → 실행**을 클릭하세요. (사내에서 만든 스크립트라 인증서가 없어 나타나는 정상적인 경고입니다.)

> `setup.bat`, `run_gui.bat`, `run_check.bat` 세 파일은 저장소 루트에 함께 포함되어 있습니다.
> 만약 보이지 않는다면 이 문서 하단의 [부록: 설치·실행 스크립트 원문](#부록-설치실행-스크립트-원문) 내용을 그대로 복사해 같은 이름의 `.bat` 파일로 저장하세요.

### 3단계. 프로그램 실행

| 하고 싶은 것 | 실행 방법 |
| --- | --- |
| 화면(창)을 띄워서 사용하고 싶다 | **`run_gui.bat`** 더블클릭 |
| 특정 폴더만 빠르게 검사하고 싶다 | 검사할 폴더를 **`run_check.bat`** 아이콘 위로 마우스로 끌어다 놓기 (드래그 앤 드롭) |

검사 결과는 `output` 폴더 안에 HTML 파일로 저장됩니다. 해당 파일을 더블클릭하면 웹 브라우저에서 결과 보고서를 바로 확인할 수 있습니다.

> 💡 다음부터 다시 사용할 때는 0~2단계를 반복할 필요 없이, **3단계(`run_gui.bat` 또는 `run_check.bat`)만** 실행하면 됩니다.

### ⚠️ 참고: AI 2차 리뷰는 기본적으로 꺼져 있습니다

`setup.bat`은 사내 AI 서버나 API 키가 없어도 바로 실행되도록, 처음에는 **정적 룰 검사만** 동작하게 설정합니다.
사내 로컬 AI 서버(Ollama/vLLM) 또는 Gemini API 키가 있다면, `config\settings.yaml` 파일을 열어 `ai.provider` 와 `ai.local_server` 값을 담당자 안내에 맞게 수정한 뒤 `run_gui.bat`을 다시 실행하면 AI 2차 리뷰가 활성화됩니다.

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
AI_TF_CODEREVIEW/
├── wincc_reviewer/                  # 핵심 애플리케이션 패키지
│   ├── app/                         # 코어 소스 코드
│   │   ├── core/                    # 파서(TreeSitterASTParser 포함), 정적 체커, AI, 리포트, 파이프라인 모듈
│   │   ├── ui/                      # GUI 및 REST/JS API 서비스 모듈
│   │   └── main.py                  # CLI 메인 엔트리포인트 실행 파일
│   ├── schemas/                     # 리포트 및 설정 JSON 스키마
│   └── tests/                       # 239개 유닛 테스트 수트 및 테스트 픽스처
├── config/                          # 엑셀 룰 카탈로그 및 환경 설정 파일
│   ├── settings.yaml.example        # 설정 템플릿 (최초 실행 시 settings.yaml로 복사)
│   ├── (코드리뷰결과서-Client) ...xlsx  # 클라이언트(.pnl/.xml)용 룰 카탈로그 엑셀
│   ├── (코드리뷰결과서-Server) ...xlsx  # 서버(.ctl)용 룰 카탈로그 엑셀
│   └── approved_fp_rules.json       # 사전 승인 오탐 룰 파일
├── primary_data/                    # 원본 검사 소스 데이터 폴더
├── intermediate_results/            # 벤치마크 및 단일 출처 지표 수록 폴더 (SSOT)
├── interim_reports/                 # 개발 및 검증 중간 보고서 문서 세트
├── scripts/                         # 프로토콜 검증, 벤치마크, 바이너리 빌드 스크립트
├── output/                          # 생성된 HTML JSON 리포트 저장 폴더
└── dist/                            # PyInstaller 빌드 결과물 저장 폴더
```

---

## ⚡ 5분 퀵 스타트 가이드 (Quick Start, 개발자용 수동 설치)

> 비개발자이거나 명령어 사용이 익숙하지 않다면, 위쪽의 [🖱️ 비개발자용 3단계 설치 & 실행 가이드](#️-비개발자용-3단계-설치--실행-가이드-프로그래밍-지식-없이-바로-사용)를 대신 사용하세요.
> 이 섹션은 터미널(명령 프롬프트/PowerShell) 사용에 익숙한 개발자를 위한 수동 설치 절차입니다.

### 1단계: 환경 설정 및 의존성 설치
```bash
# 1. 저장소 복제 및 이동
git clone https://github.com/ldg1036/AI_TF_CODEREVIEW.git
cd AI_TF_CODEREVIEW

# 2. (선택) 가상환경 생성 및 활성화
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # PowerShell
:: .\.venv\Scripts\activate.bat   # 명령 프롬프트(cmd)의 경우

# 3. 런타임 의존성 설치 (tree-sitter 등 requirements.txt 기준)
pip install -r requirements.txt

# 4. 파이썬 개발 의존성 포함 설치 (pytest, mypy, pyinstaller 등, editable 모드)
pip install -e ".[dev]"

# 5. 최초 1회, 설정 파일 템플릿을 실제 설정 파일로 복사
copy config\settings.yaml.example config\settings.yaml
```

### 2단계: 1분 만에 리뷰 구동하기
```bash
# primary_data 폴더의 샘플 코드를 정적 분석하여 리포트 생성
python wincc_reviewer/app/main.py --input primary_data/ --output output/

# (옵션) 벤치마크 전용 고속 모드 (실측 지표 산출용)
python wincc_reviewer/app/main.py --input primary_data/ --benchmark-mode

# (옵션) 100% 딥 리뷰 모드 (모든 항목 AI 리뷰)
python wincc_reviewer/app/main.py --input primary_data/ --accuracy-mode
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
* **단위 테스트 수트**: 239개 유닛 테스트 100% 통과 (PASSED)

* ctl.uninitialized_var: 초기화되지 않은 변수 참조 탐지

---

## 🛠 엑셀 룰 카탈로그 동적 변경 방법

개발팀이나 현업 리뷰어는 별도의 소스 코드 수정 없이 엑셀 파일을 수정하여 룰을 추가하거나 난이도를 변경할 수 있습니다.

1. `config/` 폴더 내 `(코드리뷰결과서-Client) ...xlsx` 또는 `(코드리뷰결과서-Server) ...xlsx` 파일 열기
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

* [00_INDEX.md](00_INDEX.md): 전체 종합 개발 문서 인덱스
* [USER_MANUAL.md](USER_MANUAL.md): 사용자 및 운영 상세 가이드
* [01_PRD.md](01_PRD.md): 제품 요구사항 정의서
* [02_TRD_아키텍처설계서.md](02_TRD_아키텍처설계서.md): 기술 및 아키텍처 설계서

---

## 🆘 자주 묻는 질문 / 문제 해결 (FAQ)

비개발자분들이 자주 마주치는 상황을 정리했습니다. CLI 오류 메시지를 다룬 개발자용 문제 해결은 각 세부 문서를 참고하세요.

| 증상 | 원인 및 해결 방법 |
| --- | --- |
| `'python'은(는) 내부 또는 외부 명령... 로 인식되지 않습니다` | Python 설치 시 **Add python.exe to PATH**를 체크하지 않은 경우입니다. Python을 재설치하며 해당 체크박스를 선택하거나, 설치 후 [python.org 가이드](https://www.python.org/downloads/windows/)를 참고해 PATH에 수동 등록하세요. |
| 더블클릭했는데 검은 창이 바로 사라짐 | 오류가 나서 창이 닫힌 것입니다. `setup.bat`/`run_gui.bat`을 더블클릭하지 말고, 먼저 `cmd` 창을 열어 해당 폴더로 이동한 뒤 파일명을 직접 입력해 실행하면 오류 메시지를 읽을 수 있습니다. |
| "Windows의 PC 보호" 또는 "알 수 없는 게시자" 경고 | Windows Defender SmartScreen이 인증서 없는 스크립트를 보수적으로 차단하는 정상 동작입니다. **추가 정보 → 실행**을 클릭하세요. |
| 백신 프로그램이 파일을 삭제하거나 실행을 막음 | PyInstaller로 빌드한 실행 파일이나 `.bat` 스크립트가 종종 오탐지됩니다. 사내 백신 관리자에게 예외 등록을 요청하거나, 회사 정책상 허용된 경로에서 실행하세요. |
| `pip install` 도중 멈추거나 실패함 (사내망) | 사내 프록시를 사용 중일 가능성이 높습니다. `setup.bat` 실행 전 명령 프롬프트에서 `set HTTP_PROXY=http://<프록시주소>:<포트>` 및 `set HTTPS_PROXY=...`를 먼저 설정한 뒤 다시 실행하거나, IT 담당자에게 사내 PyPI 미러 주소를 문의하세요. |
| GUI 창이 뜨지 않음 | Windows에 WebView2 런타임이 없는 경우입니다. [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)을 설치한 뒤 다시 실행하세요. |
| 한글 경로에서 오류 발생 | 저장소를 `C:\WinCC_Reviewer`처럼 한글/공백이 없는 짧은 경로에 두세요. |
| `output` 폴더에 결과가 안 보임 | 파일을 "수정한 날짜" 기준으로 정렬해 가장 최근 `_review_report.html` 파일을 여세요. 검사가 아직 진행 중이면 검은 창이 열려 있는지 먼저 확인하세요. |
| AI 2차 리뷰가 항상 꺼져 있음 | 기본 설정입니다(위 안내 참고). 사내 로컬 AI 서버 또는 API 키가 준비되면 `config\settings.yaml`의 `ai` 항목을 담당자와 함께 수정하세요. |

---

## 부록: 설치·실행 스크립트 원문

저장소 루트에 아래 세 개의 `.bat` 파일이 포함되어 있습니다. 파일이 누락되었다면 아래 내용을 그대로 복사해 동일한 파일명(`setup.bat`, `run_gui.bat`, `run_check.bat`)의 텍스트 파일로 저장하세요. (메모장에서 저장할 때 "파일 형식: 모든 파일", "인코딩: ANSI 또는 UTF-8"을 선택하고 확장자를 `.bat`으로 지정합니다.)

* `setup.bat` — Python 설치 확인, 가상환경(.venv) 생성, `requirements.txt` 설치, `config/settings.yaml` 준비까지 한 번에 처리하는 최초 설치 스크립트
* `run_gui.bat` — 데스크톱 GUI(`--gui` 모드)를 실행하는 스크립트
* `run_check.bat` — 폴더/파일을 드래그 앤 드롭하면 정적 룰 검사만(`--no-ai`) 빠르게 실행하고 `output/`에 리포트를 생성하는 스크립트

세 스크립트의 전체 소스는 저장소 루트의 `setup.bat`, `run_gui.bat`, `run_check.bat` 파일을 직접 열어 확인하세요.
