# Tools Folder Guide

`tools/` is organized by feature while keeping legacy entrypoints for compatibility.

## Feature Folders

- `tools/perf/`
  - `http_perf_baseline.py`
  - `playwright_ui_benchmark.js`
- `tools/ctrlpp/`
  - `run_ctrlpp_integration_smoke.py`
  - `ctrlppcheck_updater.py`
  - `ctrlppcheck_wrapper.py`
  - `README_CtrlppCheck.md`

## Runtime / Results Folders (kept at legacy paths)

- `tools/CtrlppCheck/` : CtrlppCheck runtime install/cache path (referenced by `Config/config.json`)
- `tools/benchmark_results/` : UI benchmark JSON outputs
- `tools/integration_results/` : Ctrlpp / HTTP smoke result outputs

## Compatibility Entry Points (legacy paths)

These files remain in `tools/` and forward execution to the feature folders:

- `tools/http_perf_baseline.py`
- `tools/playwright_ui_benchmark.js`
- `tools/run_ctrlpp_integration_smoke.py`
- `tools/ctrlppcheck_updater.py`
- `tools/ctrlppcheck_wrapper.py`
- `tools/README_CtrlppCheck.md` (pointer document)
