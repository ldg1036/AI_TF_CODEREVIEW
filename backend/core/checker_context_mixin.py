import hashlib
import re
from bisect import bisect_right
from typing import Any, Dict, List, Optional


_FUNCTION_SIGNATURE_PATTERN = re.compile(
    r"^(void|int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\("
)
_FUNCTION_DEF_PATTERN = re.compile(
    r"\b(?:void|int|float|string|bool|mapping|time|anytype|dyn_[a-zA-Z0-9_]+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^\)]*\)\s*\{",
    re.IGNORECASE,
)
_LOOP_HEADER_PATTERN = re.compile(r"\b(?:while|for)\s*\([^\)]*\)\s*\{", re.IGNORECASE)
_NORMALIZE_WS_PATTERN = re.compile(r"\s+")


class CheckerContextMixin:
    """Host class should combine this with checker rule/detector mixins."""

    def _build_analysis_context(self, code: str) -> Dict[str, Any]:
        lines = code.splitlines()
        line_starts: List[int] = []
        offset = 0
        for raw_line in code.splitlines(True):
            line_starts.append(offset)
            offset += len(raw_line)
        return {
            "code": code,
            "lines": lines,
            "line_count": len(lines),
            "newline_lines": code.split("\n"),
            "line_starts": line_starts or [0],
            "cache": {},
        }

    @staticmethod
    def _context_matches_code(context: Optional[Dict[str, Any]], code: str) -> bool:
        return isinstance(context, dict) and context.get("code") == code

    @staticmethod
    def _safe_int(value: Any, fallback: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    def _get_context_lines(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        if self._context_matches_code(context, code):
            return context["lines"]
        return code.splitlines()

    def _get_context_newline_lines(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        if self._context_matches_code(context, code):
            return context["newline_lines"]
        return code.split("\n")

    def _get_context_cache(self, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(context, dict):
            return {}
        cache = context.get("cache")
        if not isinstance(cache, dict):
            cache = {}
            context["cache"] = cache
        return cache

    def _get_function_bodies(self, code: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        cache = self._get_context_cache(context)
        cache_key = "function_bodies"
        if cache_key in cache:
            return cache[cache_key]

        func_defs: Dict[str, str] = {}
        for func_match in _FUNCTION_DEF_PATTERN.finditer(code):
            name = func_match.group(1)
            brace_idx = code.find("{", func_match.start())
            if brace_idx < 0:
                continue
            close_brace = self._find_matching_delimiter(code, brace_idx, "{", "}")
            if close_brace < 0:
                continue
            func_defs[name] = code[brace_idx : close_brace + 1]
        cache[cache_key] = func_defs
        return func_defs

    def _get_loop_blocks(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        cache = self._get_context_cache(context)
        cache_key = "loop_blocks"
        if cache_key in cache:
            return cache[cache_key]

        blocks: List[Dict[str, Any]] = []
        for match in _LOOP_HEADER_PATTERN.finditer(code):
            open_brace = code.find("{", match.start())
            if open_brace < 0:
                continue
            close_brace = self._find_matching_delimiter(code, open_brace, "{", "}")
            if close_brace < 0:
                continue
            blocks.append(
                {
                    "match_start": match.start(),
                    "start_line": self._line_from_offset(code, match.start(), base_line=1, context=context),
                    "end_line": self._line_from_offset(code, close_brace, base_line=1, context=context),
                    "block": code[open_brace : close_brace + 1],
                }
            )
        cache[cache_key] = blocks
        return blocks

    def _get_token_line_numbers(
        self,
        code: str,
        cache_key: str,
        pattern: re.Pattern,
        context: Optional[Dict[str, Any]] = None,
        one_based: bool = True,
    ) -> List[int]:
        cache = self._get_context_cache(context)
        full_cache_key = f"token_lines:{cache_key}:{1 if one_based else 0}"
        if full_cache_key in cache:
            return cache[full_cache_key]

        start = 1 if one_based else 0
        lines = self._get_context_newline_lines(code, context=context)
        matches = [idx for idx, line in enumerate(lines, start) if pattern.search(line)]
        cache[full_cache_key] = matches
        return matches

    def _get_normalized_lines(
        self,
        code: str,
        context: Optional[Dict[str, Any]] = None,
        *,
        ignore_comments: bool = True,
        ignore_braces_only: bool = True,
        normalize_ws: bool = True,
        min_len: int = 8,
    ) -> List[tuple[int, str]]:
        cache = self._get_context_cache(context)
        cache_key = (
            "normalized_lines",
            ignore_comments,
            ignore_braces_only,
            normalize_ws,
            min_len,
        )
        if cache_key in cache:
            return cache[cache_key]

        normalized_lines = []
        for idx, raw in enumerate(self._get_context_lines(code, context=context), 1):
            line = raw.strip()
            if not line:
                continue
            if ignore_comments and line.startswith("//"):
                continue
            if ignore_braces_only and line in {"{", "}"}:
                continue
            if normalize_ws:
                line = _NORMALIZE_WS_PATTERN.sub(" ", line)
            if len(line) < min_len:
                continue
            normalized_lines.append((idx, line))

        cache[cache_key] = normalized_lines
        return normalized_lines

    def _remove_comments(self, text: str) -> str:
        if not text:
            return text

        chars = list(text)
        i = 0
        n = len(chars)
        in_string = False
        quote_char = ""

        while i < n:
            ch = chars[i]
            nxt = chars[i + 1] if i + 1 < n else ""

            if in_string:
                if ch == "\\" and i + 1 < n:
                    i += 2
                    continue
                if ch == quote_char:
                    in_string = False
                    quote_char = ""
                i += 1
                continue

            if ch in {'"', "'"}:
                in_string = True
                quote_char = ch
                i += 1
                continue

            if ch == "/" and nxt == "/":
                chars[i] = " "
                chars[i + 1] = " "
                i += 2
                while i < n and chars[i] != "\n":
                    chars[i] = " "
                    i += 1
                continue

            if ch == "/" and nxt == "*":
                chars[i] = " "
                chars[i + 1] = " "
                i += 2
                while i + 1 < n:
                    if chars[i] == "*" and chars[i + 1] == "/":
                        chars[i] = " "
                        chars[i + 1] = " "
                        i += 2
                        break
                    if chars[i] != "\n":
                        chars[i] = " "
                    i += 1
                continue

            i += 1

        return "".join(chars)

    def _build_issue_id(self, rule_id: str, code: str, line: int, event_name: str = "") -> str:
        normalized = re.sub(r"\s+", " ", code).strip()
        fingerprint = hashlib.sha1(
            f"{rule_id}|{line}|{event_name}|{normalized}".encode("utf-8", errors="ignore")
        ).hexdigest()[:10]
        return f"P1-{rule_id}-{fingerprint}"

    def _line_from_offset(
        self,
        code: str,
        offset: int,
        base_line: int = 1,
        context: Optional[Dict[str, Any]] = None,
    ) -> int:
        if self._context_matches_code(context, code):
            line_starts = context.get("line_starts") or [0]
            line_index = bisect_right(line_starts, max(0, offset)) - 1
            return base_line + max(0, line_index)
        return base_line + code.count("\n", 0, max(0, offset))

    def _first_function_line(self, code: str, context: Optional[Dict[str, Any]] = None) -> int:
        lines = self._get_context_lines(code, context=context)
        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            if re.match(r"^(main)\s*\(", stripped):
                return idx
            if _FUNCTION_SIGNATURE_PATTERN.match(stripped):
                return idx
        return 1

    @staticmethod
    def _find_matching_delimiter(text: str, start_idx: int, left: str, right: str) -> int:
        depth = 0
        for idx in range(start_idx, len(text)):
            ch = text[idx]
            if ch == left:
                depth += 1
            elif ch == right:
                depth -= 1
                if depth == 0:
                    return idx
        return -1

    def _collect_loop_line_ranges(self, code: str, context: Optional[Dict[str, Any]] = None) -> List[tuple]:
        return [(block["start_line"], block["end_line"]) for block in self._get_loop_blocks(code, context=context)]
