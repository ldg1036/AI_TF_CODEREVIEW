﻿# WinCC OA Code Inspector

> Structure note (2026-02-27)
> - Canonical project paths are root directories: `Config`, `CodeReview_Data`, `docs`.
> - `workspace/` is a runtime/support area (for example `workspace/runtime/CodeReview_Report`).
> - Legacy tool commands under `tools/*.py` / `tools/*.js` are still supported via compatibility wrappers.
> - Official review quality baseline is `P1 (rules) + P2 (CtrlppCheck) + P3 (AI)` plus regression tests.

Last validated: 2026-02-27

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
- Annotated TXT (`*_REVIEWED.txt`)

또한 diff 승인형 source autofix를 지원하며, P3(LLM) 경로는 텍스트 입력(`*_pnl.txt`, `*_xml.txt`, raw `.txt`)에도 적용 가능합니다.

## 주요 기능

### 1) 코드 분석 (P1 / P2 / P3)
- `P1`: 정적 규칙 기반 분석
- `P2`: `CtrlppCheck` 연동 결과
  - `enable_ctrlppcheck=true` + `.ctl` 대상 분석 시작 시 CtrlppCheck preflight(자동 다운로드/설치) 1회 수행
  - preflight 실패 시 fail-soft로 P2 경고만 기록하고 P1/P3 분석은 계속 진행
- `P3`: AI(LLM) 리뷰 (선택/Fail-soft)

### 2) 성능/운영 최적화
- `/api/analyze` `metrics` 응답 제공
- async analyze progress API: `POST /api/analyze/start`, `GET /api/analyze/status?job_id=...`
- 파일 단위 bounded parallel 분석
- `.pnl/.xml -> *_txt` 변환 캐시 (`mtime + size`)
- Excel 기본 동기 생성 + 선택적 지연 생성(`defer_excel_reports`) + flush API
- 결과 테이블 virtualization
- 프론트 헤더에서 분석 진행률/ETA/경과시간 표시 (polling 기반)

### 3) Autofix
- `autofix/prepare` -> `file-diff` 확인 -> `autofix/apply`
- `llm` / `rule` / `auto(rule-first, llm-fallback)` generator
- `rule` 경로는 `.ctl` 중심, `P3(llm)` 경로는 텍스트 입력까지 지원
- hash / anchor / syntax / heuristic / optional Ctrlpp regression 검증
- multi-hunk P1 안전정책: same-block, 최대 3개, overlap/cross-block fail-soft 차단
- 백업 파일 + 감사 로그 + 사용자 승인 흐름

API note:
- `GET /api/autofix/stats` includes `multi_hunk_attempt_count`, `multi_hunk_success_count`, `multi_hunk_blocked_count`
- `POST /api/autofix/apply` may return fail-soft `error_code="APPLY_ENGINE_FAILED"` for unsafe multi-hunk scenarios

### 4) 벤치/스모크 도구
- UI benchmark: `tools/playwright_ui_benchmark.js`
- HTTP baseline: `tools/http_perf_baseline.py`
- Ctrlpp smoke: `tools/run_ctrlpp_integration_smoke.py`

## Release Verification (P1/P2/P3)

Required:
1. `python -m unittest backend.tests.test_api_and_reports -v`
2. `python -m unittest backend.tests.test_todo_rule_mining -v`
3. `python -m unittest backend.tests.test_winccoa_context_server -v`
4. `python -m py_compile backend/main.py backend/server.py backend/core/analysis_pipeline.py`

Optional (change-dependent):
1. Ctrlpp integration: `python tools/run_ctrlpp_integration_smoke.py --allow-missing-binary --skip-unittest`
2. Frontend/perf: `node --check frontend/renderer.js`, `node tools/playwright_ui_benchmark.js --help`
3. Rules/config: `python backend/tools/check_config_rule_alignment.py --json`, `python backend/tools/analyze_template_coverage.py`

## Quick Start

### UI 서버 실행
```powershell
python backend/server.py
```
접속: `http://127.0.0.1:8765`

프론트 분석 동작:
- 기본 분석 버튼은 `/api/analyze/start` + `/api/analyze/status` 폴링으로 진행률/ETA를 표시합니다.
- 완료 시 최종 결과 payload(`summary`, `violations`, `output_dir`, `metrics`, `report_jobs`)를 기존과 동일하게 렌더링합니다.

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
