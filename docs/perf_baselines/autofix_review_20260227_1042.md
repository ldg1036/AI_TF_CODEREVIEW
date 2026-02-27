# WinCC OA Code Analysis / Autofix Deep Review (2026-02-27 10:42)

## Scope
- Focus: code analysis + autofix KPI observability
- Policy: production hash gate unchanged, benchmark tooling only
- Execution modes:
  - `strict_hash` (general)
  - `benchmark_relaxed` + `line_drift` (drift stress)

## Artifacts
- General:
  - `docs/perf_baselines/autofix_apply_improved_20260227_1042_general.json`
  - `docs/perf_baselines/autofix_apply_baseline_20260227_1042_general.json`
  - `docs/perf_baselines/autofix_apply_comparison_20260227_1042_general.json`
- Drift:
  - `docs/perf_baselines/autofix_apply_improved_20260227_1042_drift.json`
  - `docs/perf_baselines/autofix_apply_baseline_20260227_1042_drift.json`
  - `docs/perf_baselines/autofix_apply_comparison_20260227_1042_drift.json`

## Result Classification

### PASS
1. Benchmark CLI now supports explicit KPI observe mode:
   - `--kpi-observe-mode strict_hash|benchmark_relaxed`
2. JSON metadata includes benchmark safety marker in relaxed mode:
   - `_meta.benchmark_mode_warning=true`
   - `_meta.not_for_production=true`
3. General strict run remains stable:
   - apply attempts: 3
   - apply success: 3
   - locator mode: `anchor_exact` only

### BLOCKED
1. Drift KPI observability is still blocked:
   - drift run with `benchmark_relaxed` still returns `BASE_HASH_MISMATCH` (3/3)
   - reason: server-side `proposal_base_hash` validation runs before fallback stage

### HOLD
1. KPI gate remains HOLD:
   - `improvement_percent = 0.0` in both general and drift comparisons
2. TODO item state should remain partial until fallback path is measurable in drift conditions.

## Quantified Snapshot
- General strict:
  - `error_code_counts = {}`
  - `locator_mode_counts = {"anchor_exact": 3}`
- Drift relaxed:
  - `error_code_counts = {"BASE_HASH_MISMATCH": 3}`
  - `locator_mode_counts = {}`

## Next Actions
- P1:
  - add benchmark-only internal hook to bypass/shift server hash gate for KPI observation runs
- P2:
  - once observability hook exists, rerun drift baseline/improved and evaluate `improvement_percent >= 10`

