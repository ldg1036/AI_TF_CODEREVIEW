# AI Agent Workflow (Codex-Centered, Local/On-Prem)

This document defines the recommended agent workflow and MCP/skill setup for `AI_TF_CodeReview`.

Last validated: 2026-02-27

## Repo Structure Note (2026-02-26)

- Canonical project paths are root directories: `Config`, `CodeReview_Data`, `docs`.
- `workspace/` is reserved for runtime/support data (for example `workspace/runtime/CodeReview_Report`).
- Legacy tool entrypoints in `tools/` remain valid via wrappers, while implementations are grouped under:
  - `tools/perf/`
  - `tools/ctrlpp/`
- See `workspace/README.md` and `tools/README.md`.

## Scope

- Client focus: Codex
- Priority: balanced (speed + safety)
- Network scope: local + on-prem/internal only

## Why This Exists

The project already has strong automation scripts (Ctrlpp smoke, UI benchmark, HTTP perf baseline, config alignment, template coverage), but agents need a thin integration layer to use them quickly and consistently.

This repo adds:

- A standard MCP bridge (`backend/tools/winccoa_context_mcp_server.py`) for WinCC OA review context
- Project-local agent rules (`AGENTS.md`)
- Project-specific Codex skills for repeatable CLI workflows

## Recommended MCP Set

### Use Now

1. WinCC OA Context MCP Bridge (read-only, stdio)
2. Filesystem MCP (or equivalent local file access)
3. Browser/Playwright MCP (frontend inspection/repro/perf support)
4. Process/Command runner MCP (optional if your client already has shell)

### Defer

1. Git/GitHub MCP (optional; use when PR/review workflow is needed)
2. Web search/fetch MCP (not needed for local-only workflows)
3. External doc search MCP (optional later)

## WinCC OA Context MCP Bridge

### Run Command

```powershell
python backend/tools/winccoa_context_mcp_server.py --project-root C:\Users\Administrator\Desktop\AI_TF_CodeReview
```

Note:
- Using the repo root path above is the canonical setup.

### Exposed Resources

- `winccoa://project/context`
- `winccoa://rules/index`

### Exposed Tools

- `health()`
- `list_review_drivers()`
- `get_rule(rule_id)`
- `find_template_coverage(query, scope?, refresh?, include_unmatched_rows?)`

### Design Notes

- Read-only only
- No external network calls
- Fail-soft tool responses for recoverable issues
- Text payloads are size-limited to avoid flooding MCP clients

## Project-Specific Codex Skills

Recommended installed skills:

- `winccoa-ctrlpp-smoke`
- `winccoa-ui-benchmark`
- `winccoa-http-perf-baseline`
- `winccoa-config-alignment`
- `winccoa-template-coverage`
- `winccoa-todo-rule-miner`

These skills wrap existing scripts and standardize:

- preflight checks
- side-effect warnings
- preset commands
- concise result summaries

## Default Agent Workflow

1. Explore target files and tests
2. Query rules/context via MCP bridge (`get_rule`, `rules/index`)
3. Make the smallest change
4. Run narrow unit tests
5. Run P1/P2/P3-centered verification (tests + `py_compile`; config alignment when rules/config changed)
6. Run Ctrlpp/UI/perf smoke only when the change touches those areas

## Hygiene Checks (Config + Prompt Path)

Current recommended checks:

1. Verify `Config/config.json` exists and loads
2. Verify `ai.system_prompt` path exists relative to repo root
3. Verify rules/config alignment

Examples:

```powershell
python backend/tools/check_config_rule_alignment.py --json
Test-Path "Config\\prompt.txt"
```

## Quick Verification Commands

Note:
- Existing commands below are still valid (compatibility wrappers in `tools/`).
- New grouped implementation paths also work (for example `tools/perf/...`, `tools/ctrlpp/...`).

```powershell
python -m unittest backend.tests.test_winccoa_context_server -v
python -m unittest backend.tests.test_api_and_reports -v
python -m unittest backend.tests.test_todo_rule_mining -v
python -m py_compile backend/main.py backend/server.py backend/core/analysis_pipeline.py
python backend/tools/winccoa_context_mcp_server.py --help
python backend/tools/check_config_rule_alignment.py --json
python tools/run_ctrlpp_integration_smoke.py --help
node tools/playwright_ui_benchmark.js --help
```

## Release Verification (P1/P2/P3)

Use a document-based checklist instead of the removed GoldenTime reference comparison scripts.

Required (default):

1. `python -m unittest backend.tests.test_api_and_reports -v`
2. `python -m unittest backend.tests.test_todo_rule_mining -v`
3. `python -m unittest backend.tests.test_winccoa_context_server -v`
4. `python -m py_compile backend/main.py backend/server.py backend/core/analysis_pipeline.py`

Optional (change-dependent, fail-soft where applicable):

1. Ctrlpp integration changes: `python tools/run_ctrlpp_integration_smoke.py --allow-missing-binary --skip-unittest`
2. Frontend/perf changes: `node --check frontend/renderer.js`, `node tools/playwright_ui_benchmark.js --help`
3. Rules/config changes: `python backend/tools/check_config_rule_alignment.py --json`, `python backend/tools/analyze_template_coverage.py`
