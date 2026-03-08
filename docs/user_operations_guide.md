# User Operations Guide

Last Updated: 2026-03-08

## Goal

This guide is for operators who need to run the WinCC OA code review program reliably without reading developer-only documentation.

## 1. Before You Start

Required:

- Windows environment
- Python installed and available in `PATH`
- project files present in `CodeReview_Data`

Recommended:

- `pip install -r requirements-dev.txt`
- `npm install`
- `npx playwright install chromium`

Optional tools:

- `CtrlppCheck`
- `Ollama`
- Playwright browser runtime

Missing optional tools should fail soft in normal operation.

## 2. Main Run Modes

### UI mode

Start the server:

```powershell
python backend/server.py
```

Open:

```text
http://127.0.0.1:8765
```

Use the dashboard cards for quick status checks:

- operations compare
- rules / dependency health

Use issue detail for code-level review actions:

- `AI 제안` tab
- `P1/P2 <> P3` compare popup
- on-demand AI review and patch-oriented follow-up

### CLI mode

```powershell
python backend/main.py --selected-files GoldenTime.ctl
```

Use this when you want a targeted analysis without the UI.

## 3. Release Gate Shortcuts

Standard local gate:

```powershell
.\run_release_gate.bat
```

Live AI scope:

```powershell
.\run_release_gate.bat live-ai
```

CI-style lightweight gate:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_release_gate.ps1 -Mode ci
```

## 4. What The Dashboard Cards Mean

### Operations compare

Shows the latest benchmark / smoke results for:

- UI benchmark
- UI real smoke
- Ctrlpp integration smoke

### Rules / dependency health

Shows:

- enabled P1 rules versus total P1 rules
- detector distribution
- `openpyxl`, `CtrlppCheck`, `Playwright` availability

This card now supports a limited management flow:

- open the rule list
- create a new P1 rule
- edit an existing P1 rule
- toggle `enabled`
- delete a rule
- export rules to JSON
- import rules from JSON with merge or replace mode
- save the change and reload the checker configuration

Current editing model:

- detector and `meta` values are edited as JSON
- validation runs on save before configuration is reloaded

Still not included:

- detector-type-specific visual form editor
- import dry-run preview before apply
- bulk multi-select editing

### Issue detail compare

P3 compare is handled from issue detail, not from a dashboard run-to-run card.

Use this when you need to compare:

- selected `P1` or `P2` issue context
- generated `P3` review or mock review
- optional patch diff after prepare/apply

## 5. Checklist Automation In Reports

Excel checklist results are now interpreted with a conservative automation policy.

Meaning of the main result columns:

- `F (1차 검증)`: `OK`, `NG`, `N/A`
- `G (검증 결과)`: automatic guidance or reason text
- `H (비고)`: template remark column, kept empty or preserved from template

Checklist automation levels:

- `완전 자동`
  - `Loop문 내에 처리 조건`
  - rule applies only when a `while` pattern exists
  - `while` 없음: `N/A`
  - `while` 있음 + 위반 검출: `NG`
  - `while` 있음 + 위반 없음: `OK`
- `부분 자동`
  - `메모리 누수 체크`
  - `하드코딩 지양`
  - `디버깅용 로그 작성 확인`
  - violation detected: `NG`
  - no violation detected: `N/A` with partial-automation guidance
- `수동 확인`
  - `쿼리 주석 처리`
  - stays `N/A` because required comment quality (`기능명_날짜_HWC`) is not trusted by regex-only checks

Interpretation rule:

- `NG` means a mapped rule violation was found
- `OK` is used only for full-automation items
- `N/A` means either the item is not applicable or it still requires operator review
## 6. Performance Checks

### End-to-end benchmark

Start the server and run:

```powershell
python tools/http_perf_baseline.py --dataset-name local-sample --iterations 3
```

### Heuristic-only baseline

Use this when scan-path performance changed:

```powershell
python tools/http_perf_baseline.py `
  --focus heuristic `
  --selected-files GoldenTime.ctl `
  --iterations 3
```

Interpretation:

- `same_findings=true` must hold
- `with_context_avg_ms` should be less than or equal to `without_context_avg_ms`

## 7. Common Trouble Cases

### UI does not open

Check:

- `python backend/server.py` is running
- port `8765` is free

### Rules / dependency card shows degraded

Typical causes:

- `openpyxl` not installed
- Playwright browser not installed
- Ctrlpp binary unavailable

This does not automatically block static analysis. It means optional capabilities are reduced.

### Heuristic baseline fails immediately

Check:

- backend server is running before executing `tools/http_perf_baseline.py`
- selected file exists in the dataset

### UI benchmark fails

Check:

- Playwright package is installed
- Chromium browser is installed
- the machine is not under unusual load

## 8. Remaining Scope Notes

Current operator UI scope supports full P1 rule CRUD and import / export management.

Not included yet:

- detector-specific rich form editing
