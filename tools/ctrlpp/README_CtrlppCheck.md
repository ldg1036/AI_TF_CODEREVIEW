# CtrlppCheck 자동 업데이트/실행 도구

마지막 업데이트: 2026-02-25 (현재 프로그램 기준 반영)

프로젝트 루트 `tools/` 폴더의 CtrlppCheck 보조 도구 설명서입니다.

이 도구들은 메인 코드리뷰 서버(`backend/server.py`)와 별개로 CtrlppCheck를 수동 실행하거나,
GitHub 릴리즈 기준으로 업데이트를 확인/설치할 때 사용합니다.

## 구성 파일

- `tools/ctrlppcheck_updater.py`
  - CtrlppCheck 최신 릴리즈 확인 및 업데이트 도구
  - GUI(Tkinter) / CLI 모드 지원
- `tools/ctrlppcheck_wrapper.py`
  - CtrlppCheck 실행 래퍼
  - 실행 전 업데이트 확인(옵션) 후 `ctrlppcheck.exe` 실행
- `tools/run_ctrlpp_integration_smoke.py`
  - 메인 프로그램 연동 기준 통합 스모크 (direct smoke + optional unittest harness)
- `tools/CtrlppCheck/version.txt`
  - 현재 설치 버전 기록 파일 (예: `v1.0.2`)

참고:
- 대용량 설치 산출물(`download/`, `extract/`)은 `.gitignore`로 제외됩니다.
- 실제 실행 파일은 일반적으로 아래 경로 중 하나에 위치합니다.
  - `tools/CtrlppCheck/<version>/extract/WinCCOA_QualityChecks/bin/ctrlppcheck/ctrlppcheck.exe`
  - `tools/CtrlppCheck/extract/WinCCOA_QualityChecks/bin/ctrlppcheck/ctrlppcheck.exe`

## 빠른 사용법

### 1) 업데이트 확인만 수행

```powershell
python tools/ctrlppcheck_updater.py --cli --check
```

### 2) 업데이트 후 실행(권장)

```powershell
python tools/ctrlppcheck_wrapper.py sample.ctl
```

### 3) 업데이트 확인 없이 바로 실행

```powershell
python tools/ctrlppcheck_wrapper.py --skip-update sample.ctl
```

### 4) XML 출력으로 실행

```powershell
python tools/ctrlppcheck_wrapper.py --xml --output-file=result.xml sample.ctl
```

## 통합 스모크 (메인 프로그램 연동 검증)

메인 프로그램의 `backend/core/ctrl_wrapper.py` 연동 경로까지 포함해서 점검하려면:

```powershell
python tools/run_ctrlpp_integration_smoke.py
```

옵션 예시:

```powershell
python tools/run_ctrlpp_integration_smoke.py --allow-missing-binary --skip-unittest
python tools/run_ctrlpp_integration_smoke.py --binary C:\path\to\ctrlppcheck.exe
```

생성 리포트:
- `tools/integration_results/ctrlpp_integration_*.json`

## `ctrlppcheck_wrapper.py` 주요 옵션

- `--check-update`, `-U`: 업데이트 확인만 수행 후 종료
- `--skip-update`, `-S`: 업데이트 확인 건너뛰기
- `--project-name`, `-p`: WinCC OA 프로젝트명 (기본값 `CodeReview`)
- `--enable`, `-e`: 검사 레벨 지정 (예: `warning`, `style`, `performance`)
- `--all`, `-a`: 모든 검사 활성화
- `--library`, `-L`: `ctrl.xml` 라이브러리 파일 경로 지정
- `--rule-file`, `-R`: 룰 파일 경로 지정
- `--naming-rule`, `-N`: 네이밍 룰 파일 경로 지정
- `--platform`: 대상 플랫폼 (`win64` 기본)
- `--xml`, `-x`: XML 출력 활성화
- `--output-file`, `-o`: 결과 파일 경로 지정
- `--quiet`, `-q`: 진행 로그 축소
- `--verbose`, `-v`: 상세 출력
- `--inline-suppr`: 인라인 suppressions 사용
- `--inconclusive`: inconclusive 결과 포함
- `--suppressions`: suppressions-list 파일 경로

## `ctrlppcheck_updater.py` 주요 옵션

- `--check`, `-c`: 업데이트 확인만 수행
- `--force`, `-f`: 사용자 확인 없이 업데이트 진행
- `--cli`: GUI 없이 CLI 모드로 실행

## 메인 코드리뷰 프로그램과의 관계

- 메인 코드리뷰 프로그램은 `backend/core/ctrl_wrapper.py`를 통해 CtrlppCheck를 연동합니다.
- 본 `tools/*.py`는 운영/개발자가 CtrlppCheck를 독립적으로 점검/업데이트/실행할 때 사용하는 보조 도구입니다.
- `Config/config.json`의 CtrlppCheck 설정(`enabled_default`, `binary_path`, `auto_install_on_missing` 등)과 병행해서 사용할 수 있습니다.
- 메인 프로그램 기준으로는 `backend/core/ctrl_wrapper.py`의 `ensure_installed()` 경로가 실제 바이너리 설치 복구에 사용됩니다.

## 스모크 테스트 (권장)

```powershell
python tools/ctrlppcheck_updater.py --help
python tools/ctrlppcheck_wrapper.py --help
python tools/run_ctrlpp_integration_smoke.py --help
python -m py_compile tools/ctrlppcheck_updater.py tools/ctrlppcheck_wrapper.py tools/run_ctrlpp_integration_smoke.py
```

## 트러블슈팅

### `ctrlppcheck.exe`를 찾지 못하는 경우

- `tools/CtrlppCheck/version.txt`는 있어도 실제 `extract` 폴더가 없을 수 있습니다.
- 먼저 업데이트 확인/설치를 수행하거나, `--check-update`로 설치 상태를 점검하세요.
- 필요하면 `--library`, `--rule-file`, `--naming-rule`를 명시적으로 지정하세요.

### GUI가 뜨지 않는 경우

- `tkinter`가 없거나 서버 환경인 경우 `--cli` 옵션을 사용하세요.

### 업데이트 확인 실패

- 네트워크 차단, GitHub API rate-limit, `requests` 미설치일 수 있습니다.
- `pip install requests` 후 재시도하세요.

## 참고

- Siemens CtrlppCheck Releases: https://github.com/siemens/CtrlppCheck/releases
- 프로젝트 메인 문서: `README.md`
