# WinCC OA Code Inspector

> Structure note (2026-02-26)
> - Actual grouped paths now live under `workspace/`:
>   - `workspace/resources/{Config, CodeReview_Data}`
>   - `workspace/runtime/CodeReview_Report`
>   - `workspace/documentation/docs`
> - Legacy root paths (`Config`, `CodeReview_Data`, `CodeReview_Report`, `docs`) are kept as compatibility junctions.
> - Legacy tool commands under `tools/*.py` / `tools/*.js` still work via compatibility wrappers.
> - See `workspace/README.md` and `tools/README.md` for details.
> - Official review quality verification is based on `P1 (rules) + P2 (CtrlppCheck) + P3 (AI)` plus regression tests.
> - GoldenTime workbook/reference Excel comparison is no longer an official quality criterion.

> WinCC OA 코드 리뷰/정적 분석/AI 보조 리뷰/승인형 자동수정을 위한 로컬 실행형 품질 점검 도구

## 개요

`WinCC OA Code Inspector`는 WinCC OA 프로젝트의 코드 리뷰를 자동화/반자동화하기 위한 도구입니다.

다음 입력을 대상으로 분석할 수 있습니다.
- `.ctl` (Server 코드)
- `.pnl`, `.xml`에서 변환된 텍스트 (`*_pnl.txt`, `*_xml.txt`)
- 필요 시 raw `.txt` (옵션 허용 시)

분석 결과는 다음 형태로 확인할 수 있습니다.
- UI (로컬 웹 인터페이스)
- HTML 리포트
- Excel 체크리스트 리포트
- Annotated TXT (`*_REVIEWED.txt`)

또한 현재 버전은 승인형(diff review) 기반의 source autofix(`.ctl` 전용)를 지원합니다.

## 주요 기능

### 1) 코드 분석 (P1 / P2 / P3)
- `P1`: 휴리스틱/정적 규칙 기반 코드 분석
- `P2`: `CtrlppCheck` 연동 결과
- `P3`: LLM 기반 AI 리뷰 (선택)

### 2) 성능/운영 최적화
- `/api/analyze` `metrics` 응답 (단계별 timing, 호출 수, cache hit/miss)
- 파일 단위 bounded parallel 분석
- `.pnl/.xml -> *_txt` 변환 캐시 (`mtime + size`)
- Excel 지연 생성(`defer_excel_reports`) + flush API
- 프론트 결과 테이블/코드뷰 virtualization

### 3) 승인형 자동수정 (CTL only)
- `autofix/prepare` → `file-diff` 확인 → `autofix/apply`
- `.ctl`만 적용 허용
- `llm` / `rule` / `auto(rule-first, llm-fallback)` generator
- hash / anchor / syntax / heuristic / optional Ctrlpp 회귀검사
- 백업 파일 + 감사 로그 + 원자적 쓰기

### 4) 품질 게이트 / 벤치마크
- Playwright UI 벤치 (`tools/playwright_ui_benchmark.js`)
- `/api/analyze` HTTP baseline 매트릭스 (`tools/http_perf_baseline.py`)
- Ctrlpp 통합 스모크 (`tools/run_ctrlpp_integration_smoke.py`)

## Release Verification (P1/P2/P3)

Use regression tests and fail-soft optional smokes as the release baseline.
GoldenTime reference workbook comparison and `goldentime_compare_result.json` are not part of the official quality criteria.

Required:

1. `python -m unittest backend.tests.test_api_and_reports -v`
2. `python -m unittest backend.tests.test_todo_rule_mining -v`
3. `python -m unittest backend.tests.test_winccoa_context_server -v`
4. `python -m py_compile backend/main.py backend/server.py backend/core/analysis_pipeline.py`

Optional (change-dependent):

1. Ctrlpp integration: `python tools/run_ctrlpp_integration_smoke.py --allow-missing-binary --skip-unittest`
2. Frontend/perf: `node --check frontend/renderer.js`, `node tools/playwright_ui_benchmark.js --help`
3. Rules/config: `python backend/tools/check_config_rule_alignment.py --json`, `python backend/tools/analyze_template_coverage.py`

## 현재 구현 상태 (요약)

현재 코드베이스 기준으로 다음이 구현되어 있습니다.
- [x] 성능 계측 (`metrics`)
- [x] 변환 캐시 + 병렬 분석 + 경로별 동시성 제한
- [x] 세션 TTL/LRU + per-session/per-file lock
- [x] Diff 승인형 source autofix (`.ctl`)
- [x] hybrid prepare (`llm` / `rule` / `auto`)
- [x] autofix 품질 메트릭 / 실패 코드 / stats API
- [x] Excel 지연 생성 + flush API
- [x] UI virtualization + Playwright 벤치 baseline
- [x] Ctrlpp 실제 바이너리 통합 스모크
- [x] UTF-8 고정 인코딩 정책 + `.editorconfig`

## 프로젝트 구조

```text
AI_TF_CodeReview/
├─ backend/
│  ├─ main.py                      # CodeInspectorApp (analysis/session/autofix orchestration)
│  ├─ server.py                    # HTTP API + static UI server
│  ├─ core/
│  │  ├─ analysis_pipeline.py      # analysis orchestration pipeline
│  │  ├─ reporter.py               # HTML/Excel/Annotated TXT reports
│  │  ├─ llm_reviewer.py           # LLM review generation
│  │  ├─ ctrl_wrapper.py           # CtrlppCheck integration
│  │  └─ ...
│  └─ tests/
├─ frontend/
│  ├─ index.html
│  ├─ renderer.js
│  └─ style.css
├─ tools/
│  ├─ perf/                        # actual perf tool implementations
│  │  ├─ playwright_ui_benchmark.js
│  │  └─ http_perf_baseline.py
│  ├─ ctrlpp/                      # actual Ctrlpp helper implementations
│  │  ├─ run_ctrlpp_integration_smoke.py
│  │  ├─ ctrlppcheck_updater.py
│  │  ├─ ctrlppcheck_wrapper.py
│  │  └─ README_CtrlppCheck.md
│  ├─ CtrlppCheck/                 # runtime install/cache path (legacy path kept)
│  ├─ benchmark_results/           # benchmark outputs (legacy path kept)
│  ├─ integration_results/         # integration smoke outputs (legacy path kept)
│  ├─ README.md                    # tools layout guide
│  ├─ playwright_ui_benchmark.js   # compatibility wrapper (legacy command path)
│  ├─ http_perf_baseline.py        # compatibility wrapper (legacy command path)
│  ├─ run_ctrlpp_integration_smoke.py
│  ├─ ctrlppcheck_updater.py
│  ├─ ctrlppcheck_wrapper.py
│  └─ README_CtrlppCheck.md        # compatibility pointer doc
├─ workspace/                      # grouped actual data/docs/report paths
│  ├─ resources/
│  │  ├─ Config/                   # actual path (root Config is a compatibility junction)
│  │  └─ CodeReview_Data/          # actual path (root CodeReview_Data is a compatibility junction)
│  ├─ runtime/
│  │  └─ CodeReview_Report/        # actual path (root CodeReview_Report is a compatibility junction)
│  ├─ documentation/
│  │  └─ docs/                     # actual path (root docs is a compatibility junction)
│  └─ README.md
├─ docs/                           # compatibility junction -> workspace/documentation/docs
├─ Config/                         # compatibility junction -> workspace/resources/Config
├─ CodeReview_Data/                # compatibility junction -> workspace/resources/CodeReview_Data
├─ CodeReview_Report/              # compatibility junction -> workspace/runtime/CodeReview_Report
├─ README.md
└─ todo.md
```

## 빠른 시작 (Quick Start)

### 요구사항
- Python 3.x
- (선택) Ollama / 로컬 LLM
- (선택) CtrlppCheck 실행 파일
- (선택) Node.js (UI 벤치/Playwright 실행 시)

### 1) UI 서버 실행

```powershell
python backend/server.py
```

브라우저 접속:
- `http://127.0.0.1:8765`

### 2) CLI 분석 실행

```powershell
python backend/main.py --selected-files GoldenTime.ctl
```

Note: `GoldenTime.ctl` is shown only as an example input filename.

추가 예시:

```powershell
python backend/main.py --selected-files GoldenTime.ctl --enable-ctrlppcheck
python backend/main.py --selected-files raw_input.txt --allow-raw-txt
python backend/main.py --selected-files GoldenTime.ctl --enable-live-ai
```

## API 개요

### 파일 조회
- `GET /api/files`
- raw `.txt` 포함 조회: `GET /api/files?allow_raw_txt=true`

### 분석 실행
- `POST /api/analyze`

주요 요청 필드:
- `selected_files`
- `allow_raw_txt`
- `enable_ctrlppcheck`
- `enable_live_ai`
- `ai_with_context`
- `defer_excel_reports`

주요 응답 필드:
- `summary`
- `violations` (`P1`, `P2`, `P3`)
- `output_dir`
- `metrics`
- `report_jobs`

### 파일 내용 조회
- `GET /api/file-content`
- `prefer_source=true` 지원 (source patch 적용 후 소스 우선 표시)

### AI 리뷰 반영 (`REVIEWED.txt`)
- `POST /api/ai-review/apply`

### Diff 승인형 Autofix (CTL only)
- `POST /api/autofix/prepare`
- `GET /api/autofix/file-diff`
- `POST /api/autofix/apply`
- `GET /api/autofix/stats`

#### `autofix/prepare` 예시

```json
{
  "file": "GoldenTime.ctl",
  "object": "GoldenTime.ctl",
  "event": "Global",
  "review": "요약: ...

코드:
```cpp
...
```",
  "session_id": "<output_dir from /api/analyze>",
  "generator_preference": "auto",
  "allow_fallback": true
}
```

Note: The sample uses `GoldenTime.ctl` only as an example target file, not as a quality gate baseline.

응답 확장 필드(하위호환):
- `generator_type` (`llm` | `rule`)
- `generator_reason`
- `quality_preview`
- `llm_meta` (LLM 경로일 때)

#### `autofix/apply` 예시

```json
{
  "proposal_id": "<proposal_id>",
  "session_id": "<output_dir from /api/analyze>",
  "file": "GoldenTime.ctl",
  "expected_base_hash": "<base_hash>",
  "apply_mode": "source_ctl",
  "block_on_regression": true,
  "check_ctrlpp_regression": false
}
```

응답 확장 필드(하위호환):
- 성공: `quality_metrics`, `validation`, `reanalysis_summary`
- 실패: `error_code`, `quality_metrics` (검증 결과가 있는 경우)

## 성능 기준선 / 품질 게이트

### UI 성능 벤치 (Playwright)

설치:

```powershell
npm i -D playwright
npx playwright install chromium
```

실행:

```powershell
node tools/playwright_ui_benchmark.js --iterations 5 --files 20 --violations-per-file 120 --code-lines 6000
```

임계치 체크 예시:

```powershell
node tools/playwright_ui_benchmark.js --max-analyze-ms 180 --max-table-scroll-ms 1050 --max-code-jump-ms 100 --max-code-scroll-ms 500
```

관련 파일:
- `docs/perf_baselines/ui_benchmark_baseline_20260225_1119.json`
- `docs/perf_baselines/ui_thresholds_20260225.json`

### HTTP baseline (`/api/analyze`)

```powershell
python backend/server.py
python tools/http_perf_baseline.py --dataset-name local_code_review_data --discover-count 1 --live-ai off --ctrlpp off,on --defer-excel off,on --iterations 2 --flush-excel
```

생성 예시:
- `docs/perf_baselines/http_perf_baseline_local_code_review_data_20260225_111410.json`

## CtrlppCheck 연동 / 운영 도구

### 메인 프로그램 연동
- 메인 프로그램은 `backend/core/ctrl_wrapper.py`를 통해 CtrlppCheck를 사용합니다.
- `Config/config.json`의 `ctrlppcheck` 섹션으로 동작을 제어합니다.

### 단독 점검/업데이트 도구
- `tools/README_CtrlppCheck.md` 참고
- 통합 스모크:

```powershell
python tools/run_ctrlpp_integration_smoke.py
```

## 설정 (`Config/config.json`)

주요 섹션:
- `ai`
  - provider/model/timeout/snippet window/batch groups
- `ctrlppcheck`
  - binary path/auto install/version/rule files
- `performance`
  - worker limits, deferred Excel default
- `autofix`
  - session TTL/LRU, proposal limit, regression policy
  - `prepare_generator_default`, `allow_fallback_default`

## 테스트 / 검증

핵심 회귀 테스트:

```powershell
python -m unittest backend.tests.test_api_and_reports
```

전체 핵심 테스트 묶음:

```powershell
python -m unittest backend.system_verification backend.tests.test_api_and_reports backend.tests.test_todo_rule_mining backend.tests.test_winccoa_context_server
```

문법/정적 확인 예시:

```powershell
python -m py_compile backend/main.py backend/server.py backend/core/analysis_pipeline.py
node --check frontend/renderer.js
```

## 문서

### 제품/설계 문서
- `docs/WinCC OA Code Inspector – Design Guide.md`
- `docs/WinCC OA Code Inspector – Information Architecture.md`
- `docs/WinCC OA Code Inspector – Product Requir.md`
- `docs/WinCC OA Code Inspector – Use-case.md`

### 운영/품질 문서
- `docs/performance.md`
- `docs/autofix_safety.md`
- `docs/encoding_policy.md`
- `docs/perf_baselines/README.md`

### 구현/진행 현황
- `todo.md`

## 인코딩 정책 (중요)

- 텍스트 소스/문서는 UTF-8 고정
- `.editorconfig` 기준 준수
- 인코딩 이상 발생 시 백업 후 부분 복구 + diff 검토

## 참고

- CtrlppCheck Releases: https://github.com/siemens/CtrlppCheck/releases
- (내부 운영) 자동수정 고도화 후속 계획은 `todo.md`의 `8) 후속 고도화 계획` 섹션 참고
