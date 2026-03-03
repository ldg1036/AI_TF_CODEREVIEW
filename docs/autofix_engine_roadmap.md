# Autofix Engine Roadmap (T2/T3)

## Scope

This document captures post-P1/P2 status and remaining T3 work.

Implemented baseline:
- compare mode (`rule` vs `llm`)
- token-based anchor fallback
- semantic guard v1 (rule generator path)
- multi-hunk P1 safety policy (same block, max 3, fail-soft)

## T2: Parser-lite Apply Engine (Implemented)

### Goal
Improve apply robustness for WinCC OA `.ctl` with structure-aware matching while preserving current safety checks.

### Implemented coverage
- function/event block boundaries
- brace nesting
- same-block multi-hunk apply (max 3)
- overlap/cross-block fail-soft blocking

### Implemented policy
- structure-aware apply path first
- fallback to text patch flow when safe
- fail-soft block for unsafe multi-hunk (`too_many_hunks`, `overlapping_hunks`, `hunks_span_multiple_blocks`, `anchor_context_not_unique`)
- existing `hash/anchor/syntax/heuristic/optional ctrlpp` gates preserved

## T3: Structured LLM Edit Instructions (Phase 1 Implemented)

### Goal
Move from full generated code blocks to structured edit intents that can be validated/applied by engine logic.

### Draft instruction shape
```json
{
  "target": {"file":"sample.ctl","object":"...","event":"Global"},
  "operation":"insert|replace|delete",
  "locator":{"kind":"function|event|token_context","value":"..."},
  "payload":{"code":"..."},
  "safety":{"requires_hash_match":true}
}
```

### Implemented in T3-1 (2026-03-03)
- scope: LLM proposal path only
- operations: `replace`, `insert` only (`delete` not supported)
- feature flag: `autofix.engine.structured_instruction_enabled` (default `false`)
- behavior:
  - flag OFF: legacy hunk apply path unchanged
  - flag ON + valid instruction: structured instruction converted to hunks and applied first
  - invalid instruction: fail-soft fallback to legacy proposal hunks
- observability:
  - apply validation/quality fields: `instruction_mode`, `instruction_validation_errors`,
    `instruction_operation`, `instruction_apply_success`
  - stats fields:
    - `instruction_attempt_count`
    - `instruction_apply_success_count`
    - `instruction_fallback_to_hunk_count`
    - `instruction_validation_fail_count`

### Planned policy (Remaining)
- feature-flagged rollout
- fail-soft fallback to current patch path
- audit log keeps both instruction and final patch summary

### Decision-complete breakdown (next implementation batch)
1. Schema v1 lock
   - fields: `target`, `locator`, `operation`, `payload`, `safety`
   - validation: required fields + enum checks + locator uniqueness checks
2. Runtime integration (feature flag OFF by default)
   - [x] new flag: `autofix.engine.structured_instruction_enabled`
   - [x] if ON and instruction parse succeeds: engine consumes structured instruction first
   - [x] if instruction parse fails: fallback to current unified-diff hunk path
3. Ownership transfer phases
   - Phase 1: dual-path (instruction apply + legacy patch diff for verification only)
   - Phase 2: parser/token engine primary patch generation/apply owner
   - Phase 3: legacy path fallback-only, with explicit diagnostics
4. Compare mode compatibility
   - [x] `rule` and `llm` candidates carry the same normalized instruction envelope (both proposals attach `_structured_instruction`; compare selection policy + score/reason metadata exposed)
   - [x] selection/apply keeps existing `proposal_id` contract
5. Acceptance criteria
   - [x] no regression in `hash/anchor/syntax/semantic/heuristic/ctrlpp` safety gates (T3-1 scope tests)
   - [x] deterministic error mapping for instruction parse/resolve failures (fallback_hunks + validation errors)
   - [x] stats include instruction-path attempt/success/fallback counts

## Feature Flags (default OFF, planned)
- `autofix.engine.parser_lite_enabled`
- `autofix.engine.structured_instruction_enabled`

## Acceptance for remaining phase
- no regression in existing apply safety checks
- reduced anchor mismatch failure rate on real `.ctl` edits
- deterministic fallback behavior when parser/instruction resolution is ambiguous
- parser/token engine becomes primary patch generation/apply owner for structured instructions
