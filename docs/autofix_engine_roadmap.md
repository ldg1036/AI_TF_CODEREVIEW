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

## T3: Structured LLM Edit Instructions (Remaining)

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

### Planned policy
- feature-flagged rollout
- fail-soft fallback to current patch path
- audit log keeps both instruction and final patch summary

## Feature Flags (default OFF, planned)
- `autofix.engine.parser_lite_enabled`
- `autofix.engine.structured_instruction_enabled`

## Acceptance for remaining phase
- no regression in existing apply safety checks
- reduced anchor mismatch failure rate on real `.ctl` edits
- deterministic fallback behavior when parser/instruction resolution is ambiguous
- parser/token engine becomes primary patch generation/apply owner for structured instructions
