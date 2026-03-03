# Autofix Engine Roadmap (T2/T3)

## Scope

This document tracks post-P1/P2 status and remaining T3 work.

Implemented baseline:
- compare mode (`rule` vs `llm`)
- token-based anchor fallback
- semantic guard v1 (rule generator path)
- multi-hunk P1 safety policy (same block, max 3, fail-soft)

## T2: Parser-lite Apply Engine (Implemented)

### Goal
Improve apply robustness for WinCC OA `.ctl` with structure-aware matching while preserving existing safety checks.

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

## T3: Structured Edit Instructions

### Goal
Move from full generated code blocks to structured edit intents that can be validated/applied by engine logic.

### Instruction shape (v1.1, internal)
```json
{
  "target": {"file": "sample.ctl", "object": "...", "event": "Global"},
  "operations": [
    {
      "operation": "insert|replace",
      "locator": {
        "kind": "anchor_context",
        "start_line": 123,
        "context_before": "...",
        "context_after": "..."
      },
      "payload": {"code": "..."}
    }
  ],
  "safety": {"requires_hash_match": true}
}
```

### T3-1 (Implemented)
- scope: rule + llm proposal paths
- operations: `replace`, `insert` only (`delete` excluded)
- feature flag: `autofix.engine.structured_instruction_enabled` (default `false`)
- behavior:
  - flag OFF: legacy hunk apply path unchanged
  - flag ON + valid instruction: instruction converted to hunks and applied first
  - invalid instruction: fail-soft fallback to legacy proposal hunks
- observability:
  - apply validation/quality fields: `instruction_mode`, `instruction_validation_errors`, `instruction_operation`, `instruction_operation_count`, `instruction_apply_success`
  - stats fields: `instruction_attempt_count`, `instruction_apply_success_count`, `instruction_fallback_to_hunk_count`, `instruction_validation_fail_count`, `instruction_operation_total_count`

### T3-2 (Observability / Rollout Decision, Implemented in this batch)
- apply validation/quality fields added:
  - `instruction_path_reason` (`applied|validation_failed|engine_failed|fallback_hunks|off`)
  - `instruction_failure_stage` (`validate|convert|apply|none`)
  - `instruction_candidate_hunk_count`
  - `instruction_applied_hunk_count`
- stats fields added:
  - `instruction_engine_fail_count`
  - `instruction_convert_fail_count`
  - `instruction_validation_fail_by_reason` (dict)
  - `instruction_mode_counts` (dict)
- perf baseline summary/comparison added:
  - `instruction_apply_rate`
  - `instruction_fallback_rate`
  - `instruction_validation_fail_rate`
  - `instruction_fail_stage_distribution`
  - `rollout_ready`, `rollout_checks`

### Rollout criteria (flag default OFF 유지)
- `instruction_apply_rate >= 0.70`
- `instruction_validation_fail_rate <= 0.20`
- `REGRESSION_BLOCKED == 0`

## Decision-complete status

1. Schema lock
- [x] fields: `target`, `operations[]`, `safety`
- [x] validation: required fields + enum checks + per-op locator/code checks

2. Runtime integration (feature flag OFF by default)
- [x] `autofix.engine.structured_instruction_enabled`
- [x] ON + valid instruction: instruction-first apply
- [x] invalid instruction: fallback to legacy hunk path

3. Ownership transfer phases
- [x] Phase 1: dual-path (instruction apply + legacy hunk fallback)
- [x] Phase 2: instruction-first apply + stage-level observability
- [-] Phase 3: legacy path fallback-only hardening/policy tuning

4. Compare mode compatibility
- [x] `rule` and `llm` candidates carry normalized instruction envelope
- [x] selection/apply keeps existing `proposal_id` contract

5. Acceptance criteria
- [x] no regression in `hash/anchor/syntax/semantic/heuristic/ctrlpp` safety gates
- [x] deterministic fallback behavior for invalid instructions
- [x] stats include attempt/success/fallback/validation counts and operation totals
- [x] observability supports rollout decision by failure stage/reason

## Feature Flags
- `autofix.engine.parser_lite_enabled`
- `autofix.engine.structured_instruction_enabled`

## Remaining focus
- compare UX/policy tuning for instruction-heavy proposals
- rollout threshold tuning with additional real-data baselines
- gradual shift of legacy path to fallback-only role
