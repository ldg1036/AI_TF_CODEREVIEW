# Performance Baselines and Quality Gates

Last Updated: 2026-03-08

## Goal

Performance checks in this project now separate three questions:

- Is the frontend still responsive?
- Is the end-to-end analyze path still acceptable?
- Did heuristic scan changes actually improve scan cost without changing findings?

## Available Performance Tools

- UI benchmark: `node tools/playwright_ui_benchmark.js`
- Real UI smoke: `node tools/playwright_ui_real_smoke.js`
- HTTP analyze baseline: `python tools/http_perf_baseline.py`
- Heuristic same-build baseline: `python tools/http_perf_baseline.py --focus heuristic`

## Dashboard Observability

The default operator dashboard now focuses on two cards:

- operations compare
  - recent benchmark / smoke runs
- rules / dependency health
  - P1 enabled / total
  - detector distribution
  - `openpyxl`, `CtrlppCheck`, `Playwright` availability
  - rule management panel with P1 CRUD and import / export actions

P3 comparison is no longer presented as a dashboard run-to-run card. It is handled from issue detail as `P1/P2 <> P3` compare in the right-side panel.

`operations compare` is read-only. `rules / dependency health` includes limited operational editing for P1 rule configuration.

## Backend Timing Signals

Primary runtime metrics still come from `POST /api/analyze`.

Important fields:

- `metrics.timings_ms.total`
- `metrics.timings_ms.collect`
- `metrics.timings_ms.analyze`
- `metrics.timings_ms.heuristic`
- `metrics.timings_ms.report`
- `metrics.timings_ms.excel`

Interpretation rule:

- Use `total` for release-facing end-to-end behavior
- Use `analyze` and `heuristic` for scan-path changes
- Do not judge heuristic improvements only by `total` when report / Excel cost is significant

## Heuristic Same-Build Baseline

The heuristic-focused mode exists to avoid misleading comparisons against older historical HTTP baselines.

Run:

```powershell
python backend/server.py
```

In another terminal:

```powershell
python tools/http_perf_baseline.py `
  --focus heuristic `
  --selected-files GoldenTime.ctl `
  --iterations 3
```

Output is written to `docs/perf_baselines/`.

Current example:

- `docs/perf_baselines/http_perf_baseline_local-sample_20260308_123340.json`

Expected JSON fields:

- `dataset_name`
- `selected_files`
- `comparison_basis`
- `metrics_focus`
- `violation_signature`
- `same_build_ab`
  - `without_context_avg_ms`
  - `with_context_avg_ms`
  - `delta_ms`
  - `improvement_percent`
  - `same_findings`
- `notes`

Interpretation:

- `same_findings` must stay `true`
- `with_context_avg_ms` should be less than or equal to `without_context_avg_ms`
- Use this result for heuristic-only optimization review
- Do not compare this directly with 2026-02-25 historical HTTP baselines

## End-to-End HTTP Baseline

For release-sensitive backend changes, use the regular HTTP matrix.

Run:

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

Use this to judge:

- full request latency
- report / Excel cost
- optional dependency overhead

## Regression Rules

Recommended rules:

- UI benchmark: treat `p95` drift over `20%` as suspicious
- HTTP analyze baseline: treat `total`, `analyze`, or `report` drift over `20%` as suspicious unless explained
- Heuristic same-build baseline:
  - `same_findings=true`
  - `with_context_avg_ms <= without_context_avg_ms`

## Noise Handling

- Run at least `3` iterations
- Compare on the same machine profile
- Keep `live_ai`, `ctrlpp`, `defer_excel_reports`, and selected file set identical
- If one run spikes once, rerun before calling it a regression

## Storage Convention

Store performance artifacts in:

- `docs/perf_baselines/`
- `tools/benchmark_results/`
- `tools/integration_results/`

Suggested interpretation order:

1. UI benchmark
2. UI real smoke
3. HTTP baseline
4. heuristic same-build baseline
