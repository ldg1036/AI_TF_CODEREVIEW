# WinCC OA Code Review Project Agent Guide

This repository contains a WinCC OA code review application with optional local AI, CtrlppCheck integration, report generation, and benchmarking utilities.

## Goal

Optimize for fast, safe iteration in this project:

1. Explore existing rules/context first
2. Make the smallest targeted code change
3. Run the narrowest relevant verification
4. Escalate to quality/perf/smoke checks only when the change requires it

## Default Workflow

Use this order unless the request explicitly skips steps:

1. Explore target code and related rules/docs
2. Query WinCC OA review context (MCP bridge preferred)
3. Implement a small change
4. Run focused unit tests
5. Run P1/P2/P3-centered verification (tests + py_compile; config alignment when rules/config changed)
6. Run perf benchmark or Ctrlpp smoke when frontend/perf/Ctrlpp behavior changes

## Project-Specific Tools

Core app entrypoints:

- `python backend/server.py` (HTTP UI/API server)
- `python backend/main.py --selected-files GoldenTime.ctl` (CLI analysis)

Read-only context servers:

- HTTP context server: `python backend/tools/winccoa_context_server.py`
- Standard MCP bridge (stdio): `python backend/tools/winccoa_context_mcp_server.py`

High-value verification tools:

- `python backend/tools/check_config_rule_alignment.py`
- `python backend/tools/analyze_template_coverage.py`
- `python tools/run_ctrlpp_integration_smoke.py`
- `python tools/http_perf_baseline.py`
- `node tools/playwright_ui_benchmark.js`

## Optional Dependencies (Fail-Soft)

Treat these as optional unless the user asks for them explicitly:

- Ollama/local LLM (`ai.provider=ollama`)
- CtrlppCheck binary/toolchain
- Playwright browser install (`npx playwright install chromium`)

If missing, prefer a fail-soft path:

- Continue static checks/tests without LLM
- Use `--allow-missing-binary` for Ctrlpp smoke when appropriate
- Skip UI benchmark and report prerequisite clearly

## Encoding and Text Handling

This project handles mixed encodings in review inputs.

- Prefer UTF-8 when writing new files
- Be careful with WinCC OA input files using `cp949` / `euc-kr`
- `README.md` may display mojibake in some consoles/shell encodings; do not assume file corruption from console output alone
- When changing prompt/rule/config files, verify path existence and effective loading behavior

## Safety Rules

- Do not enable destructive batch rewrites for review data by default
- Keep MCP tools read-only
- Prefer explicit commands and narrow test scopes
- For autofix-related changes, preserve existing validation behavior (hash/anchor/heuristic/Ctrlpp regression options)

## Recommended Checks by Change Type

Backend API / pipeline change:

- `python -m unittest backend.tests.test_api_and_reports`
- `python -m py_compile backend/main.py backend/server.py backend/core/analysis_pipeline.py`

Context/rules/tooling change:

- `python -m unittest backend.tests.test_winccoa_context_server -v`
- `python backend/tools/check_config_rule_alignment.py --json`
- `python backend/tools/analyze_template_coverage.py`

Frontend rendering/perf change:

- `node --check frontend/renderer.js`
- `node tools/playwright_ui_benchmark.js --help`
- Run benchmark thresholds only when Playwright is installed

Ctrlpp integration change:

- `python tools/run_ctrlpp_integration_smoke.py --allow-missing-binary --skip-unittest`
- Full smoke only if binary is installed

## Agent Notes

- This repository is currently not a Git repository in the inspected path, so GitHub/PR workflows are not the default path here.
- Prefer the project-specific WinCC OA skills (Ctrlpp smoke, UI benchmark, HTTP perf baseline, config alignment, template coverage, TODO rule miner) when available.
