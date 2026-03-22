# WinCC OA Full Audit 2026-03-22

## Summary
- Audit id: `full_audit_20260322_131956`
- Fresh audit server: `http://127.0.0.1:8776`
- Baseline remained green:
  - `release gate`: `15 passed, 0 failed`
  - `refactor compare`: `no_missing_features=true`
  - `Benchmark smoke`: `5/5`
  - `canonical boundary parity`: `txt 38/38`, `pnl 38/38`, `UNKNOWN 0`
- Final verdict:
  - Rule engine accuracy: `PASS`
  - Product completeness: `MOSTLY PASS`

## Execution Log
- Environment readiness captured:
  - `npx` / Playwright available
  - Ollama reachable, `/api/ai/models` returned `qwen2.5-coder:3b`
  - Ctrlpp smoke ready
- Pristine backups created for:
  - `Config/p1_rule_defs.json`
  - `Config/review_applicability.json`
  - `CodeReview_Data/BenchmarkP1Fixture.ctl`
  - `CodeReview_Data/GoldenTime.ctl`
  - `CodeReview_Data/POP_CTRL_AUTOBACKUP_HGB_C2_2_pnl.txt`
- Baseline verification rerun:
  - `check_config_rule_alignment`: unknown rule ids `0`
  - `analyze_template_coverage`: client `15/15`, server `20/20`
  - `verify_p1_rules_matrix`: enabled `42`, supported `42`, positive `100%`, negative `100%`
  - `backend.tests.test_api_and_reports`: `182 passed, 1 skipped`
  - `backend.tests.test_winccoa_context_server`: `6 passed`
  - `npm run test:frontend`: `67 passed`
  - `release_gate`: `15 passed, 0 failed`

## Real User Flow Audit
### Dashboard -> Settings
- Rules health matched API and baseline:
  - `P1 활성 42`
  - `미참조 rule_id 0`
  - `Degraded NO`
- Dependency cards matched reality:
  - `openpyxl ready`
  - `Ctrlpp ready`
  - `Playwright ready`
- Latest operation cards matched artifacts:
  - `UI Real Smoke` passed
  - `Ctrlpp` passed
  - `Live AI` available
  - `release gate` passed

### Workspace: BenchmarkP1Fixture.ctl
- `P1 only` rows: `5`
- `P1 + Ctrlpp` rows: `6`
- UI displayed the expected core findings:
  - `PERF-SETMULTIVALUE-ADOPT-01`
  - `ACTIVE-01`
  - `EXC-TRY-01`
  - `EXC-DP-01`
- Additional low-severity style finding:
  - `STYLE-HEADER-01`
- Detail panel evidence was correct. Example:
  - `EXC-DP-01`
  - detector `heuristic`
  - matched text `dpSet("SYS.A.C1", v1);`
  - matched line `14`
- Triage round trip passed:
  - suppress
  - show suppressed
  - unsuppress

### Workspace: GoldenTime.ctl
- `P1 only` rows: `4`
- UI displayed the expected core findings:
  - `HARD-01`
  - `STYLE-IDX-01`
  - `PERF-EV-01`
  - `HARD-03`
- Severity and line references matched API/report output.

### Workspace: txt/pnl boundary
- `POP_CTRL_AUTOBACKUP_HGB_C2_2_pnl.txt`
  - UI rows `38`
  - summary `38`
  - `UNKNOWN` rows `0`
- `POP_CTRL_AUTOBACKUP_HGB_C2_2.pnl`
  - UI rows `38`
  - summary `38`
  - `UNKNOWN` rows `0`
  - viewer resolved to canonical converted txt
- Result:
  - `.pnl converted only` policy worked as intended
  - UI/API/Excel/summary parity held for txt/pnl

### Live AI
- `/api/ai/models` responded successfully.
- Real browser flow succeeded:
  - `Generate AI Review`
  - `P1/P2 <> P3 compare`
  - `Prepare patch`
  - unified diff open
- Quality checks passed:
  - no `obj_auto_sel`
  - no `System1:Obj1`
  - no `=>`
  - real DP names reused
- Current limitation:
  - compare modal apply remained blocked with `proposal_missing`
  - safe, but still confusing for users

### Excel
- Benchmark, GoldenTime, txt, and pnl report outputs matched their summary counts.
- Download path was available in the real UI flow.

## Manual vs Automatic Comparison
| file | manual finding | expected rule | CLI P1 | CLI P1+P2 | UI | Excel | AI mention | autofix | classification | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| BenchmarkP1Fixture.ctl | repeated setValue batching needed | PERF-SETMULTIVALUE-ADOPT-01 | yes | yes | yes | yes | yes | yes | matched | representative performance rule matched |
| BenchmarkP1Fixture.ctl | mutating call without active guard | ACTIVE-01 | yes | yes | yes | yes | yes | yes | matched | same source block as repeated setValue |
| BenchmarkP1Fixture.ctl | dpSet lacks try/catch contract | EXC-TRY-01 | yes | yes | yes | yes | no | no | matched | AI priority cap skipped this one |
| BenchmarkP1Fixture.ctl | dpSet lacks DP error handling | EXC-DP-01 | yes | yes | yes | yes | yes | yes | matched | detail evidence matched exact dpSet line |
| GoldenTime.ctl | hardcoded path/environment string | HARD-01 | yes | yes | yes | yes | no | no | matched | stable across UI/API/report |
| GoldenTime.ctl | magic index should be constantized | STYLE-IDX-01 | yes | yes | yes | yes | no | no | matched | correct rule and severity |
| GoldenTime.ctl | loop/event exchange optimization needed | PERF-EV-01 | yes | yes | yes | yes | no | no | matched | representative performance finding matched |
| GoldenTime.ctl | repeated float literal should be externalized | HARD-03 | yes | yes | yes | yes | no | no | matched | representative hardcoding finding matched |
| POP_CTRL_AUTOBACKUP_HGB_C2_2_pnl.txt | canonical count and display parity | boundary/display correctness | yes | n/a | yes | yes | no | no | matched | `38/38`, `UNKNOWN 0` |
| POP_CTRL_AUTOBACKUP_HGB_C2_2.pnl | alias must resolve to canonical txt set | boundary/display correctness | yes | n/a | yes | yes | no | no | matched | same `38/38`, `UNKNOWN 0` |

## Current Rule Detection Failures
- No representative rule-detection failure was confirmed in this audit.
- No critical false positive was confirmed on the representative `.ctl` samples.
- Current representative status:
  - Benchmark core required rules: all matched
  - GoldenTime core required rules: all matched
  - txt/pnl boundary correctness: matched

## Current Product Issues
### 1. Autofix prepare/apply contract gap
- Some copy-file prepare responses reported `allow_apply=true`.
- Later apply returned `409 SEMANTIC_GUARD_BLOCKED` for:
  - `EXC-DP-01`
  - `PERF-SETMULTIVALUE-ADOPT-01`
  - `EXC-TRY-01`
- This is safe behavior, but the contract is still too optimistic.

### 2. Compare modal apply clarity
- Live AI compare/prepare worked and produced a clean diff.
- The modal still showed:
  - `Apply blocked`
  - `No prepared source proposal is available. [proposal_missing]`
- This is acceptable for conservative apply, but the reason needs to be surfaced more clearly per candidate.

## Rules Write Round-Trip
- Endpoints exercised:
  - `/api/rules/create`
  - `/api/rules/update`
  - `/api/rules/delete`
  - `/api/rules/import` dry-run
  - `/api/rules/rollback/latest`
- Observed behavior:
  - create mutated rule health from `43/42` to `44/43`
  - rollback restored `43/42`
  - pristine config hashes matched after rollback
- Note:
  - the audit helper's `create_rule_present=false` and `import_merge_present=false` flags did not match the live health counters
  - this looks like an audit-helper presence-check issue, not a confirmed product restore failure

## Autofix Apply and Restore
- Copy flow:
  - prepare/diff/apply/reanalyze tested
  - safe rule proposals applied
  - high-risk proposals were blocked by semantic guard
- Original file flow:
  - target rule: `STYLE-HEADER-01`
  - apply succeeded
  - reanalyze reduced total from `5` to `4`
  - pristine backup restored
  - SHA256 before and after restore matched exactly

## Restore Verification
- Config restore:
  - `p1_rule_defs.json`: matched pristine hash
  - `review_applicability.json`: matched pristine hash
- Original code restore:
  - `BenchmarkP1Fixture.ctl`: matched pristine hash
- Result:
  - `rules config restore mismatch = 0`
  - `original autofix restore hash mismatch = 0`

## Baseline Comparison
- Benchmark smoke baseline remained `5/5`
- canonical parity remained:
  - `txt 38/38`
  - `pnl 38/38`
  - `UNKNOWN 0`
- refactor compare remained:
  - `no_missing_features=true`
- release gate remained green:
  - `15 passed, 0 failed`

## Top 10 Improvements
1. Make `prepare` run the same semantic guard path as `apply` so `allow_apply` cannot over-promise.
2. Show candidate-specific blocked reasons in compare modal instead of a generic `proposal_missing`.
3. Return a stable prepared proposal id from compare/prepare to tighten UI apply wiring.
4. Add a regression test for `prepare=true` but `apply=409`.
5. Add a stable rules-write revision id or echo payload for easier live create/import verification.
6. Expose generated Excel row counts directly in API payloads.
7. Add Benchmark/GoldenTime representative manual-rule assertions to release gate.
8. Surface detected encoding and canonical source more clearly for txt/pnl files.
9. Persist compare/triage telemetry in a compact audit artifact.
10. Keep rotating audit artifacts automatically so future full audits are easier to run.

## Environment Blocks
- None in this run.

## Final Verdict
- As a WinCC OA code review product, the current program is correctly detecting the representative rule set required by this audit.
- The main remaining issues are no longer rule-detection accuracy issues.
- The remaining gap is product contract clarity around `prepare -> compare -> apply`, especially for conservative semantic-guard blocking.
