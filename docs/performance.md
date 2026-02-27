# Performance Baselines and Quality Gates

Last Updated: 2026-02-25 (current implementation baseline reflected)

Structure note (2026-02-26):
- Benchmark scripts are now organized by feature under `tools/perf/` (actual implementation path).
- Existing commands documented here (`tools/playwright_ui_benchmark.js`, `tools/http_perf_baseline.py`) still work via compatibility wrappers.
- Benchmark outputs remain in legacy result paths (`tools/benchmark_results/`, `docs/perf_baselines/`) for backward compatibility.

This project now exposes runtime metrics on `POST /api/analyze` and includes two benchmark drivers:

- UI rendering benchmark (Playwright): `tools/playwright_ui_benchmark.js`
- Backend HTTP/matrix benchmark (server metrics): `tools/http_perf_baseline.py`
- Autofix apply baseline/improved comparison: `tools/perf/autofix_apply_baseline.py`

The goal is to make "performance is acceptable" a measurable statement instead of a subjective impression.

## Autofix Apply Safety Baseline (P1 Multi-hunk)

Current P1 safety policy for multi-hunk apply:
- same block only (`brace` parser-lite boundary)
- max 3 hunks per apply
- fail-soft blocking on ambiguous/high-risk cases:
  - `too_many_hunks`
  - `overlapping_hunks`
  - `hunks_span_multiple_blocks`
  - `anchor_context_not_unique`

Related stats from `GET /api/autofix/stats`:
- `multi_hunk_attempt_count`
- `multi_hunk_success_count`
- `multi_hunk_blocked_count`

## 1. What To Measure

### UI (frontend responsiveness)
- `analyzeUiMs`
- `resultTableScrollMs`
- `codeJumpMs`
- `codeViewerScrollMs`

These come from `tools/playwright_ui_benchmark.js` using mocked API responses so backend variability does not hide rendering regressions.

### Backend (`/api/analyze`)
- `metrics.timings_ms.*` (especially `collect`, `convert`, `analyze`, `report`, `ai`, `ctrlpp`, `server_total`)
- `metrics.llm_calls`
- `metrics.ctrlpp_calls`
- `metrics.convert_cache.{hits,misses}`
- `report_jobs.excel.pending_count` (when `defer_excel_reports=true`)

These come from the real backend and reflect actual file I/O, reporting, LLM, and Ctrlpp behavior.

### Analyze progress/ETA (UI polling)
- `POST /api/analyze/start` returns `202` with `job_id` and initial progress.
- `GET /api/analyze/status?job_id=...` returns `status`, `progress`, `timing` (`elapsed_ms`, `eta_ms`), and final `result` on completion.
- Frontend header panel uses this status API to render `percent`, `completed/total files`, `ETA`, and `elapsed`.

## 2. Recommended Baseline Process

### A. UI baseline (Playwright)
Prerequisites:

```powershell
npm i -D playwright
npx playwright install chromium
```

Run baseline:

```powershell
node tools/playwright_ui_benchmark.js `
  --iterations 5 `
  --files 20 `
  --violations-per-file 120 `
  --code-lines 6000 `
  --output tools/benchmark_results/ui_benchmark_baseline_20260225.json
```

Recommended initial thresholds (before real baseline tuning):
- `analyzeUiMs.p95 <= 1500`
- `resultTableScrollMs.p95 <= 1200`
- `codeJumpMs.p95 <= 800`
- `codeViewerScrollMs.p95 <= 800`

Current tuned thresholds (based on local real baseline):
- See `docs/perf_baselines/ui_thresholds_20260225.json`
- Current p95 limits:
  - `analyzeUiMs <= 180`
  - `resultTableScrollMs <= 1050`
  - `codeJumpMs <= 100`
  - `codeViewerScrollMs <= 500`

Threshold check example:

```powershell
node tools/playwright_ui_benchmark.js `
  --iterations 5 `
  --files 20 `
  --violations-per-file 120 `
  --code-lines 6000 `
  --max-analyze-ms 1500 `
  --max-table-scroll-ms 1200 `
  --max-code-jump-ms 800 `
  --max-code-scroll-ms 800
```

### B. Backend baseline (`/api/analyze`)
Start server:

```powershell
python backend/server.py
```

In another terminal, run the HTTP matrix baseline:

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

Output is written to `docs/perf_baselines/` by default.

Example generated backend baseline (local sample):
- `docs/perf_baselines/http_perf_baseline_local_code_review_data_20260225_111410.json`

## 3. Regression Decision Rules (Recommended)

Use the same machine/profile when comparing results.

- Compare against a saved baseline using the same benchmark parameters.
- Prefer `p95` over single-run values.
- Treat these as regressions unless there is an explained change:
  - UI: `p95` increases by more than `20%`
  - Backend: `server_total` or stage timings increase by more than `20%`
  - LLM/Ctrlpp: unexpected call count increases
- Deferred Excel: pending jobs not draining after flush

### Autofix anchor mismatch improvement rule
- Collect one `baseline` JSON and one `improved` JSON using the same file set and iteration count.
- Compare `kpi_anchor_failure_rate` via comparison JSON:
  - `baseline_failure_rate`
  - `improved_failure_rate`
  - `improvement_percent`
- Recommended gate:
  - Pass: `improvement_percent >= 10`
  - Hold (`[-]` in TODO): `< 10` or sample has no anchor-mismatch events

## 4. Noise / Variance Handling

Performance measurements on developer PCs are noisy. Use these rules:

- Run at least `3` iterations (prefer `5`)
- Close heavy background processes during UI benchmarks
- Compare with same `Ctrlpp`/`Live AI`/`defer_excel_reports` settings
- For LLM-enabled runs, note provider status (local model warm/cold start changes results)
- If a spike occurs once, rerun before declaring regression

## 5. Baseline Storage Convention

Store outputs in `docs/perf_baselines/`.

Suggested naming:
- `http_perf_baseline_<dataset>_<YYYYMMDD_HHMMSS>.json`
- `ui_benchmark_baseline_<YYYYMMDD_HHMMSS>.json`
- `ui_thresholds_<YYYYMMDD>.json`

Keep a short note beside each baseline:
- machine / CPU / RAM
- Python version
- Node version
- Ctrlpp version
- LLM provider/model (if enabled)

## 6. Current Baseline Snapshot (2026-02-25)

UI Playwright baseline (`tools/benchmark_results/ui_benchmark_baseline_20260225_1119.json`)
- `analyzeUiMs p95 = 93`
- `resultTableScrollMs p95 = 831`
- `codeJumpMs p95 = 48`
- `codeViewerScrollMs p95 = 364`

Threshold check validation run
- `analyzeUiMs p95 = 114` (<= 180)
- `resultTableScrollMs p95 = 831` (<= 1050)
- `codeJumpMs p95 = 62` (<= 100)
- `codeViewerScrollMs p95 = 364` (<= 500)

## 7. Autofix Apply Baseline Workflow (2026-02-27)

Start server:

```powershell
python backend/server.py
```

Collect improved run:

```powershell
python tools/perf/autofix_apply_baseline.py `
  --mode improved `
  --discover-count 1 `
  --iterations 3 `
  --perturb-anchor-mode none `
  --kpi-observe-mode strict_hash `
  --output docs/perf_baselines/autofix_apply_improved_20260227_0938.json
```

Collect baseline run + comparison:

```powershell
python tools/perf/autofix_apply_baseline.py `
  --mode baseline `
  --discover-count 1 `
  --iterations 3 `
  --perturb-anchor-mode none `
  --kpi-observe-mode strict_hash `
  --output docs/perf_baselines/autofix_apply_baseline_20260227_0938.json `
  --compare-with docs/perf_baselines/autofix_apply_improved_20260227_0938.json `
  --output-compare docs/perf_baselines/autofix_apply_comparison_20260227_0938.json
```

### Matrix auto-run (general + drift, benchmark-only tuning)

Use one command to run `general/drift x baseline/improved` and produce comparison JSON + review markdown:

```powershell
python tools/perf/autofix_apply_baseline.py `
  --auto-run-matrix `
  --scenario both `
  --discover-count 1 `
  --iterations 3 `
  --tune-min-confidence 0.55 `
  --tune-min-gap 0.05 `
  --tune-max-line-drift 900 `
  --output docs/perf_baselines `
  --review-output docs/perf_baselines/autofix_review_latest.md
```

Notes:
- Tuning headers are sent only in `benchmark_relaxed` runs.
- Runtime behavior is unchanged unless server process has `AUTOFIX_BENCHMARK_OBSERVE=1`.
- Response validation includes:
  - `token_min_confidence_used`
  - `token_min_gap_used`
  - `token_max_line_drift_used`
  - `benchmark_tuning_applied`
- Frontend `Autofix Validation` panel now surfaces benchmark/tuning metadata
  (`benchmark_observe_mode`, `hash_gate_bypassed`, `benchmark_tuning_applied`, `token_*_used`) without API schema changes.

Anchor drift stress run (line shift perturbation):

```powershell
python tools/perf/autofix_apply_baseline.py `
  --mode improved `
  --discover-count 1 `
  --iterations 3 `
  --perturb-anchor-mode line_drift `
  --kpi-observe-mode benchmark_relaxed `
  --output docs/perf_baselines/autofix_apply_improved_<timestamp>_drift.json
```

Perturbation modes:
- `none`: no source perturbation
- `whitespace`: trailing whitespace injection before apply
- `line_drift`: blank line insertion before resolved anchor line

KPI observe modes:
- `strict_hash`: runtime hash gate policy preserved (production-equivalent)
- `benchmark_relaxed`: benchmark-only KPI observability mode (does not send `expected_base_hash`)
- In `benchmark_relaxed`, output JSON includes:
  - `_meta.benchmark_mode_warning=true`
  - `_meta.not_for_production=true`
- Limitation (current implementation):
  - `benchmark_relaxed` only bypasses request-level `expected_base_hash`.
  - Server still validates internal `proposal_base_hash` first, so drift perturbation can still end at `BASE_HASH_MISMATCH`.

Generated artifacts:
- `docs/perf_baselines/autofix_apply_baseline_20260227_0938.json`
- `docs/perf_baselines/autofix_apply_improved_20260227_0938.json`
- `docs/perf_baselines/autofix_apply_comparison_20260227_0938.json`
- `docs/perf_baselines/autofix_apply_baseline_20260227_1042_general.json`
- `docs/perf_baselines/autofix_apply_improved_20260227_1042_general.json`
- `docs/perf_baselines/autofix_apply_comparison_20260227_1042_general.json`
- `docs/perf_baselines/autofix_apply_baseline_20260227_1042_drift.json`
- `docs/perf_baselines/autofix_apply_improved_20260227_1042_drift.json`
- `docs/perf_baselines/autofix_apply_comparison_20260227_1042_drift.json`

Current comparison result:
- `baseline_failure_rate = 0.0`
- `improved_failure_rate = 0.0`
- `improvement_percent = 0.0`
- Interpretation:
  - general(strict): no anchor mismatch events observed
  - drift(relaxed): still blocked by internal `proposal_base_hash` check, so fallback-path KPI is not yet measurable

Note on hash gate and KPI observability:
- Current `autofix/apply` flow validates proposal base hash before anchor/token fallback.
- If source is perturbed between `prepare` and `apply`, request is blocked as `BASE_HASH_MISMATCH` before fallback stage.
- Therefore, anchor mismatch KPI should be interpreted with this constraint and validated either:
  - on naturally drifting real sessions where proposal hash still matches (rare), or
  - via dedicated benchmark harness/server test hook that can safely simulate post-hash pre-anchor conditions.
