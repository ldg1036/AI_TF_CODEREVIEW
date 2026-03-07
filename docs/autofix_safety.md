# Autofix Safety and Parserless Patch Limits

Last Updated: 2026-02-27 (LLM/rule/auto hybrid prepare + quality metrics)

This project supports diff approval-based autofix for `.ctl` and normalized text targets (`*_pnl.txt`, `*_xml.txt`, raw `.txt` when allowed).

Implemented API flow:
- `POST /api/autofix/prepare`
- `GET /api/autofix/file-diff`
- `POST /api/autofix/apply`
- `GET /api/autofix/stats`

## Current Safety Model

Autofix is intentionally conservative:

- Rule generator path is `.ctl`-centric; non-CTL targets are handled via LLM-based proposals with conservative validation skips recorded in metrics.
- `prepare` generates a diff proposal
- User reviews and explicitly approves
- `apply` validates before writing

Validation steps include:
- base hash check (source unchanged since prepare)
- anchor/context check
- basic syntax precheck (brace/parenthesis balance)
- heuristic regression check (P1 count delta)
- optional Ctrlpp regression check
- backup creation + atomic write
- audit log entry

## Why Parserless Patching Was Chosen (Phase 1)

WinCC OA-specific parsing support is not yet integrated. Phase 1 uses a text-based patch application strategy because it is:

- faster to implement
- easy to audit (plain unified diff)
- compatible with approval workflows
- safe enough when combined with hash/anchor validation

## Known Limits of Parserless Patching

Text anchor-based patching has predictable limits:

- fragile under heavy concurrent edits to the same file
- can reject valid edits if surrounding context changes
- cannot reason about semantic equivalence
- complex refactors are not suitable (control-flow rewrites, deep condition restructuring)
- newline/format-only edits can look small but still affect diff/hunk behavior

These limits are acceptable for Phase 1 because the system is approval-based and fail-safe.

## Recommended Use Cases (Safe)

Prefer autofix for:

- deterministic hygiene/format fixes
- repeated rule-template substitutions with clear local context
- LLM proposals that add guarded snippets/comments near a flagged line
- small localized changes reviewed by an engineer

Avoid autofix for:

- multi-function rewrites
- protocol/state machine changes
- broad logic refactors
- changes requiring project-wide semantic knowledge

## Hybrid Strategy (Recommended)

Use a hybrid generator policy:

- `rule-first` for deterministic/safe fixes
- `llm-fallback` for advisory fixes when no rule template applies
- `auto` mode to choose the above flow automatically

This reduces:
- token cost
- non-determinism
- review burden for common patterns

## Future Hardening / Parser Roadmap

Longer-term options (investigate before implementation):

1. WinCC OA lexer/tokenizer for structure-aware hunk placement
2. Minimal AST/CFG extraction for selected `.ctl` constructs
3. Semantic patching only for a small curated rule set
4. Multi-candidate prepare (`rule` vs `llm`) with side-by-side diff comparison

Until then, keep the current guardrails:
- approval required
- hash+anchor validation
- regression checks enabled in production defaults


