# 환경설정 가이드

> 본 문서는 `AI_TF_CODEREVIEW` 프로젝트를 개발자 PC 및 현장 배포 환경에서 실행하기 위한 상세 설정 절차를 설명합니다.  
> 대상: Windows 10/11 (64-bit), Python 3.12 이상

---

## 1. 개요

`WinCC OA Code Reviewer`는 Siemens WinCC Open Architecture(SCADA) 프로젝트의 `.ctl`, `.pnl`, `.xml` 소스 코드에 대해 엑셀 기반 표준 리뷰 가이드라인을 정적 분석하고 리포트를 생성하는 자동화 도구입니다.

### 1.1 지원 플랫폼

- **운영체제**: Windows 10 또는 Windows 11 (64-bit)
- **Python**: 3.12 이상
- **GUI**: pywebview (기본 내장 WebView 사용, 별도 웹서버 불필요)

### 1.2 실행 모드

| 모드 | 명령어 | 용도 |
|---|---|---|
| CLI | `python -m app.main --input <경로>` | 터미널에서 배치/스크립트 실행 |
| GUI | `python -m app.ui.app` 또는 `python -m app.main --gui` | 데스크톱 윈도우 앱 |

---

## 2. 사전 요구사항

### 2.1 필수 항목

1. **Python 3.12 이상** 설치
   - 확인: `python --version`
   - 다운로드: https://www.python.org/downloads/windows/

2. **Git** 설치
   - 확인: `git --version`

3. **레포지토리 클론**
   ```bash
   git clone https://github.com/ldg1036/AI_TF_CODEREVIEW.git
   cd AI_TF_CODEREVIEW
   cd wincc_reviewer
   ```

### 2.2 선택 항목

| 기능 | 필요 조건 | 비고 |
|---|---|---|
| **WinMerge Diff** | WinMerge 설치 | 미설치 시 Python `difflib` 자동 폴백 |
| **AI 2차 심층 리뷰** | 사내 로컬 AI 서버(vLLM, Ollama 등) 또는 Gemini API 키 | `config/settings.yaml`에서 설정 |
| **자동수정(AutoFix)** | 별도 설치 불필요 | `config/settings.yaml` `autofix.enabled`로 제어 |

---

## 3. 개발 환경 설정

### 3.1 가상환경 생성 및 활성화

```bash
# 가상환경 생성
python -m venv .venv

# 활성화 (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# 활성화 (Windows Command Prompt)
.\.venv\Scripts\activate.bat
```

### 3.2 의존성 설치

```bash
# 개발 의존성 포함 설치 (editable 모드)
pip install -e ".[dev]"
```

주요 패키지:
- `openpyxl>=3.1,<4` — Excel 룰 파일 파싱
- `pywebview>=5,<6` — 데스크톱 GUI
- `httpx>=0.27,<1` — AI 서버 HTTP 통신
- `pyyaml>=6,<7` — settings.yaml 파싱
- `pytest>=8,<9` — 테스트 프레임워크 (dev)
- `pyinstaller>=6,<7` — EXE 빌드 (dev)

### 3.3 설정 파일 확인

프로젝트 루트의 다음 파일들이 존재하는지 확인합니다:

```
config/
├── (코드리뷰결과서-Client) 코드 리뷰 결과서 양식_v2.0_20251201.xlsx
├── (코드리뷰결과서-Server) 코드 리뷰 결과서 양식_v2.0_20251104.xlsx
├── settings.yaml
└── legacy_mapping/
    ├── client.yaml
    └── server.yaml
```

> **주의**: `config/` 디렉터리는 Git LFS 또는 별도 관리로 운영될 수 있습니다.  
> 파일이 누락된 경우 정적 룰 검사가 비활성화됩니다.

### 3.4 테스트 실행

```bash
pytest tests/ -v
```

테스트 디렉터리: `tests/`  
테스트 데이터: `tests/fixtures/` (ctl, pnl, xml 샘플)

### 3.5 기본 CLI 실행

```bash
python -m app.main --help
```

주요 옵션:

| 옵션 | 설명 | 기본값 |
|---|---|---|
| `--input <경로>` | 검사 대상 파일 또는 디렉터리 | — |
| `--rule-source <경로>` | 룰 원천 Excel 파일 | Client/Server 자동 감지 |
| `--no-ai` | AI 리뷰 비활성화 (정적 룰만) | `False` |
| `--gui` | GUI 모드 실행 | `False` |
| `--autofix` | 자동수정 제안 생성 | `False` |
| `--diff` | WinMerge Diff 생성 | `False` |
| `--max-ai-reviews <N>` | AI 2차 리뷰 최대 위반 건수 (0=전체) | `10` |
| `--output <디렉터리>` | 결과 출력 경로 | `./output/` |
| `--log-level <LEVEL>` | 로그 레벨 (DEBUG/INFO/WARNING/ERROR) | `INFO` |
| `--config <경로>` | 설정 파일 경로 | `config/settings.yaml` |

### 3.6 GUI 실행

```bash
# 방법 1: GUI 전용
python -m app.ui.app

# 방법 2: main 모듈 (인자 없이 실행 시 GUI 모드)
python -m app.main
```

---

## 4. 설정 파일 상세

### 4.1 `config/settings.yaml`

```yaml
app:
  version: "0.1.0"
  log_level: "INFO"

rule_sources:
  client:
    path: "config/(코드리뷰결과서-Client) 코드 리뷰 결과서 양식_v2.0_20251201.xlsx"
    sheet_name: "(클라이언트) 코드 리뷰 결과서"
    file_types: ["pnl", "xml"]
  server:
    path: "config/(코드리뷰결과서-Server) 코드 리뷰 결과서 양식_v2.0_20251104.xlsx"
    sheet_name: "(서버) 코드 리뷰 결과서"
    file_types: ["ctl"]

excel_structure:
  header_row: 17
  data_start_row: 18
  data_columns: "B:H"
  client_data_rows: [18, 32]
  server_data_rows: [18, 37]

ai:
  enabled: true
  provider: "local"        # local | gemini | mock
  timeout_seconds: 60
  max_retries: 3
  local_server:
    host: "127.0.0.1"
    port: 8000
    api_key: ""
    endpoint: "/v1/chat/completions"
    model_id: "sane_local_llm"

autofix:
  enabled: false

winmerge:
  enabled: false
  fallback_to_difflib: true

output:
  default_dir: "./output"
  formats: ["json", "html"]

legacy_mapping:
  client: "config/legacy_mapping/client.yaml"
  server: "config/legacy_mapping/server.yaml"
```

### 4.2 AI 프로바이더 설정

#### 사내 로컬 AI 서버 (vLLM, Ollama 등)

```yaml
ai:
  enabled: true
  provider: "local"
  local_server:
    host: "192.168.1.100"   # 사내 서버 IP
    port: 8000
    api_key: ""             # 필요 시 입력
    endpoint: "/v1/chat/completions"
    model_id: "sane_local_llm"
```

#### Gemini API 사용

```yaml
ai:
  enabled: true
  provider: "gemini"
```

환경변수로 API 키 설정:
```bash
set GEMINI_API_KEY=your_api_key_here
# 또는
set GOOGLE_API_KEY=your_api_key_here
```

#### AI 비활성화 (정적 룰만 사용)

```bash
python -m app.main --input <경로> --no-ai
```

### 4.3 legacy_mapping 디렉터리

`config/legacy_mapping/*.yaml`은 엑셀 룰과 내부 체커를 연결하는 매핑 파일입니다.  
엑셀 양식 변경 시 해당 YAML도 함께 수정해야 합니다.

---

## 5. 선택적 기능 설정

### 5.1 WinMerge 연동

1. WinMerge 설치 (https://winmerge.org/downloads/)
2. 설치 후 자동 감지되며, 미감지 시 `difflib` 폴백 모드로 동작

`settings.yaml`에서 강제 지정 가능:
```yaml
winmerge:
  enabled: true
  fallback_to_difflib: true
```

### 5.2 자동수정(AutoFix)

```bash
# CLI에서 활성화
python -m app.main --input <경로> --autofix

# 또는 settings.yaml
autofix:
  enabled: true
```

### 5.3 점진적 검사 캐시

파일 변경 시 SHA256 해시 기반으로 캐시를 자동 관리합니다.  
캐시 파일 위치: `config/../cache/review_cache.json`

---

## 6. 배포 (PyInstaller)

### 6.1 빌드

```bash
# 폴더 배포 방식 (권장)
pyinstaller wincc_reviewer.spec --noconfirm
```

출력물: `dist/WinCC_OA_Code_Reviewer/`

### 6.2 배포 시 주의사항

1. **config 디렉터리 동봉 필수**
   - Excel 룰 파일 2개
   - `settings.yaml`
   - `legacy_mapping/*.yaml`

2. **실행 방법**
   - `WinCC_OA_Code_Reviewer.exe` 더블클릭 (GUI 모드)
   - 명령줄: `WinCC_OA_Code_Reviewer.exe --input <경로>`

3. **Windows WebView 런타임**
   - Windows 10/11에는 기본 내장되어 있습니다.
   - 오류 발생 시: https://developer.microsoft.com/en-us/microsoft-edge/webview2/

---

## 7. 문제 해결 (Troubleshooting)

### 7.1 Python 버전 불일치

```
ERROR: Package requires Python >=3.12
```
해결: Python 3.12 이상으로 업그레이드 또는 가상환경 재생성

### 7.2 pywebview GUI 실행 실패

```
ImportError: No module named 'webview'
```
해결:
```bash
pip install pywebview>=5,<6
```

Windows WebView 런타임 누락 시 Microsoft Edge WebView2 Runtime 설치

### 7.3 Excel 룰 파일 경로 오류

```
Client Excel 룰셋 컴파일 실패
```
확인:
- `config/` 디렉터리에 Excel 파일 2개 존재 여부
- 파일명이 정확한지 확인 (한글 파일명 주의)
- `settings.yaml`의 `rule_sources.path` 확인

### 7.4 AI 서버 연결 실패

```
로컬 AI 연동 실패: 통신 실패 (URLError)
```
확인:
- `settings.yaml`의 `ai.local_server.host` 및 `port`
- 방화벽에서 해당 포트 개방 여부
- AI 서버 실행 상태 확인
- `--no-ai` 플래그로 정적 룰만 사용

### 7.5 인코딩 오류

```
UnicodeDecodeError / 파싱 실패
```
- 소스 파일 인코딩: UTF-8 또는 CP949(EUC-KR) 자동 감지
- 파싱 실패 파일은 리포트의 `Errors` 탭에 별도 수집됨

### 7.6 WinMerge 미탐지

```
WinMerge 미설치 — difflib 폴백 모드로 작동합니다.
```
해결: WinMerge 설치 또는 `--diff` 옵션 생략

---

## 8. 디렉터리 구조

```
AI_TF_CODEREVIEW/
├── config/
│   ├── (코드리뷰결과서-Client) 코드 리뷰 결과서 양식_v2.0_20251201.xlsx
│   ├── (코드리뷰결과서-Server) 코드 리뷰 결과서 양식_v2.0_20251104.xlsx
│   ├── settings.yaml
│   └── legacy_mapping/
│       ├── client.yaml
│       └── server.yaml
├── primary_data/              # 검사 대상 샘플 데이터
├── output/                    # 리포트 출력 디렉터리 (자동 생성)
├── cache/                     # 점진적 검사 캐시 (자동 생성)
├── wincc_reviewer/
│   ├── app/
│   │   ├── main.py            # CLI 진입점
│   │   ├── core/              # 파이프라인, 룰 엔진, AI 프로바이더
│   │   └── ui/                # pywebview GUI
│   ├── tests/                 # 테스트 스위트
│   ├── schemas/               # JSON 스키마
│   └── pyproject.toml         # 프로젝트 설정
└── SETUP_GUIDE.md             # 본 문서
```

---

## 9. 참고 문서

| 문서 | 설명 |
|---|---|
| `README.md` | 프로젝트 개요 및 빠른 시작 |
| `USER_MANUAL.md` | GUI 사용자 매뉴얼 및 오류 코드 가이드 |
| `02_TRD_아키텍처설계서.md` | 기술 상세 설계서 |
| `03_정적분석_룰카탈로그.md` | 정적 분석 룰 카탈로그 |
| `09_구현착수_패키지_계약.md` | 구현 계약 및 데이터 모델 정의 |
| `BLOCKED.md` | 미확정/BLOCKED 항목 관리 |
