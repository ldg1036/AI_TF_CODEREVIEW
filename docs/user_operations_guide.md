# User Operations Guide

Last Updated: 2026-03-06

## Goal

This guide is for the final user or operator who needs to run the WinCC OA code review program reliably without reading the full developer documentation.

## 1. Before You Start

Required:
- Windows environment
- Python installed and available in `PATH`
- Project files present in `CodeReview_Data`

Recommended:
- `pip install -r requirements-dev.txt`
- `npm install`
- `npx playwright install chromium`

Optional tools:
- `CtrlppCheck`: used for `P2`
- `Ollama`: used for live AI `P3`
- Playwright browser: used for UI smoke/benchmark

The program is designed to fail soft when optional tools are missing, unless you explicitly choose checks that require them.

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

Use this when:
- you want to browse files
- you want to inspect issues visually
- you want to review reports and workspace results interactively

### CLI mode

Run a direct file analysis:

```powershell
python backend/main.py --selected-files GoldenTime.ctl
```

Use this when:
- you want a quick targeted analysis
- you do not need the UI

## 3. Release Gate Shortcuts

### Standard local gate

```powershell
.\run_release_gate.bat
```

### Local gate with live AI and MCP context

```powershell
.\run_release_gate.bat live-ai
```

### CI-style lightweight gate

```powershell
powershell -ExecutionPolicy Bypass -File .\run_release_gate.ps1 -Mode ci
```

## 4. What Each Gate Means

### Standard local gate

Checks:
- backend tests
- verification profile
- config/rule alignment
- template coverage
- warning gate
- frontend syntax
- Ctrlpp smoke
- UI benchmark
- real UI smoke

Use this before a normal release or local handoff.

### Live AI gate

Adds:
- one real live AI analysis on `BenchmarkP1Fixture.ctl`
- optional MCP context requirement

Use this when:
- Ollama is available
- you want to confirm live AI still produces at least one real `P3` review

### CI-style gate

Checks only the core regression path.

Use this when:
- optional tools are unavailable
- you want a fast minimum acceptance pass

## 5. Where Results Are Written

Main reports:
- `CodeReview_Report/release_gate_*.json`
- `CodeReview_Report/release_gate_*.md`

Additional artifacts:
- `tools/integration_results/ctrlpp_release_gate_*.json`
- `tools/integration_results/ui_real_smoke_release_gate_*.json`
- `tools/integration_results/live_ai_release_gate_*.json`
- `tools/benchmark_results/ui_benchmark_release_gate_*.json`

## 6. How To Interpret Results

Release gate result meanings:
- `passed`: all enabled checks passed
- `failed`: one or more enabled checks failed
- `skipped_optional_missing`: an optional dependency was not available and the check degraded safely

For a normal local release candidate, the expected outcome is:
- local gate: `passed`
- live AI gate: `passed` if live AI is part of the release scope

## 7. Common Trouble Cases

### UI does not open

Check:
- `python backend/server.py` is running
- port `8765` is free

### Ctrlpp smoke fails

Check:
- `CtrlppCheck` is installed or downloadable
- the binary path is valid

If Ctrlpp is not required for the current delivery, use the core or CI-style gate instead of blocking on it.

### Live AI gate fails

Check:
- Ollama is running
- the selected model is available
- the context server is reachable when `--live-ai-with-context` is used

### UI benchmark fails

Check:
- Playwright package is installed
- Chromium browser was installed with Playwright
- the machine is not under unusual load

## 8. Recommended Final Routine

For a normal final handoff:
1. Run `.\run_release_gate.bat`
2. If live AI is part of the delivery, run `.\run_release_gate.bat live-ai`
3. Keep the latest JSON and Markdown reports with the delivery notes
