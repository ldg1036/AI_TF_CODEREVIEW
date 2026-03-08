# WinCC OA Code Inspector

> Structure note (2026-02-27)
> - Canonical project paths are root directories: `Config`, `CodeReview_Data`, `docs`.
> - `workspace/` is a runtime/support area (for example `workspace/runtime/CodeReview_Report`).
> - Legacy tool commands under `tools/*.py` / `tools/*.js` are still supported via compatibility wrappers.
> - Official review quality baseline is `P1 (rules) + P2 (CtrlppCheck) + P3 (AI)` plus regression tests.

Last validated: 2026-03-09

## 개요

`WinCC OA Code Inspector`는 WinCC OA 프로젝트 코드 리뷰를 자동화/보조하기 위한 도구입니다.

지원 입력:
- `.ctl` (Server 코드)
- `.pnl`, `.xml`에서 변환된 텍스트 (`*_pnl.txt`, `*_xml.txt`)
- 필요 시 raw `.txt` (옵션)

출력 결과:
- UI 결과 화면
- HTML 리포트
- Excel 리포트
  - 메인 체크리스트 시트 기준 `F=1차 검증`, `G=검증 결과`, `H=비고`
  - 체크리스트 판정은 `완전 자동 / 부분 자동 / 수동 확인`으로 보수적으로 구분
- Annotated TXT (`*_REVIEWED.txt`)

또한 diff 승인형 source autofix를 지원하며, P3(LLM) 경로는 텍스트 입력(`*_pnl.txt`, `*_xml.txt`, raw `.txt`)에도 적용 가능합니다.

## 주요 기능

### 1) 코드 분석 (P1 / P2 / P3)
- `P1`: 정적 규칙 기반 분석
- `P2`: `CtrlppCheck` 연동 결과
  - `enable_ctrlppcheck=true` + `.ctl` 대상 분석 시작 시 CtrlppCheck preflight(자동 다운로드/설치) 1회 수행
  - preflight 실패 시 fail-soft로 P2 경고만 기록하고 P1/P3 분석은 계속 진행
- `P3`: AI(LLM) 리뷰 (선택/Fail-soft)

### 2) UI/운영 흐름
- 대시보드 / 작업공간 / 우측 이슈 상세 패널 3영역 UI
- 좌측 사이드바에서 프로젝트 파일 선택, 외부 파일 추가, 폴더 선택 지원
- 상단 헤더에서 `P2 CtrlppCheck`, `P3 Live AI`, `P3 모델`, `MCP 문맥 포함`, `검증 레벨`, `검증 프로파일`을 한 번에 제어
- `MCP 문맥` 상태는 실제 요청 예정/시도 결과가 있을 때만 짧게 표시
- `AI 제안` 탭에서 선택 이슈 기준 `추가 AI 분석` 실행 가능
- Excel 결과는 기본 즉시 생성 대신 필요 시 `Excel 결과 생성` 버튼으로 별도 생성
- 생성된 Excel은 헤더의 접힘(download panel) UI에서 파일별 다운로드

### 3) 성능/운영 최적화
- `/api/analyze` `metrics` 응답 제공 (optional dependency 상태 포함: `metrics.optional_dependencies`)
- `/api/analyze` `summary.verification_level` 제공 (`CORE_ONLY` 또는 `CORE+REPORT`)
- async analyze progress API: `POST /api/analyze/start`, `GET /api/analyze/status?job_id=...`
- dependency preflight API: `GET /api/health/deps` (`openpyxl` / `CtrlppCheck` / `Playwright` 상태 + capability readiness)
- rules/dependency status API: `GET /api/rules/health`
- 파일 단위 bounded parallel 분석
- `.pnl/.xml -> *_txt` 변환 캐시 (`mtime + size`)
- Excel 기본 동기 생성 + 선택적 지연 생성(`defer_excel_reports`) + flush API

### 체크리스트 판정 기준

- `완전 자동`
  - `Loop문 내에 처리 조건`
  - `while` 패턴이 있는 경우에만 `OK/NG`를 자동 판정
- `부분 자동`
  - `메모리 누수 체크`
  - `하드코딩 지양`
  - `디버깅용 로그 작성 확인`
  - 위반이 검출되면 `NG`, 미검출이면 `N/A + 수동 확인 권장`
- `수동 확인`
  - `쿼리 주석 처리`
  - 형식 품질(`기능명_날짜_HWC`)까지 자동 보장하지 않으므로 결과서는 `N/A` 유지
- 결과 테이블 virtualization
- 프론트 헤더에서 분석 진행률/ETA/경과시간 표시 (polling 기반)

### 4) Autofix
- `autofix/prepare` -> `file-diff` 확인 -> `autofix/apply`
- `llm` / `rule` / `auto(rule-first, llm-fallback)` generator
- `rule` 경로는 `.ctl` 중심, `P3(llm)` 경로는 텍스트 입력까지 지원
- hash / anchor / syntax / heuristic / optional Ctrlpp regression 검증
- multi-hunk P1 안전정책: same-block, 최대 3개, overlap/cross-block fail-soft 차단
- 백업 파일 + 감사 로그 + 사용자 승인 흐름

API note:
- `GET /api/autofix/stats` includes `multi_hunk_attempt_count`, `multi_hunk_success_count`, `multi_hunk_blocked_count`
- `POST /api/autofix/apply` may return fail-soft `error_code="APPLY_ENGINE_FAILED"` for unsafe multi-hunk scenarios

### 5) 벤치/스모크 도구
- UI benchmark: `tools/playwright_ui_benchmark.js`
- Real-server UI smoke: `tools/playwright_ui_real_smoke.js`
- Consolidated release gate: `python tools/release_gate.py`
- Consolidated release gate with live AI: `python tools/release_gate.py --with-live-ai --live-ai-with-context`
- CI profile gate: `python tools/release_gate.py --profile ci`
- Windows one-click wrappers: `run_release_gate.bat`, `run_release_gate.ps1`
- HTTP baseline: `tools/http_perf_baseline.py`
- Ctrlpp smoke: `tools/run_ctrlpp_integration_smoke.py`
- Autofix root-cause summary: `python tools/perf/autofix_root_cause_summary.py --input-glob "docs/perf_baselines/autofix_apply_improved_*.json"`

## Release Verification (P1/P2/P3)

Prerequisite (report/template validation):
- `pip install -r requirements-dev.txt` (`openpyxl` for Excel/template checks)

Required:
1. `python -m unittest backend.tests.test_api_and_reports -v`
2. `python -m unittest backend.tests.test_todo_rule_mining -v`
3. `python -m unittest backend.tests.test_winccoa_context_server -v`
4. `python -m py_compile backend/main.py backend/server.py backend/core/analysis_pipeline.py`
5. `python backend/tools/check_config_rule_alignment.py --json`
6. `python backend/tools/run_verification_profile.py --profile core --include-report` (writes `CodeReview_Report/verification_summary_*.json`)

Optional (change-dependent):
1. Ctrlpp integration: `python tools/run_ctrlpp_integration_smoke.py --allow-missing-binary --skip-unittest`
2. Frontend/perf: `node --check frontend/renderer.js`, `node tools/playwright_ui_benchmark.js --iterations 3`, `node tools/playwright_ui_real_smoke.js --target-file BenchmarkP1Fixture.ctl`
3. Rules/config: `python backend/tools/check_config_rule_alignment.py --json`, `python backend/tools/analyze_template_coverage.py`
   - `openpyxl`가 없는 환경에서는 `python backend/tools/analyze_template_coverage.py --ensure-openpyxl`로 자동 설치 후 실행 가능
   - 네트워크/설치 제한 환경에서는 `python backend/tools/analyze_template_coverage.py --fail-soft`로 optional missing 상태 리포트를 생성 가능

Release checklist:
- See `docs/release_gate_checklist.md`
- User operations guide: `docs/user_operations_guide.md`
- Release packaging criteria: `docs/release_packaging_criteria.md`
- One-shot gate: `python tools/release_gate.py`
- Gate summary markdown is written beside the JSON report
- `local` profile runs UI/Ctrlpp by default, `ci` profile skips those unless explicitly included
- Quick Windows entrypoints:
  - `run_release_gate.bat`
  - `run_release_gate.bat live-ai`
  - `powershell -ExecutionPolicy Bypass -File .\run_release_gate.ps1 -Mode ci`

## Quick Start

### UI 서버 실행
```powershell
python backend/server.py
```
접속: `http://127.0.0.1:8765`

프론트 분석 동작:
- 기본 분석 버튼은 `/api/analyze/start` + `/api/analyze/status` 폴링으로 진행률/ETA를 표시합니다.
- 완료 시 최종 결과 payload(`summary`, `violations`, `output_dir`, `metrics`, `report_jobs`)를 기존과 동일하게 렌더링합니다.
- 기본 UI 흐름은 `대시보드 -> 작업공간 -> 이슈 상세` 순서이며, P3는 이슈 상세의 `AI 제안` 탭에서 확인/재생성합니다.
- Excel 리포트는 분석 완료 후 필요할 때만 `Excel 결과 생성` 버튼으로 생성하고 다운로드합니다.

### CLI 분석 실행
```powershell
python backend/main.py --selected-files GoldenTime.ctl
```

추가 예시:
```powershell
python backend/main.py --selected-files GoldenTime.ctl --enable-ctrlppcheck
python backend/main.py --selected-files raw_input.txt --allow-raw-txt
python backend/main.py --selected-files GoldenTime.ctl --enable-live-ai
```

## 주요 API

- `POST /api/analyze/start`
- `GET /api/analyze/status?job_id=...`
- `POST /api/report/excel`
- `GET /api/report/excel/download?output_dir=...&name=...`
- `POST /api/ai-review/generate`
- `GET /api/health/deps`
- `GET /api/rules/health`

## 현재 UI 기준 사용 흐름

1. 좌측 사이드바에서 분석할 파일을 선택하거나 외부 파일/폴더를 추가합니다.
2. 상단 헤더에서 `P2`, `P3`, 모델, MCP 문맥 포함 여부를 조정합니다.
3. `선택 항목 분석`을 실행하면 진행률/ETA가 헤더에 표시됩니다.
4. 작업공간에서 결과 리스트를 확인하고, 우측 `이슈 상세` / `AI 제안` 탭에서 상세 내용을 봅니다.
5. P3가 없거나 보강이 필요하면 `추가 AI 분석`으로 선택 이슈 1건만 다시 생성할 수 있습니다.
6. Excel이 필요하면 `Excel 결과 생성`을 눌러 별도 생성한 뒤 다운로드합니다.

## 프로젝트 구조

```text
AI_TF_CodeReview/
├─ backend/
├─ frontend/
├─ tools/
│  ├─ perf/
│  └─ ctrlpp/
├─ Config/                 # canonical config path
├─ CodeReview_Data/        # canonical input data path
├─ docs/                   # canonical docs path
├─ workspace/              # runtime/support area
│  ├─ runtime/
│  │  └─ CodeReview_Report/
│  ├─ resources/
│  │  └─ README.md
│  └─ documentation/
│     └─ README.md
├─ CodeReview_Report/      # report output path (gitignored)
├─ README.md
└─ todo.md
```
