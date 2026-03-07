# Autofix KPI Drift Tuning Sweep

- generated_at: 2026-03-03T14:35:54
- row_count: 27
- best_candidate:
  - min_confidence: 0.55
  - min_gap: 0.05
  - max_line_drift: 300
  - kpi_observability_pass: True
  - kpi_observability_reason: PASS
  - improvement_percent: 0.0
  - kpi_10_percent_pass: False

## Sweep Rows
- c=0.55 g=0.05 d=300: obs=True/PASS, improve=0.0%
- c=0.55 g=0.05 d=600: obs=True/PASS, improve=0.0%
- c=0.55 g=0.05 d=900: obs=True/PASS, improve=0.0%
- c=0.55 g=0.1 d=300: obs=True/PASS, improve=0.0%
- c=0.55 g=0.1 d=600: obs=True/PASS, improve=0.0%
- c=0.55 g=0.1 d=900: obs=True/PASS, improve=0.0%
- c=0.55 g=0.15 d=300: obs=True/PASS, improve=0.0%
- c=0.55 g=0.15 d=600: obs=True/PASS, improve=0.0%
- c=0.55 g=0.15 d=900: obs=True/PASS, improve=0.0%
- c=0.65 g=0.05 d=300: obs=True/PASS, improve=0.0%
- c=0.65 g=0.05 d=600: obs=True/PASS, improve=0.0%
- c=0.65 g=0.05 d=900: obs=True/PASS, improve=0.0%
- c=0.65 g=0.1 d=300: obs=True/PASS, improve=0.0%
- c=0.65 g=0.1 d=600: obs=True/PASS, improve=0.0%
- c=0.65 g=0.1 d=900: obs=True/PASS, improve=0.0%
- c=0.65 g=0.15 d=300: obs=True/PASS, improve=0.0%
- c=0.65 g=0.15 d=600: obs=True/PASS, improve=0.0%
- c=0.65 g=0.15 d=900: obs=True/PASS, improve=0.0%
- c=0.8 g=0.05 d=300: obs=True/PASS, improve=0.0%
- c=0.8 g=0.05 d=600: obs=True/PASS, improve=0.0%
- c=0.8 g=0.05 d=900: obs=True/PASS, improve=0.0%
- c=0.8 g=0.1 d=300: obs=True/PASS, improve=0.0%
- c=0.8 g=0.1 d=600: obs=True/PASS, improve=0.0%
- c=0.8 g=0.1 d=900: obs=True/PASS, improve=0.0%
- c=0.8 g=0.15 d=300: obs=True/PASS, improve=0.0%
- c=0.8 g=0.15 d=600: obs=True/PASS, improve=0.0%
- c=0.8 g=0.15 d=900: obs=True/PASS, improve=0.0%

## Root Cause Aggregate
- aggregate_reason_counts: {"BLOCKED_ANCHOR_MISMATCH_ONLY": 27}
- aggregate_fragment_counts: {"ambiguous_candidates": 0, "low_confidence": 0, "drift_exceeded": 0}
