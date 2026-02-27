# WinCC OA Code Analysis / Autofix Deep Review (2026-02-27 10:35)

## Scope
- Focus: code analysis + autofix reliability
- Environment: local server (`backend/server.py`) + HTTP benchmark harness
- Policy: fail-soft safety first, no API breaking changes

## Evidence
- Compile:
  - `python -m py_compile backend/main.py backend/server.py backend/core/analysis_pipeline.py backend/core/autofix_apply_engine.py backend/core/autofix_semantic_guard.py backend/core/autofix_tokenizer.py`
- Unit:
  - `backend.tests.test_autofix_token_fallback` (4/4)
  - `backend.tests.test_autofix_semantic_guard` (5/5)
  - `backend.tests.test_autofix_apply_engine` (8/8)
- Integration:
  - `backend.tests.test_api_and_reports.ApiIntegrationTests` (47 passed, 1 skipped)
- Perf/KPI artifacts:
  - `docs/perf_baselines/autofix_apply_improved_20260227_1035_general.json`
  - `docs/perf_baselines/autofix_apply_baseline_20260227_1035_general.json`
  - `docs/perf_baselines/autofix_apply_comparison_20260227_1035_general.json`
  - `docs/perf_baselines/autofix_apply_improved_20260227_1035_drift.json`
  - `docs/perf_baselines/autofix_apply_baseline_20260227_1035_drift.json`
  - `docs/perf_baselines/autofix_apply_comparison_20260227_1035_drift.json`

## Result Classification

### PASS
1. Core safety chain is stable:
   - hash guard
   - anchor exact/normalized
   - token fallback
   - apply engine fail-soft
   - semantic guard
   - regression checks
2. Multi-hunk P1 policy behaves as designed (same-block only, blocking overlap/cross-block).
3. API behavior is backward compatible for `/api/analyze`, `/api/autofix/*`.

### BLOCKED
1. Anchor-mismatch KPI observability remains blocked in real API flow:
   - if source drifts after prepare, apply is blocked by `BASE_HASH_MISMATCH` before anchor/token fallback stage.
   - drift stress run therefore does not produce anchor mismatch events for KPI.

### HOLD
1. KPI gate (`improvement_percent >= 10`) remains HOLD:
   - general run: `improvement_percent = 0.0` (no anchor mismatch events)
   - drift run: hash-gate pre-block prevents fallback-path KPI measurement
2. T3 structured-instruction implementation remains pending (design now decision-complete).

## Quantified Risk Summary
- Semantic guard blocked cases are actively filtered in benchmark target selection.
- General run selected applicable proposals and completed with `anchor_exact` locator mode.
- No ambiguity (`ambiguous_candidates`) or drift/low-confidence fallback errors were observed in selected targets.

## Priority Recommendations

### P1 (Immediate)
1. Add benchmark harness mode that can evaluate fallback path after hash gate (controlled test-only mode).
2. Keep TODO KPI item as partial until measurable anchor mismatch events are observed in compatible conditions.

### P2 (Next)
1. Implement T3 schema v1 + feature-flagged runtime integration.
2. Add instruction-path counters to `/api/autofix/stats`.

### P3 (Later)
1. Expand structured instruction coverage for compare mode and multi-hunk composition.

## File Mapping (for immediate follow-up)
- Benchmark harness: `tools/perf/autofix_apply_baseline.py`
- Perf policy docs: `docs/performance.md`
- T3 breakdown: `docs/autofix_engine_roadmap.md`
- Tracking state: `todo.md`
