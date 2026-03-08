# Release Gate Checklist

Last Updated: 2026-03-08

## Goal

Use this checklist before treating a WinCC OA code review build as release-ready.

## 1. Core Regression Gate

Run these first:

```powershell
python -m unittest discover backend/tests -v
python backend/tools/run_verification_profile.py --profile core --include-report
python backend/tools/check_config_rule_alignment.py --json
python backend/tools/analyze_template_coverage.py
python -W error::DeprecationWarning -m unittest backend.tests.test_api_and_reports backend.tests.test_winccoa_context_server
node --check frontend/renderer.js
```

Pass criteria:

- backend tests pass except documented optional skips
- config / rule alignment mismatch is `0`
- template coverage is `Client 15/15`, `Server 20/20`
- frontend syntax passes

## 2. Optional Dependency Gate

### Ctrlpp

```powershell
python tools/run_ctrlpp_integration_smoke.py --allow-missing-binary --skip-unittest
```

When production actually requires Ctrlpp:

```powershell
python tools/run_ctrlpp_integration_smoke.py
```

### Live AI

Representative run:

```powershell
python backend/main.py --selected-files BenchmarkP1Fixture.ctl --enable-live-ai --ai-with-context
```

Pass criteria:

- analyze completes
- fail-soft behavior is preserved when optional AI infrastructure is unavailable

## 3. Frontend Gate

### UI benchmark

```powershell
node tools/playwright_ui_benchmark.js --iterations 3
```

### Real UI smoke

```powershell
node tools/playwright_ui_real_smoke.js --target-file BenchmarkP1Fixture.ctl
```

Pass criteria:

- analyze button is clickable
- async analyze flow completes
- workspace becomes visible
- result rows render
- operations compare and rules / dependency health cards do not block workspace activation
- issue detail `AI 제안` tab and `P1/P2 <> P3` compare flow do not block workspace activation

## 4. Performance-Sensitive Gate

Use this when heuristic, report, or pipeline timing changed.

### End-to-end HTTP baseline

```powershell
python backend/server.py
```

In another terminal:

```powershell
python tools/http_perf_baseline.py `
  --dataset-name local-sample `
  --discover-count 1 `
  --ctrlpp off,on `
  --live-ai off `
  --defer-excel off,on `
  --iterations 3 `
  --flush-excel
```

### Heuristic same-build baseline

```powershell
python tools/http_perf_baseline.py `
  --focus heuristic `
  --selected-files GoldenTime.ctl `
  --iterations 3
```

Pass criteria:

- representative violation set is unchanged
- `same_findings=true`
- `with_context_avg_ms <= without_context_avg_ms`

## 5. Operator Visibility Gate

Verify these operator-facing APIs are healthy:

- `GET /api/health/deps`
- `GET /api/operations/latest`
- `GET /api/rules/health`
- `GET /api/rules/list`
- `GET /api/rules/export`
- `POST /api/rules/create`
- `POST /api/rules/replace`
- `POST /api/rules/delete`
- `POST /api/rules/import`

Minimum expectations:

- dependency state is accurate
- recent benchmark / smoke compare payload is readable
- rules / dependency health shows enabled rule counts and detector distribution
- rule management endpoints can load, persist, and reload P1 rule changes safely
- issue detail P3 compare flow is usable after analysis completes

## 6. Artifacts To Keep

Keep the latest:

- `CodeReview_Report/verification_summary_*.json`
- `CodeReview_Report/template_coverage_*.json`
- `CodeReview_Report/*/analysis_summary.json`
- `tools/integration_results/ctrlpp_integration_*.json`
- `tools/integration_results/ui_real_smoke_*.json`
- `tools/benchmark_results/ui_benchmark_*.json`
- `docs/perf_baselines/http_perf_baseline_*.json`

## 7. Operator Notes

- `CtrlppCheck`, `Ollama`, and `Playwright` remain optional dependencies unless the release scope explicitly requires them.
- For heuristic changes, prefer same-build baseline review over direct comparison with old historical HTTP baseline JSON.
- Rules / dependency health now supports full P1 rule CRUD and import / export workflow.
- P3 comparison is part of issue-detail workflow, not a dashboard run-to-run compare flow.
- Detector-specific rich editing UI is still a follow-up enhancement, not a release blocker.
