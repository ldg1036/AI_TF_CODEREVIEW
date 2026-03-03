# Autofix KPI Review

- generated_at: 2026-03-03T14:28:49
- scope: general(strict_hash), drift(benchmark_relaxed)

## General (strict_hash)
- baseline_failure_rate: 0.0
- improved_failure_rate: 0.0
- improvement_percent: 0.0
- error_code_counts: {"SEMANTIC_GUARD_BLOCKED": 3}

## Drift (benchmark_relaxed)
- baseline_failure_rate: 1.0
- improved_failure_rate: 1.0
- improvement_percent: 0.0
- kpi_observability_pass: True
- kpi_observability_reason: PASS
- kpi_10_percent_pass: False
- instruction_apply_rate: 0.0
- instruction_validation_fail_rate: 0.0
- instruction_fail_stage_distribution: {"none": 3}
- rollout_ready: False
- rollout_checks: {"instruction_apply_rate_ok": false, "instruction_validation_fail_rate_ok": true, "safety_gate_regression_ok": true}
- hash_gate_bypassed_count: 3
- benchmark_observe_mode_counts: {"benchmark_relaxed": 3}
- locator_mode_counts: {"anchor_exact": 3}
- validation_error_fragment_counts: {"ambiguous_candidates": 0, "low_confidence": 0, "drift_exceeded": 0, "engine_fallback": 0}
- error_code_counts: {"ANCHOR_MISMATCH": 3}
