from __future__ import annotations

import collections
from typing import Dict, List, TypedDict

try:
    from core.autofix_tokenizer import tokenize_ctl
except ModuleNotFoundError:  # pragma: no cover - import path depends on entrypoint
    from backend.core.autofix_tokenizer import tokenize_ctl


class SemanticDeltaResult(TypedDict, total=False):
    ok: bool
    blocked: bool
    reason: str
    violations: List[str]
    details: Dict[str, object]


_HIGH_RISK_OPERATORS = {
    "=",
    "+=",
    "-=",
    "*=",
    "/=",
    "==",
    "!=",
    "<",
    ">",
    "<=",
    ">=",
    "&&",
    "||",
}

_KEYWORDS = {
    "if",
    "else",
    "switch",
    "case",
    "for",
    "while",
    "return",
    "break",
    "continue",
}


def _build_profile(text: str) -> Dict[str, List[str]]:
    source = str(text or "")
    strings: List[str] = []
    numbers: List[str] = []
    operators: List[str] = []
    keywords: List[str] = []

    for token in tokenize_ctl(source):
        token_type = str(token.get("type", ""))
        if token_type.startswith("comment"):
            continue

        start = int(token.get("start", 0) or 0)
        end = int(token.get("end", 0) or 0)
        raw = source[start:end]

        if token_type == "string":
            strings.append(raw)
            continue
        if token_type == "number":
            numbers.append(raw)
            continue
        if token_type == "operator":
            op = raw.strip()
            if op in _HIGH_RISK_OPERATORS:
                operators.append(op)
            continue
        if token_type == "identifier":
            ident = str(token.get("value", "") or "").strip().lower()
            if ident in _KEYWORDS:
                keywords.append(ident)

    return {
        "strings": strings,
        "numbers": numbers,
        "operators": operators,
        "keywords": keywords,
    }


def _counter(values: List[str]) -> Dict[str, int]:
    return dict(collections.Counter(values))


def evaluate_semantic_delta(before_text: str, after_text: str) -> SemanticDeltaResult:
    try:
        before_profile = _build_profile(before_text)
        after_profile = _build_profile(after_text)

        violations: List[str] = []
        sequence_changed: List[str] = []
        details: Dict[str, object] = {
            "before_counts": {},
            "after_counts": {},
            "sequence_changed_categories": sequence_changed,
        }

        for category in ("strings", "numbers", "operators", "keywords"):
            before_values = list(before_profile.get(category, []))
            after_values = list(after_profile.get(category, []))

            before_counts = _counter(before_values)
            after_counts = _counter(after_values)
            details_before = details["before_counts"]
            details_after = details["after_counts"]
            if isinstance(details_before, dict):
                details_before[category] = before_counts
            if isinstance(details_after, dict):
                details_after[category] = after_counts

            if before_counts != after_counts:
                violations.append(f"{category}_changed")
            elif before_values != after_values:
                sequence_changed.append(category)

        if violations:
            return {
                "ok": True,
                "blocked": True,
                "reason": "high_risk_token_delta",
                "violations": violations,
                "details": details,
            }

        if sequence_changed:
            return {
                "ok": True,
                "blocked": False,
                "reason": "insufficient_signal",
                "violations": [],
                "details": details,
            }

        return {
            "ok": True,
            "blocked": False,
            "reason": "no_risk_delta",
            "violations": [],
            "details": details,
        }
    except Exception as exc:
        return {
            "ok": False,
            "blocked": False,
            "reason": "insufficient_signal",
            "violations": [],
            "details": {"error": str(exc)},
        }
