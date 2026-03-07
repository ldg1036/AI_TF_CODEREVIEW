# Release Gate Checklist

Last Updated: 2026-03-06

## Goal

Use this checklist before treating a WinCC OA code review build as release-ready.

One-shot runner:

```powershell
python tools/release_gate.py
```

Windows wrappers:

```powershell
.\run_release_gate.bat
.\run_release_gate.bat live-ai
powershell -ExecutionPolicy Bypass -File .\run_release_gate.ps1 -Mode ci
```

Optional live AI gate:

```powershell
python tools/release_gate.py --with-live-ai --live-ai-with-context
```

CI-oriented lightweight profile:

```powershell
python tools/release_gate.py --profile ci
```

The gate is intentionally split into three layers:
- core regression checks
- optional dependency validation
- operator-facing smoke checks

## 1. Core Regression Gate

Run these first on every release candidate.

```powershell
python -m unittest discover backend/tests -v
python backend/tools/run_verification_profile.py --profile core --include-report
python backend/tools/check_config_rule_alignment.py --json
python backend/tools/analyze_template_coverage.py
python -W error::DeprecationWarning -m unittest backend.tests.test_api_and_reports backend.tests.test_winccoa_context_server
node --check frontend/renderer.js
```

Pass criteria:
- backend tests pass, except documented optional skips
- verification profile reports `6/6` passed
- config/rule alignment mismatch count is `0`
- template coverage reports `Client 15/15`, `Server 20/20`
- no `DeprecationWarning` escapes the targeted warning gate

## 2. Optional Dependency Gate

Run these when release scope touches integration behavior.

### Ctrlpp

Fail-soft availability check:

```powershell
python tools/run_ctrlpp_integration_smoke.py --allow-missing-binary --skip-unittest
```

Real binary smoke when Ctrlpp is expected to work in production:

```powershell
python tools/run_ctrlpp_integration_smoke.py
```

Pass criteria:
- missing binary path produces clean fail-soft `binary_not_found`
- installed binary path completes direct smoke and unittest harness

### Live AI + MCP context

Start context server if needed:

```powershell
python backend/tools/winccoa_context_server.py --host 127.0.0.1 --port 3000
```

Representative live run:

```powershell
python backend/main.py --selected-files BenchmarkP1Fixture.ctl --enable-live-ai --ai-with-context
```

Pass criteria:
- analyze completes without crashing
- result summary and report output are generated
- context failure degrades gracefully instead of aborting P1/P2
- release gate default expectation is `successful_file_count >= 1`, `p1_total >= 1`, `p3_total >= 1`

## 3. Frontend Release Gate

### UI benchmark

Run the mocked UI benchmark with built-in p95 thresholds:

```powershell
node tools/playwright_ui_benchmark.js --iterations 3
```

Default thresholds applied unless `--no-default-thresholds` is provided:
- `analyzeUiMs.p95 <= 300`
- `resultTableScrollMs.p95 <= 1050`
- `codeJumpMs.p95 <= 100`
- `codeViewerScrollMs.p95 <= 500`

### Real-server UI smoke

Run the Playwright smoke against a real backend:

```powershell
node tools/playwright_ui_real_smoke.js --target-file BenchmarkP1Fixture.ctl
```

Pass criteria:
- `#btn-analyze` is pointer-clickable, not covered by another panel
- analysis completes through the real `/api/analyze/start` + `/api/analyze/status` flow
- workspace becomes visible and at least one result row is rendered

## 4. Output Artifacts To Keep

Keep or attach these when closing the release gate:
- latest `CodeReview_Report/verification_summary_*.json`
- latest `CodeReview_Report/template_coverage_*.json`
- latest `CodeReview_Report/release_gate_*.md`
- latest `tools/integration_results/ctrlpp_integration_*.json` when Ctrlpp was checked
- latest `tools/benchmark_results/ui_benchmark_*.json`
- latest `tools/integration_results/ui_real_smoke_*.json`
- latest `tools/integration_results/live_ai_release_gate_*.json` when live AI was checked

## 5. Operator Notes

- `CtrlppCheck`, `Ollama`, and `Playwright` remain optional dependencies. Missing optional tools should fail soft unless the release specifically requires them.
- Use the same machine profile when comparing benchmark numbers. Treat large `p95` drift as suspicious even if the hard gate still passes.
- If the real UI smoke fails but the mocked benchmark passes, treat it as a layout or integration regression, not a benchmark issue.
