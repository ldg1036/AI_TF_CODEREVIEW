import difflib
import re
from typing import Dict, List, Optional, Tuple, TypedDict


class CtlToken(TypedDict):
    type: str
    value: str
    start: int
    end: int
    line: int
    column: int


class TokenLocateResult(TypedDict, total=False):
    ok: bool
    line: int
    confidence: float
    candidate_count: int
    top1_confidence: float
    top2_confidence: float
    confidence_gap: float
    reason: str


_TOKEN_RE = re.compile(
    r"""
    (?P<comment_line>//[^\n]*)
  | (?P<comment_block>/\*.*?\*/)
  | (?P<string>"(?:\\.|[^"\\])*")
  | (?P<identifier>[A-Za-z_]\w*)
  | (?P<number>\d+(?:\.\d+)?)
  | (?P<operator>==|!=|<=|>=|&&|\|\||[+\-*/%<>=!&|^~?:])
  | (?P<brace>[{}\[\]()])
  | (?P<punct>[;,\.])
    """,
    re.VERBOSE | re.DOTALL | re.MULTILINE,
)


def _line_starts(text: str) -> List[int]:
    starts = [0]
    for m in re.finditer(r"\n", text):
        starts.append(m.end())
    return starts


def _line_col_from_pos(starts: List[int], pos: int) -> Tuple[int, int]:
    line = 1
    low = 0
    high = len(starts) - 1
    while low <= high:
        mid = (low + high) // 2
        if starts[mid] <= pos:
            line = mid + 1
            low = mid + 1
        else:
            high = mid - 1
    col = (pos - starts[line - 1]) + 1
    return line, max(1, col)


def tokenize_ctl(text: str) -> List[CtlToken]:
    source = str(text or "")
    starts = _line_starts(source)
    out: List[CtlToken] = []
    for m in _TOKEN_RE.finditer(source):
        token_type = m.lastgroup or "unknown"
        raw = m.group(0)
        if token_type.startswith("comment"):
            value = "<comment>"
        elif token_type == "string":
            value = "<string>"
        elif token_type == "identifier":
            value = raw.lower()
        else:
            value = raw
        line, col = _line_col_from_pos(starts, m.start())
        out.append(
            {
                "type": token_type,
                "value": value,
                "start": m.start(),
                "end": m.end(),
                "line": line,
                "column": col,
            }
        )
    return out


def token_values(text: str) -> List[str]:
    return [t["value"] for t in tokenize_ctl(text)]


def token_similarity(a: str, b: str) -> float:
    ta = token_values(a)
    tb = token_values(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return difflib.SequenceMatcher(a=ta, b=tb).ratio()


def normalize_anchor_text(text: str) -> str:
    line = str(text or "")
    # Normalize whitespace noise first.
    line = line.replace("\t", " ")
    line = re.sub(r"\s+", " ", line).strip()
    # Drop line comments for anchor matching stability.
    line = re.sub(r"//.*$", "", line).strip()
    return line


def locate_anchor_line_by_tokens(
    lines: List[str],
    *,
    before_expected: str = "",
    after_expected: str = "",
    hint_line: int = 1,
    min_confidence: float = 0.8,
    min_gap: float = 0.15,
    max_line_drift: int = 200,
) -> TokenLocateResult:
    if not isinstance(lines, list) or not lines:
        return {"ok": False, "reason": "empty_input", "candidate_count": 0, "confidence": 0.0}

    hint = max(1, int(hint_line or 1))
    before_expected = str(before_expected or "")
    after_expected = str(after_expected or "")
    wanted_before = bool(before_expected.strip())
    wanted_after = bool(after_expected.strip())
    if not wanted_before and not wanted_after:
        return {"ok": False, "reason": "no_expected_context", "candidate_count": 0, "confidence": 0.0}

    candidates: List[Tuple[float, int]] = []
    scanned = 0
    total = len(lines)
    for line_no in range(1, total + 1):
        if abs(line_no - hint) > max_line_drift:
            continue
        scanned += 1
        before_actual = lines[line_no - 2] if line_no >= 2 and (line_no - 2) < total else ""
        after_actual = lines[line_no - 1] if 0 <= (line_no - 1) < total else ""
        scores: List[float] = []
        if wanted_before:
            scores.append(token_similarity(before_actual, before_expected))
        if wanted_after:
            scores.append(token_similarity(after_actual, after_expected))
        if not scores:
            continue
        confidence = sum(scores) / len(scores)
        if confidence >= min_confidence:
            candidates.append((confidence, line_no))

    if not candidates:
        if scanned == 0:
            return {
                "ok": False,
                "reason": "drift_exceeded",
                "candidate_count": 0,
                "confidence": 0.0,
                "top1_confidence": 0.0,
                "top2_confidence": 0.0,
                "confidence_gap": 0.0,
            }
        return {"ok": False, "reason": "no_candidate", "candidate_count": 0, "confidence": 0.0}

    candidates.sort(key=lambda x: (-x[0], abs(x[1] - hint)))
    top_conf = candidates[0][0]
    second_conf = candidates[1][0] if len(candidates) >= 2 else 0.0
    confidence_gap = float(top_conf - second_conf)
    top = [item for item in candidates if abs(item[0] - top_conf) < 1e-9]
    if len(top) != 1 or (len(candidates) > 1 and confidence_gap < float(min_gap)):
        return {
            "ok": False,
            "reason": "ambiguous_candidates",
            "candidate_count": len(top),
            "confidence": float(top_conf),
            "top1_confidence": float(top_conf),
            "top2_confidence": float(second_conf),
            "confidence_gap": confidence_gap,
        }
    return {
        "ok": True,
        "line": int(top[0][1]),
        "candidate_count": len(candidates),
        "confidence": float(top_conf),
        "top1_confidence": float(top_conf),
        "top2_confidence": float(second_conf),
        "confidence_gap": confidence_gap,
    }
